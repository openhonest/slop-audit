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

/// How a repository says which runner it uses, for a language that has more than one.
///
/// Declarative, so a variant is a row rather than a branch. Three signals, because Ruby
/// needs all three and each answers a different question: a directory or file that only
/// one runner creates, a pair that must BOTH be present, and a gem named in the lockfile.
pub struct Detect {
    /// Any one of these paths existing selects this variant.
    pub any: &'static [&'static str],
    /// ALL of these must exist. `test/` alone is not a Minitest project; `test/` beside a
    /// Rakefile is.
    pub all: &'static [&'static str],
    /// A file that must contain a line matching this prefix, at any indent.
    ///
    /// The PREFIX of a gem entry, not the bare name anywhere in the file. The reference
    /// matched the substring, which any project depending on rspec-expectations satisfies,
    /// and that gem stands alone: a Minitest project can use RSpec's matchers without
    /// RSpec. Such a project was read as an RSpec suite and the harness ran a binary that
    /// is not installed there.
    pub contains: Option<(&'static str, &'static str)>,
}

/// One way a language runs its suite, where the language has more than one.
pub struct Variant {
    pub name: &'static str,
    pub detect: Detect,
    pub command: &'static [&'static str],
    pub ran_markers: &'static [&'static str],
    pub nothing_ran: &'static str,
}

/// Whether this repository matches a variant's signals.
pub fn matches(detect: &Detect, repo: &Path) -> bool {
    if detect.any.iter().any(|path| repo.join(path).exists()) {
        return true;
    }
    if !detect.all.is_empty() && detect.all.iter().all(|path| repo.join(path).exists()) {
        return true;
    }
    match detect.contains {
        Some((file, prefix)) => std::fs::read_to_string(repo.join(file))
            .map(|text| text.lines().any(|line| line.trim_start().starts_with(prefix)))
            .unwrap_or(false),
        None => false,
    }
}

