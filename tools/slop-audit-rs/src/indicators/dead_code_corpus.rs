//! What the repository says about a name, gathered once from every file in it. Ported from
//! l1_analyzer.dead_code_corpus.
//!
//! The other half of the dead-code reading. This one walks the whole tree and records where
//! every name appears; the driver decides which definitions that leaves unreachable. The seam
//! is real rather than a size cut: this touches the disk and answers "where is this name
//! written", and nothing here knows what a definition is or what dead means.
//!
//! A name is recorded as a HARD reference when a grammar this binary carries parsed it as an
//! identifier, and as a word otherwise, split by what the file is: prose, configuration, a
//! specification, or a dotted path naming a module. Those four carry different weight,
//! because a configuration file that names a function can be calling it and a paragraph that
//! names it cannot.

use crate::nodes::{children, descendants, text};
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;
use tree_sitter::Node;

/// Node types that are an identifier without saying so in their name.
const IDENT_EXTRA: &[&str] = &["identifier", "constant"];
/// A file that DESCRIBES the code rather than wiring it.
const DOC_EXTS: &[&str] = &["md", "rst", "txt", "adoc", "org"];
/// A file that describes BEHAVIOUR rather than wiring it.
///
/// Read apart from the configuration beside it: a scenario binds a step to a function by
/// matching the step TEXT against a pattern, never by the function's name, so a scenario
/// titled after a function calls nothing. Found in a package that writes one scenario per
/// function as a commit gate: that put every function name it has into a feature file, so
/// every function nobody called came back "an entry point can be wired by name", and four
/// dead ones sat in one module behind that excuse.
const SPEC_EXTS: &[&str] = &["feature", "story"];
const MAX_BYTES: u64 = 1_048_576;

/// Every name occurrence the classifier can consult.
///
/// The word buckets live in one map rather than as four fields because every reader of them
/// picks a bucket by NAME at run time: the harvester chooses documentation or configuration
/// from a file extension, and the soft-reason rule walks them in priority order.
#[derive(Debug, Default)]
pub struct Corpus {
    /// name -> the files and byte offsets of real identifier uses.
    pub hard: BTreeMap<String, Vec<(String, usize)>>,
    /// bucket -> the words in it.
    pub words: BTreeMap<&'static str, BTreeSet<String>>,
    pub unreadable: usize,
}

impl Corpus {
    fn new() -> Self {
        let mut words = BTreeMap::new();
        for bucket in ["strings", "config", "docs", "specs", "dotted"] {
            words.insert(bucket, BTreeSet::new());
        }
        Corpus { hard: BTreeMap::new(), words, unreadable: 0 }
    }
}

fn is_identifier_leaf(node: Node) -> bool {
    node.child_count() == 0
        && (IDENT_EXTRA.contains(&node.kind()) || node.kind().ends_with("_identifier"))
}

/// Whether the whole of `s` is one identifier.
fn is_one_word(s: &str) -> bool {
    let mut chars = s.chars();
    match chars.next() {
        Some(c) if c.is_ascii_alphabetic() || c == '_' => {}
        _ => return false,
    }
    chars.all(|c| c.is_ascii_alphanumeric() || c == '_')
}

/// Every identifier-shaped word in a text.
fn words_in(text: &str) -> BTreeSet<String> {
    let mut out = BTreeSet::new();
    let bytes: Vec<char> = text.chars().collect();
    let mut i = 0usize;
    while i < bytes.len() {
        if bytes[i].is_ascii_alphabetic() || bytes[i] == '_' {
            let start = i;
            while i < bytes.len() && (bytes[i].is_ascii_alphanumeric() || bytes[i] == '_') {
                i += 1;
            }
            out.insert(bytes[start..i].iter().collect());
        } else {
            i += 1;
        }
    }
    out
}

