//! L1.19 from a finished run: the share of decisions the tests reached, or why not.
//!
//! The VERDICT and the report readers. Given what a coverage tool wrote, what does it say.
//! What to RUN, and what to refuse before running anything, is `runtime::coverage_runners`.
//!
//! The seam is real rather than a line count. Nothing here touches a filesystem or starts
//! a process: every function takes text and answers with numbers or with nothing. The two
//! were one file of 1,398 lines, and the god-file rule this instrument publishes failed
//! its own commit, which is the rule working on the tool that states it.

use crate::runtime::determinism::{not_measured, Reading};
use crate::runtime::{coverage_band, timeout_note, TIMED_OUT};

/// What a coverage tool reported, once the caller has made the two numbers mean the same
/// thing in every language.
///
/// ABSENCE AND ZERO ARE SEPARATE CASES and have to stay separate. No totals at all means
/// the tool wrote no report, which is a build that does not include it; a total of zero
/// means it ran and found nothing with a branch in it. They send a reader to different
/// repairs.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Totals {
    pub covered: i64,
    pub total: i64,
}

/// The sentences one language owes a reader, because only the caller knows which tool it
/// ran and what to do about it.
///
/// Nothing here is defaulted: a runner that forgets to name its tool is refused rather than
/// handed a generic sentence nobody can act on.
pub struct CoverageWords {
    /// Why there is no report, and what would produce one.
    ///
    /// `{toolchain}` is replaced with the toolchain below, where a language names it here.
    /// Ruby does: the reference says which ruby produced no resultset, because a gem that is
    /// missing from one ruby is present in another and the version is the first thing a
    /// reader checks.
    pub no_report: &'static str,
    /// Why a report exists and carries nothing to cover.
    pub nothing_to_cover: &'static str,
    /// What the numbers are counts OF, named in the details line.
    pub how: &'static str,
    /// The toolchain that took the reading, so a number always says what measured it.
    pub toolchain: String,
    /// What this language's figure is a share of, where that is not branches.
    ///
    /// The substitution a verdict cannot show in its own value: L1.19 carries BRANCH
    /// coverage, and the Go toolchain instruments statements, so statement coverage goes
    /// into the same field. The details line discloses it. The value and the band cannot.
    pub substitution: &'static str,
}

