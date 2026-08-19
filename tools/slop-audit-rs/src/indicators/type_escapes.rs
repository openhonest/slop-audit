//! L1.15 type-escape density: count tree-sitter leaf nodes whose exact text is one of
//! the language's escape tokens, plus comment nodes carrying an ignore-marker and
//! annotation nodes naming a suppression, over kLOC. Ported from
//! l1_analyzer.indicators._compute_type_escapes and _count_type_escapes_in_tree.
//!
//! Language-driven: the escape tokens come from lang::LangCfg, so the four untyped or
//! no-escape-hatch languages (Ruby, JavaScript, Rust, C) report n/a exactly as the
//! reference does, and the five typed ones each use their own tokens.

use crate::lang;
use crate::{band, bucket_reason, Indicator, is_file_entry, parser_for, py_round2, repo_has_packages, splitlines_count_str, walk_repo};
use std::path::Path;
use tree_sitter::Node;

// _COMMENT_TYPE_ESCAPES (language agnostic; substring match on a comment node).
const COMMENT_ESCAPES: &[&str] = &["# type: ignore", "// @ts-ignore", "/* @ts-ignore"];
// _read_source_bytes(..., extra_ignore=("tests", "test")).
const EXTRA_IGNORE: &[&str] = &["tests", "test"];

/// True if any ancestor is a string node. A leaf inside a string is data, not an
/// annotation: `("Any",)` in a pattern table, an "object" key in a C# message, a
/// "dynamic" label. None of them opt out of a type checker.
fn in_string(node: Node) -> bool {
    let mut parent = node.parent();
    while let Some(n) = parent {
        if n.kind().contains("string") {
            return true;
        }
        parent = n.parent();
    }
    false
}

/// _annotation_name: the name an annotation declares, read from the grammar's `name`
/// field and followed down as far as the field goes, so a scoped annotation
/// (`@java.lang.SuppressWarnings`) reads as `SuppressWarnings`.
fn annotation_name<'a>(node: Node<'a>, src: &[u8]) -> String {
    let mut node = node;
    while let Some(name) = node.child_by_field_name("name") {
        node = name;
    }
    String::from_utf8_lossy(&src[node.byte_range()]).into_owned()
}

/// _count_type_escapes_in_tree: a leaf whose exact text is an escape token and is not
/// inside a string, a comment node that BEGINS with an ignore-marker, and an annotation
/// node naming a suppression. A comment that merely mentions the marker while explaining
/// the rule is documentation.
///
/// The annotation arm is what Java's `@SuppressWarnings` needs: it parses as an
/// `annotation` node, so the comment arm never saw it. One annotation is one escape
/// however many warnings it names.
/// The whole vocabulary travels in `cfg`, as it does in the reference: unpacking it at
/// each call site is how a new vocabulary silently splits the measure in two.
/// True when a matching token sits somewhere its language says is not a type: an import
/// or using declaration that names the symbol, or an object key spelled like it.
///
/// `from typing import Any` makes a symbol available and types nothing. Without this,
/// every statically-typed Python file carried a floor of one escape, and a file that
/// imported the name without using it was charged for the import alone. The reference has
/// had this rule; the port did not, and counted 179 escapes where the reference counted
/// 167 on the same tree.
fn in_non_type_position(leaf: Node, nonpositions: &[&str]) -> bool {
    let mut parent = leaf.parent();
    while let Some(node) = parent {
        if nonpositions.contains(&node.kind()) {
            return true;
        }
        parent = node.parent();
    }
    false
}

/// The escape tokens named inside a cast's STRING first argument.
///
/// `cast("dict[str, Any]", ctx)` names a type, and the leaf walk drops it with every other
/// string. `("Any",)` in a pattern table does not name a type, and the call name is what
/// separates them. Without this the same code scored 2 unquoted and 1 quoted, so a reader
/// could move the number by adding quotation marks.
///
/// A language declaring no cast calls gets no walk, which is every language but Python.
fn count_cast_type_strings(node: Node, src: &[u8], cfg: &lang::LangCfg) -> usize {
    if cfg.type_cast_calls.is_empty() {
        return 0;
    }
    let mut count = 0usize;
    if node.kind() == "call" {
        let named = node.child_by_field_name("function").map(|f| {
            String::from_utf8_lossy(&src[f.byte_range()]).into_owned()
        });
        if named.is_some_and(|n| cfg.type_cast_calls.contains(&n.as_str())) {
            let first = node
                .child_by_field_name("arguments")
                .and_then(|a| a.named_child(0));
            if let Some(arg) = first {
                if arg.kind().contains("string") {
                    let text = String::from_utf8_lossy(&src[arg.byte_range()]);
                    // One count per escape token NAMED in the type, matching the
                    // reference's word-boundary search over the string's own text.
                    for token in cfg.type_escape_patterns {
                        count += text
                            .match_indices(token)
                            .filter(|(i, _)| {
                                let before = text[..*i].chars().next_back();
                                let after = text[i + token.len()..].chars().next();
                                !before.is_some_and(|c| c.is_alphanumeric() || c == '_')
                                    && !after.is_some_and(|c| c.is_alphanumeric() || c == '_')
                            })
                            .count();
                    }
                }
            }
        }
    }
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        count += count_cast_type_strings(child, src, cfg);
    }
    count
}