/// The variant this repository uses, in the order the rows are written, or nothing.
///
/// ORDER IS THE RULE where signals overlap: a project with both a spec directory and a
/// test directory is an RSpec project, and the row written first says so.
pub fn variant_for(runner: &Runner, repo: &Path) -> Option<&'static Variant> {
    runner.variants.iter().find(|v| matches(&v.detect, repo))
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
    /// Exit codes that mean the suite did not complete a valid run, and why.
    ///
    /// An EXIT CODE is a better signal than a marker in the output, and Python is the one
    /// row that has one. A marker can be deleted by the command's own flags, which is how
    /// Java came to report that every Maven project on earth never ran its suite; an exit
    /// code cannot be.
    pub incomplete: &'static [(i32, &'static str)],
    /// Exit codes that mean the runner collected nothing to run.
    pub collected_nothing: &'static [i32],
    /// The ways this language's projects run their suites, where there is more than one.
    ///
    /// Empty for a language with one runner, which is most of them. A language with
    /// variants and no match is REFUSED rather than run with the first row, because
    /// running a binary a project does not use is how a Minitest project came to be handed
    /// an RSpec command.
    pub variants: &'static [Variant],
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
        incomplete: &[],
        collected_nothing: &[],
        variants: &[],
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
        incomplete: &[],
        collected_nothing: &[],
        variants: &[],
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
        incomplete: &[],
        collected_nothing: &[],
        variants: &[],
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
        incomplete: &[],
        collected_nothing: &[],
        variants: &[],
    },
    Runner {
        lang: "python",
        tool: "python3",
        tool_missing: "needs a Python interpreter in PATH",
        // pytest-randomly supplies the seed; a project without it is refused by the
        // caller, because five identical runs say nothing about order.
        command: &["{python}", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                   "--randomly-seed={seed}"],
        ordering: Ordering::Seeded,
        // Read by exit code instead, which is what the two tables below are for.
        ran_markers: &[],
        never_ran: &[],
        unit: "seed",
        describe: "randomized-order runs passed cleanly",
        no_runs: "no randomized-order runs were made; determinism not measured",
        nothing_ran: "pytest collected no tests",
        incomplete: &[
            (2, "the run was interrupted"),
            (3, "pytest hit an internal error"),
            (4, "pytest usage or collection error (the suite did not run)"),
        ],
        collected_nothing: &[5],
        variants: &[],
    },
    Runner {
        lang: "ruby",
        tool: "bundle",
        tool_missing: "needs Ruby and Bundler (ruby, bundle) in PATH",
        // Chosen per repository: see the variants below.
        command: &[],
        ordering: Ordering::Seeded,
        ran_markers: &[],
        never_ran: &[],
        unit: "seed",
        describe: "randomized-order runs passed cleanly",
        no_runs: "no randomized-order runs were made; determinism not measured",
        nothing_ran: "the runner reported no tests",
        incomplete: &[],
        collected_nothing: &[],
        variants: &[
            // RSpec first: a project with both a spec directory and a test directory is an
            // RSpec project, and order is what says so.
            Variant {
                name: "rspec",
                detect: Detect {
                    any: &["spec", ".rspec"],
                    all: &[],
                    contains: Some(("Gemfile.lock", "rspec (")),
                },
                command: &["bundle", "exec", "rspec", "--order", "random", "--seed", "{seed}"],
                ran_markers: &[" example", " examples"],
                nothing_ran: "rspec reported no examples",
            },
            Variant {
                name: "minitest",
                detect: Detect {
                    any: &[],
                    // A test directory ALONE is not a Minitest project; one beside a
                    // Rakefile is.
                    all: &["test", "Rakefile"],
                    contains: None,
                },
                command: &["bundle", "exec", "rake", "test", "TESTOPTS=--seed={seed}"],
                ran_markers: &[" runs, "],
                nothing_ran: "the rake test task reported no runs",
            },
        ],
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
    // A language with variants and no match is REFUSED rather than run with the first row.
    // Running a binary a project does not use is how a Minitest project came to be handed
    // an RSpec command, and the refusal names what it looked for.
    let variant = if runner.variants.is_empty() {
        None
    } else {
        match variant_for(runner, repo) {
            Some(found) => Some(found),
            None => {
                let names: Vec<&str> = runner.variants.iter().map(|v| v.name).collect();
                return not_measured(format!(
                    "no {} suite detected ({}); determinism not measured",
                    runner.lang, names.join(" or ")));
            }
        }
    };
    let command = variant.map(|v| v.command).unwrap_or(runner.command);
    // A row whose command names an interpreter needs the project's own, resolved once.
    let interpreter = if command.iter().any(|part| part.contains("{python}")) {
        match python_interpreter(repo) {
            Some((path, _provenance)) => path,
            None => return not_measured(runner.tool_missing),
        }
    } else {
        String::new()
    };
    let markers = variant.map(|v| v.ran_markers).unwrap_or(runner.ran_markers);
    let nothing_ran = variant.map(|v| v.nothing_ran).unwrap_or(runner.nothing_ran);

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
        let filled: Vec<String> = command.iter()
            .map(|part| part.replace("{seed}", &attempt.to_string())
                            .replace("{python}", &interpreter))
            .collect();
        let finished = run_untrusted(&filled, repo, &[], timeout_seconds);
        let output = finished.output();
        // A row that declares exit codes is read by them, because a code cannot be deleted
        // by the command's own flags the way a marker can. A row that declares none falls
        // to its markers, which is every other language.
        let by_code = !runner.incomplete.is_empty() || !runner.collected_nothing.is_empty();
        let why = if runner.collected_nothing.contains(&finished.status) {
            nothing_ran.to_string()
        } else {
            match runner.incomplete.iter().find(|(code, _)| *code == finished.status) {
                Some((_, reason)) => (*reason).to_string(),
                None => nothing_ran.to_string(),
            }
        };
        let ran = if finished.status == TIMED_OUT {
            false
        } else if by_code {
            !runner.collected_nothing.contains(&finished.status)
                && !runner.incomplete.iter().any(|(code, _)| *code == finished.status)
        } else {
            !runner.never_ran.iter().any(|m| output.contains(m))
                && markers.iter().any(|m| output.contains(m))
        };
        Attempt {
            status: finished.status,
            isolation: finished.isolation,
            ran_tests: ran,
            summary: first_line(&output),
            why_it_did_not_run: format!("{why} under {toolchain}"),
        }
    });
    tally(attempts, &words, timeout_seconds)
}

