//! L1.13, near-duplicate code. Ported from l1_analyzer.clone_detect.
//!
//! The canon asks for the percentage of production lines participating in a clone class of
//! at least fifty tokens, with identifiers and literals normalised. It names a copy-paste
//! detector as the reference tool, and the reference implementation used to shell out to
//! one. That tool was installed on no machine that ever ran the panel, so this indicator
//! reported n/a on every repository ever measured, both validation controls included. An
//! indicator that has never produced a number is not a lenient one: it is a column in a
//! published panel nobody has read.
//!
//! HOW IT WORKS. Every leaf token of the parse tree becomes one symbol. An identifier
//! becomes `I` and a literal becomes `L`, whatever they were called, which is what makes a
//! renamed copy match. Keywords, operators and punctuation keep their text, so the SHAPE of
//! the code is what is compared. A window of fifty consecutive symbols that appears in two
//! or more distinct places is a clone, and every line those windows touch is duplicated.
//!
//! WHAT IT DOES NOT DO. A clone with an insertion inside it is caught only where a window of
//! the required length still matches on one side of the gap. Chasing gapped clones needs
//! suffix trees or a similarity threshold, and neither is what the canon's reference tool
//! does either.

use crate::indicators::data_tables::{declares_a_table, is_table, literal_types};
use crate::lang_spec::LangSpec;
use crate::nodes::{children, field, text};
use crate::{band, lang, py_round2, Indicator};
use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::path::Path;
use tree_sitter::Node;

const IDENTIFIER: &str = "I";
const LITERAL: &str = "L";
/// The canon's threshold, named rather than spelled at the call site.
pub const MIN_TOKENS: usize = 50;

/// How each language spells bringing a name in from somewhere else.
///
/// The STATEMENT, never a call: a runtime import does work and is code like any other.
const IMPORT_STATEMENTS: &[&str] = &["import_statement", "import_from_statement",
                                     "import_declaration", "using_directive",
                                     "use_declaration", "preproc_include",
                                     "package_declaration"];

/// How a language spells a name carrying a type.
///
/// A record holds these and its own description and nothing else; the type is what separates
/// a field from an ordinary assignment, so a class of constants is still read as code.
const FIELD_DECLARATIONS: &[&str] = &["assignment", "typed_parameter", "annotated_assignment",
                                      "field_declaration", "property_declaration",
                                      "variable_declaration"];

/// Whether this node is a record declaration and nothing else.
///
/// A class whose body holds only annotated names and its own description. One method makes
/// it code, and this answers false, because a rule that skipped any class would let anyone
/// hide duplication behind a keyword.
fn declares_only_fields(node: Node, sp: &LangSpec) -> bool {
    if !sp.class_types.contains(&node.kind()) {
        return false;
    }
    let Some(body) = field(Some(node), "body") else { return false };
    let statements: Vec<Node> = children(body).into_iter().filter(|c| c.is_named()).collect();
    if statements.is_empty() {
        return false;
    }
    let mut fields = 0;
    for statement in statements {
        if statement.kind() == "comment" {
            continue;
        }
        let inner = if sp.sink_types.contains(&statement.kind()) {
            children(statement).into_iter().find(|c| c.is_named()).unwrap_or(statement)
        } else {
            statement
        };
        if inner.kind().contains("string") {
            continue;
        }
        if FIELD_DECLARATIONS.contains(&inner.kind()) && field(Some(inner), "type").is_some() {
            fields += 1;
            continue;
        }
        return false;
    }
    fields > 0
}

/// One token of the normalised stream: the symbol, and the line it sits on.
pub struct Token {
    pub symbol: String,
    pub line: usize,
}