/// L1.19 from a finished run and what the coverage report carried.
///
/// A FAILING SUITE STILL REPORTS ITS COVERAGE, and says the suite failed. The number is
/// true either way, and coverage from a red suite is not the same evidence as coverage from
/// a green one.
///
/// `timeout_seconds` is required for the same reason the words are: the refusal below names
/// the number it allowed, and a runner that did not say what it allowed cannot be quoted.
pub fn verdict(totals: Option<Totals>, status: i32, words: &CoverageWords,
               timeout_seconds: f64) -> Reading {
    if status == TIMED_OUT {
        return not_measured(format!(
            "test suite timed out before coverage could be measured{}",
            timeout_note(timeout_seconds)));
    }
    let Some(totals) = totals else {
        return not_measured(words.no_report.replace("{toolchain}", &words.toolchain));
    };
    if totals.total == 0 {
        return not_measured(words.nothing_to_cover);
    }
    let share = totals.covered as f64 / totals.total as f64 * 100.0;
    let suite = if status == 0 {
        "suite passed".to_string()
    } else {
        format!("suite exit {status}")
    };
    Reading {
        value: format!("{:.1}", (share * 10.0).round() / 10.0),
        band: coverage_band(share).to_string(),
        details: format!(
            "{}/{} decision branches exercised by tests ({}; {suite}; ran under {}){}",
            totals.covered, totals.total, words.how, words.toolchain, words.substitution),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn words() -> CoverageWords {
        CoverageWords {
            no_report: "coverage needs the plugin in the build (no report produced)",
            nothing_to_cover: "no enumerable decision branches found",
            how: "a tool's branch counters",
            toolchain: "a runtime".into(),
            substitution: "",
        }
    }

    #[test]
    fn a_measured_share_carries_its_counts_its_tool_and_its_runtime() {
        let reading = verdict(Some(Totals { covered: 2, total: 4 }), 0, &words(), 300.0);
        assert_eq!(reading.value, "50.0");
        assert_eq!(reading.band, "Slop");
        assert!(reading.details.contains("2/4 decision branches"));
        assert!(reading.details.contains("suite passed"));
        assert!(reading.details.contains("ran under a runtime"));
    }

    #[test]
    fn no_report_and_nothing_to_cover_are_different_refusals() {
        // They send a reader to different repairs: one is a build that does not include
        // the tool, the other is a tool that ran and found nothing with a branch in it.
        let absent = verdict(None, 0, &words(), 300.0);
        let empty = verdict(Some(Totals { covered: 0, total: 0 }), 0, &words(), 300.0);
        assert_eq!(absent.band, "n/a");
        assert_eq!(empty.band, "n/a");
        assert_ne!(absent.details, empty.details);
        assert!(absent.details.contains("no report produced"));
        assert!(empty.details.contains("no enumerable"));
    }

    #[test]
    fn a_timed_out_run_is_refused_and_names_the_seconds_it_was_allowed() {
        let reading = verdict(Some(Totals { covered: 2, total: 4 }), TIMED_OUT,
                              &words(), 300.0);
        assert_eq!(reading.band, "n/a");
        assert!(reading.details.contains("allowed 300s"));
    }

    #[test]
    fn a_failing_suite_still_reports_its_coverage_and_says_the_suite_failed() {
        // The number is true either way, and coverage from a red suite is not the same
        // evidence as coverage from a green one.
        let reading = verdict(Some(Totals { covered: 3, total: 4 }), 1, &words(), 300.0);
        assert_eq!(reading.value, "75.0");
        assert!(reading.details.contains("suite exit 1"));
    }

    #[test]
    fn nought_covered_of_a_real_total_is_a_reading_and_not_a_refusal() {
        // A suite that reaches none of four branches measured nought per cent. That is a
        // fact about the code; the refusals above are facts about the measurement.
        let reading = verdict(Some(Totals { covered: 0, total: 4 }), 0, &words(), 300.0);
        assert_eq!(reading.value, "0.0");
        assert_eq!(reading.band, "Slop");
    }

    #[test]
    fn a_language_measuring_something_else_discloses_it_in_the_line() {
        // The substitution the value cannot show. Go instruments statements, and statement
        // coverage goes into the field every other language fills with branches.
        let mut go = words();
        go.substitution = "; Go instruments statements rather than branches, so this field \
                           carries statement coverage where other languages carry branch \
                           coverage";
        let reading = verdict(Some(Totals { covered: 9, total: 10 }), 0, &go, 300.0);
        assert!(reading.details.contains("statement coverage"));
    }

    #[test]
    fn the_band_edges_are_the_published_ones() {
        let at_ninety = verdict(Some(Totals { covered: 90, total: 100 }), 0, &words(), 300.0);
        let above = verdict(Some(Totals { covered: 901, total: 1000 }), 0, &words(), 300.0);
        let at_sixty = verdict(Some(Totals { covered: 60, total: 100 }), 0, &words(), 300.0);
        assert_eq!(at_ninety.band, "Not Healthy", "strictly above 90 is Healthy");
        assert_eq!(above.band, "Healthy");
        assert_eq!(at_sixty.band, "Not Healthy");
    }
}

// --------------------------------------------------------------------------
// Go: `go test -coverprofile`, totalled by `go tool cover -func`.
// --------------------------------------------------------------------------


/// The line `go tool cover -func` ends with, carrying the whole module's total.
pub fn go_total(func_output: &str) -> Option<f64> {
    for line in func_output.lines() {
        let line = line.trim();
        if !line.starts_with("total:") {
            continue;
        }
        // `total:\t(statements)\t83.3%`
        let percent = line.rsplit_once('\t').map(|(_, tail)| tail).unwrap_or(line);
        return percent.trim().trim_end_matches('%').parse().ok();
    }
    None
}

/// One element found by the scan below: its name, its depth, and its attributes as text.
pub struct Element<'a> {
    pub name: &'a str,
    pub depth: usize,
    pub attrs: &'a str,
}