/// The interpreter a Python project's suite must run under.
///
/// THE PROJECT'S OWN, not the one that happened to launch this binary. The target package
/// and its test dependencies are installed in the project's environment, and a suite run
/// under the wrong interpreter imports nothing and fails every time, which would read as a
/// suite that cannot pass rather than one that was never given its own library.
///
/// The layouts are tried in the order a project is most likely to use. None of them
/// present falls back to the interpreter on PATH, and the details line names which was
/// used so a reading always says what took it.
pub fn python_interpreter(repo: &Path) -> Option<(String, String)> {
    const LAYOUTS: &[&str] = &[
        ".venv/bin/python", ".venv/bin/python3", "venv/bin/python", "venv/bin/python3",
        ".venv/Scripts/python.exe", "venv/Scripts/python.exe",
    ];
    for layout in LAYOUTS {
        let candidate = repo.join(layout);
        if candidate.is_file() {
            return Some((candidate.display().to_string(), format!("the repo's {layout}")));
        }
    }
    which("python3").map(|path| (path.display().to_string(), "python3 on PATH".into()))
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
            // A row read by exit code needs no marker, which is the better signal: a
            // code cannot be deleted by the command's own flags.
            if !runner.incomplete.is_empty() || !runner.collected_nothing.is_empty() {
                assert!(!runner.command.is_empty(), "{} has no command", runner.lang);
                assert!(!runner.nothing_ran.is_empty(), "{} cannot say why", runner.lang);
                continue;
            }
            if runner.variants.is_empty() {
                assert!(!runner.ran_markers.is_empty(), "{} has no marker", runner.lang);
                assert!(!runner.command.is_empty(), "{} has no command", runner.lang);
                assert!(!runner.nothing_ran.is_empty(), "{} cannot say why", runner.lang);
                continue;
            }
            // A language whose command depends on the repository carries its markers and
            // its sentence on each variant instead, and every variant needs all three.
            for variant in runner.variants {
                assert!(!variant.command.is_empty(),
                        "{}/{} has no command", runner.lang, variant.name);
                assert!(!variant.ran_markers.is_empty(),
                        "{}/{} has no marker", runner.lang, variant.name);
                assert!(!variant.nothing_ran.is_empty(),
                        "{}/{} cannot say why", runner.lang, variant.name);
            }
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

#[cfg(test)]
mod variant_tests {
    use super::*;

    fn repo(name: &str, paths: &[(&str, &str)]) -> std::path::PathBuf {
        let root = std::env::temp_dir()
            .join(format!("slop-variant-{}-{name}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        for (path, body) in paths {
            let full = root.join(path);
            if body.is_empty() {
                std::fs::create_dir_all(&full).unwrap();
            } else {
                if let Some(parent) = full.parent() {
                    std::fs::create_dir_all(parent).unwrap();
                }
                std::fs::write(&full, body).unwrap();
            }
        }
        root
    }

    #[test]
    fn a_spec_directory_selects_the_rspec_variant() {
        let root = repo("spec", &[("spec", "")]);
        let ruby = runner_for("ruby").expect("ruby");
        assert_eq!(variant_for(ruby, &root).map(|v| v.name), Some("rspec"));
        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn a_test_directory_alone_is_not_a_minitest_project() {
        // It needs a Rakefile beside it. A repository with a stray test directory and no
        // task to run would otherwise be handed a rake command it has no task for.
        let root = repo("testonly", &[("test", "")]);
        let ruby = runner_for("ruby").expect("ruby");
        assert_eq!(variant_for(ruby, &root).map(|v| v.name), None);
        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn a_test_directory_beside_a_rakefile_is_a_minitest_project() {
        let root = repo("minitest", &[("test", ""), ("Rakefile", "task :test\n")]);
        let ruby = runner_for("ruby").expect("ruby");
        assert_eq!(variant_for(ruby, &root).map(|v| v.name), Some("minitest"));
        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn a_lockfile_naming_the_rspec_gem_selects_rspec() {
        let lock = "GEM\n  specs:\n    rspec (3.13.0)\n    rake (13.0)\n";
        let root = repo("lockrspec", &[("Gemfile.lock", lock)]);
        let ruby = runner_for("ruby").expect("ruby");
        assert_eq!(variant_for(ruby, &root).map(|v| v.name), Some("rspec"));
        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn a_lockfile_naming_only_rspec_expectations_is_not_an_rspec_project() {
        // The defect this rule exists for. The reference matched the substring, which any
        // project depending on rspec-expectations satisfies, and that gem stands alone: a
        // Minitest project can use RSpec's matchers without RSpec. Such a project was read
        // as an RSpec suite and handed a binary that is not installed there.
        let lock = "GEM\n  specs:\n    rspec-expectations (3.13.0)\n    minitest (5.25)\n";
        let root = repo("lockexp", &[("Gemfile.lock", lock),
                                     ("test", ""), ("Rakefile", "task :test\n")]);
        let ruby = runner_for("ruby").expect("ruby");
        assert_eq!(variant_for(ruby, &root).map(|v| v.name), Some("minitest"));
        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn rspec_wins_where_both_signals_are_present() {
        // Order is the rule where signals overlap.
        let root = repo("both", &[("spec", ""), ("test", ""), ("Rakefile", "task :test\n")]);
        let ruby = runner_for("ruby").expect("ruby");
        assert_eq!(variant_for(ruby, &root).map(|v| v.name), Some("rspec"));
        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn a_repository_with_no_suite_shape_is_refused_and_names_what_it_looked_for() {
        // Refused rather than run with the first row. Running a binary a project does not
        // use is how a Minitest project came to be handed an RSpec command.
        if which("bundle").is_none() {
            eprintln!("skipped: bundle is not on PATH");
            return;
        }
        let root = repo("bare", &[("README.md", "nothing here\n")]);
        let reading = test_determinism(&root, "ruby", 3, 30.0, "a ruby");
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(reading.band, "n/a");
        assert!(reading.details.contains("rspec or minitest"), "{}", reading.details);
    }
}

#[cfg(test)]
mod ruby_live {
    //! The Ruby row against a real Minitest project the test builds and installs itself.

    use super::*;

    fn minitest_project() -> Option<std::path::PathBuf> {
        if which("bundle").is_none() || which("ruby").is_none() {
            return None;
        }
        let root = std::env::temp_dir().join(format!("slop-rbdet-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(root.join("lib")).ok()?;
        std::fs::create_dir_all(root.join("test")).ok()?;
        // rake and minitest are DECLARED. Bundler hides the default gems, so a project
        // that names neither gets a load error that reads like a broken Ruby install.
        std::fs::write(root.join("Gemfile"),
            "source \"https://rubygems.org\"\ngem \"rake\"\ngem \"minitest\"\n").ok()?;
        std::fs::write(root.join("Rakefile"),
            "require \"rake/testtask\"\nRake::TestTask.new(:test) do |t|\n\
             \x20 t.libs << \"lib\" << \"test\"\n\
             \x20 t.test_files = FileList[\"test/**/*_test.rb\"]\nend\n").ok()?;
        std::fs::write(root.join("lib").join("band.rb"),
            "def band(n)\n  return \"neg\" if n < 0\n  \"pos\"\nend\n").ok()?;
        std::fs::write(root.join("test").join("band_test.rb"),
            "require \"minitest/autorun\"\nrequire \"band\"\n\
             class BandTest < Minitest::Test\n\
             \x20 def test_positive\n    assert_equal \"pos\", band(3)\n  end\nend\n").ok()?;
        let installed = run_untrusted(
            &["bundle".into(), "install".into(), "--path".into(), "vendor/bundle".into()],
            &root, &[], 600.0);
        if installed.status != 0 {
            let _ = std::fs::remove_dir_all(&root);
            return None;
        }
        Some(root)
    }

    #[test]
    fn a_real_minitest_suite_that_passes_every_seed_is_the_whole_count() {
        let Some(root) = minitest_project() else {
            eprintln!("skipped: ruby or bundler is not on PATH, or the bundle would not install");
            return;
        };
        let ruby = runner_for("ruby").expect("ruby");
        assert_eq!(variant_for(ruby, &root).map(|v| v.name), Some("minitest"));
        let reading = test_determinism(&root, "ruby", 3, 600.0, "ruby 2.6");
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(reading.value, "3/3", "{}", reading.details);
        assert_eq!(reading.band, "Healthy");
    }
}

// --------------------------------------------------------------------------
// JavaScript and TypeScript, whose runner is named in a manifest rather than by a path.
// --------------------------------------------------------------------------

/// The runners this harness can drive into a randomised order, and the command for one
/// attempt.
const JS_DRIVABLE: &[(&str, &[&str], &[&str])] = &[
    ("vitest",
     &["npx", "--no-install", "vitest", "run", "--sequence.shuffle",
       "--sequence.seed={seed}"],
     &["Test Files", "Tests "]),
    ("jest",
     &["npx", "--no-install", "jest", "--seed={seed}", "--ci"],
     &["Tests:", "Test Suites:"]),
];

/// Runners this harness RECOGNISES and cannot order-randomise.
///
/// Named in the refusal rather than lumped with "no runner found", because the two send a
/// reader to different places: one says install a runner, the other says this runner
/// cannot shuffle and a score over unshuffled runs would be a number nobody earned.
const JS_UNDRIVABLE: &[&str] =
    &["mocha", "ava", "tape", "tap", "jasmine", "node --test"];

/// What a JavaScript project's manifest says about how it runs tests.
#[derive(Debug, PartialEq, Eq)]
pub enum JsRunner {
    /// A runner this harness can shuffle, by name.
    Drivable(&'static str),
    /// A runner this harness knows and cannot shuffle, by name.
    Undrivable(&'static str),
    /// Nothing in the manifest names a runner this harness knows.
    Unknown,
}

/// The runner a project uses, from its dependencies and its test script.
///
/// BOTH are read, because a project can depend on a runner without naming it in the script
/// and can name it in the script without declaring it. The dependency lists are merged
/// rather than searched in turn: a runner in either is a runner this project has.
pub fn js_runner(manifest: &str) -> JsRunner {
    let script = crate::runtime::coverage::json_object(manifest, "scripts")
        .and_then(|scripts| crate::runtime::coverage::json_string(scripts, "test"))
        .unwrap_or_default();
    let declares = |name: &str| {
        for section in ["devDependencies", "dependencies"] {
            let found = crate::runtime::coverage::json_object(manifest, section)
                .map(|body| crate::runtime::coverage::json_has_key(body, name))
                .unwrap_or(false);
            if found {
                return true;
            }
        }
        false
    };
    for (name, _, _) in JS_DRIVABLE {
        if declares(name) || script.contains(name) {
            return JsRunner::Drivable(name);
        }
    }
    for name in JS_UNDRIVABLE {
        // The first word, because a runner named `node --test` is declared as `node`.
        let package = name.split_whitespace().next().unwrap_or(name);
        if declares(package) || script.contains(name) {
            return JsRunner::Undrivable(name);
        }
    }
    JsRunner::Unknown
}

/// L1.20 for JavaScript and TypeScript.
///
/// Its own entry point rather than a row in the table, because the question it asks first
/// is not "which command" but "can this project's runner be shuffled at all". A score over
/// runs that were never reordered would be a number nobody earned, so a project on a
/// runner this harness cannot drive is refused with that runner named.
pub fn js_determinism(repo: &Path, runs: usize, timeout_seconds: f64,
                      runtime: &str) -> Reading {
    if which("npx").is_none() || which("node").is_none() {
        return not_measured("needs node and npx in PATH");
    }
    let Ok(manifest) = std::fs::read_to_string(repo.join("package.json")) else {
        return not_measured("no package.json found");
    };
    let (name, command, markers) = match js_runner(&manifest) {
        JsRunner::Drivable(name) => {
            let row = JS_DRIVABLE.iter().find(|(n, _, _)| *n == name)
                .expect("a drivable runner has a row");
            (name, row.1, row.2)
        }
        JsRunner::Undrivable(name) => {
            return not_measured(format!(
                "determinism needs an order-randomizing runner (vitest --sequence.shuffle \
                 or jest --seed); detected {name}"));
        }
        JsRunner::Unknown => {
            return not_measured(
                "determinism needs an order-randomizing runner (vitest --sequence.shuffle \
                 or jest --seed); detected no recognized test runner");
        }
    };
    if !repo.join("node_modules").is_dir() {
        return not_measured(format!(
            "{name} is named in package.json and node_modules is not installed; this \
             harness runs a project's own suite and installs nothing"));
    }

    let words = RunWords {
        unit: "seed",
        timed_out: "a seed timed out",
        no_runs: "no shuffled runs were made; determinism not measured",
        describe: format!("shuffled-order {name} runs passed cleanly (under {runtime})"),
    };
    let attempts = (1..=runs).map(|attempt| {
        let filled: Vec<String> = command.iter()
            .map(|part| part.replace("{seed}", &attempt.to_string()))
            .collect();
        let finished = run_untrusted(&filled, repo, &[], timeout_seconds);
        let output = finished.output();
        let ran = finished.status != TIMED_OUT
            && markers.iter().any(|marker| output.contains(marker));
        Attempt {
            status: finished.status,
            isolation: finished.isolation,
            ran_tests: ran,
            summary: first_line(&output),
            why_it_did_not_run: format!("{name} reported no tests under {runtime}"),
        }
    });
    tally(attempts, &words, timeout_seconds)
}

#[cfg(test)]
mod js_tests {
    use super::*;

    #[test]
    fn a_declared_drivable_runner_is_found() {
        let manifest = r#"{"devDependencies": {"vitest": "^2.0.0"}}"#;
        assert_eq!(js_runner(manifest), JsRunner::Drivable("vitest"));
    }

    #[test]
    fn a_runner_named_only_in_the_test_script_is_found() {
        // A project can name its runner in the script without declaring it, and the other
        // way round, so both are read.
        let manifest = r#"{"scripts": {"test": "jest --coverage"}}"#;
        assert_eq!(js_runner(manifest), JsRunner::Drivable("jest"));
    }

    #[test]
    fn a_runner_in_the_runtime_dependencies_counts_too() {
        let manifest = r#"{"dependencies": {"jest": "30.0.0"}}"#;
        assert_eq!(js_runner(manifest), JsRunner::Drivable("jest"));
    }

    #[test]
    fn a_recognised_runner_that_cannot_shuffle_is_named_rather_than_lumped_in() {
        // The two refusals send a reader to different places: one says install a runner,
        // the other says this one cannot shuffle and a score over unshuffled runs would be
        // a number nobody earned.
        let manifest = r#"{"scripts": {"test": "node --test"}}"#;
        assert_eq!(js_runner(manifest), JsRunner::Undrivable("node --test"));
        let mocha = r#"{"devDependencies": {"mocha": "^10.0.0"}}"#;
        assert_eq!(js_runner(mocha), JsRunner::Undrivable("mocha"));
    }

    #[test]
    fn a_manifest_naming_no_runner_this_harness_knows_says_so() {
        assert_eq!(js_runner(r#"{"name": "x"}"#), JsRunner::Unknown);
    }

    #[test]
    fn a_drivable_runner_wins_over_an_undrivable_one() {
        // A project can carry both. It is drivable if anything it has can shuffle.
        let manifest = r#"{"devDependencies": {"mocha": "^10.0.0", "vitest": "^2.0.0"}}"#;
        assert_eq!(js_runner(manifest), JsRunner::Drivable("vitest"));
    }

    #[test]
    fn a_project_whose_dependencies_are_not_installed_is_told_so() {
        // The harness runs a project's own suite and installs nothing.
        if which("npx").is_none() || which("node").is_none() {
            eprintln!("skipped: node or npx is not on PATH");
            return;
        }
        let root = std::env::temp_dir().join(format!("slop-jsdet-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        std::fs::write(root.join("package.json"),
                       r#"{"devDependencies": {"vitest": "^2.0.0"}}"#).unwrap();
        let reading = js_determinism(&root, 3, 30.0, "node");
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(reading.band, "n/a");
        assert!(reading.details.contains("node_modules"), "{}", reading.details);
    }

    #[test]
    fn a_project_on_an_unshufflable_runner_is_refused_with_that_runner_named() {
        if which("npx").is_none() || which("node").is_none() {
            eprintln!("skipped: node or npx is not on PATH");
            return;
        }
        let root = std::env::temp_dir().join(format!("slop-jsnd-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        std::fs::write(root.join("package.json"),
                       r#"{"scripts": {"test": "node --test"}}"#).unwrap();
        let reading = js_determinism(&root, 3, 30.0, "node");
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(reading.band, "n/a");
        assert!(reading.details.contains("node --test"), "{}", reading.details);
    }
}

#[cfg(test)]
mod python_live {
    //! The Python row against a real suite, including the two refusals its exit codes give.

    use super::*;

    /// A project with its own virtual environment, pytest and pytest-randomly installed.
    /// Nothing is measured without the randomiser: five identical runs say nothing about
    /// order, so a project without it is a refusal rather than a score.
    fn pytest_project(body: &str) -> Option<std::path::PathBuf> {
        let uv = which("uv")?;
        let root = std::env::temp_dir().join(format!(
            "slop-pydet-{}-{}", std::process::id(),
            std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_nanos()).unwrap_or(0)));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).ok()?;
        std::fs::write(root.join("band.py"),
            "def band(n):\n    if n < 0:\n        return \"neg\"\n    return \"pos\"\n").ok()?;
        std::fs::write(root.join("test_band.py"), body).ok()?;
        let made = run_untrusted(
            &[uv.display().to_string(), "venv".into(), ".venv".into()], &root, &[], 300.0);
        if made.status != 0 {
            let _ = std::fs::remove_dir_all(&root);
            return None;
        }
        let installed = run_untrusted(
            &[uv.display().to_string(), "pip".into(), "install".into(), "--quiet".into(),
              "pytest".into(), "pytest-randomly".into()],
            &root,
            &[("VIRTUAL_ENV".into(), root.join(".venv").display().to_string())],
            600.0);
        if installed.status != 0 {
            let _ = std::fs::remove_dir_all(&root);
            return None;
        }
        Some(root)
    }

    #[test]
    fn the_projects_own_interpreter_is_preferred_over_the_one_on_the_path() {
        // The target package and its test dependencies live in the project's environment.
        // A suite run under the wrong interpreter imports nothing and fails every time,
        // which reads as a suite that cannot pass rather than one never given its library.
        let root = std::env::temp_dir().join(format!("slop-pyenv-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(root.join(".venv").join("bin")).unwrap();
        std::fs::write(root.join(".venv").join("bin").join("python"), "#!/bin/sh\n").unwrap();
        let (path, provenance) = python_interpreter(&root).expect("an interpreter");
        let _ = std::fs::remove_dir_all(&root);
        assert!(path.contains(".venv"), "{path}");
        assert!(provenance.contains(".venv"), "{provenance}");
    }

    #[test]
    fn a_real_suite_that_passes_every_seed_is_the_whole_count() {
        let Some(root) = pytest_project(
            "from band import band\n\n\ndef test_positive():\n    assert band(3) == \"pos\"\n")
        else {
            eprintln!("skipped: uv is not on PATH, or the environment would not build");
            return;
        };
        let reading = test_determinism(&root, "python", 3, 600.0, "a python");
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(reading.value, "3/3", "{}", reading.details);
        assert_eq!(reading.band, "Healthy");
    }

    #[test]
    fn a_real_suite_that_collects_nothing_is_refused_rather_than_scored() {
        // pytest answers exit 5, which cannot be deleted by a quiet flag the way a marker
        // can. Nought of three would read as a flaky suite.
        let Some(root) = pytest_project("# no tests here\n") else {
            eprintln!("skipped: uv is not on PATH, or the environment would not build");
            return;
        };
        let reading = test_determinism(&root, "python", 3, 600.0, "a python");
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(reading.band, "n/a", "{}", reading.details);
        assert!(reading.details.contains("collected no tests"), "{}", reading.details);
    }

    #[test]
    fn a_real_suite_that_will_not_import_is_refused_with_the_reason() {
        // A collection error is exit 4: the suite did not run, which is not the same fact
        // as a suite that ran and failed.
        let Some(root) = pytest_project("import there_is_no_such_module\n") else {
            eprintln!("skipped: uv is not on PATH, or the environment would not build");
            return;
        };
        let reading = test_determinism(&root, "python", 3, 600.0, "a python");
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(reading.band, "n/a", "{}", reading.details);
        assert!(reading.details.contains("did not run"), "{}", reading.details);
    }
}