/// The names a string literal could be RESOLVING, which is not every word it holds.
///
/// The reference collected every word of every string and comment, and a hit exempts a
/// definition as "a dynamic reference cannot be resolved". So a dead function whose name
/// appeared in any docstring anywhere was excluded from the numerator, and the exemption
/// written for a reflective lookup was satisfied by prose.
///
/// A string is a candidate reference when the WHOLE string is one identifier, which is what a
/// reflective lookup and a registry subscript look like. A string carrying the name among
/// other words is prose and carries no lookup. The quote characters are children of the
/// string node in every grammar here, so the content is read from the named children rather
/// than by trimming quotes this reader would have to know the spelling of.
fn string_reference_names(node: Node, src: &[u8]) -> BTreeSet<String> {
    let parts: Vec<Node> = children(node).into_iter()
        .filter(|c| c.is_named() && c.kind().contains("content"))
        .collect();
    let body = if parts.is_empty() {
        text(Some(node), src)
    } else {
        parts.into_iter().map(|c| text(Some(c), src)).collect::<String>()
    };
    let stripped = body.trim();
    let mut out = BTreeSet::new();
    if is_one_word(stripped) {
        out.insert(stripped.to_string());
    }
    out
}

/// The dotted module path a string holds, or the empty string.
///
/// Every framework that loads code the parser cannot follow spells it this way: a plugin
/// named on a command line, an application factory behind a colon, a task named by its path.
/// The file is imported by a name in a string, so nothing imports it in the source and the
/// island rule reads it and everything in it as dead.
///
/// Two segments at least, each one an identifier, and the colon form is cut at the colon
/// because what follows it is a symbol inside the module rather than part of the path.
/// Whether it means anything is settled by resolving it against the repository's own files,
/// which is what keeps this from becoming "any string with a dot in it".
pub fn dotted_path_in(text: &str) -> String {
    let head = text.trim().split(':').next().unwrap_or("");
    let parts: Vec<&str> = head.split('.').collect();
    if parts.len() < 2 || !parts.iter().all(|p| is_one_word(p)) {
        return String::new();
    }
    head.to_string()
}

fn harvest_source(root: Node, relpath: &str, src: &[u8], corpus: &mut Corpus) {
    for node in descendants(root) {
        if is_identifier_leaf(node) {
            corpus.hard.entry(text(Some(node), src)).or_default()
                .push((relpath.to_string(), node.start_byte()));
        } else if node.kind().contains("string") {
            let names = string_reference_names(node, src);
            corpus.words.get_mut("strings").expect("the strings bucket").extend(names);
            let spelling = text(Some(node), src);
            let dotted = dotted_path_in(spelling.trim_matches(['"', '\'']));
            if !dotted.is_empty() {
                corpus.words.get_mut("dotted").expect("the dotted bucket").insert(dotted);
            }
        }
    }
}

/// What one file contributes to the corpus, decided from its bytes and its suffix.
///
/// A file this binary has a grammar for is parsed, so a name is a name rather than a run of
/// letters that happens to match one. Everything else contributes words, split into
/// documentation and configuration because the two carry different weight downstream.
///
/// Binary contributes nothing. A null byte in the first eight kibibytes is the test, which is
/// what the version-control tools use and is wrong only for text that legitimately holds one.
pub fn classify_into(corpus: &mut Corpus, relpath: &str, suffix: &str, raw: &[u8]) {
    if raw[..raw.len().min(8192)].contains(&0) {
        return;
    }
    if let Some((grammar, _collector)) =
        crate::indicators::dead_code_grammars::for_extension(suffix) {
        let mut parser = crate::indicators::dead_code_grammars::parser_for_grammar(grammar);
        if let Some(tree) = parser.parse(raw, None) {
            harvest_source(tree.root_node(), relpath, raw, corpus);
        }
        return;
    }
    // Invalid bytes are dropped where they sit, which is what the reference's decode does.
    // Neither a lossy conversion nor a lossy conversion with the replacement characters
    // stripped is the same thing, and both were wrong here in opposite directions.
    let decoded = crate::decode_ignoring_invalid(raw);
    let found = words_in(&decoded);
    let bucket = if SPEC_EXTS.contains(&suffix) {
        "specs"
    } else if DOC_EXTS.contains(&suffix) {
        "docs"
    } else {
        "config"
    };
    corpus.words.get_mut(bucket).expect("a declared bucket").extend(found);
}

