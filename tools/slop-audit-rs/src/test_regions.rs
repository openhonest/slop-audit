//! The parts of a production file that are somebody's tests. Ported from
//! l1_analyzer.test_regions.
//!
//! EIGHT INDICATORS MEASURE PRODUCTION CODE ONLY, and a project's test tree is deliberately
//! outside them. Every rule that decides this works on PATHS: a directory named test or
//! tests, a file whose stem ends in _test or .spec. Eight of the nine languages this
//! instrument reads put their tests where such a rule can see them.
//!
//! Rust does not. A Rust unit test lives inside the file it tests, so no path names it and it
//! was measured as production code. Counted on the 68 crates on one machine, 1,799 files:
//! 2,532 of uuid-rs/uuid's 9,821 lines are inside a test module, 25.8 per cent, and 4,300 of
//! this crate's own 21,633, 19.9 per cent. The numbers were not wrong about what they
//! measured; they answered a different question for Rust than for the other eight, and
//! nothing said so.
//!
//! So a region of a file can be excluded, not only a whole file. The region is replaced by
//! spaces of the same length, newlines kept, so every line number a reader reports is still
//! the line number in the file, and every reader gets the exclusion without knowing this
//! module exists.
//!
//! TWO SHAPES ARE READ AND ONE IS NOT, and the third is named here so its absence is a
//! measured gap rather than a silence. Counted across those same crates:
//!
//!   227 test modules written in the file they test, `#[cfg(test)] mod tests { ... }`   READ
//!   851 test functions in 54 files of tests under src, declared `#[cfg(test)] mod tests;`
//!       from the parent file, the file itself carrying no marker at all                NOT READ
//!   the rest, a bare `#[test]` on a function with no such module around it             READ
//!
//! The second needs a module declaration followed from one file to another, which no reader
//! here does. Rayon, indexmap and winnow all write their tests that way, so a third of the
//! test code inside src is still measured as production. slop-audit-12x carries that half.
//!
//! WHAT THE BLANKING CANNOT DO, and L1.12 publishes a zero over it today. A definition whose only
//! caller is the crate's own unit test should be reported test-only: the tests call it, so it is
//! not dead, and it is not load-bearing production code either. Deciding that needs the REFERENCES
//! split the same way the definitions now are, and they are not: the reference corpus reads every
//! file whole, so a name used only inside a test module still reads as used from production. uuid-
//! rs/uuid reports 0 definitions referenced only by tests across 2,532 lines of test module, which
//! is the vacuous affirmative this instrument exists to name, and 497 of its names appear nowhere
//! but inside a test region. Splitting the corpus per region, not per file, is what would fix it.
//! slop-audit-12x carries this half as well.
//!
//! THE TRAP, and it is why this reads a cfg predicate rather than matching on the word test.
//! `#[cfg(any(test, feature = "std"))]` mentions test and is not test-only: `any` means the
//! item ships whenever either condition holds, so a normal build with that feature on
//! includes it. There are 13 of those. `#[cfg(feature = "test_debug")]` and `#[cfg(doctest)]`
//! are the same mistake wearing different words. Excluding any of them would delete
//! production code from the measurement, which is the one error worse than the one being
//! fixed.

use regex::Regex;
use std::collections::BTreeSet;
use std::sync::OnceLock;
use tree_sitter::Node;

/// TEST_REGION_LANGUAGES: which extensions carry tests inside a production file. One entry,
/// and the emptiness of the rest is the finding: every other language this reads puts its
/// tests in their own file.
pub const TEST_REGION_EXTENSIONS: &[&str] = &[".rs"];

/// _TEST_ONLY_CFG: a cfg predicate that REQUIRES test. `cfg(test)` on its own, and
/// `cfg(all(test, ...))` where every condition must hold, so test must hold. Anything inside
/// `any(...)` is excluded by the `all` requirement: that item ships without test as well.
fn test_only_cfg() -> &'static Regex {
    static PATTERN: OnceLock<Regex> = OnceLock::new();
    PATTERN.get_or_init(|| {
        Regex::new(r"^#!?\[\s*cfg\s*\(\s*(?:test\s*\)|all\s*\(\s*test\b)")
            .expect("the cfg pattern")
    })
}

