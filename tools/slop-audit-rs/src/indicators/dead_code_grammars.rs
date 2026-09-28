//! The grammars the dead-code reading parses with, and the extension that picks one. Ported
//! from l1_analyzer.dead_code_grammars.
//!
//! Its own table and NOT the one the rest of the panel reads, because a React component needs
//! the JSX grammar: parsing one with the plain TypeScript grammar loses every element and the
//! names inside it. The grammar key and the language key differ only there.

/// Extension to (grammar, collector language). The grammar is the parser to run; the language
/// is the collector to run on what it produced.
const EXT_LANG: &[(&str, (&str, &str))] = &[
    ("py", ("python", "python")),
    ("rs", ("rust", "rust")),
    ("c", ("c", "c")), ("h", ("c", "c")),
    ("java", ("java", "java")),
    ("ts", ("typescript", "typescript")), ("tsx", ("tsx", "typescript")),
    ("cs", ("csharp", "csharp")),
    ("js", ("javascript", "javascript")), ("jsx", ("javascript", "javascript")),
    ("mjs", ("javascript", "javascript")), ("cjs", ("javascript", "javascript")),
    ("rb", ("ruby", "ruby")),
    ("go", ("go", "go")),
];

/// The grammar and collector for one extension, or nothing where this reading has neither.
pub fn for_extension(suffix: &str) -> Option<(&'static str, &'static str)> {
    crate::lang_spec::lookup(EXT_LANG, &suffix.to_lowercase())
}

/// Every extension whose collector is this language.
pub fn extensions_for(lang: &str) -> Vec<&'static str> {
    EXT_LANG.iter().filter(|(_, (_g, key))| *key == lang).map(|(ext, _)| *ext).collect()
}

/// A parser for one grammar key.
///
/// `tsx` is the one key the shared parser table has no row for, because nothing else in the
/// panel needs it.
pub fn parser_for_grammar(grammar: &str) -> tree_sitter::Parser {
    if grammar == "tsx" {
        let mut parser = tree_sitter::Parser::new();
        parser.set_language(&tree_sitter_typescript::LANGUAGE_TSX.into())
            .expect("set the tsx grammar");
        return parser;
    }
    crate::parser_for(grammar)
}

/// Every production file whose collector is `lang`, parsed with the grammar its EXTENSION
/// picks, with how many of each file's lines are a test region, and the count that could not
/// be read.
///
/// THE TEST-REGION COUNT IS A DENOMINATOR CORRECTION, and it is per file rather than one
/// total. A Rust test region comes out as spaces of the same length so that line numbers stay
/// the author's, which means `splitlines` counts the emptied lines back in; the dead-code
/// ratio divides by that count, so uuid-rs/uuid's 2,532 lines of test module left its
/// numerator and stayed under it. Per file, because that reader drops a file the grammar could
/// not parse from the number it publishes as analyzed, and one repository total cannot say
/// which file's emptied lines to drop with it.
///
/// Its own walk rather than the shared one, and the difference is the grammar: the shared
/// walk parses every file of a language with that language's parser, and a React component
/// needs the JSX grammar. Parsed with the plain TypeScript one it loses every element and the
/// names inside it, so the collectors would find fewer definitions and the corpus fewer
/// references, both silently.
pub fn parsed_files(repo: &std::path::Path, lang: &str)
    -> (Vec<(String, tree_sitter::Tree, Vec<u8>, usize)>, usize) {
    let wanted = extensions_for(lang);
    if wanted.is_empty() {
        return (Vec::new(), 0);
    }
    let has_packages = crate::repo_has_packages(repo);
    let disowned = crate::ignored_paths(repo);
    let mut out = Vec::new();
    let mut skipped = 0usize;
    for entry in crate::walk_repo(repo) {
        let path = entry.path();
        if !crate::is_file_entry(&entry) {
            continue;
        }
        let Some(ext) = path.extension().and_then(|e| e.to_str()) else { continue };
        let ext = ext.to_lowercase();
        if !wanted.contains(&ext.as_str()) {
            continue;
        }
        if crate::bucket_reason(path, repo, has_packages, crate::PRODUCTION,
                                crate::PRODUCTION_BUCKETS, &disowned).is_some() {
            continue;
        }
        let Ok(src) = std::fs::read(path) else { skipped += 1; continue };
        let Some((grammar, _collector)) = for_extension(&ext) else { continue };
        let (src, region_lines) = crate::test_regions::blanked(&src, &format!(".{ext}"));
        let test_lines = region_lines.len();
        let Some(tree) = parser_for_grammar(grammar).parse(&src, None) else {
            skipped += 1;
            continue;
        };
        let rel = path.strip_prefix(repo).unwrap_or(path).to_string_lossy().into_owned();
        out.push((rel, tree, src, test_lines));
    }
    (out, skipped)
}