/// Every leaf of the tree as a symbol and a line, with identifiers and literals normalised.
///
/// A comment is dropped rather than normalised. Two blocks that differ only in their
/// comments are the same code, and counting comment text would let a copied block escape by
/// having its comment reworded.
///
/// An explicit stack, because this walk stops at a table, a record, an import and a literal
/// rather than reading every node, which is the one thing the shared descendant walk cannot
/// be asked for. Children go on reversed so they come off in source order, which is the
/// order the lines below are appended in.
pub fn normalized_tokens(root: Node, sp: &LangSpec, src: &[u8]) -> Vec<Token> {
    let literals = literal_types(sp);
    // The same discount the god-file count applies, for the same stated reason. A
    // per-language vocabulary table is nine rows of the same keys, so normalising the
    // identifiers and literals makes every row read identically and the whole table
    // measures as duplicated code. On the first real run of this indicator one table
    // contributed 390 such lines and another 142, and neither is duplicated code.
    let tables = sp_literal_containers(sp);
    let mut out = Vec::new();
    let mut stack = vec![root];
    while let Some(node) = stack.pop() {
        if node.kind().contains("comment") {
            continue;
        }
        if is_table(node, tables, literals) || declares_a_table(node, tables, literals) {
            continue;
        }
        // A record declaration, for the same reason as a data table. This check erases
        // identifiers so that two functions doing one thing with different names read
        // alike, and that is exactly what makes it wrong here: a record IS its field names,
        // and erasing them leaves the shape every record ever written has. Four types in
        // the reference package are called Finding and hold different facts; merging them
        // would be a defect rather than a fix.
        if declares_only_fields(node, sp) {
            continue;
        }
        // An import statement, for the third time the same argument. The import case is the
        // strongest of the three, because the duplication cannot be removed: a module that
        // uses a name has to import it, and a measurement an author cannot act on teaches
        // them to ignore the measurement.
        if IMPORT_STATEMENTS.contains(&node.kind()) {
            continue;
        }
        // The literal test comes BEFORE the descent, because a literal is not always a leaf.
        // Python spells a string as a node with a start, a body and an end beneath it, so a
        // leaf-only test emitted three tokens carrying the text itself and a string
        // assignment failed to match a number assignment.
        if literals.contains(&node.kind()) {
            out.push(Token { symbol: LITERAL.into(), line: node.start_position().row + 1 });
            continue;
        }
        let kids = children(node);
        if kids.is_empty() {
            let line = node.start_position().row + 1;
            if node.kind() == "identifier" || node.kind().ends_with("_identifier") {
                out.push(Token { symbol: IDENTIFIER.into(), line });
            } else {
                let spelling = text(Some(node), src);
                if !spelling.trim().is_empty() {
                    out.push(Token { symbol: spelling, line });
                }
            }
            continue;
        }
        stack.extend(kids.into_iter().rev());
    }
    out
}

/// The container types this language spells a data literal with, which is the same list the
/// god-file count discounts.
fn sp_literal_containers(sp: &LangSpec) -> &'static [&'static str] {
    // The generated language config carries it; the language table carries the literals.
    // Looked up by key rather than passed in, because the two tables are keyed the same way
    // and a caller holding one already knows the other.
    lang::cfg(sp.key).map(|cfg| cfg.literal_nodes).unwrap_or(&[])
}

/// A window's identity.
///
/// The reference hashes the window's symbols so a large repository holds one short digest
/// per window instead of fifty strings, and this does the same. The digest is 128 bits wide
/// and never leaves this function's caller, so what matters is that two different windows
/// almost never share one, not that it matches the reference's bytes: at half a million
/// windows the chance of any collision is about one in ten to the twenty-seventh.
fn window_digest(symbols: &[u32]) -> u128 {
    let mut low: u64 = 0xcbf2_9ce4_8422_2325;
    let mut high: u64 = 0x9ddf_ea08_eb38_2d69;
    for &s in symbols {
        low = (low ^ s as u64).wrapping_mul(0x0000_0100_0000_01b3);
        high = (high ^ (s as u64).rotate_left(17)).wrapping_mul(0xff51_afd7_ed55_8ccd);
    }
    ((high as u128) << 64) | low as u128
}

