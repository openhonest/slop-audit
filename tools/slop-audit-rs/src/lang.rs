//! Per-language vocabulary for the source indicators, ported from
//! l1_analyzer.indicators.LANG_CFG plus the two god-file tables beside it
//! (_GOD_FILE_LANG, _LITERAL_NODES).
//!
//! One table, nine languages. Every source indicator reads the grammar's node types
//! through here and never hard-codes one, so a language is added by adding a row.

use std::path::Path;
use tree_sitter::{Language, Parser};

/// The subset of LANG_CFG the ported indicators read. Fields are added as the
/// indicators that need them land; a row carries an empty slice for what it lacks.
pub struct LangCfg {
    /// LANG_CFG key. Also the name the CLI accepts for --lang.
    pub key: &'static str,
    /// LANG_CFG["extensions"], leading dot, lowercase.
    pub extensions: &'static [&'static str],
    /// LANG_CFG["type_escape_patterns"]. Empty means L1.15 is n/a for the language
    /// (untyped, or no configured escape hatch): Ruby, JavaScript, Rust, C.
    pub type_escape_patterns: &'static [&'static str],
    /// LANG_CFG["annotation_escape_nodes"]: the grammar's annotation node types, where
    /// a language writes its suppressions as an annotation rather than a comment.
    pub annotation_escape_nodes: &'static [&'static str],
    /// LANG_CFG["annotation_escape_names"]: the annotation names that suppress a type
    /// diagnostic. Java only for now; see
    /// research/amendments/amendment-2026-08-14-java-suppression-marker.md.
    pub annotation_escape_names: &'static [&'static str],
    /// LANG_CFG["type_escape_nonpositions"]: node types under which a matching token is
    /// NOT a type. `from typing import Any` makes a symbol available and types nothing,
    /// so every statically-typed Python file carried a floor of one escape without this.
    ///
    /// Stated as a refusal rather than an allow-list of type positions, because Go and C#
    /// put a bare type straight into a declaration with no node to key on. An empty
    /// vocabulary refuses nothing, which is the counted direction.
    pub type_escape_nonpositions: &'static [&'static str],
    /// LANG_CFG["type_cast_calls"]: calls whose first argument IS a type, so a STRING
    /// there is counted like the annotation it is. `cast("dict[str, Any]", ctx)` is the
    /// ordinary way to write the one acknowledged escape at a framework seam, and the
    /// leaf walk drops it with every other string: the same code scored 2 unquoted and 1
    /// quoted, so a reader could move the number by adding quotation marks.
    pub type_cast_calls: &'static [&'static str],
    /// _LITERAL_NODES[lang]: container-literal node types that read as a data table,
    /// discounted from the L1.17 code-line count.
    pub literal_nodes: &'static [&'static str],
}

