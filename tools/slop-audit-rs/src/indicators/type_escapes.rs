//! L1.15 type-escape density (Python path): count tree-sitter leaf nodes whose exact
//! text is "Any" plus comment nodes carrying an ignore-marker, over kLOC. Ported from
//! l1_analyzer.indicators._compute_type_escapes / _count_type_escapes_in_tree; validated
//! equal for lang=python. Other languages are a follow-up (different escape tokens).

use crate::{band, in_ignored_dir, parser_for, Indicator};
use std::path::Path;
use tree_sitter::Node;

// LANG_CFG["python"]["type_escape_patterns"] == ("Any",).
const ESCAPE_TOKENS: &[&str] = &["Any"];
// _COMMENT_TYPE_ESCAPES (language agnostic; substring match on a comment node).
const COMMENT_ESCAPES: &[&str] = &["# type: ignore", "// @ts-ignore", "/* @ts-ignore", "@SuppressWarnings"];
// _read_source_bytes(..., extra_ignore=("tests", "test")).
const EXTRA_IGNORE: &[&str] = &["tests", "test"];
// _TOOLING_FILES, recognised by filename.
const TOOLING_FILES: &[&str] = &["setup.py", "noxfile.py", "conftest.py", "tasks.py", "manage.py"];

/// True if any full-path component is a scoped-out dir/file, mirroring
/// _bucket_reason returning non-None (vendored / tests / test / docs / tooling / root-script).
fn scoped_out(path: &Path, repo: &Path, has_packages: bool) -> bool {
    if in_ignored_dir(path) {
        return true; // vendored
    }
    let mut has_docs = false;
    for c in path.components() {
        if let std::path::Component::Normal(os) = c {
            if let Some(s) = os.to_str() {
                if EXTRA_IGNORE.contains(&s) {
                    return true; // tests / test
                }
                if s == "docs" {
                    has_docs = true;
                }
            }
        }
    }
    if has_docs {
        return true;
    }
    if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
        if TOOLING_FILES.contains(&name) {
            return true; // tooling
        }
    }
    // A loose top-level .py beside packages, in a repo whose root is not itself a
    // package, is a dev/entry-point script, not the library.
    if has_packages && path.parent() == Some(repo) && !repo.join("__init__.py").exists() {
        return true; // root-script
    }
    false
}

/// _repo_has_packages: any __init__.py that is not in a vendored/tooling dir.
fn repo_has_packages(repo: &Path) -> bool {
    for entry in walkdir::WalkDir::new(repo).into_iter().filter_map(Result::ok) {
        let path = entry.path();
        if entry.file_type().is_file()
            && path.file_name().and_then(|n| n.to_str()) == Some("__init__.py")
            && !in_ignored_dir(path)
        {
            return true;
        }
    }
    false
}

/// Count of lines under Python's str.splitlines() semantics (all Unicode line
/// boundaries, \r\n as one), so total_loc matches the reference exactly.
fn splitlines_count(s: &str) -> usize {
    let chars: Vec<char> = s.chars().collect();
    let is_bound = |c: char| {
        matches!(
            c,
            '\n' | '\r' | '\u{0b}' | '\u{0c}' | '\u{1c}' | '\u{1d}' | '\u{1e}'
                | '\u{85}' | '\u{2028}' | '\u{2029}'
        )
    };
    let mut count = 0usize;
    let mut i = 0usize;
    let n = chars.len();
    let mut trailing = false;
    while i < n {
        let c = chars[i];
        if is_bound(c) {
            count += 1;
            if c == '\r' && i + 1 < n && chars[i + 1] == '\n' {
                i += 2;
            } else {
                i += 1;
            }
            trailing = false;
        } else {
            trailing = true;
            i += 1;
        }
    }
    count + usize::from(trailing)
}

/// _count_type_escapes_in_tree: a leaf whose exact text is an escape token, plus a
/// comment node carrying an ignore-marker. Substring on comments; exact on leaves.
fn count_escapes_in_tree(node: Node, src: &[u8]) -> usize {
    let mut count = 0usize;
    if node.child_count() == 0 {
        let text = String::from_utf8_lossy(&src[node.byte_range()]);
        if ESCAPE_TOKENS.contains(&text.as_ref()) {
            count += 1;
        }
    }
    if node.kind().contains("comment") {
        let text = String::from_utf8_lossy(&src[node.byte_range()]);
        if COMMENT_ESCAPES.iter().any(|p| text.contains(p)) {
            count += 1;
        }
    }
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        count += count_escapes_in_tree(child, src);
    }
    count
}

/// Python's json repr of round(x, 2): shortest round-trip, always with a decimal point.
fn py_float(x: f64) -> String {
    let rounded = (x * 100.0).round() / 100.0;
    let mut s = format!("{rounded}");
    if !s.contains('.') && !s.contains('e') {
        s.push_str(".0");
    }
    s
}

pub fn analyze(repo: &Path) -> Indicator {
    let has_packages = repo_has_packages(repo);
    let mut parser = parser_for("python");

    let mut escape_count = 0usize;
    let mut total_loc = 0usize;
    let mut skipped = 0usize;

    for entry in walkdir::WalkDir::new(repo).into_iter().filter_map(Result::ok) {
        let path = entry.path();
        if !entry.file_type().is_file() {
            continue;
        }
        if path.extension().and_then(|e| e.to_str()) != Some("py") {
            continue;
        }
        if scoped_out(path, repo, has_packages) {
            continue;
        }
        let src = match std::fs::read(path) {
            Ok(b) => b,
            Err(_) => {
                skipped += 1;
                continue;
            }
        };
        total_loc += splitlines_count(&String::from_utf8_lossy(&src));
        if let Some(tree) = parser.parse(&src, None) {
            escape_count += count_escapes_in_tree(tree.root_node(), &src);
        }
    }

    let density = if total_loc > 1000 {
        escape_count as f64 / (total_loc as f64 / 1000.0)
    } else {
        0.0
    };
    let mut details = format!("{escape_count} escapes in ~{}kLOC", total_loc / 1000);
    if skipped != 0 {
        details = format!("{details}; {skipped} file(s) unreadable and excluded");
    }
    Indicator {
        code: "L1.15".into(),
        label: "type-escapes".into(),
        value: py_float(density),
        band: band(density, 1.0, 5.0, false).into(),
        details,
    }
}