/// Every element in an XML document, with the depth it sits at.
///
/// A scanner rather than a parser, and rather than a dependency. It reads tag names,
/// attribute text and nesting depth, which is the whole of what the two report schemas
/// below need, and this binary is one file an auditor carries: a full XML parser would be
/// its first dependency that is not a grammar.
///
/// DEPTH IS THE POINT. JaCoCo writes a `counter` element at four levels, report, package,
/// class and method, and the report-level ones are the grand total. A reader that matched
/// every counter in the file would add the same branches four times over.
pub fn xml_elements(xml: &str) -> Vec<Element<'_>> {
    let mut found = Vec::new();
    let mut depth = 0usize;
    let bytes = xml.as_bytes();
    let mut at = 0usize;
    while at < bytes.len() {
        let Some(open) = xml[at..].find('<').map(|i| at + i) else { break };
        let Some(close) = xml[open..].find('>').map(|i| open + i) else { break };
        let inner = &xml[open + 1..close];
        at = close + 1;
        // Declarations, comments and doctypes carry no structure this reader wants.
        if inner.starts_with('?') || inner.starts_with('!') {
            continue;
        }
        if let Some(name) = inner.strip_prefix('/') {
            let _ = name;
            depth = depth.saturating_sub(1);
            continue;
        }
        let self_closing = inner.ends_with('/');
        let body = inner.trim_end_matches('/');
        let (name, attrs) = match body.find(char::is_whitespace) {
            Some(cut) => (&body[..cut], &body[cut..]),
            None => (body, ""),
        };
        depth += 1;
        found.push(Element { name, depth, attrs });
        if self_closing {
            depth -= 1;
        }
    }
    found
}

/// One attribute's value, read out of an element's attribute text.
pub fn xml_attr<'a>(attrs: &'a str, name: &str) -> Option<&'a str> {
    let key = format!("{name}=\"");
    let start = attrs.find(&key)? + key.len();
    let rest = &attrs[start..];
    let end = rest.find('"')?;
    Some(&rest[..end])
}

/// (covered, total) branches from a JaCoCo report, or nothing when it carries no branch
/// counter.
///
/// JaCoCo reports covered and MISSED, so the total is their sum. Only the REPORT-LEVEL
/// counter is read, which is the grand total across every package: the same element appears
/// on each package, class and method, and adding them all would count every branch four
/// times.
///
/// Nothing, never a pair of zeroes, for a report with no branch counter. A project with no
/// branches to cover and a schema this reader does not know are different facts, and
/// reading the second as zero would publish Slop for a repository whose coverage was never
/// measured.
pub fn jacoco_totals(xml: &str) -> Option<Totals> {
    for element in xml_elements(xml) {
        if element.name != "counter" || element.depth != 2 {
            continue;
        }
        if xml_attr(element.attrs, "type") != Some("BRANCH") {
            continue;
        }
        let covered: i64 = xml_attr(element.attrs, "covered")?.parse().ok()?;
        let missed: i64 = xml_attr(element.attrs, "missed")?.parse().ok()?;
        return Some(Totals { covered, total: covered + missed });
    }
    None
}

/// (covered, total) branches from a Cobertura report, or nothing when it carries no counts.
///
/// Covered first, then VALID, because the verdict takes covered-and-total and the report
/// writes the pair the other way round. One transposition is a coverage of 105 per cent.
///
/// Nothing, never a pair of zeroes, for the reason the JaCoCo reader gives.
pub fn cobertura_totals(xml: &str) -> Option<Totals> {
    for element in xml_elements(xml) {
        if element.name != "coverage" {
            continue;
        }
        let covered: i64 = xml_attr(element.attrs, "branches-covered")?.parse().ok()?;
        let valid: i64 = xml_attr(element.attrs, "branches-valid")?.parse().ok()?;
        return Some(Totals { covered, total: valid });
    }
    None
}

