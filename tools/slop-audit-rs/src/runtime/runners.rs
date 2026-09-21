//! What each language does to run its own suite in a varied order, and how to tell whether
//! it ran at all. Ported from the determinism halves of the nine `*_trace` modules.
//!
//! One driver, nine rows. The RULES are shared and live in the tally; what differs is the
//! toolchain to find, the command to build, and the marker that says a suite executed.
//! Those three are data, so a tenth language is a row rather than a copy of the driver.
//!
//! WHAT VARIES THE ORDER is the part that cannot be shared, and it is not the same fact
//! twice. Go and Ruby take a seed on the command line, so run three IS seed three. Rust and
//! C# take none and vary by scheduler, so run three is just run three and a reader must not
//! be told about seeds. C ships no standard randomizer at all, so there is no shuffled run
//! to count and the honest answer is a permanent refusal naming why.

use crate::runtime::determinism::{not_measured, tally, Attempt, Reading, RunWords};
use crate::runtime::{run_untrusted, TIMED_OUT};
use std::path::Path;

/// How one language varies the order its tests run in.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Ordering {
    /// The runner takes a seed, so the position in the sequence IS the seed and is named
    /// as one.
    Seeded,
    /// The runner takes no seed and the scheduler varies the order. An attempt is a run,
    /// never a seed, and the details line says which so a reader comparing this against a
    /// seeded language does not read one guarantee for the other.
    SchedulerVaried,
    /// The language ships no standard test-order randomizer. There is no shuffled run to
    /// count, and a score over unshuffled runs would be a number nobody earned.
    NotRandomizable,
}

/// One language's determinism row.
pub struct Runner {
    pub lang: &'static str,
    /// The executable this runner needs on PATH, and the refusal when it is absent.
    pub tool: &'static str,
    pub tool_missing: &'static str,
    /// The command for one attempt. `{seed}` is replaced with the attempt's number where
    /// the runner takes one.
    pub command: &'static [&'static str],
    pub ordering: Ordering,
    /// Markers that say a suite actually built and ran. ANY of them is enough.
    ///
    /// Reading the output for this is the reference's approach for seven of the nine, and
    /// it is exactly what broke Java: the quiet flag deleted the line the reader looked
    /// for, so every project reported a suite that never ran. A row whose marker can be
    /// suppressed by its own command is a row that has to read a report instead.
    pub ran_markers: &'static [&'static str],
    /// What the runner prints when a package never ran, even though a marker above appears
    /// on the same line. Checked FIRST, and it beats every marker.
    ///
    /// Go reports a package that would not compile as `FAIL <pkg> [build failed]`, which
    /// carries the `FAIL` marker, so a repository that does not build read as a suite that
    /// ran and failed: three such runs graded it Slop on test determinism, which is a
    /// claim about flakiness on code that never executed a test. The reference had the
    /// same defect and was fixed with it.
    pub never_ran: &'static [&'static str],
    /// What one attempt is called, in this language's own words.
    pub unit: &'static str,
    /// The tail of the details line, after "N of M ".
    pub describe: &'static str,
    /// The sentence for zero attempts.
    pub no_runs: &'static str,
    /// The sentence for an attempt that executed nothing.
    pub nothing_ran: &'static str,
}

/// Every language, in the order the panel prints them.
pub const RUNNERS: &[Runner] = &[
    Runner {
        lang: "go",
        tool: "go",
        tool_missing: "needs the Go toolchain (go) in PATH",
        // The seed is the POSITION: shuffled one to N in order, so the Nth attempt is seed
        // N. Carrying the number alongside it would be a second copy of one fact.
        command: &["go", "test", "./...", "-shuffle={seed}", "-count=1"],
        ordering: Ordering::Seeded,
        ran_markers: &["ok  ", "PASS", "FAIL", "--- FAIL"],
        never_ran: &["[build failed]", "[setup failed]"],
        unit: "seed",
        describe: "shuffled-order runs passed cleanly",
        no_runs: "no shuffled runs were made; determinism not measured",
        nothing_ran: "no test packages built or executed",
    },
    Runner {
        lang: "csharp",
        tool: "dotnet",
        tool_missing: "needs the dotnet SDK in PATH",
        command: &["dotnet", "test"],
        ordering: Ordering::SchedulerVaried,
        ran_markers: &["Total tests:", "Passed!", "Failed!", "Passed :", "Failed :",
                       "Passed: ", "Failed: "],
        // A build failure prints no counts line at all, so no marker matches and nothing
        // has to be excluded.
        never_ran: &[],
        unit: "run",
        describe: "`dotnet test` runs passed cleanly (order is scheduler-varied, \
                   not seed-controlled)",
        no_runs: "no `dotnet test` runs were made; determinism not measured",
        nothing_ran: "no test project built or executed",
    },
    Runner {
        lang: "rust",
        tool: "cargo",
        tool_missing: "needs a Rust toolchain (cargo) in PATH",
        command: &["cargo", "test", "--quiet"],
        ordering: Ordering::SchedulerVaried,
        ran_markers: &["test result:", "running "],
        // cargo prints `error[...]` and no test-result line when a crate will not build.
        never_ran: &[],
        unit: "run",
        describe: "cargo-test runs passed cleanly (libtest varies order across runs)",
        no_runs: "no cargo-test runs were made; determinism not measured",
        nothing_ran: "cargo test collected no tests",
    },
    Runner {
        lang: "c",
        tool: "cc",
        tool_missing: "needs a C compiler (cc) in PATH",
        command: &[],
        // Not a gap in this harness and not a failure on the repository. C ships no
        // standard test-order randomizer, so there is no shuffled run to count, and a
        // score of nought over five would read as a suite that falls over when reordered
        // rather than one that was never reordered.
        ordering: Ordering::NotRandomizable,
        ran_markers: &[],
        never_ran: &[],
        unit: "run",
        describe: "",
        no_runs: "C has no standard test-order randomizer; determinism not measured",
        nothing_ran: "",
    },
];

