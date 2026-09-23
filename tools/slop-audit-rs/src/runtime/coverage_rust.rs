//! L1.19 for Rust: region coverage from cargo-llvm-cov. Ported from
//! l1_analyzer.rust_trace.decision_space_coverage and its verdict.
//!
//! EXECUTES THE AUDITED PROJECT'S CODE. Every refusal here comes before a number.
//!
//! Its own module, and not a ninth arm of `coverage_runners`, for two reasons. That file
//! stands at 956 lines against a god-file threshold of 1000, so a ninth arm would break the
//! rule this binary enforces on other people. And this reading does not go through the shared
//! verdict: the eight languages there report branches or statements and hand over a pair of
//! counts, while llvm-cov reports REGIONS, which is a third unit, and the reference prints a
//! sentence of its own for it. A reader comparing a Rust figure with a Java one has to be told
//! they are not the same measurement.
//!
//! Rust was the last language with no runtime coverage in this binary, which is a strange gap
//! in a tool written in Rust: the static enumeration stood in, and it counts decision points
//! FOUND where this reports the share REACHED.

use crate::runtime::determinism::{not_measured, Reading};
use crate::runtime::runners::{first_line, which};
use crate::runtime::{coverage_band, run_untrusted, timeout_note, TIMED_OUT};
use std::path::{Path, PathBuf};

/// A scratch directory no other run will use. Named per CALL, so two audits on one machine
/// cannot delete each other's report.
fn scratch_dir() -> PathBuf {
    use std::sync::atomic::{AtomicU64, Ordering};
    static NEXT: AtomicU64 = AtomicU64::new(0);
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let serial = NEXT.fetch_add(1, Ordering::Relaxed);
    std::env::temp_dir().join(format!("slop-rustcov-{}-{nanos}-{serial}", std::process::id()))
}

/// The one command this module runs. `cargo_args` is the caller's own words, handed to cargo
/// untouched, because a workspace can hold a target that will not build and cargo already has
/// the vocabulary for saying which packages to measure.
pub fn llvm_cov_command(cargo: &str, report_file: &Path, cargo_args: &[String]) -> Vec<String> {
    let mut command: Vec<String> = vec![
        cargo.to_string(), "llvm-cov".into(), "--json".into(), "--quiet".into(),
        "--output-path".into(), report_file.display().to_string(),
    ];
    command.extend(cargo_args.iter().cloned());
    command
}

/// The rustc toolchain rustup resolves for this repository, named so the result says which
/// environment measured it.
///
/// The rustc BESIDE the cargo on PATH, run with the repository as the working directory, so a
/// `rust-toolchain.toml` in the tree wins. A probe that would not answer is named unknown
/// rather than left blank: a reader uses this to decide whether to believe the number.
fn toolchain_named(repo: &Path, timeout_seconds: f64) -> String {
    let unknown = "an unknown rust toolchain".to_string();
    let Some(cargo) = which("cargo") else { return unknown };
    let rustc = Path::new(&cargo).with_file_name("rustc");
    let probe = run_untrusted(
        &[rustc.display().to_string(), "--version".into()],
        repo, &[], timeout_seconds.min(30.0));
    if probe.status != 0 {
        return unknown;
    }
    probe.stdout.lines().map(str::trim).find(|line| !line.is_empty())
        .map(|line| line.to_string())
        .unwrap_or(unknown)
}

/// Whether `cargo llvm-cov` is installed, asked of the tool itself.
fn llvm_cov_available(cargo: &str) -> bool {
    let here = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    run_untrusted(&[cargo.to_string(), "llvm-cov".into(), "--version".into()],
                  &here, &[], 30.0).status == 0
}

/// (count, covered) regions from a cargo-llvm-cov export, or nothing when it has no totals.
///
/// Nothing, never (0, 0), for a report this reader cannot find totals in. That is a schema it
/// does not know, which is a different fact from a tree with no regions, and reading it as
/// zero would publish Slop for a repository whose coverage was never measured.
fn region_totals(report: &serde_json::Value) -> Option<(u64, u64)> {
    let regions = report.get("data")?.get(0)?.get("totals")?.get("regions")?;
    Some((regions.get("count")?.as_u64()?, regions.get("covered")?.as_u64()?))
}