#[cfg(test)]
mod report_tests {
    use super::*;

    const JACOCO: &str = r#"<?xml version="1.0"?>
<report name="fixture">
  <package name="band">
    <class name="band/Band">
      <counter type="BRANCH" missed="1" covered="1"/>
    </class>
    <counter type="BRANCH" missed="1" covered="1"/>
  </package>
  <counter type="INSTRUCTION" missed="3" covered="9"/>
  <counter type="BRANCH" missed="2" covered="2"/>
</report>"#;

    #[test]
    fn only_the_report_level_counter_is_read() {
        // The same element appears on the report, each package, each class and each
        // method. Adding them all would count every branch four times over.
        assert_eq!(jacoco_totals(JACOCO), Some(Totals { covered: 2, total: 4 }));
    }

    #[test]
    fn the_instruction_counter_is_not_the_branch_counter() {
        // Reading the first counter rather than the branch one would report nine of twelve
        // where two of four is the answer.
        let totals = jacoco_totals(JACOCO).expect("a branch counter");
        assert_ne!(totals.covered, 9);
    }

    #[test]
    fn a_report_with_no_branch_counter_yields_nothing_rather_than_zero() {
        // A project with no branches and a schema this reader does not know are different
        // facts, and reading the second as zero publishes Slop for a repository whose
        // coverage was never measured.
        let xml = r#"<report name="x"><counter type="INSTRUCTION" missed="1" covered="9"/></report>"#;
        assert_eq!(jacoco_totals(xml), None);
    }

    #[test]
    fn cobertura_counts_are_read_covered_first_then_valid() {
        // The report writes the pair the other way round from the verdict. One
        // transposition is a coverage of 105 per cent.
        let xml = r#"<?xml version="1.0"?>
<coverage line-rate="0.8" branch-rate="0.5" branches-covered="2" branches-valid="4">
  <packages/>
</coverage>"#;
        assert_eq!(cobertura_totals(xml), Some(Totals { covered: 2, total: 4 }));
    }

    #[test]
    fn a_cobertura_report_with_no_branch_attributes_yields_nothing() {
        let xml = r#"<coverage line-rate="0.8"><packages/></coverage>"#;
        assert_eq!(cobertura_totals(xml), None);
    }

    #[test]
    fn the_scan_tracks_depth_through_self_closing_and_paired_tags() {
        let found = xml_elements(r#"<a><b/><c><d/></c></a>"#);
        let depths: Vec<(&str, usize)> = found.iter().map(|e| (e.name, e.depth)).collect();
        assert_eq!(depths, vec![("a", 1), ("b", 2), ("c", 2), ("d", 3)]);
    }

    #[test]
    fn a_declaration_or_comment_is_not_an_element() {
        let found = xml_elements(r#"<?xml version="1.0"?><!-- note --><a/>"#);
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].name, "a");
    }
}

// --------------------------------------------------------------------------
// The runners that produce a report and read it.
// --------------------------------------------------------------------------

/// A JSON string starting at `at`, and the index just past it.
fn read_json_string(json: &str, at: usize) -> Option<(String, usize)> {
    let bytes = json.as_bytes();
    let mut out = String::new();
    let mut index = at + 1;
    while index < bytes.len() {
        match bytes[index] {
            b'\\' => {
                index += 2;
                continue;
            }
            b'"' => return Some((out, index + 1)),
            byte => out.push(byte as char),
        }
        index += 1;
    }
    None
}