/// One language's row, or nothing when this port has none for it.
///
/// Refused rather than defaulted: a language with no row must reach a refusal at the call
/// site, because a driver that ran some default command would report a number about
/// whatever that command happened to do.
pub fn runner_for(lang: &str) -> Option<&'static Runner> {
    RUNNERS.iter().find(|r| r.lang == lang)
}

/// Whether this output says a suite actually built and ran.
///
/// The difference between a real determinism data point and the suite never executing. A
/// compilation failure and a module with no tests both answer false.
pub fn ran_tests(runner: &Runner, output: &str) -> bool {
    // The exclusion is checked FIRST and beats every marker, because the marker can appear
    // on the very line that says the package never ran.
    if runner.never_ran.iter().any(|marker| output.contains(marker)) {
        return false;
    }
    runner.ran_markers.iter().any(|marker| output.contains(marker))
}

/// The first non-empty line of a run's output, capped, which is what turns a bare score
/// into a reason a reader can act on.
pub fn first_line(output: &str) -> String {
    output
        .lines()
        .map(str::trim)
        .find(|line| !line.is_empty())
        .map(|line| line.chars().take(200).collect())
        .unwrap_or_else(|| "no output".to_string())
}

/// The command for one attempt, with the seed filled in where the runner takes one.
fn command_for(runner: &Runner, attempt: usize) -> Vec<String> {
    runner.command.iter()
        .map(|part| part.replace("{seed}", &attempt.to_string()))
        .collect()
}

/// L1.20 for one repository: run the suite `runs` times and count the runs where the whole
/// suite passes.
///
/// EXECUTES THE AUDITED PROJECT'S CODE, by the decision of 2026-09-21. Every run is
/// isolated and time-limited by the runner below, and every refusal the reference makes
/// survives: a suite that did not build, ran no tests, or timed out is not a determinism
/// result and says so rather than scoring zero.
///
/// The attempts are produced lazily and the tally returns on the first terminal one, so a
/// timed-out first run does not spend four more full timeouts proving the same thing.
pub fn test_determinism(repo: &Path, lang: &str, runs: usize, timeout_seconds: f64,
                        toolchain: &str) -> Reading {
    let Some(runner) = runner_for(lang) else {
        return not_measured(format!(
            "no determinism harness is ported for {lang}; run the Python reference for \
             this indicator"));
    };
    if runner.ordering == Ordering::NotRandomizable {
        return not_measured(format!("{} ({}: {toolchain})", runner.no_runs, runner.tool));
    }
    if which(runner.tool).is_none() {
        return not_measured(runner.tool_missing);
    }

    let words = RunWords {
        unit: runner.unit,
        timed_out: match runner.ordering {
            Ordering::Seeded => "a seed timed out",
            _ => "a run timed out",
        },
        no_runs: runner.no_runs,
        describe: format!("{} (under {toolchain})", runner.describe),
    };

    // Lazy, so the tally's return on a timed-out or never-run attempt stops the rest.
    let attempts = (1..=runs).map(|attempt| {
        let finished = run_untrusted(&command_for(runner, attempt), repo, &[], timeout_seconds);
        let output = finished.output();
        let ran = finished.status != TIMED_OUT && ran_tests(runner, &output);
        Attempt {
            status: finished.status,
            isolation: finished.isolation,
            ran_tests: ran,
            summary: first_line(&output),
            why_it_did_not_run: format!("{} under {toolchain}", runner.nothing_ran),
        }
    });
    tally(attempts, &words, timeout_seconds)
}

