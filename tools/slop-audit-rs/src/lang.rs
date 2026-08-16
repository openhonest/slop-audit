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
        annotation_escape_nodes: &[],
        annotation_escape_names: &[],
        literal_nodes: &["dictionary", "list", "set", "tuple"],
    },
    LangCfg {
        key: "rust",
        extensions: &[".rs"],
        type_escape_patterns: &[],
        annotation_escape_nodes: &[],
        annotation_escape_names: &[],
        literal_nodes: &["array_expression"],
    },
    LangCfg {
        key: "c",
        extensions: &[".c", ".h"],
        type_escape_patterns: &[],
        annotation_escape_nodes: &[],
        annotation_escape_names: &[],
        literal_nodes: &["initializer_list"],
    },
    LangCfg {
        key: "java",
        extensions: &[".java"],
        type_escape_patterns: &["Object"],
        annotation_escape_nodes: &["annotation", "marker_annotation"],
        annotation_escape_names: &["SuppressWarnings"],
        literal_nodes: &["array_initializer"],
    },
    LangCfg {
        key: "typescript",
        extensions: &[".ts", ".tsx"],
        type_escape_patterns: &["any", "unknown"],
        annotation_escape_nodes: &[],
        annotation_escape_names: &[],
        literal_nodes: &["object", "array"],
    },
    LangCfg {
        key: "csharp",
        extensions: &[".cs"],
        type_escape_patterns: &["object", "dynamic"],
        annotation_escape_nodes: &[],
        annotation_escape_names: &[],
        literal_nodes: &["initializer_expression", "collection_expression"],
    },
    LangCfg {
        key: "javascript",
        extensions: &[".js", ".jsx", ".mjs", ".cjs"],
        type_escape_patterns: &[],
        annotation_escape_nodes: &[],
        annotation_escape_names: &[],
        literal_nodes: &["object", "array"],
    },
    LangCfg {
        key: "ruby",
        extensions: &[".rb"],
        type_escape_patterns: &[],
        annotation_escape_nodes: &[],
        annotation_escape_names: &[],
        literal_nodes: &["hash", "array"],
    },
    LangCfg {
        key: "go",
        extensions: &[".go"],
        type_escape_patterns: &["any"],
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
/// Counts every matching file exactly as the reference's `_rglob_files(repo, f"*{ext}")`
/// does, with no vendored-directory filter. That is the reference's behaviour, so a repo
/// whose node_modules dwarfs its source resolves the same way in both tools. Filtering
/// vendored code out here would be a better meter and a different one. A directory whose
/// name ends in a source extension is not counted: it is not a file.
pub fn detect_primary_language(repo: &Path) -> &'static str {
    let mut counts = vec![0usize; LANGS.len()];
    for entry in crate::walk_repo(repo) {
        if !crate::is_file_entry(&entry) {
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