/// The body of a top-level object in a JSON document, by its key.
///
/// DEPTH IS THE POINT, the same rule the XML scan follows. A coverage summary holds a
/// named section beside one entry per FILE, and a file path is itself a key: it can contain
/// a brace, or the word the section is named with. Strings are skipped rather than scanned
/// so neither can be mistaken for structure.
fn json_section<'a>(json: &'a str, key: &str) -> Option<&'a str> {
    let bytes = json.as_bytes();
    let mut depth = 0usize;
    let mut at = 0usize;
    let mut want_value = false;
    while at < bytes.len() {
        match bytes[at] {
            b'"' => {
                let (text, next) = read_json_string(json, at)?;
                // A key at depth one names a section; deeper is somebody's contents.
                want_value = depth == 1 && text == key;
                at = next;
                continue;
            }
            b'{' | b'[' if want_value => {
                let close = matching_close(json, at)?;
                return Some(&json[at + 1..close]);
            }
            b'{' | b'[' => depth += 1,
            b'}' | b']' => depth -= 1,
            _ => {}
        }
        at += 1;
    }
    None
}

/// The index of the brace or bracket closing the one at `open`.
fn matching_close(json: &str, open: usize) -> Option<usize> {
    let bytes = json.as_bytes();
    let mut depth = 0usize;
    let mut at = open;
    while at < bytes.len() {
        match bytes[at] {
            b'"' => {
                let (_, next) = read_json_string(json, at)?;
                at = next;
                continue;
            }
            b'{' | b'[' => depth += 1,
            b'}' | b']' => {
                depth -= 1;
                if depth == 0 {
                    return Some(at);
                }
            }
            _ => {}
        }
        at += 1;
    }
    None
}

/// A numeric field read out of a JSON object body.
fn json_number(body: &str, key: &str) -> Option<i64> {
    let needle = format!("\"{key}\":");
    let start = body.find(&needle)? + needle.len();
    let tail = body[start..].trim_start();
    let end = tail.find(|c: char| c != '-' && !c.is_ascii_digit()).unwrap_or(tail.len());
    tail[..end].parse().ok()
}

/// A string field read out of a JSON object body.
pub fn json_string(body: &str, key: &str) -> Option<String> {
    let needle = format!("\"{key}\":");
    let start = body.find(&needle)? + needle.len();
    let tail = body[start..].trim_start();
    if !tail.starts_with('"') {
        return None;
    }
    read_json_string(tail, 0).map(|(text, _)| text)
}

/// Whether a JSON object body carries this key at all, which is how a manifest names a
/// dependency: the version it maps to says nothing this reader needs.
pub fn json_has_key(body: &str, key: &str) -> bool {
    body.contains(&format!("\"{key}\":"))
}

/// The body of a top-level object, exposed so a manifest can be read the same way a report
/// is. One scan, two kinds of document.
pub fn json_object<'a>(json: &'a str, key: &str) -> Option<&'a str> {
    json_section(json, key)
}

/// (covered, total) branches from a c8 json-summary, or nothing when it carries none.
///
/// The summary holds a `total` section beside one entry per file, and every one of those
/// entries carries a `branches` object of its own. So the reader cannot search for the
/// first `branches` it sees: it reads the top-level `total` section and takes the branches
/// from inside that.
pub fn c8_totals(json: &str) -> Option<Totals> {
    let total = json_section(json, "total")?;
    // Wrapped back into an object so the same depth rule applies one level in: inside the
    // total section, `branches` is again a key at depth one.
    let wrapped = format!("{{{total}}}");
    let branches = json_section(&wrapped, "branches")?;
    Some(Totals {
        covered: json_number(branches, "covered")?,
        total: json_number(branches, "total")?,
    })
}

/// (covered, total) branches from a coverage.py JSON report, or nothing when it carries
/// none.
///
/// Its totals sit at the top of a `totals` section under their own names rather than inside
/// a branches object, which is why this is a second reader and not a second call: the shape
/// is shared and the words are not.
pub fn coveragepy_totals(json: &str) -> Option<Totals> {
    let totals = json_section(json, "totals")?;
    Some(Totals {
        covered: json_number(totals, "covered_branches")?,
        total: json_number(totals, "num_branches")?,
    })
}

#[cfg(test)]
mod c8_tests {
    use super::*;