/// How many files the report covered, or nothing when the table cannot be read.
///
/// Read off the report rather than counted from the repository, because the question is what
/// the run measured and not what is there. Nothing rather than zero: a zero is a real answer
/// to a different question, and a file table nobody could read once reported as a measurement
/// of no files.
fn files_measured(report: &serde_json::Value) -> Option<usize> {
    Some(report.get("data")?.get(0)?.get("files")?.as_array()?.len())
}

/// How many tests cargo says ran, summed across every `test result:` line.
///
/// Regions come from compiled code, so a crate that compiles and has no tests has regions and
/// no measurement. It banded Slop at nought with the details line saying "suite passed", which
/// is true, because cargo test passes when there is nothing to run.
fn tests_run(output: &str) -> u64 {
    let mut total = 0u64;
    for line in output.lines() {
        let Some(rest) = line.split_once("test result:").map(|(_, r)| r) else { continue };
        for word in ["passed", "failed", "ignored"] {
            if let Some(n) = count_before(rest, word) {
                total += n;
            }
        }
    }
    total
}

/// The number standing immediately before `word` in `text`, as cargo writes `2 passed`.
fn count_before(text: &str, word: &str) -> Option<u64> {
    let at = text.find(word)?;
    text[..at].split_whitespace().next_back()?.parse().ok()
}

/// How much of the repository the figure is a share of, in the reference's own words.
fn scope_words(files: Option<usize>) -> String {
    match files {
        None => "a file table this reader could not count".to_string(),
        Some(1) => "1 file".to_string(),
        Some(n) => format!("{n} files"),
    }
}

/// The words that chose which packages cargo measured, or a sentence saying there were none.
///
/// The operator chooses the denominator, so the figure has to say what they chose. Two runs of
/// one commit on one compiler once reported 66.9 and 65.1 with the numerators agreeing within
/// four regions, and nothing in either line said how much each had read.
fn package_scope(cargo_args: &[String]) -> String {
    if cargo_args.is_empty() {
        return "cargo's own default at the repository root, no package arguments given".into();
    }
    cargo_args.join(" ")
}

/// L1.19 for Rust, from a finished run and cargo-llvm-cov's totals. No I/O, so it can be
/// asserted without a toolchain on the machine.
///
/// The timeout is decided first, before any total is touched: a killed run wrote no summary,
/// so the caller has nothing to hand over.
pub fn coverage_verdict(totals: Option<(u64, u64)>, status: i32, toolchain: &str,
                        timeout_seconds: f64, output: &str, files: Option<usize>,
                        cargo_args: &[String]) -> Reading {
    if status == TIMED_OUT {
        return not_measured(format!("test suite timed out before coverage could be measured{}",
                                    timeout_note(timeout_seconds)));
    }
    let Some((count, covered)) = totals else {
        return not_measured("coverage report had no region totals");
    };
    if count == 0 {
        return not_measured(
            "no coverage regions found, so nothing this reader can measure compiled");
    }
    if tests_run(output) == 0 {
        return not_measured(
            "no test ran, so a share of the regions they exercised is a share of nothing; \
             region coverage needs a suite that executes");
    }
    let pct = covered as f64 / count as f64 * 100.0;
    let suite = if status == 0 { "suite passed".to_string() }
                else { format!("suite exit {status}") };
    Reading {
        value: format!("{:.1}", (pct * 10.0).round() / 10.0),
        band: coverage_band(pct).to_string(),
        details: format!(
            "{covered}/{count} llvm-cov regions exercised by tests across {}, region coverage \
             ({suite}; ran under {toolchain}; package scope: {})",
            scope_words(files), package_scope(cargo_args)),
    }
}

