//! Per-language vocabulary for the source indicators, ported from
//! l1_analyzer.indicators.LANG_CFG plus the two god-file tables beside it
//! (_GOD_FILE_LANG, _LITERAL_NODES).
//!
//! One table, nine languages. Every source indicator reads the grammar's node types
//! through here and never hard-codes one, so a language is added by adding a row.

use std::path::Path;
use tree_sitter::{Language, Parser};

/// The generated per-language configuration, re-exported so every reader imports it from
/// here, which is where it has always been imported from.
///
/// The table itself moved to a generated file on 2026-09-21. It was transcribed by hand, and
/// it had drifted in the one field whose value is its ORDER: the reference appends TypeScript
/// after every other language, the copy had it fifth, and the detector below breaks a count
/// tie by that order.
pub use crate::lang_cfg::{cfg, LangCfg, LANGS};


/// _LANGUAGE_UNKNOWN: the repo holds no recognised source, so callers report n/a
/// rather than guess.
pub const UNKNOWN: &str = "unknown";

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

    /// The tie-break order, stated here because it is a VALUE and not a formatting
    /// choice, and because the hand-copied table had it wrong.
    ///
    /// The reference builds TypeScript's row out of JavaScript's and appends it, so
    /// TypeScript is last. The copy had it fifth, ahead of C#, and the detector breaks a
    /// count tie by this order: a repository with as many .ts files as .cs files detected
    /// as TypeScript here and as C# in the reference, and every indicator below that
    /// followed a different grammar in the two tools.
    #[test]
    fn the_language_order_is_the_reference_s_and_typescript_is_last() {
        let keys: Vec<&str> = LANGS.iter().map(|row| row.key).collect();
        assert_eq!(keys, vec!["python", "rust", "c", "java", "csharp", "javascript",
                              "ruby", "go", "typescript"]);
    }

    #[test]
    fn a_tie_between_typescript_and_csharp_breaks_the_way_the_reference_breaks_it() {
        let root = std::env::temp_dir().join(format!("slop-audit-tie-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).expect("make the fixture");
        for n in 0..3 {
            std::fs::write(root.join(format!("a{n}.ts")), "export const x = 1;\n")
                .expect("write ts");
            std::fs::write(root.join(format!("a{n}.cs")), "class A { int x; }\n")
                .expect("write cs");
        }
        let detected = detect_primary_language(&root);
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(detected, "csharp", "the tie broke the wrong way");
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