/// LANG_CFG in its Python declaration order. The order is load-bearing:
/// detect_primary_language breaks a count tie by it, exactly as Counter.most_common
/// breaks a tie by insertion order.
pub const LANGS: &[LangCfg] = &[
    LangCfg {
        key: "python",
        extensions: &[".py"],
        type_escape_patterns: &["Any"],
        type_escape_nonpositions: &["import_statement", "import_from_statement"],
        type_cast_calls: &["cast"],
        annotation_escape_nodes: &[],
        annotation_escape_names: &[],
        literal_nodes: &["dictionary", "list", "set", "tuple"],
    },
    LangCfg {
        key: "rust",
        extensions: &[".rs"],
        type_escape_patterns: &[],
        type_escape_nonpositions: &[],
        type_cast_calls: &[],
        annotation_escape_nodes: &[],
        annotation_escape_names: &[],
        literal_nodes: &["array_expression"],
    },
    LangCfg {
        key: "c",
        extensions: &[".c", ".h"],
        type_escape_patterns: &[],
        type_escape_nonpositions: &[],
        type_cast_calls: &[],
        annotation_escape_nodes: &[],
        annotation_escape_names: &[],
        literal_nodes: &["initializer_list"],
    },
    LangCfg {
        key: "java",
        extensions: &[".java"],
        type_escape_patterns: &["Object"],
        type_escape_nonpositions: &["import_declaration"],
        type_cast_calls: &[],
        annotation_escape_nodes: &["annotation", "marker_annotation"],
        annotation_escape_names: &["SuppressWarnings"],
        literal_nodes: &["array_initializer"],
    },
    LangCfg {
        key: "typescript",
        extensions: &[".ts", ".tsx"],
        type_escape_patterns: &["any", "unknown"],
        type_escape_nonpositions: &["import_statement", "pair"],
        type_cast_calls: &[],
        annotation_escape_nodes: &[],
        annotation_escape_names: &[],
        literal_nodes: &["object", "array"],
    },
    LangCfg {
        key: "csharp",
        extensions: &[".cs"],
        type_escape_patterns: &["object", "dynamic"],
        type_escape_nonpositions: &["using_directive"],
        type_cast_calls: &[],
        annotation_escape_nodes: &[],
        annotation_escape_names: &[],
        literal_nodes: &["initializer_expression", "collection_expression"],
    },
    LangCfg {
        key: "javascript",
        extensions: &[".js", ".jsx", ".mjs", ".cjs"],
        type_escape_patterns: &[],
        type_escape_nonpositions: &[],
        type_cast_calls: &[],
        annotation_escape_nodes: &[],
        annotation_escape_names: &[],
        literal_nodes: &["object", "array"],
    },
    LangCfg {
        key: "ruby",
        extensions: &[".rb"],
        type_escape_patterns: &[],
        type_escape_nonpositions: &[],
        type_cast_calls: &[],
        annotation_escape_nodes: &[],
        annotation_escape_names: &[],
        literal_nodes: &["hash", "array"],
    },
    LangCfg {
        key: "go",
        extensions: &[".go"],
        type_escape_patterns: &["any"],
        type_escape_nonpositions: &["import_declaration", "import_spec"],
        type_cast_calls: &[],
        annotation_escape_nodes: &[],
        annotation_escape_names: &[],
        literal_nodes: &["literal_value", "composite_literal"],
    },
];

/// _LANGUAGE_UNKNOWN: the repo holds no recognised source, so callers report n/a
/// rather than guess.
pub const UNKNOWN: &str = "unknown";

pub fn cfg(key: &str) -> Option<&'static LangCfg> {
    LANGS.iter().find(|l| l.key == key)
}

/// _GOD_FILE_LANG: the extension-to-grammar map L1.17 uses. It is its own table in
/// the reference, not a reverse of `extensions`: L1.17 scans a fixed ten-extension
/// set regardless of the repo's primary language, and .tsx/.jsx/.mjs/.cjs are not
/// in it.
pub fn god_file_lang(ext: &str) -> Option<&'static str> {
    Some(match ext {
        ".py" => "python",
        ".rs" => "rust",
        ".c" | ".h" => "c",
        ".js" => "javascript",
        ".ts" => "typescript",
        ".java" => "java",
        ".cs" => "csharp",
        ".go" => "go",
        ".rb" => "ruby",
        _ => return None,
    })
}

/// _GOD_FILE_EXTS, in sorted order so the scan is deterministic.
pub const GOD_FILE_EXTS: &[&str] = &[
    ".c", ".cs", ".go", ".h", ".java", ".js", ".py", ".rb", ".rs", ".ts",
];

/// A parser for one LANG_CFG key. Every grammar links statically into the binary,
/// which is the whole reason this port exists.
pub fn parser_for(key: &str) -> Parser {
    let language: Language = match key {
        "python" => tree_sitter_python::LANGUAGE.into(),
        "rust" => tree_sitter_rust::LANGUAGE.into(),
        "c" => tree_sitter_c::LANGUAGE.into(),
        "java" => tree_sitter_java::LANGUAGE.into(),
        "typescript" => tree_sitter_typescript::LANGUAGE_TYPESCRIPT.into(),
        "csharp" => tree_sitter_c_sharp::LANGUAGE.into(),
        "javascript" => tree_sitter_javascript::LANGUAGE.into(),
        "ruby" => tree_sitter_ruby::LANGUAGE.into(),
        "go" => tree_sitter_go::LANGUAGE.into(),
        other => panic!("no grammar linked for {other}"),
    };
    let mut parser = Parser::new();
    parser.set_language(&language).expect("set grammar");
    parser
}