/// The path of an executable on PATH, or nothing.
///
/// Its own function because a missing tool is a REFUSAL with a repair in it, and the
/// refusal reads better when the question is asked once and named.
pub fn which(program: &str) -> Option<std::path::PathBuf> {
    let path = std::env::var_os("PATH")?;
    std::env::split_paths(&path)
        .map(|dir| dir.join(program))
        .find(|candidate| candidate.is_file())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_language_with_no_row_is_refused_rather_than_run_with_a_default() {
        // A driver that ran some default command would report a number about whatever that
        // command happened to do.
        let reading = test_determinism(Path::new("."), "cobol", 5, 30.0, "a toolchain");
        assert_eq!(reading.band, "n/a");
        assert!(reading.details.contains("cobol"));
    }

    #[test]
    fn c_refuses_permanently_and_names_why_rather_than_scoring_zero() {
        // Not a gap in this harness and not a failure on the repository. A score of nought
        // over five would read as a suite that falls over when reordered rather than one
        // that was never reordered.
        let reading = test_determinism(Path::new("."), "c", 5, 30.0, "cc (Apple clang)");
        assert_eq!(reading.band, "n/a");
        assert!(reading.details.contains("no standard test-order randomizer"));
        assert!(reading.details.contains("cc (Apple clang)"), "{}", reading.details);
    }

    #[test]
    fn a_missing_toolchain_is_a_refusal_carrying_its_own_repair() {
        let runner = runner_for("go").expect("go");
        assert!(runner.tool_missing.contains("PATH"));
        assert!(runner.tool_missing.contains("go"));
    }

    #[test]
    fn a_seeded_runner_puts_the_attempt_number_in_its_command() {
        // The seed IS the position. Go shuffles with seeds one to N in order, so carrying
        // the number alongside would be a second copy of one fact.
        let runner = runner_for("go").expect("go");
        assert_eq!(command_for(runner, 3),
                   vec!["go", "test", "./...", "-shuffle=3", "-count=1"]);
    }

    #[test]
    fn a_scheduler_varied_runner_takes_no_seed_and_its_words_say_so() {
        // A reader comparing this against a seeded language would otherwise read the same
        // sentence for two different guarantees.
        let runner = runner_for("csharp").expect("csharp");
        assert_eq!(runner.ordering, Ordering::SchedulerVaried);
        assert_eq!(runner.unit, "run");
        assert!(runner.describe.contains("scheduler-varied"));
        assert_eq!(command_for(runner, 3), vec!["dotnet", "test"]);
    }

    #[test]
    fn a_suite_that_built_and_ran_is_told_from_one_that_did_not() {
        let go = runner_for("go").expect("go");
        assert!(ran_tests(go, "ok  \texample/pkg\t0.01s\n"));
        assert!(ran_tests(go, "--- FAIL: TestThing\nFAIL\n"));
        assert!(!ran_tests(go, "# example/pkg\n./main.go:3:2: undefined: x\n"),
                "a build error is not a suite that ran");
        assert!(!ran_tests(go, ""), "no output is not a suite that ran");
    }

    #[test]
    fn every_row_that_reads_output_has_a_marker_to_read() {
        // A randomizable row with no marker cannot tell a suite that ran from one that did
        // not, so every attempt would read as never having executed. Java is the reason
        // this is asserted: its marker was deleted by its own command's quiet flag, and
        // every project reported a suite that never ran.
        for runner in RUNNERS {
            if runner.ordering == Ordering::NotRandomizable {
                continue;
            }
            assert!(!runner.ran_markers.is_empty(), "{} has no marker", runner.lang);
            assert!(!runner.command.is_empty(), "{} has no command", runner.lang);
            assert!(!runner.nothing_ran.is_empty(), "{} cannot say why", runner.lang);
        }
    }

    #[test]
    fn a_build_failure_carrying_a_pass_marker_is_still_a_suite_that_did_not_run() {
        // Go reports a package that would not compile as `FAIL <pkg> [build failed]`, and
        // `FAIL` is a marker. Three such runs graded a repository Slop on test
        // determinism, which is a claim about flakiness on code that never ran a test.
        let go = runner_for("go").expect("go");
        assert!(!ran_tests(go, "FAIL\tfixture [build failed]\n"));
        assert!(!ran_tests(go, "FAIL\tfixture [setup failed]\n"));
        assert!(ran_tests(go, "--- FAIL: TestThing\nFAIL\tfixture\t0.01s\n"),
                "a real failure is still a suite that ran");
    }

    #[test]
    fn the_first_line_of_output_survives_as_a_reason() {
        assert_eq!(first_line("\n\n  FAIL: three tests  \nmore\n"), "FAIL: three tests");
        assert_eq!(first_line(""), "no output");
    }

    #[test]
    fn a_tool_that_is_not_on_the_path_is_not_found() {
        assert!(which("there-is-no-such-program-here").is_none());
        assert!(which("sh").is_some());
    }
}