fn count_escapes_in_tree(node: Node, src: &[u8], cfg: &lang::LangCfg) -> usize {
    let mut count = 0usize;
    if node.child_count() == 0 {
        let text = String::from_utf8_lossy(&src[node.byte_range()]);
        if cfg.type_escape_patterns.contains(&text.as_ref())
            && !in_string(node)
            && !in_non_type_position(node, cfg.type_escape_nonpositions)
        {
            count += 1;
        }
    }
    if node.kind().contains("comment") {
        let text = String::from_utf8_lossy(&src[node.byte_range()]);
        if COMMENT_ESCAPES.iter().any(|p| text.trim_start().starts_with(p)) {
            count += 1;
        }
    }
    if cfg.annotation_escape_nodes.contains(&node.kind())
        && cfg.annotation_escape_names.contains(&annotation_name(node, src).as_str())
    {
        count += 1;
    }
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        count += count_escapes_in_tree(child, src, cfg);
    }
    count
}

fn na(details: String) -> Indicator {
    Indicator {
        code: "L1.15".into(),
        label: "type-escapes".into(),
        value: "n/a".into(),
        band: "n/a".into(),
        details,
    }
}

pub fn analyze(repo: &Path, language: &str) -> Indicator {
    let cfg = match lang::cfg(language) {
        Some(cfg) => cfg,
        None => return na(format!("no tree-sitter config for {language}")),
    };
    if cfg.type_escape_patterns.is_empty() {
        // Untyped or no configured escape hatch (Ruby, JavaScript, Rust, C).
        return na(format!("type-escape density not applicable for {language}"));
    }

    let has_packages = repo_has_packages(repo);
    let mut parser = parser_for(language);
    let mut escape_count = 0usize;
    let mut total_loc = 0usize;
    let mut skipped = 0usize;

    // min_depth(1) and is_file_entry: see the note in god_files.rs. A directory whose
    // name ends in a source extension is not a file, so it is skipped in silence.
    for entry in walk_repo(repo) {
        if !is_file_entry(&entry) {
            continue;
        }
        let path = entry.path();
        let name = match path.file_name().and_then(|n| n.to_str()) {
            Some(n) => n,
            None => continue,
        };
        if !cfg.extensions.iter().any(|ext| name.ends_with(ext)) {
            continue;
        }
        if bucket_reason(path, repo, has_packages, EXTRA_IGNORE).is_some() {
            continue;
        }
        let src = match std::fs::read(path) {
            Ok(bytes) => bytes,
            Err(_) => {
                skipped += 1;
                continue;
            }
        };
        total_loc += splitlines_count_str(&String::from_utf8_lossy(&src));
        if let Some(tree) = parser.parse(&src, None) {
            escape_count += count_escapes_in_tree(tree.root_node(), &src, cfg)
                + count_cast_type_strings(tree.root_node(), &src, cfg);
        }
    }

    // There is no minimum denominator, and the absence of one is the rule.
    //
    // This read `if total_loc > 1000 { .. } else { 0.0 }` until 2026-08-15, ported
    // verbatim from the reference. Below a thousand production lines both tools published
    // 0.0 per kLOC and band Healthy however many escape hatches the input held: a
    // twenty-line file of nothing but `Any` scored the same clean as a file with none.
    // That is a fabricated number over a non-empty input, not an empty-set claim, and it
    // is the worse of the two because the lines were there and were counted correctly
    // right up to the last step of arithmetic. The threshold had no derivation anywhere;
    // the canon's bands are `<1 / 1-5 / >5` per kLOC with no floor under them, and where
    // the canon and the implementation disagree the canon wins.
    //
    // The parity differ is what makes this comment worth writing here rather than only in
    // the reference: the two sides carried one rule, so they had to lose it together.
    //
    // Zero lines is the one case with no density to report, and it refuses.
    if total_loc == 0 {
        let mut details = "no production source lines found".to_string();
        if skipped != 0 {
            details = format!("{details}; {skipped} file(s) unreadable and excluded");
        }
        return na(details);
    }
    let density = escape_count as f64 / (total_loc as f64 / 1000.0);
    // The denominator is printed exactly. Rounded to whole thousands it read "~0kLOC" for
    // every input the floor used to swallow, so the disclosure that exists to let a reader
    // recompute the ratio hid the only term that moved.
    let mut details = format!("{escape_count} escapes in {total_loc} production LOC");
    if skipped != 0 {
        details = format!("{details}; {skipped} file(s) unreadable and excluded");
    }
    Indicator {
        code: "L1.15".into(),
        label: "type-escapes".into(),
        value: py_round2(density),
        band: band(density, 1.0, 5.0, false).into(),
        details,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The count one file yields, through the same walker `analyze` uses.
    fn count(language: &str, source: &str) -> usize {
        let cfg = lang::cfg(language).expect("language row");
        let mut parser = parser_for(language);
        let src = source.as_bytes();
        let tree = parser.parse(src, None).expect("parse");
        count_escapes_in_tree(tree.root_node(), src, cfg)
            + count_cast_type_strings(tree.root_node(), src, cfg)
    }

    /// Java's suppression marker parses as an `annotation` node, so the comment arm never
    /// saw it and Java's real escape hatch went uncounted. `@Override` is an annotation
    /// too and is not a type escape.
    #[test]
    fn java_suppresswarnings_on_a_method_is_counted() {
        let src = "class A {\n    @SuppressWarnings(\"unchecked\")\n    @Override\n    public void m() {}\n}\n";
        assert_eq!(count("java", src), 1);
    }

    /// One annotation is one decision to opt out, however many warnings it names, and a
    /// scoped annotation names the same marker.
    #[test]
    fn java_suppression_counts_once_however_many_warnings() {
        let src = "class A {\n    @SuppressWarnings({\"unchecked\", \"rawtypes\"})\n    void m() {}\n    @java.lang.SuppressWarnings(\"unchecked\")\n    void n() {}\n}\n";
        assert_eq!(count("java", src), 2);
    }

    /// Prose about the marker, and a string holding it, are not suppressions. Moving the
    /// marker to the annotation table must not reopen the self-reference hole.
    #[test]
    fn java_comment_mentioning_the_marker_is_documentation() {
        let src = "class A {\n    // use @SuppressWarnings(\"unchecked\") only where the cast is proven\n    void m() {\n        String s = \"@SuppressWarnings\";\n    }\n}\n";
        assert_eq!(count("java", src), 0);
    }

    /// A one-file tree under the system temp directory. No dev-dependency: adding one to
    /// reach `analyze`, which is the only function here that does I/O, would put a crate in
    /// the lockfile of a binary whose whole claim is that it is portable.
    fn one_file_tree(stem: &str, name: &str, source: &str) -> std::path::PathBuf {
        let root = std::env::temp_dir().join(format!("slop-l115-{stem}"));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).expect("temp tree");
        std::fs::write(root.join(name), source).expect("write source");
        root
    }

    /// The thousand-line floor, removed 2026-08-15. Twenty lines, twenty escape hatches,
    /// and both tools called it Healthy at 0.0. A rate is a rate at any denominator.
    #[test]
    fn a_small_file_of_nothing_but_escapes_is_not_healthy() {
        let root = one_file_tree("all-escapes", "a.py", &"v: Any = 1\n".repeat(20));
        let got = analyze(&root, "python");
        assert_eq!(got.value, "1000.0");
        assert_eq!(got.band, "Slop");
        assert_eq!(got.details, "20 escapes in 20 production LOC");
        let _ = std::fs::remove_dir_all(&root);
    }

    /// The case that motivated the fix: at per-edit tempo an agent holds one file, and
    /// under the floor every file below a thousand lines banded Healthy by construction.
    #[test]
    fn one_escape_at_file_scope_is_measured() {
        let src = format!("{}v: Any = 1\n", "def f(x):\n    return x\n".repeat(99));
        let root = one_file_tree("file-scope", "a.py", &src);
        let got = analyze(&root, "python");
        assert_eq!(got.value, "5.03");
        assert_eq!(got.band, "Slop");
        let _ = std::fs::remove_dir_all(&root);
    }

    /// Honest zero is the control. Removing the floor must not make every small input a
    /// finding; a file that really was read and held nothing keeps its Healthy, earned.
    #[test]
    fn a_clean_small_file_still_reads_healthy() {
        let root = one_file_tree("clean", "a.py", &"def f(x: int) -> int:\n    return x\n".repeat(20));
        let got = analyze(&root, "python");
        assert_eq!(got.value, "0.0");
        assert_eq!(got.band, "Healthy");
        let _ = std::fs::remove_dir_all(&root);
    }

    /// The empty-denominator half. Zero escapes over zero lines is the same 0.0 as zero
    /// over a thousand, and band cannot tell them apart, so there is no density to publish.
    #[test]
    fn no_production_lines_is_na_not_healthy() {
        let root = one_file_tree("empty", "README.md", "nothing here\n");
        let got = analyze(&root, "python");
        assert_eq!(got.value, "n/a");
        assert_eq!(got.band, "n/a");
        assert_eq!(got.details, "no production source lines found");
        let _ = std::fs::remove_dir_all(&root);
    }

    /// The reference's own L1.15 cases, so the two walkers cannot drift on the rules the
    /// annotation arm sits beside.
    #[test]
    fn the_comment_and_string_rules_are_unchanged() {
        assert_eq!(count("python", "x = 1  # type: ignore\n"), 1);
        assert_eq!(count("python", "x = 1  # type: ignore[attr-defined]\n"), 1);
        assert_eq!(count("python", "# the marker is # type: ignore, mid-sentence\nx = 1\n"), 0);
        assert_eq!(count("python", "PATTERNS = (\"Any\",)\nx = 1\n"), 0);
        assert_eq!(count("java", "class A {\n    Object o;\n}\n"), 1);
    }
}
