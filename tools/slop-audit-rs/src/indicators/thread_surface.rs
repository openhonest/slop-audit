//! The thread-safety SURFACE meter. Ported from l1_analyzer.thread_surface.
//!
//! What it is, and is not. This meter does NOT detect data races. Race detection is
//! undecidable statically without whole-program alias and happens-before reasoning; it is a
//! ThreadSanitizer job, and claiming "thread-safe" from a static pass would be the exact
//! silent-failure lie the audit exists to surface.
//!
//! What it measures instead is the concurrency AUDIT SURFACE: every site where a language's
//! compiler-enforced thread-safety guarantee is overridden by hand or is simply absent. Each
//! finding is a fact about the syntax, "here is surface a human or a sanitiser must verify",
//! never a verdict that a race exists.
//!
//! The motivating case is a free-threaded write-ahead-log bug. The meter would not have
//! caught the race, but it flags the `unsafe impl Sync` on the struct whose hand-asserted
//! thread-safety turned out to be wrong: it puts the struct on the audit list, and the human
//! finds the missing guard inside it.
//!
//! UNREAD IS NOT CLEAN, and collapsing them is a false pass. Every number here is counted
//! over the sites the scanner RECOGNISED, so an empty recognition set produces the same
//! triple of zeros a genuinely clean repository produces. The denominator that tells them
//! apart is the count of files that PARSED, not the count opened: hand tree-sitter source it
//! cannot read and it answers with an error-bearing tree whose node queries all come back
//! empty, which no file count can see.
//!
//! Two things deliberately do NOT trigger the refusal. A finding recovered from an
//! error-bearing tree keeps the verdict, because the scanner demonstrably read something.
//! And one readable file among many unreadable ones is enough to grade: a thin reading is
//! not the same fact as no reading, and the two counts are published beside each other so a
//! reader can see how thin it was.

use crate::lang_spec::LangSpec;
use crate::nodes::{descendants, field, text};
use crate::{lang, Indicator};
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;
use tree_sitter::Node;

/// A hand-override of the thread-safety guarantee.
pub const EXPOSED: &str = "exposed";
/// A lower-severity footgun, such as a relaxed atomic ordering that gates control flow.
pub const REVIEW: &str = "review";
/// A real hazard SHAPE, measured low-precision: the non-atomic read-modify-write rule fires
/// on correct lock-free code by design. It never flips a headline verdict on its own and
/// reads as "confirm with the prove stage", not as an accusation.
pub const CANDIDATE: &str = "candidate";
/// A scanner exists for the language and found no surface.
pub const CLEAN: &str = "clean";
/// A scanner exists and had nothing readable to run over.
///
/// Its own word rather than n/a, because "we have no scanner for your language" sends the
/// reader to us and "we could not read your source" sends them to their scope rules or their
/// syntax, and one label for both sent them to neither.
pub const UNREAD: &str = "unread";
/// No scanner for the language at all.
pub const NO_SCANNER: &str = "n/a";

/// One concurrency-surface site.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Finding {
    pub kind: String,
    pub symbol: String,
    pub severity: &'static str,
    pub file: String,
    pub line: usize,
}

/// One finding, with its symbol's whitespace collapsed: a multi-line field access must read
/// as one symbol rather than carry the source's line breaks into the report.
pub(crate) fn mk(kind: &str, symbol: &str, severity: &'static str, rel: &str, node: Node) -> Finding {
    Finding {
        kind: kind.to_string(),
        symbol: symbol.split_whitespace().collect::<Vec<_>>().join(" "),
        severity,
        file: rel.to_string(),
        line: node.start_position().row + 1,
    }
}

/// (method, receiver) for a `receiver.method(...)` call, else nothing.
///
/// One function for every language. The reference wrote it twice, once for Rust and once for
/// JavaScript, and the two differed in four words: which node is a call, which is a member
/// access, what the grammar calls the member, and what it calls the object. All four have
/// been in the per-language vocabulary since before that module existed.
pub fn method_receiver(call: Node, sp: &LangSpec, src: &[u8]) -> Option<(String, String)> {
    if !sp.call_types.contains(&call.kind()) {
        return None;
    }
    let named = field(Some(call), sp.call_fn)?;
    if !sp.member_types.contains(&named.kind()) {
        return None;
    }
    let member = field(Some(named), sp.mem_attr)?;
    let object = field(Some(named), sp.mem_object)?;
    Some((text(Some(member), src), text(Some(object), src)))
}

/// Receivers hanging off the object itself, for any call whose method is in `methods`.
///
/// Only state on the object counts, because that is what two threads can share. A method
/// call on a local is one thread's own.
pub fn receivers_by_method(scope: Option<Node>, methods: &[&str], sp: &LangSpec,
                           src: &[u8]) -> BTreeSet<String> {
    let mut out = BTreeSet::new();
    let Some(scope) = scope else { return out };
    for node in descendants(scope) {
        if let Some((method, receiver)) = method_receiver(node, sp, src) {
            if methods.contains(&method.as_str())
                && sp.this_idents.iter().any(|w| receiver.starts_with(&format!("{w}."))) {
                out.insert(receiver);
            }
        }
    }
    out
}

/// The scanner for one language, or nothing where this meter has none.
///
/// Refused rather than emptied: a language with no scanner must reach the n/a row and never
/// a clean one, because an empty finding list reads exactly like clean code.
pub(crate) fn scanner_for(lang: &str) -> Option<fn(Node, &str, &LangSpec, &[u8]) -> Vec<Finding>> {
    use crate::indicators::thread_scanners as scanners;
    match lang {
        "rust" => Some(scanners::scan_rust),
        "python" => Some(scanners::scan_python),
        "typescript" | "javascript" => Some(scanners::scan_jsts),
        "go" => Some(scanners::scan_go),
        "java" => Some(scanners::scan_java),
        "ruby" => Some(scanners::scan_ruby),
        _ => None,
    }
}