    /// What c8 10.1 actually wrote for a fixture with four branches and two covered.
    const REAL: &str = r#"{"total": {"lines":{"total":5,"covered":5,"skipped":0,"pct":100},"statements":{"total":5,"covered":5,"skipped":0,"pct":100},"functions":{"total":1,"covered":1,"skipped":0,"pct":100},"branches":{"total":4,"covered":2,"skipped":0,"pct":50},"branchesTrue":{"total":0,"covered":0,"skipped":0,"pct":"Unknown"}}
,"/tmp/fixture/band.js": {"lines":{"total":5,"covered":5,"skipped":0,"pct":100},"functions":{"total":1,"covered":1,"skipped":0,"pct":100},"statements":{"total":5,"covered":5,"skipped":0,"pct":100},"branches":{"total":4,"covered":2,"skipped":0,"pct":50}}
}"#;

    #[test]
    fn the_branches_read_are_the_ones_in_the_total_section() {
        // Taken from a summary c8 wrote, not one this file made up. Every per-file entry
        // carries a branches object of its own, so a reader that took the first one it
        // saw would be right by luck and wrong on a document ordered differently.
        assert_eq!(c8_totals(REAL), Some(Totals { covered: 2, total: 4 }));
    }

    #[test]
    fn a_summary_with_no_total_section_yields_nothing_rather_than_zero() {
        let json = r#"{"/tmp/f.js": {"branches":{"total":4,"covered":2}}}"#;
        assert_eq!(c8_totals(json), None);
    }

    #[test]
    fn a_total_section_with_no_branches_yields_nothing() {
        let json = r#"{"total": {"lines":{"total":5,"covered":5}}}"#;
        assert_eq!(c8_totals(json), None);
    }

    #[test]
    fn a_real_coverage_py_report_reads_its_totals_section() {
        // The file checked in beside this crate is what coverage.py 7 wrote for a fixture
        // with four branches and two covered, trimmed to one file entry. A parser proved
        // only against a string the test holds is a parser proved against the test.
        let json = include_str!("../../tests/reports/coveragepy-summary.json");
        assert_eq!(coveragepy_totals(json), Some(Totals { covered: 2, total: 4 }));
    }

    #[test]
    fn a_coverage_py_report_with_no_totals_yields_nothing_rather_than_zero() {
        assert_eq!(coveragepy_totals(r#"{"files": {}}"#), None);
    }

    #[test]
    fn a_file_path_containing_the_word_total_is_not_read_as_the_section() {
        // A path is a key in this document, and depth is what tells a key naming a section
        // from a key naming a file.
        let json = r#"{"/tmp/total/band.js": {"branches":{"total":9,"covered":9}},
                       "total": {"branches":{"total":4,"covered":2}}}"#;
        assert_eq!(c8_totals(json), Some(Totals { covered: 2, total: 4 }));
    }
}

/// (covered, total) branches from a SimpleCov resultset, or nothing when it carries none.
///
/// SimpleCov nests them two deep: every file's `branches` object maps a branch to its
/// LEAVES, and each leaf holds a hit count. A leaf is covered when its count is above
/// zero, so the totals are a count of leaves rather than of branches.
///
/// Every `branches` object in the document is read, across every command and every file,
/// because a resultset holds one entry per test command and a project can have several.
///
/// Files stored in the old line-only format contribute nothing: their entry is a list
/// rather than an object and carries no branches at all. That is a file this reader cannot
/// count, not a file with no branches, and it drops out of both halves rather than
/// inflating the denominator.
pub fn simplecov_totals(json: &str) -> Option<Totals> {
    let mut covered = 0i64;
    let mut total = 0i64;
    let mut seen_any = false;
    let mut at = 0usize;
    while let Some(found) = json[at..].find("\"branches\":").map(|i| at + i) {
        at = found + "\"branches\":".len();
        let Some(open) = json[at..].find('{').map(|i| at + i) else { break };
        let Some(close) = matching_close(json, open) else { break };
        let body = &json[open + 1..close];
        seen_any = true;
        // Each entry of a branches object is one branch mapping its leaves to hit counts.
        let mut inner = 0usize;
        while let Some(leaf_open) = body[inner..].find('{').map(|i| inner + i) {
            let Some(leaf_close) = matching_close(body, leaf_open) else { break };
            for hits in json_numbers(&body[leaf_open + 1..leaf_close]) {
                total += 1;
                if hits > 0 {
                    covered += 1;
                }
            }
            inner = leaf_close + 1;
        }
        at = close + 1;
    }
    if !seen_any {
        return None;
    }
    Some(Totals { covered, total })
}

