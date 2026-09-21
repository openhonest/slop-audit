//! L1.19 from a finished run: the share of decisions the tests reached, or why not. Ported
//! from pytest_trace.coverage_verdict.
//!
//! ONE function for every language. The reference wrote it seven times, once per runner,
//! and reading those seven together is what showed them to be the same: each asks the same
//! four questions in the same order. Did the suite time out. Did the coverage tool write a
//! report at all. Did it find anything with a branch in it. What share was covered, and
//! what band is that.
//!
//! What differed was the words and one piece of arithmetic. JaCoCo reports covered and
//! MISSED, so the total is their sum; Cobertura reports covered and VALID, where valid is
//! already the total. So the caller does its own extraction and hands over a pair that
//! already means the same thing everywhere.

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
    let Some(totals) = totals else { return not_measured(words.no_report) };
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

use crate::runtime::runners::{first_line, ran_tests, runner_for, which};
use crate::runtime::run_untrusted;
use std::path::Path;

/// A JaCoCo-instrumented pom, used by the live test below.
#[cfg(test)]
const JACOCO_POM: &str = r#"<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>fixture</groupId>
  <artifactId>band</artifactId>
  <version>1.0</version>
  <properties>
    <maven.compiler.source>17</maven.compiler.source>
    <maven.compiler.target>17</maven.compiler.target>
  </properties>
  <dependencies>
    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter</artifactId>
      <version>5.10.2</version>
      <scope>test</scope>
    </dependency>
  </dependencies>
  <build><plugins>
    <plugin>
      <groupId>org.jacoco</groupId>
      <artifactId>jacoco-maven-plugin</artifactId>
      <version>0.8.12</version>
      <executions>
        <execution><goals><goal>prepare-agent</goal></goals></execution>
        <execution><id>report</id><phase>test</phase><goals><goal>report</goal></goals></execution>
      </executions>
    </plugin>
  </plugins></build>
</project>"#;

/// A scratch directory no other run will use.
///
/// Named per CALL, not per process. Naming it per process made two runs in one process
/// share a directory, and each one's clean-up deleted the other's profile: a suite that
/// measured 40 per cent reported "coverage produced no data". Two audits running side by
/// side on one machine would collide the same way, which is how an auditor would meet it.
fn scratch_dir(purpose: &str) -> std::path::PathBuf {
    use std::sync::atomic::{AtomicU64, Ordering as AtomicOrdering};
    static NEXT: AtomicU64 = AtomicU64::new(0);
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let serial = NEXT.fetch_add(1, AtomicOrdering::Relaxed);
    std::env::temp_dir().join(format!(
        "slop-{purpose}-{}-{nanos}-{serial}", std::process::id()))
}