/// The severity order a reader is shown: worst first, then by where it is.
fn severity_rank(severity: &str) -> u8 {
    match severity {
        EXPOSED => 0,
        REVIEW => 1,
        _ => 2,
    }
}

/// The whole reading of a repository's concurrency surface.
pub struct Surface {
    pub verdict: &'static str,
    pub value: String,
    pub counts: BTreeMap<&'static str, usize>,
    pub findings: Vec<Finding>,
    pub files_read: usize,
    pub files_parsed: usize,
    pub details: String,
}

fn empty_counts() -> BTreeMap<&'static str, usize> {
    [(EXPOSED, 0), (REVIEW, 0), (CANDIDATE, 0)].into_iter().collect()
}

fn no_scanner(lang: &str) -> Surface {
    Surface {
        verdict: NO_SCANNER,
        value: "n/a".into(),
        counts: empty_counts(),
        findings: Vec::new(),
        files_read: 0,
        files_parsed: 0,
        details: format!("thread-safety surface meter has no scanner for {lang} yet"),
    }
}

/// The refusal. The value carries it too, because that is the field a reader and a report
/// template look at, and the first version of this disclosure lived in the prose while the
/// verdict still said clean. Prose is not a disclosure when the headline says otherwise.
fn unread(lang: &str, read: usize) -> Surface {
    let why = if read == 0 {
        "no file was in scope".to_string()
    } else {
        format!("the parser could not read any of the {read} file(s) in scope")
    };
    Surface {
        verdict: UNREAD,
        value: "n/a".into(),
        counts: empty_counts(),
        findings: Vec::new(),
        files_read: read,
        files_parsed: 0,
        details: format!(
            "thread-safety surface: not measured for {lang}, because {why}. This is a limit \
             of the reading, not a finding about the code: a clean verdict here would be \
             counted over no source at all. Check what the scope rules set aside (listed \
             beside this) and whether the source parses."),
    }
}

/// The concurrency-surface distribution for a repository.
pub fn scan(repo: &Path, language: &str) -> Surface {
    let Some(scanner) = scanner_for(language) else { return no_scanner(language) };
    let Some(sp) = crate::lang_spec::spec_for(language) else { return no_scanner(language) };
    let parsed_files = crate::state::census::parsed_files(repo, language);
    let read = parsed_files.len();

    let mut findings: Vec<Finding> = Vec::new();
    let mut parsed = 0usize;
    for (rel, tree, src) in &parsed_files {
        // Counted, then scanned regardless. The error flag is a denominator, never a filter:
        // tree-sitter recovers usefully from most errors, and a hazard it did recover is a
        // hazard whatever else in the file defeated it.
        if !tree.root_node().has_error() {
            parsed += 1;
        }
        findings.extend(scanner(tree.root_node(), rel, sp, src));
    }

    // A finding is positive evidence the scanner read something, so it outranks the parse
    // count: a result stands whatever else went unread.
    if parsed == 0 && findings.is_empty() {
        return unread(language, read);
    }

    let mut counts = empty_counts();
    for f in &findings {
        *counts.entry(f.severity).or_insert(0) += 1;
    }
    let verdict = if counts[EXPOSED] > 0 {
        EXPOSED
    } else if counts[REVIEW] > 0 {
        REVIEW
    } else if counts[CANDIDATE] > 0 {
        CANDIDATE
    } else {
        CLEAN
    };
    findings.sort_by(|a, b| {
        severity_rank(a.severity).cmp(&severity_rank(b.severity))
            .then(a.file.cmp(&b.file))
            .then(a.line.cmp(&b.line))
    });
    let details = format!(
        "thread-safety surface: {} hand-overrides of the thread-safety guarantee, {} \
         lower-severity footguns, {} low-precision candidate shape(s) across {} sites; read \
         over {parsed} of {read} file(s) in scope that the parser could read",
        counts[EXPOSED], counts[REVIEW], counts[CANDIDATE], findings.len());
    Surface {
        verdict,
        value: format!("{} exposed / {} review / {} candidate",
                       counts[EXPOSED], counts[REVIEW], counts[CANDIDATE]),
        counts,
        findings,
        files_read: read,
        files_parsed: parsed,
        details,
    }
}

/// The panel row for this meter.
pub fn analyze(repo: &Path, language: &str) -> Indicator {
    // A language this binary has no grammar for cannot even be scanned for surface.
    if lang::cfg(language).is_none() {
        return Indicator {
            code: "thread_surface".into(), label: "thread-surface".into(),
            value: "n/a".into(), band: "n/a".into(),
            details: format!("no tree-sitter config for {language}"),
        };
    }
    let surface = scan(repo, language);
    Indicator {
        code: "thread_surface".into(),
        label: "thread-surface".into(),
        value: surface.value,
        band: "n/a".into(),
        details: surface.details,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_repository_with_nothing_readable_is_unread_and_never_clean() {
        // The false pass this meter exists to refuse: an empty recognition set produces the
        // same triple of zeros a genuinely clean repository produces.
        let root = std::env::temp_dir().join(format!("slop-surface-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).expect("make the fixture");
        let got = scan(&root, "rust");
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(got.verdict, UNREAD);
        assert_eq!(got.value, "n/a");
        assert!(got.details.contains("no file was in scope"), "{}", got.details);
    }

    #[test]
    fn a_language_with_no_scanner_says_so_rather_than_reading_clean() {
        let got = scan(std::path::Path::new("."), "c");
        assert_eq!(got.verdict, NO_SCANNER);
        assert!(got.details.contains("no scanner for c"), "{}", got.details);
    }
}