#[cfg(test)]
mod live {
    //! The harness driven against a REAL suite, not a fixture of one.
    //!
    //! These execute code, which is what the binary now does at a client site. A harness
    //! whose only tested paths are its refusals has been proved to decline and never to
    //! measure, and that was the defect this whole session opened with.
    //!
    //! A test is skipped only when its toolchain is genuinely absent, and the skip says
    //! which. Skipping silently would turn a missing compiler into a green run.

    use super::*;
    use std::io::Write;

    /// A Go module with one passing test, written fresh so the run is reproducible.
    fn go_fixture(name: &str) -> std::path::PathBuf {
        let root = std::env::temp_dir().join(format!("slop-det-{}-{name}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).expect("a directory");
        let files: &[(&str, &str)] = &[
            ("go.mod", "module fixture\n\ngo 1.21\n"),
            ("band.go", "package fixture\n\nfunc Band(n int) string {\n\tif n > 10 {\n\t\treturn \"high\"\n\t}\n\treturn \"low\"\n}\n"),
            ("band_test.go", "package fixture\n\nimport \"testing\"\n\nfunc TestHigh(t *testing.T) {\n\tif Band(20) != \"high\" {\n\t\tt.Fatal(\"high\")\n\t}\n}\n"),
        ];
        for (name, body) in files {
            let mut f = std::fs::File::create(root.join(name)).expect("a file");
            f.write_all(body.as_bytes()).expect("written");
        }
        root
    }

    #[test]
    fn a_real_go_suite_that_passes_every_shuffle_is_the_whole_count() {
        if which("go").is_none() {
            eprintln!("skipped: go is not on PATH");
            return;
        }
        let repo = go_fixture("pass");
        let reading = test_determinism(&repo, "go", 3, 300.0, "go version");
        let _ = std::fs::remove_dir_all(&repo);
        assert_eq!(reading.value, "3/3", "{}", reading.details);
        assert_eq!(reading.band, "Healthy");
        assert!(reading.details.contains("shuffled-order"), "{}", reading.details);
    }

    #[test]
    fn a_real_module_with_no_tests_is_not_a_determinism_result() {
        // The refusal beside the measurement, on real code. A module that builds and runs
        // nothing is not five clean runs; it is nothing to score.
        if which("go").is_none() {
            eprintln!("skipped: go is not on PATH");
            return;
        }
        let repo = go_fixture("empty");
        let _ = std::fs::remove_file(repo.join("band_test.go"));
        let reading = test_determinism(&repo, "go", 3, 300.0, "go version");
        let _ = std::fs::remove_dir_all(&repo);
        assert_eq!(reading.band, "n/a", "{}", reading.details);
        assert!(reading.details.contains("did not run"), "{}", reading.details);
    }

    #[test]
    fn a_real_suite_that_will_not_build_is_refused_rather_than_scored() {
        // A compilation failure is not flakiness. Nought of three would read as a suite
        // that falls over when reordered.
        if which("go").is_none() {
            eprintln!("skipped: go is not on PATH");
            return;
        }
        let repo = go_fixture("broken");
        std::fs::write(repo.join("band.go"), "package fixture\n\nfunc Band() { undefined() }\n")
            .expect("written");
        let reading = test_determinism(&repo, "go", 3, 300.0, "go version");
        let _ = std::fs::remove_dir_all(&repo);
        assert_eq!(reading.band, "n/a", "{}", reading.details);
        assert!(reading.details.contains("did not run"), "{}", reading.details);
    }

    #[test]
    fn a_real_suite_that_outlasts_the_clock_is_refused_and_names_the_seconds() {
        // The refusal an adopter is most likely to meet, on a suite that really does hang.
        if which("go").is_none() {
            eprintln!("skipped: go is not on PATH");
            return;
        }
        let repo = go_fixture("slow");
        std::fs::write(repo.join("band_test.go"),
            "package fixture\n\nimport (\n\t\"testing\"\n\t\"time\"\n)\n\n\
             func TestSlow(t *testing.T) {\n\ttime.Sleep(60 * time.Second)\n}\n")
            .expect("written");
        let reading = test_determinism(&repo, "go", 3, 2.0, "go version");
        let _ = std::fs::remove_dir_all(&repo);
        assert_eq!(reading.band, "n/a", "{}", reading.details);
        assert!(reading.details.contains("timed out"), "{}", reading.details);
        assert!(reading.details.contains("allowed 2s"), "{}", reading.details);
    }
}
