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