/// What may stand between an attribute and the item it marks, and therefore belongs inside the
/// region with them. A comment written there is Rust and is common, and reading it as the marked
/// ITEM left the function behind, bare and private and called by nothing, which is the same
/// defect the attribute RUN fixed from the other end.
const RUN_TYPES: &[&str] = &["attribute_item", "line_comment", "block_comment"];

/// _TEST_ATTRIBUTES: the attributes that mark one function as a test the harness runs. A bare
/// `#[test]`, and the async runtimes' own spellings, which are the same declaration with a
/// runtime attached.
fn test_attributes() -> &'static Regex {
    static PATTERN: OnceLock<Regex> = OnceLock::new();
    PATTERN.get_or_init(|| {
        Regex::new(concat!(
            r"^#\[\s*(?:test|ignore|bench|",
            r"(?:tokio|async_std|actix_rt|actix_web|smol|serial_test|rstest|proptest)::[\w:]*test\w*",
            r")\s*(?:\(|\])")).expect("the attribute pattern")
    })
}

/// marks_a_test: whether this attribute says the item under it exists only for tests.
///
/// Read as a predicate rather than searched for the word, because `any(test, feature = "std")`
/// carries the word and ships in a normal build. The two mistakes are not symmetric: missing a
/// test region leaves the old answer, and excluding a production item deletes somebody's code
/// from the measurement.
pub fn marks_a_test(attribute: &str) -> bool {
    let flat = attribute.split_whitespace().collect::<Vec<_>>().join(" ");
    test_only_cfg().is_match(&flat) || test_attributes().is_match(&flat)
}

/// blanked: the same bytes with every test region replaced by spaces, and which line numbers
/// those were, counting from 1. An extension with no entry above comes back untouched, which is
/// eight of the nine.
///
/// Spaces rather than deletion, so a line number a reader reports is the line number in the
/// file. A reader that says line 391 must mean line 391 of what the author wrote.
///
/// THE LINE NUMBERS TRAVEL WITH THE BYTES because nothing can recover them afterwards: an
/// emptied line and a line the author left blank are the same bytes. Two readers want them for
/// different reasons and one structure answers both. Three readers divide by a line count, and
/// without the numbers their numerator excluded a crate's tests while their denominator kept
/// them. The secret scanner wants membership rather than a count: it reports a credential
/// wherever it sits and labels the ones in a test, so a fixture key in a Rust test module was
/// labelled production until it could ask this.
///
/// A SET, because the first version added up each span's line count. Regions nest inside one
/// another and sit on consecutive lines, so the shared lines were counted twice over: uuid-rs/
/// uuid's lib.rs came out at 1,302 lines of 1,715 where 710 are test. Comparing the two byte
/// strings line by line fixed the double count and gave 598, which is wrong the other way: a
/// line the author left blank inside a test module does not change, so it stayed under every
/// ratio that divides by a line count. The line numbers are read off the parse tree instead.
///
/// One line can still be part test and part production, where an author puts code after the
/// closing brace of a test item. The whole line is called test, and nothing in the 68 crates
/// measured is written that way.
pub fn blanked(source: &[u8], ext: &str) -> (Vec<u8>, BTreeSet<usize>) {
    if !TEST_REGION_EXTENSIONS.contains(&ext) {
        return (source.to_vec(), BTreeSet::new());
    }
    let mut parser = crate::parser_for("rust");
    let Some(tree) = parser.parse(source, None) else {
        return (source.to_vec(), BTreeSet::new());
    };
    let mut keep = source.to_vec();
    let mut lines = BTreeSet::new();
    for (start, end, first_row, last_row) in regions(tree.root_node(), source) {
        for byte in &mut keep[start..end] {
            if *byte != b'\n' {
                *byte = b' ';
            }
        }
        lines.extend(first_row + 1..=last_row + 1);
    }
    (keep, lines)
}