/// L1.19 for Rust: run cargo-llvm-cov once and read its report.
pub fn rust_coverage(repo: &Path, timeout_seconds: f64, cargo_args: &[String]) -> Reading {
    let Some(cargo) = which("cargo") else {
        return not_measured("needs a Rust toolchain (cargo) in PATH");
    };
    let cargo = cargo.display().to_string();
    if !llvm_cov_available(&cargo) {
        return not_measured(
            "needs cargo-llvm-cov to measure coverage (cargo install cargo-llvm-cov)");
    }
    let scratch = scratch_dir();
    let _ = std::fs::create_dir_all(&scratch);
    let report_file = scratch.join("cov.json");
    let run = run_untrusted(&llvm_cov_command(&cargo, &report_file, cargo_args),
                            repo, &[], timeout_seconds);
    let written = report_file.exists();
    let raw = if written { std::fs::read_to_string(&report_file).ok() } else { None };
    let _ = std::fs::remove_dir_all(&scratch);

    if run.status == TIMED_OUT {
        // The instrumented build's own stopwatch, not the suite's. Without the number, "the
        // test suite timed out" reads as a fact about the repository when the fact is that
        // nobody asked for long enough.
        return not_measured(format!("test suite timed out before coverage could be measured{}",
                                    timeout_note(timeout_seconds)));
    }
    if run.stderr.contains("llvm-tools") && !written {
        return not_measured(
            "cargo-llvm-cov could not find the LLVM coverage tools; install the \
             llvm-tools-preview rustup component, or set LLVM_COV / LLVM_PROFDATA");
    }
    if !written {
        let said = if run.stderr.trim().is_empty() { &run.stdout } else { &run.stderr };
        return not_measured(format!("coverage produced no data (cargo exit {}): {}",
                                    run.status, first_line(said)));
    }
    let Some(report) = raw.and_then(|text| serde_json::from_str::<serde_json::Value>(&text).ok())
    else {
        return not_measured("coverage report was unreadable");
    };
    coverage_verdict(region_totals(&report), run.status,
                     &toolchain_named(repo, timeout_seconds), timeout_seconds,
                     &format!("{}{}", run.stdout, run.stderr),
                     files_measured(&report), cargo_args)
}

#[cfg(test)]
mod tests {
    use super::*;

    const RAN_TWO: &str =
        "test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out\n";
    const RAN_NONE: &str =
        "test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out\n";

    #[test]
    fn a_measured_run_reports_the_share_and_says_what_it_is_a_share_of() {
        let got = coverage_verdict(Some((100, 66)), 0, "rustc 1.88", 600.0, RAN_TWO,
                                   Some(12), &[]);
        assert_eq!(got.value, "66.0");
        assert!(got.details.contains("66/100 llvm-cov regions"), "{}", got.details);
        assert!(got.details.contains("across 12 files"), "{}", got.details);
        assert!(got.details.contains("ran under rustc 1.88"), "{}", got.details);
    }

    /// A reader who meets "1 files" stops trusting the sentence around it.
    #[test]
    fn one_file_is_said_in_the_singular() {
        let got = coverage_verdict(Some((10, 5)), 0, "rustc 1.88", 600.0, RAN_TWO, Some(1), &[]);
        assert!(got.details.contains("across 1 file,"), "{}", got.details);
    }

    /// Nothing rather than zero. A zero would be a real answer to a different question.
    #[test]
    fn a_file_table_this_reader_cannot_count_is_not_a_count_of_none() {
        let got = coverage_verdict(Some((100, 66)), 0, "rustc 1.88", 600.0, RAN_TWO, None, &[]);
        assert!(got.details.contains("could not count"), "{}", got.details);
        assert!(!got.details.contains("0 file"), "{}", got.details);
    }

    /// The operator picks the denominator with cargo's own words, and the figure has to say
    /// which words they picked or two honest percentages read as one comparison.
    #[test]
    fn the_details_name_the_package_scope_the_operator_chose() {
        let args = vec!["-p".to_string(), "core".to_string(), "--exclude".to_string(),
                        "bindings".to_string()];
        let got = coverage_verdict(Some((100, 66)), 0, "rustc 1.88", 600.0, RAN_TWO,
                                   Some(12), &args);
        assert!(got.details.contains("-p core --exclude bindings"), "{}", got.details);
    }