/// detect_primary_language: the LANG_CFG key with the most files, or "unknown" when
/// the repo holds no recognised source.
///
/// Counts every matching file the way the reference does, THROUGH THE SAME SCOPE POLICY
/// every other reader uses. A directory whose name ends in a source extension is not
/// counted: it is not a file.
///
/// This paragraph used to say the opposite, that there was deliberately no
/// vendored-directory filter because that was the reference's behaviour. The reference has
/// since been corrected and this was not, so the sentence described a tool that no longer
/// existed and the two answered differently.
///
/// Reproduced on this crate: thirteen `.rs` files outside `target/`, no `.c` or `.h`
/// outside it, and twenty-three vendored `.c` and `.h` inside it from the linked
/// tree-sitter grammars. The crate detected as C, every source indicator then ran the C
/// grammar over Rust, and the parity job read two indicators as differing when what
/// differed was which language each tool thought it was reading.
pub fn detect_primary_language(repo: &Path) -> &'static str {
    let mut counts = vec![0usize; LANGS.len()];
    for entry in crate::walk_repo(repo) {
        if !crate::is_file_entry(&entry) {
            continue;
        }
        if crate::in_ignored_dir(entry.path()) {
            continue;
        }
        let name = match entry.path().file_name().and_then(|n| n.to_str()) {
            Some(n) => n,
            None => continue,
        };
        for (i, lang) in LANGS.iter().enumerate() {
            if lang.extensions.iter().any(|ext| name.ends_with(ext)) {
                counts[i] += 1;
            }
        }
    }
    // Strictly greater keeps the earlier row on a tie, which is Counter's
    // insertion-order tie-break.
    let mut best: Option<(&'static str, usize)> = None;
    for (i, lang) in LANGS.iter().enumerate() {
        if counts[i] > best.map_or(0, |(_, n)| n) {
            best = Some((lang.key, counts[i]));
        }
    }
    match best {
        Some((key, n)) if n > 0 => key,
        _ => UNKNOWN,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Every linked grammar loads and parses. A grammar crate compiled against a newer
    /// tree-sitter ABI than the core crate builds cleanly and then panics at
    /// `set_language`, which would strand the failure in the field on whichever
    /// language the auditor happens to point it at. This turns that into a build
    /// failure.
    #[test]
    fn every_language_parses() {
        for cfg in LANGS {
            let mut parser = parser_for(cfg.key);
            let tree = parser.parse(b"", None);
            assert!(tree.is_some(), "{} parsed nothing", cfg.key);
        }
    }

    /// A build directory does not decide which grammar the whole audit runs.
    ///
    /// This crate is the case that found it: thirteen Rust files beside twenty-three
    /// vendored C files under `target/`, and the binary called it a C project while the
    /// Python reference called it Rust. Every source indicator then ran the wrong grammar,
    /// and the parity job reported two indicators differing when the disagreement was
    /// about which language each tool was reading.
    #[test]
    fn a_build_directory_does_not_decide_the_language() {
        let root = std::env::temp_dir().join(format!("lang-detect-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(root.join("src")).expect("make src");
        std::fs::create_dir_all(root.join("target").join("build")).expect("make target");
        for n in 0..2 {
            std::fs::write(root.join("src").join(format!("m{n}.rs")), "fn main() {}\n")
                .expect("write rust");
        }
        for n in 0..9 {
            std::fs::write(root.join("target").join("build").join(format!("g{n}.c")), "int x;\n")
                .expect("write vendored c");
        }
        let detected = detect_primary_language(&root);
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(detected, "rust", "a build artifact outvoted the source");
    }

    /// Every extension L1.17 scans maps to a grammar, and every mapped grammar is a
    /// LANGS row. A typo in either table would silently drop the data-literal discount
    /// and inflate the god-file count.
    #[test]
    fn god_file_extensions_all_map_to_a_linked_grammar() {
        for ext in GOD_FILE_EXTS {
            let key = god_file_lang(ext).unwrap_or_else(|| panic!("{ext} maps to no grammar"));
            assert!(cfg(key).is_some(), "{key} is not a LANGS row");
        }
    }
}