/// The line `go tool cover -func` ends with, carrying the whole module's total.
fn go_total(func_output: &str) -> Option<f64> {
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

/// L1.19 for Go: statement coverage from `go test -coverprofile`.
///
/// EXECUTES THE AUDITED PROJECT'S CODE. The suite runs once into a profile in a scratch
/// directory, and the profile is totalled by a second command only when the first wrote
/// one and was not killed: totalling a profile that was never written, or one from a run
/// that was killed, buys nothing the verdict can use.
///
/// A PROFILE IS NOT A READING. `go test ./...` over a module whose packages carry no test
/// file exits non-zero having compiled nothing and STILL writes a profile, which totals at
/// nought per cent, and nought is the Slop end of this scale. So a directory the toolchain
/// never compiled scored the worst possible reading. The same question the determinism arm
/// asks, asked here.
pub fn go_coverage(repo: &Path, timeout_seconds: f64, toolchain: &str) -> Reading {
    let runner = runner_for("go").expect("go has a row");
    if which("go").is_none() {
        return not_measured(runner.tool_missing);
    }
    let scratch = scratch_dir("gocov");
    let _ = std::fs::create_dir_all(&scratch);
    let profile = scratch.join("cover.out");
    let _ = std::fs::remove_file(&profile);

    let run = run_untrusted(
        &["go".into(), "test".into(), "./...".into(), "-covermode=set".into(),
          format!("-coverprofile={}", profile.display())],
        repo, &[], timeout_seconds);
    let output = run.output();
    let written = std::fs::metadata(&profile).map(|m| m.len() > 0).unwrap_or(false);

    let words = CoverageWords {
        no_report: "coverage produced no data",
        nothing_to_cover: "coverage profile had no statement total",
        how: "`go test -coverprofile`",
        toolchain: toolchain.to_string(),
        substitution: "; Go instruments statements rather than branches, so this field \
                       carries statement coverage where other languages carry branch \
                       coverage",
    };

    if run.status == TIMED_OUT {
        let _ = std::fs::remove_dir_all(&scratch);
        return verdict(None, TIMED_OUT, &words, timeout_seconds);
    }
    if !written {
        let _ = std::fs::remove_dir_all(&scratch);
        return not_measured(format!("coverage produced no data (go test exit {}): {}",
                                    run.status, first_line(&output)));
    }
    if !ran_tests(runner, &output) {
        let _ = std::fs::remove_dir_all(&scratch);
        return not_measured(format!(
            "no Go test ran, so coverage was not measured (go test exit {}): {}",
            run.status, first_line(&output)));
    }

    let func = run_untrusted(
        &["go".into(), "tool".into(), "cover".into(),
          format!("-func={}", profile.display())],
        repo, &[], timeout_seconds.min(60.0));
    let total = go_total(&func.stdout);
    let _ = std::fs::remove_dir_all(&scratch);

    let Some(pct) = total else {
        return not_measured("coverage profile had no statement total");
    };
    // NOT through the shared verdict, and that is the point. Every other language hands
    // over real counts; the Go toolchain reports a PERCENTAGE and nothing else, so
    // reconstructing a pair from it would put counts in the details line that nothing
    // measured. My first draft did exactly that and published "833/1000 decision branches
    // exercised by tests" off a figure of 83.3 per cent.
    //
    // Two substitutions are disclosed here rather than hidden in a number: the figure is
    // statements where every other language carries branches, and it is a percentage where
    // every other language carries counts.
    let suite = if run.status == 0 {
        "suite passed".to_string()
    } else {
        format!("suite exit {}", run.status)
    };
    Reading {
        value: format!("{:.1}", pct),
        band: crate::runtime::coverage_band(pct).to_string(),
        details: format!(
            "{pct}% STATEMENT coverage from `go test -coverprofile` ({suite}; ran under \
             {toolchain}); Go instruments statements rather than branches, so this field \
             carries statement coverage where other languages carry branch coverage, and \
             the toolchain reports a percentage rather than the counts every other \
             language supplies"),
    }
}

#[cfg(test)]
mod go_tests {
    use super::*;

    #[test]
    fn the_total_line_is_read_off_the_tools_own_output() {
        let output = "fixture/band.go:3:\tBand\t83.3%\ntotal:\t(statements)\t83.3%\n";
        assert_eq!(go_total(output), Some(83.3));
    }

    #[test]
    fn output_with_no_total_line_yields_nothing_rather_than_a_zero() {
        assert_eq!(go_total("fixture/band.go:3:\tBand\t83.3%\n"), None);
        assert_eq!(go_total(""), None);
    }

    #[test]
    fn a_real_go_module_measures_its_own_statements() {
        if which("go").is_none() {
            eprintln!("skipped: go is not on PATH");
            return;
        }
        let root = std::env::temp_dir().join(format!("slop-gocov-live-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).expect("a directory");
        std::fs::write(root.join("go.mod"), "module fixture\n\ngo 1.21\n").unwrap();
        // Three arms, tests reaching two, so the figure is short by construction and a
        // reader can check it against the fixture.
        std::fs::write(root.join("band.go"),
            "package fixture\n\nfunc Band(n int) string {\n\tif n > 10 {\n\t\treturn \"high\"\n\t}\n\tif n > 5 {\n\t\treturn \"mid\"\n\t}\n\treturn \"low\"\n}\n").unwrap();
        std::fs::write(root.join("band_test.go"),
            "package fixture\n\nimport \"testing\"\n\nfunc TestHigh(t *testing.T) {\n\tif Band(20) != \"high\" {\n\t\tt.Fatal(\"high\")\n\t}\n}\n").unwrap();

        let reading = go_coverage(&root, 300.0, "go version");
        let _ = std::fs::remove_dir_all(&root);
        assert_ne!(reading.band, "n/a", "{}", reading.details);
        let pct: f64 = reading.value.parse().expect("a percentage");
        assert!(pct > 0.0 && pct < 100.0, "the fixture leaves an arm unreached: {pct}");
        assert!(reading.details.contains("STATEMENT coverage"), "{}", reading.details);
        assert!(reading.details.contains("percentage rather than the counts"),
                "the second substitution must be disclosed too: {}", reading.details);
    }

    #[test]
    fn a_module_that_will_not_build_is_refused_rather_than_scored_nought() {
        // `go test ./...` writes a profile even when nothing compiled, and that profile
        // totals at nought per cent, which is the Slop end of the scale. So a directory
        // the toolchain never compiled scored the worst possible reading.
        if which("go").is_none() {
            eprintln!("skipped: go is not on PATH");
            return;
        }
        let root = std::env::temp_dir().join(format!("slop-gocov-bad-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).expect("a directory");
        std::fs::write(root.join("go.mod"), "module fixture\n\ngo 1.21\n").unwrap();
        std::fs::write(root.join("band.go"),
                       "package fixture\n\nfunc Band() { undefined() }\n").unwrap();
        std::fs::write(root.join("band_test.go"),
            "package fixture\n\nimport \"testing\"\n\nfunc TestX(t *testing.T) { Band() }\n").unwrap();
        let reading = go_coverage(&root, 300.0, "go version");
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(reading.band, "n/a", "{}", reading.details);
    }

    #[test]
    fn a_module_with_no_tests_is_refused_rather_than_scored_nought() {
        if which("go").is_none() {
            eprintln!("skipped: go is not on PATH");
            return;
        }
        let root = std::env::temp_dir().join(format!("slop-gocov-none-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).expect("a directory");
        std::fs::write(root.join("go.mod"), "module fixture\n\ngo 1.21\n").unwrap();
        std::fs::write(root.join("band.go"),
            "package fixture\n\nfunc Band(n int) int { return n }\n").unwrap();
        let reading = go_coverage(&root, 300.0, "go version");
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(reading.band, "n/a", "{}", reading.details);
    }
}

// --------------------------------------------------------------------------
// Reading a report. Two schemas, two shapes of lie available to a careless reader.
// --------------------------------------------------------------------------

/// One element found by the scan below: its name, its depth, and its attributes as text.
struct Element<'a> {
    name: &'a str,
    depth: usize,
    attrs: &'a str,
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
fn elements(xml: &str) -> Vec<Element<'_>> {
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
fn attr<'a>(attrs: &'a str, name: &str) -> Option<&'a str> {
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
    for element in elements(xml) {
        if element.name != "counter" || element.depth != 2 {
            continue;
        }
        if attr(element.attrs, "type") != Some("BRANCH") {
            continue;
        }
        let covered: i64 = attr(element.attrs, "covered")?.parse().ok()?;
        let missed: i64 = attr(element.attrs, "missed")?.parse().ok()?;
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
    for element in elements(xml) {
        if element.name != "coverage" {
            continue;
        }
        let covered: i64 = attr(element.attrs, "branches-covered")?.parse().ok()?;
        let valid: i64 = attr(element.attrs, "branches-valid")?.parse().ok()?;
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
        let found = elements(r#"<a><b/><c><d/></c></a>"#);
        let depths: Vec<(&str, usize)> = found.iter().map(|e| (e.name, e.depth)).collect();
        assert_eq!(depths, vec![("a", 1), ("b", 2), ("c", 2), ("d", 3)]);
    }

    #[test]
    fn a_declaration_or_comment_is_not_an_element() {
        let found = elements(r#"<?xml version="1.0"?><!-- note --><a/>"#);
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].name, "a");
    }
}

// --------------------------------------------------------------------------
// The runners that produce a report and read it.
// --------------------------------------------------------------------------

/// Every file under `root` whose name matches, deepest-first order not guaranteed.
///
/// Its own walk rather than the repository walker: a results directory is scratch space
/// this run created, so none of the scope rules that decide what belongs to a repository
/// apply to it.
fn find_reports(root: &Path, filename: &str) -> Vec<std::path::PathBuf> {
    let mut found = Vec::new();
    let mut stack = vec![root.to_path_buf()];
    while let Some(dir) = stack.pop() {
        let Ok(entries) = std::fs::read_dir(&dir) else { continue };
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                stack.push(path);
            } else if path.file_name().and_then(|n| n.to_str()) == Some(filename) {
                found.push(path);
            }
        }
    }
    found.sort();
    found
}

/// L1.19 for C#: branch coverage from `dotnet test --collect:"XPlat Code Coverage"`.
///
/// EXECUTES THE AUDITED PROJECT'S CODE. The collector writes a Cobertura report into a
/// results directory this run owns, so nothing is left in the repository.
pub fn csharp_coverage(repo: &Path, timeout_seconds: f64, sdk: &str) -> Reading {
    if which("dotnet").is_none() {
        return not_measured("needs the dotnet SDK in PATH");
    }
    let results = scratch_dir("cscov");
    let _ = std::fs::create_dir_all(&results);
    let run = run_untrusted(
        &["dotnet".into(), "test".into(), "--collect:XPlat Code Coverage".into(),
          "--results-directory".into(), results.display().to_string()],
        repo, &[], timeout_seconds);

    let words = CoverageWords {
        no_report: "C# branch coverage needs the XPlat Code Coverage collector \
                    (no cobertura report was written)",
        nothing_to_cover: "no enumerable decision branches found \
                           (cobertura reported zero valid branches)",
        how: "Cobertura branch counters",
        toolchain: sdk.to_string(),
        substitution: "",
    };
    let reports = find_reports(&results, "coverage.cobertura.xml");
    let totals = reports.first()
        .and_then(|path| std::fs::read_to_string(path).ok())
        .and_then(|xml| cobertura_totals(&xml));
    // A report that exists and carries no branch attributes is a schema this reader does
    // not know, which is neither a missing collector nor a project with no branches.
    let unreadable = !reports.is_empty() && totals.is_none() && run.status != TIMED_OUT;
    let _ = std::fs::remove_dir_all(&results);
    if unreadable {
        return not_measured("cobertura report had no branch counts");
    }
    verdict(totals, run.status, &words, timeout_seconds)
}

/// L1.19 for Java: branch coverage from JaCoCo, via `mvn test jacoco:report`.
///
/// EXECUTES THE AUDITED PROJECT'S CODE. The report lands in the project's own build
/// directory, because that is where the plugin puts it and the plugin is the project's.
pub fn java_coverage(repo: &Path, timeout_seconds: f64, jdk: &str) -> Reading {
    let maven = repo.join("mvnw");
    let maven = if maven.exists() {
        maven.display().to_string()
    } else if which("mvn").is_some() {
        "mvn".to_string()
    } else {
        return not_measured(
            "needs Maven (mvn) on PATH or a ./mvnw wrapper in the repo");
    };
    if !repo.join("pom.xml").exists() {
        if repo.join("build.gradle").exists() || repo.join("build.gradle.kts").exists() {
            return not_measured("Gradle Java projects not yet supported by this harness");
        }
        return not_measured("needs a Maven build (no pom.xml found)");
    }

    let run = run_untrusted(
        &[maven, "-q".into(), "test".into(), "jacoco:report".into()],
        repo, &[], timeout_seconds);
    let report = repo.join("target").join("site").join("jacoco").join("jacoco.xml");

    let words = CoverageWords {
        no_report: "Java branch coverage needs the JaCoCo plugin in the build \
                    (jacoco.xml not produced)",
        nothing_to_cover: "no enumerable decision branches found \
                           (JaCoCo reported zero BRANCH counters)",
        how: "JaCoCo BRANCH counters",
        toolchain: jdk.to_string(),
        substitution: "",
    };
    if run.status == TIMED_OUT || !report.exists() {
        return verdict(None, run.status, &words, timeout_seconds);
    }
    let Ok(xml) = std::fs::read_to_string(&report) else {
        return not_measured("JaCoCo report was unreadable");
    };
    // Absent here means the report carries no BRANCH counter at all, which JaCoCo writes
    // for a project with no branches to cover. That is the nothing-to-cover case rather
    // than a missing report, and the verdict tells them apart by the zero.
    let totals = jacoco_totals(&xml).unwrap_or(Totals { covered: 0, total: 0 });
    verdict(Some(totals), run.status, &words, timeout_seconds)
}

#[cfg(test)]
mod runner_tests {
    use super::*;

    #[test]
    fn a_gradle_project_is_named_as_unsupported_rather_than_measured_at_zero() {
        let root = scratch_dir("gradle");
        std::fs::create_dir_all(&root).unwrap();
        std::fs::write(root.join("build.gradle"), "plugins { id 'java' }\n").unwrap();
        let reading = java_coverage(&root, 30.0, "a jdk");
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(reading.band, "n/a");
        assert!(reading.details.contains("Gradle"), "{}", reading.details);
    }

    #[test]
    fn a_directory_with_no_maven_build_is_told_what_it_needs() {
        let root = scratch_dir("nomaven");
        std::fs::create_dir_all(&root).unwrap();
        let reading = java_coverage(&root, 30.0, "a jdk");
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(reading.band, "n/a");
        assert!(reading.details.contains("pom.xml") || reading.details.contains("mvnw"),
                "{}", reading.details);
    }

    #[test]
    fn a_real_maven_project_measures_its_own_branches() {
        // Builds its OWN project rather than pointing at one an earlier step left behind.
        // A test pinned to a path only one machine has always skips everywhere else, which
        // is a test that looks present and proves nothing.
        if which("mvn").is_none() {
            eprintln!("skipped: mvn is not on PATH");
            return;
        }
        let root = scratch_dir("mvncov");
        let main = root.join("src").join("main").join("java").join("band");
        let test = root.join("src").join("test").join("java").join("band");
        std::fs::create_dir_all(&main).unwrap();
        std::fs::create_dir_all(&test).unwrap();
        std::fs::write(root.join("pom.xml"), JACOCO_POM).unwrap();
        // Four branches, a test reaching two, so the figure is short by construction and a
        // reader can check it against the fixture.
        std::fs::write(main.join("Band.java"),
            "package band;\n\npublic final class Band {\n\
             \x20   public static String classify(int n) {\n\
             \x20       if (n < 0) { return \"neg\"; }\n\
             \x20       if (n == 0) { return \"zero\"; }\n\
             \x20       return \"pos\";\n\
             \x20   }\n}\n").unwrap();
        std::fs::write(test.join("BandTest.java"),
            "package band;\n\nimport static org.junit.jupiter.api.Assertions.assertEquals;\n\
             import org.junit.jupiter.api.Test;\n\n\
             class BandTest {\n\
             \x20   @Test void positive() { assertEquals(\"pos\", Band.classify(3)); }\n}\n")
            .unwrap();

        let reading = java_coverage(&root, 900.0, "a jdk");
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(reading.value, "50.0", "{}", reading.details);
        assert!(reading.details.contains("2/4 decision branches"), "{}", reading.details);
    }

    #[test]
    fn the_report_walk_finds_a_file_nested_under_the_results_directory() {
        // The collector writes into a run-id directory it names itself, so the report is
        // never at a path this reader could have predicted.
        let root = scratch_dir("walk");
        let nested = root.join("some-guid").join("deeper");
        std::fs::create_dir_all(&nested).unwrap();
        std::fs::write(nested.join("coverage.cobertura.xml"), "<coverage/>").unwrap();
        std::fs::write(root.join("other.xml"), "<x/>").unwrap();
        let found = find_reports(&root, "coverage.cobertura.xml");
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(found.len(), 1);
    }
}

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