/// The lines of each file that sit inside a window repeated somewhere in the tree.
///
/// Two passes, because a window is only a clone once a SECOND occurrence is known, and the
/// first occurrence's lines count as duplicated too. Counting on one pass would charge the
/// copy and acquit the original.
pub fn duplicated_lines(streams: &BTreeMap<String, Vec<Token>>,
                        min_tokens: usize) -> BTreeMap<String, BTreeSet<usize>> {
    // Symbols are interned once, so a window is fifty small numbers rather than fifty
    // strings, and two windows compare by what they hold rather than by how they were spelt.
    let mut ids: HashMap<&str, u32> = HashMap::new();
    let mut streams_as_ids: Vec<(&String, Vec<u32>, Vec<usize>)> = Vec::new();
    for (relpath, stream) in streams {
        let mut symbols = Vec::with_capacity(stream.len());
        let mut lines = Vec::with_capacity(stream.len());
        for token in stream {
            let next = ids.len() as u32;
            let id = *ids.entry(token.symbol.as_str()).or_insert(next);
            symbols.push(id);
            lines.push(token.line);
        }
        streams_as_ids.push((relpath, symbols, lines));
    }

    let mut seen: HashMap<u128, Vec<(&String, usize)>> = HashMap::new();
    for (relpath, symbols, _lines) in &streams_as_ids {
        if symbols.len() < min_tokens {
            continue;
        }
        for start in 0..=(symbols.len() - min_tokens) {
            let digest = window_digest(&symbols[start..start + min_tokens]);
            seen.entry(digest).or_default().push((relpath, start));
        }
    }

    let by_path: HashMap<&String, &Vec<usize>> =
        streams_as_ids.iter().map(|(p, _s, l)| (*p, l)).collect();
    let mut duplicated: BTreeMap<String, BTreeSet<usize>> = BTreeMap::new();
    for occurrences in seen.values() {
        if occurrences.len() < 2 {
            continue;
        }
        // Distinct PLACES, not distinct digests. A window that overlaps itself inside one
        // long run of identical tokens is one clone, not a hundred, and the start line is
        // what separates them.
        let places: BTreeSet<(&String, usize)> = occurrences.iter()
            .map(|(relpath, start)| (*relpath, by_path[relpath][*start]))
            .collect();
        if places.len() < 2 {
            continue;
        }
        // The lines the clone's TOKENS sit on, not the range from its first line to its
        // last. A docstring is one token spanning many lines, so a window could reach across
        // a signature, a docstring and the next signature and call every line between
        // duplicated: one held fifty tokens on six lines and was credited with twenty-six.
        for (relpath, start) in occurrences {
            let lines = by_path[relpath];
            duplicated.entry((*relpath).clone()).or_default()
                .extend(lines[*start..*start + min_tokens].iter().copied());
        }
    }
    duplicated
}