/// _regions: every test region, its first and last byte, then its first and last row, counting
/// rows from 0 the way tree-sitter does. The region is the whole run of attributes and the item
/// they mark.
///
/// The rows come from the parse tree rather than from counting newlines in the bytes, because
/// tree-sitter already knows them and a second count is a second answer.
///
/// THE RUN, NOT THE ONE ATTRIBUTE. An item may carry several, and the one that marks it a test
/// need not be next to it:
///
/// ```text
///     #[test]
///     #[cfg(windows)]
///     fn guid_to_uuid() { ... }
/// ```
///
/// Taking the marking attribute and its next sibling took the two attributes and left the
/// function, bare and private and called by nothing, so the dead-code reader said somebody's
/// example was dead. uuid-rs/uuid has three written that way and the 68 crates have 391.
/// Starting at the run's first attribute matters for the same reason from the other end: begin
/// at the marking one and a `#[cfg(windows)]` is left in front of nothing, which is not Rust.
///
/// AND A COMMENT MAY STAND BETWEEN THEM, which is the same defect from a third direction:
///
/// ```text
///     #[test]
///     #[cfg(windows)]
///     // why this one is windows-only
///     fn guid_to_uuid() { ... }
/// ```
///
/// tree-sitter gives the comment its own named node, so the run ended at the attributes and the
/// comment was read as the item they marked. The function was left bare again. Three of these
/// are written across the 68 crates on one machine. The run absorbs comments and the marked
/// item is the first node after it that is not one.
///
/// An explicit stack, and it does not read below a region. A test module holds functions
/// carrying their own attributes, and walking in would find them all again for no gain.
fn regions(root: Node, source: &[u8]) -> Vec<(usize, usize, usize, usize)> {
    let mut spans = Vec::new();
    let mut stack = vec![root];
    while let Some(node) = stack.pop() {
        let mut cursor = node.walk();
        let children: Vec<Node> = node.named_children(&mut cursor).collect();
        let mut at = 0usize;
        while at < children.len() {
            if children[at].kind() != "attribute_item" {
                at += 1;
                continue;
            }
            let run = at;
            while at < children.len() && RUN_TYPES.contains(&children[at].kind()) {
                at += 1;
            }
            let attributes: Vec<Node> = children[run..at].iter().copied()
                .filter(|c| c.kind() == "attribute_item").collect();
            let marked = children.get(at);
            let marks = attributes.iter().any(|a| {
                marks_a_test(&String::from_utf8_lossy(&source[a.start_byte()..a.end_byte()]))
            });
            match marked {
                // From the first ATTRIBUTE, not from the first node of the run: a comment
                // written above the attributes may belong to whatever stands above them, and
                // the run only ever starts at an attribute because of the test above.
                Some(item) if marks => {
                    spans.push((attributes[0].start_byte(), item.end_byte(),
                                attributes[0].start_position().row, item.end_position().row));
                    at += 1; // the item is inside the region, so nothing below it is read
                }
                _ => stack.extend(children[run..at].iter().copied()),
            }
        }
        stack.extend(children.into_iter().filter(|c| c.kind() != "attribute_item"));
    }
    spans
}

#[cfg(test)]
mod tests {
    use super::*;

    const A_CRATE: &str = concat!(
        "pub fn band(n: i32) -> &'static str {\n",
        "    if n < 0 { \"neg\" } else { \"pos\" }\n",
        "}\n",
        "\n",
        "#[cfg(test)]\n",
        "mod tests {\n",
        "    use super::*;\n",
        "\n",
        "    #[test]\n",
        "    fn negatives_are_neg() {\n",
        "        assert_eq!(band(-1), \"neg\");\n",
        "    }\n",
        "}\n");

    // The two orders an item's attributes come in, and the item bare in between. Taking the
    // marking attribute and its next sibling left `fn guid_to_uuid` standing with no attribute
    // in front of it, so the dead-code reader called somebody's example dead. uuid-rs/uuid
    // writes three of these and the 68 crates write 391.
    const BOTH_ORDERS: &str = concat!(
        "#[test]\n#[cfg(windows)]\nfn guid_to_uuid() { assert_eq!(1 + 1, 2); }\n\n",
        "#[cfg(windows)]\n#[test]\nfn uuid_to_guid() { let n: i32 = 3; assert!(n > 0); }\n\n",
        "pub fn shipped() -> i32 { 1 }\n");