    #[test]
    fn no_package_arguments_is_said_in_words_rather_than_left_blank() {
        let got = coverage_verdict(Some((100, 66)), 0, "rustc 1.88", 600.0, RAN_TWO,
                                   Some(12), &[]);
        assert!(got.details.contains("no package arguments given"), "{}", got.details);
    }

    /// Regions come from compiled code, so a crate that compiles and has no tests has regions
    /// and no measurement. It banded Slop at nought with the line saying "suite passed".
    #[test]
    fn a_crate_that_compiled_and_ran_no_test_is_refused_rather_than_graded() {
        let got = coverage_verdict(Some((40, 0)), 0, "rustc 1.88", 600.0, RAN_NONE,
                                   Some(3), &[]);
        assert_eq!(got.band, "n/a");
        assert!(got.details.starts_with("no test ran"), "{}", got.details);
    }

    #[test]
    fn a_report_with_no_totals_is_refused_and_a_tree_with_no_regions_says_so_differently() {
        let no_totals = coverage_verdict(None, 0, "rustc 1.88", 600.0, RAN_TWO, Some(3), &[]);
        let no_regions = coverage_verdict(Some((0, 0)), 0, "rustc 1.88", 600.0, RAN_TWO,
                                          Some(3), &[]);
        assert!(no_totals.details.contains("no region totals"), "{}", no_totals.details);
        assert!(no_regions.details.contains("nothing this reader can measure compiled"),
                "{}", no_regions.details);
        assert_ne!(no_totals.details, no_regions.details);
    }

    /// The timeout is decided before any total is touched, and it names the seconds it
    /// allowed: the refusal an adopter is most likely to meet is the one that says a suite
    /// outlasted a clock it never chose.
    #[test]
    fn a_killed_run_names_the_clock_it_was_given() {
        let got = coverage_verdict(None, TIMED_OUT, "rustc 1.88", 600.0, "", Some(3), &[]);
        assert!(got.details.contains("allowed 600s"), "{}", got.details);
    }

    #[test]
    fn a_failing_suite_is_graded_and_the_line_says_the_suite_failed() {
        let got = coverage_verdict(Some((40, 38)), 101, "rustc 1.88", 600.0, RAN_TWO,
                                   Some(2), &[]);
        assert_eq!(got.value, "95.0");
        assert!(got.details.contains("suite exit 101"), "{}", got.details);
    }

    #[test]
    fn the_counts_come_from_cargos_own_summary_lines() {
        assert_eq!(tests_run(RAN_TWO), 2);
        assert_eq!(tests_run(RAN_NONE), 0);
        assert_eq!(tests_run(&format!("{RAN_TWO}{RAN_TWO}")), 4);
        assert_eq!(tests_run("nothing cargo would print"), 0);
    }

    #[test]
    fn the_command_passes_the_callers_words_to_cargo_untouched() {
        let args = vec!["--workspace".to_string(), "--exclude".to_string(), "bad".to_string()];
        let built = llvm_cov_command("cargo", Path::new("/tmp/cov.json"), &args);
        assert_eq!(&built[..6], &["cargo", "llvm-cov", "--json", "--quiet", "--output-path",
                                  "/tmp/cov.json"]);
        assert_eq!(&built[6..], &args[..]);
    }

    #[test]
    fn a_report_is_read_for_its_totals_and_its_file_count() {
        let report: serde_json::Value = serde_json::from_str(
            r#"{"data": [{"totals": {"regions": {"count": 10, "covered": 7}},
                          "files": [{"filename": "a.rs"}, {"filename": "b.rs"}]}]}"#)
            .expect("valid json");
        assert_eq!(region_totals(&report), Some((10, 7)));
        assert_eq!(files_measured(&report), Some(2));
        let empty: serde_json::Value = serde_json::from_str("{}").expect("valid json");
        assert_eq!(region_totals(&empty), None);
        assert_eq!(files_measured(&empty), None);
    }
}