/// L1.13 for one repository: the share of production lines inside a repeated window.
pub fn analyze(repo: &Path, language: &str) -> Indicator {
    let row = |value: String, band: String, details: String| Indicator {
        code: "L1.13".into(), label: "duplication".into(), value, band, details,
    };
    let Some(sp) = crate::lang_spec::spec_for(language) else {
        return row("n/a".into(), "n/a".into(),
                   format!("no tree-sitter config for {language}"));
    };
    let (parsed, skipped) = crate::production_files(repo, language);
    if parsed.is_empty() {
        // A share of no lines is absent, not zero. Reporting 0.0 here would band healthy for
        // a repository nobody read, which is the zero-denominator lie this refuses.
        return row("n/a".into(), "n/a".into(), format!(
            "no production {language} source in scope, so duplication was not measured"));
    }

    let mut streams: BTreeMap<String, Vec<Token>> = BTreeMap::new();
    let mut total_lines = 0usize;
    for (rel, tree, src) in &parsed {
        let stream = normalized_tokens(tree.root_node(), sp, src);
        // Lines that carry a code token, which is what production lines means and what the
        // numerator counts. The reference counted every line in the file, blanks and
        // docstrings included, while the numerator marked whole line ranges: both halves
        // generous, and generosity in a divisor lowers a percentage.
        total_lines += stream.iter().map(|t| t.line).collect::<BTreeSet<usize>>().len();
        streams.insert(rel.clone(), stream);
    }

    let duplicated = duplicated_lines(&streams, MIN_TOKENS);
    let duplicated_count: usize = duplicated.values().map(|lines| lines.len()).sum();
    if total_lines == 0 {
        // A share over no code lines is absent, not zero, and zero is the HEALTHY end of
        // this scale: a tree the parser found no token in must not read as clean.
        return row("n/a".into(), "n/a".into(), format!(
            "no {language} code line carried a token, so duplication was not measured"));
    }
    let pct = (duplicated_count as f64 / total_lines as f64 * 100.0 * 100.0).round() / 100.0;
    // Every discount named, not one of them. The reference's line said only "large data
    // tables" while the walk was passing over three things, which is a reading of less code
    // than a reader was told about.
    let mut detail = format!(
        "{duplicated_count} of {total_lines} production code lines inside a repeated \
         {MIN_TOKENS}-token window, identifiers and literals normalized, across {} file(s). \
         Three things carry no logic and are discounted: a large data table, as L1.17 \
         discounts one; a record declaration, which is a list of field names; and an import \
         statement, which is a list of imported names and whose repetition no author can \
         remove", parsed.len());
    if skipped != 0 {
        detail.push_str(&format!("; {skipped} file(s) unreadable or oversized and excluded"));
    }
    row(py_round2(pct), band(pct, 3.0, 10.0, false).into(), detail)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::lang_spec::spec_for;
    use crate::parser_for;

    fn tokens(source: &str, lang: &str) -> Vec<String> {
        let mut parser = parser_for(lang);
        let src = source.as_bytes().to_vec();
        let tree = parser.parse(&src, None).expect("a parse");
        let sp = spec_for(lang).expect("a language row");
        normalized_tokens(tree.root_node(), sp, &src).into_iter().map(|t| t.symbol).collect()
    }

    #[test]
    fn a_renamed_copy_reads_the_same_as_its_original() {
        // Type-2 is the whole point: erase the names and the literals, keep the shape.
        let one = tokens("def total(items):\n    return sum(items) + 1\n", "python");
        let two = tokens("def add_up(rows):\n    return sum(rows) + 99\n", "python");
        assert_eq!(one, two);
        assert!(one.contains(&"I".to_string()) && one.contains(&"L".to_string()), "{one:?}");
    }

    #[test]
    fn a_string_is_one_token_however_its_grammar_spells_it() {
        // Python hangs a start, a body and an end under a string, so a leaf-only rule
        // emitted three tokens carrying the text and a string assignment stopped matching a
        // number assignment.
        assert_eq!(tokens("x = 'text'\n", "python"), tokens("x = 1\n", "python"));
    }

    #[test]
    fn a_comment_carries_no_shape_and_is_dropped() {
        // Two blocks differing only in their comments are the same code, and counting the
        // comment text would let a copy escape by having its comment reworded.
        assert_eq!(tokens("x = 1  # one\n", "python"), tokens("x = 1  # something else\n",
                                                              "python"));
    }

    #[test]
    fn an_import_block_is_a_list_of_names_and_not_a_repeated_block() {
        // The strongest of the three discounts: a module that uses a name has to import it,
        // so the repetition is one no author can remove.
        assert!(tokens("import os\nimport sys\nfrom a import b\n", "python").is_empty());
    }

    #[test]
    fn a_data_table_is_discounted_and_a_pile_of_logic_is_not() {
        let table = "T = {'a': 1, 'b': 2, 'c': 3}\n";
        let logic = "def f(x):\n    if x:\n        return 1\n    return 2\n";
        assert!(tokens(table, "python").is_empty(), "{:?}", tokens(table, "python"));
        assert!(!tokens(logic, "python").is_empty());
    }

    #[test]
    fn a_window_repeated_in_one_long_run_is_one_clone_and_not_a_hundred() {
        // Distinct PLACES, not distinct digests: a window sliding through a run of identical
        // tokens overlaps itself, and the start line is what separates a real second
        // occurrence from the same one seen again.
        let mut streams: BTreeMap<String, Vec<Token>> = BTreeMap::new();
        streams.insert("a.py".into(),
                       (0..8).map(|_| Token { symbol: "x".into(), line: 1 }).collect());
        assert!(duplicated_lines(&streams, 3).is_empty());
    }

    #[test]
    fn both_occurrences_of_a_clone_are_counted_and_not_only_the_copy() {
        let run = |line: usize| -> Vec<Token> {
            "abcd".chars().map(|c| Token { symbol: c.to_string(), line }).collect()
        };
        let mut streams: BTreeMap<String, Vec<Token>> = BTreeMap::new();
        streams.insert("a.py".into(), run(7));
        streams.insert("b.py".into(), run(42));
        let found = duplicated_lines(&streams, 4);
        assert_eq!(found.get("a.py").map(|l| l.iter().copied().collect::<Vec<_>>()),
                   Some(vec![7]));
        assert_eq!(found.get("b.py").map(|l| l.iter().copied().collect::<Vec<_>>()),
                   Some(vec![42]));
    }

    #[test]
    fn a_share_over_no_source_at_all_is_absent_and_never_zero() {
        // Zero is the HEALTHY end of this scale, so a tree nobody read must not report it.
        let root = std::env::temp_dir().join(format!("slop-dup-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).expect("make the fixture");
        let got = analyze(&root, "python");
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(got.value, "n/a");
        assert_eq!(got.band, "n/a");
        assert!(got.details.contains("not measured"), "{}", got.details);
    }
}