    // The trap. `any` means the item ships whenever either condition holds, so a build with
    // the std feature on includes it, and excluding it would delete production code from the
    // measurement. Thirteen items on that machine are written this way.
    const SHIPS_ANYWAY: &str = concat!(
        "#[cfg(any(test, feature = \"std\"))]\npub fn with_std() -> i32 { 1 }\n\n",
        "#[cfg(feature = \"test_debug\")]\npub fn debug_only() -> String { \"d\".into() }\n\n",
        "#[cfg(doctest)]\npub fn doc_only(n: i32) -> i32 { n * 3 }\n");

    #[test]
    fn a_test_module_comes_out_and_the_production_function_stays() {
        let (out, region_lines) = blanked(A_CRATE.as_bytes(), ".rs");
        let text = String::from_utf8(out).expect("still utf8");
        assert!(text.contains("pub fn band"));
        assert!(!text.contains("negatives_are_neg"));
        assert!(!text.contains("mod tests"));
        // Lines 5 to 13 of the fixture, the attribute and the module it marks. The blank line
        // inside the module is in the region too, because it is a line of the module.
        assert_eq!(region_lines, (5..=13).collect::<BTreeSet<usize>>(), "{text}");
    }

    #[test]
    fn every_line_number_is_still_the_authors() {
        let (out, _) = blanked(A_CRATE.as_bytes(), ".rs");
        assert_eq!(out.len(), A_CRATE.len());
        assert_eq!(out.iter().filter(|b| **b == b'\n').count(),
                   A_CRATE.bytes().filter(|b| *b == b'\n').count());
        let text = String::from_utf8(out).expect("still utf8");
        assert_eq!(text.lines().next(), A_CRATE.lines().next());
    }

    #[test]
    fn an_attribute_run_goes_with_the_item_it_marks() {
        let (out, _) = blanked(BOTH_ORDERS.as_bytes(), ".rs");
        let text = String::from_utf8(out).expect("still utf8");
        assert!(!text.contains("guid_to_uuid"));
        assert!(!text.contains("uuid_to_guid"));
        assert!(!text.contains("cfg(windows)"),
                "an attribute left in front of nothing is not Rust");
        assert!(text.contains("pub fn shipped"));
    }

    #[test]
    fn a_cfg_that_mentions_test_but_ships_anyway_is_left_alone() {
        let (out, region_lines) = blanked(SHIPS_ANYWAY.as_bytes(), ".rs");
        let text = String::from_utf8(out).expect("still utf8");
        assert!(text.contains("with_std"));
        assert!(text.contains("debug_only"));
        assert!(text.contains("doc_only"));
        assert!(region_lines.is_empty());
    }

    /// A comment between an attribute and the item it marks is Rust, and it is common. Read as
    /// the marked ITEM it left the function bare and private and called by nothing, which is the
    /// dead-code false positive the attribute run already fixed from the other end.
    #[test]
    fn a_comment_between_an_attribute_and_its_item_stays_inside_the_region() {
        let src = concat!(
            "#[test]\n#[cfg(windows)]\n// why this one is windows-only\n",
            "fn guid_to_uuid() { assert!(true); }\n\npub fn shipped() -> i32 { 1 }\n");
        let (out, region_lines) = blanked(src.as_bytes(), ".rs");
        let text = String::from_utf8(out).expect("still utf8");
        assert!(!text.contains("guid_to_uuid"), "{text}");
        assert!(!text.contains("windows"), "{text}");
        assert!(text.contains("pub fn shipped"), "{text}");
        assert_eq!(region_lines, (1..=4).collect::<BTreeSet<usize>>());
    }

    #[test]
    fn the_other_eight_languages_come_back_untouched() {
        let python = b"def band(n):\n    return 'neg' if n < 0 else 'pos'\n";
        assert_eq!(blanked(python, ".py"), (python.to_vec(), BTreeSet::new()));
        assert!(blanked(b"func Band() int { return 1 }\n", ".go").1.is_empty());
    }
}