/// Every file in the repository is a possible reference site: a sibling module, a test, a
/// workflow that names an entry point, a README.
///
/// Vendored and ignored directories are skipped; unreadable and oversized files are counted
/// and disclosed, never silently dropped.
pub fn read_corpus(repo: &Path) -> Corpus {
    let mut corpus = Corpus::new();
    for entry in crate::walk_repo(repo) {
        let path = entry.path();
        if !crate::is_file_entry(&entry) || crate::in_ignored_dir(path) {
            continue;
        }
        let relpath = path.strip_prefix(repo).unwrap_or(path).to_string_lossy().into_owned();
        match std::fs::metadata(path) {
            Ok(meta) if meta.len() > MAX_BYTES => {
                corpus.unreadable += 1;
                continue;
            }
            Err(_) => {
                corpus.unreadable += 1;
                continue;
            }
            _ => {}
        }
        let Ok(raw) = std::fs::read(path) else {
            corpus.unreadable += 1;
            continue;
        };
        let suffix = path.extension().and_then(|e| e.to_str()).unwrap_or("").to_lowercase();
        classify_into(&mut corpus, &relpath, &suffix, &raw);
    }
    corpus
}

#[cfg(test)]
mod tests {
    use super::*;

    fn corpus_of(relpath: &str, suffix: &str, raw: &str) -> Corpus {
        let mut corpus = Corpus::new();
        classify_into(&mut corpus, relpath, suffix, raw.as_bytes());
        corpus
    }

    #[test]
    fn a_string_that_is_one_identifier_could_be_a_lookup_and_prose_could_not() {
        // The exemption exists for a reflective lookup. Satisfying it with a paragraph
        // excused every dead function whose name appeared in any docstring anywhere.
        let lookup = corpus_of("m.py", "py", "x = getattr(o, 'handler')\n");
        assert!(lookup.words["strings"].contains("handler"), "{:?}", lookup.words["strings"]);
        let prose = corpus_of("m.py", "py", "x = 'calls the handler once'\n");
        assert!(prose.words["strings"].is_empty(), "{:?}", prose.words["strings"]);
    }

    #[test]
    fn a_parsed_file_yields_names_and_an_unparsed_one_yields_words() {
        let parsed = corpus_of("m.py", "py", "def handler():\n    pass\n");
        assert!(parsed.hard.contains_key("handler"));
        assert!(parsed.words["config"].is_empty());
        let config = corpus_of("ci.yml", "yml", "run: handler\n");
        assert!(config.hard.is_empty());
        assert!(config.words["config"].contains("handler"));
    }

    #[test]
    fn a_scenario_describes_behaviour_and_a_configuration_wires_it() {
        let spec = corpus_of("a.feature", "feature", "Scenario: handler returns\n");
        assert!(spec.words["specs"].contains("handler"));
        assert!(spec.words["config"].is_empty());
        let doc = corpus_of("README.md", "md", "The handler returns.\n");
        assert!(doc.words["docs"].contains("handler"));
    }

    #[test]
    fn a_dotted_string_names_a_module_and_a_sentence_does_not() {
        assert_eq!(dotted_path_in("pkg.plugin"), "pkg.plugin");
        assert_eq!(dotted_path_in("app.main:create_app"), "app.main");
        assert_eq!(dotted_path_in("1.2.3"), "");
        assert_eq!(dotted_path_in("ends in a full stop."), "");
        assert_eq!(dotted_path_in("single"), "");
    }

    #[test]
    fn binary_contributes_nothing() {
        let mut corpus = Corpus::new();
        classify_into(&mut corpus, "a.bin", "bin", b"handler\0more");
        assert!(corpus.hard.is_empty());
        assert!(corpus.words.values().all(|b| b.is_empty()));
    }
}

/// The corpus as a flat, comparable listing, for the parity dump.
///
/// A hard reference is one row per name and file, with the number of occurrences rather than
/// each offset: the offsets matter to the driver's own-file rule, and a byte-for-byte dump of
/// them is a wall nobody reads. A word is one row per bucket and word.
pub fn dump(corpus: &Corpus) -> Vec<String> {
    let mut rows = Vec::new();
    for (name, uses) in &corpus.hard {
        let mut by_file: BTreeMap<&str, usize> = BTreeMap::new();
        for (relpath, _offset) in uses {
            *by_file.entry(relpath.as_str()).or_insert(0) += 1;
        }
        for (relpath, count) in by_file {
            rows.push(format!("hard\t{name}\t{relpath}\t{count}"));
        }
    }
    for (bucket, found) in &corpus.words {
        for word in found {
            rows.push(format!("word\t{bucket}\t{word}"));
        }
    }
    rows
}