/// Every numeric value in a flat JSON object body, in order.
fn json_numbers(body: &str) -> Vec<i64> {
    let mut found = Vec::new();
    let mut at = 0usize;
    let bytes = body.as_bytes();
    while at < bytes.len() {
        match bytes[at] {
            b'"' => {
                // A key, skipped whole: it can hold digits, and SimpleCov's do.
                match read_json_string(body, at) {
                    Some((_, next)) => at = next,
                    None => break,
                }
                continue;
            }
            b':' => {
                let tail = body[at + 1..].trim_start();
                let end = tail.find(|c: char| c != '-' && !c.is_ascii_digit())
                    .unwrap_or(tail.len());
                if end > 0 {
                    if let Ok(value) = tail[..end].parse::<i64>() {
                        found.push(value);
                    }
                }
            }
            _ => {}
        }
        at += 1;
    }
    found
}

#[cfg(test)]
mod simplecov_tests {
    use super::*;

    #[test]
    fn a_real_resultset_counts_its_branch_leaves() {
        // What SimpleCov wrote for a fixture with two conditionals: four leaves, two hit.
        // The reference reads the same pair from this file.
        let json = include_str!("../../tests/reports/simplecov-resultset.json");
        assert_eq!(simplecov_totals(json), Some(Totals { covered: 2, total: 4 }));
    }

    #[test]
    fn a_leaf_with_no_hits_is_counted_in_the_total_and_not_in_the_covered() {
        let json = r#"{"Unit Tests": {"coverage": {"/a.rb": {"lines": [1],
            "branches": {"[:if, 0]": {"[:then, 1]": 0, "[:else, 2]": 3}}}}}}"#;
        assert_eq!(simplecov_totals(json), Some(Totals { covered: 1, total: 2 }));
    }

    #[test]
    fn every_command_in_a_resultset_is_counted() {
        // A resultset holds one entry per test command, and a project can have several.
        let json = r#"{"A": {"coverage": {"/a.rb": {"branches": {"x": {"t": 1, "e": 0}}}}},
                       "B": {"coverage": {"/b.rb": {"branches": {"y": {"t": 1, "e": 1}}}}}}"#;
        assert_eq!(simplecov_totals(json), Some(Totals { covered: 3, total: 4 }));
    }

    #[test]
    fn a_resultset_with_no_branch_data_yields_nothing_rather_than_zero() {
        // SimpleCov writes line-only data unless the project enables branch coverage. That
        // is a measurement nobody took, not a project with no branches, and reading it as
        // zero would publish Slop for a repository whose branches were never counted.
        let json = r#"{"Unit Tests": {"coverage": {"/a.rb": [1, 0, null]}}}"#;
        assert_eq!(simplecov_totals(json), None);
    }

    #[test]
    fn a_key_holding_digits_is_not_read_as_a_hit_count() {
        // SimpleCov's branch keys are full of numbers: `[:if, 0, 2, 2, 2, 23]`. A reader
        // that scanned for digits would count the key's own line numbers as coverage.
        let json = r#"{"A": {"coverage": {"/a.rb": {"branches":
            {"[:if, 0, 2, 2, 2, 23]": {"[:then, 1, 2, 2, 2, 14]": 0,
                                       "[:else, 2, 2, 2, 2, 23]": 7}}}}}}"#;
        assert_eq!(simplecov_totals(json), Some(Totals { covered: 1, total: 2 }));
    }
}

