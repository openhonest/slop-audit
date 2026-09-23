//! Building the panel for a repository.
//!
//! Lifted out of `main` so the shape of the output is testable. While it lived in `main`
//! nothing could assert what the binary actually emits, which is how six indicators went
//! missing from the output without a single test noticing.

use crate::runtime::{coverage_runners as runtime_cov, determinism::Reading, runners};
use crate::{coverage, indicators, Indicator};
use std::path::Path;

/// How long one execution of a target's whole suite is allowed, and how many attempts a
/// determinism reading makes.
///
/// Both are the reference's numbers. The seconds are named in every refusal that comes of
/// them, because the refusal an adopter is most likely to meet is the one that says a
/// suite outlasted a clock it never chose.
const SUITE_TIMEOUT_SECONDS: f64 = 300.0;
const DETERMINISM_RUNS: usize = 5;

/// L1.20 for whichever language this repository is.
///
/// EXECUTES THE AUDITED PROJECT'S CODE, by the decision of 2026-09-21. Three rows read
/// their attempts three different ways and two of them have entry points of their own, so
/// the dispatch is here rather than inside the driver: Java reads the reports its runner
/// writes, JavaScript asks first whether the project's runner can shuffle at all, and the
/// rest go through the table.
fn test_determinism(repo: &Path, language: &str) -> Reading {
    match language {
        "java" => crate::runtime::runners_java::java_determinism(repo, DETERMINISM_RUNS, SUITE_TIMEOUT_SECONDS,
                                            &toolchain_name(repo, language)),
        "javascript" | "typescript" =>
            crate::runtime::runners_js::js_determinism(repo, DETERMINISM_RUNS, SUITE_TIMEOUT_SECONDS,
                                    &toolchain_name(repo, language)),
        other => runners::test_determinism(repo, other, DETERMINISM_RUNS,
                                           SUITE_TIMEOUT_SECONDS,
                                           &toolchain_name(repo, language)),
    }
}

/// L1.19's RUNTIME half for whichever language this repository is: the share of decisions
/// the project's own tests actually reached.
///
/// Distinct from the static half already on the panel, which enumerates decision points
/// without running anything. This one EXECUTES the audited project's code.
///
/// A language with no runtime runner is refused by name rather than falling back to the
/// static count, because the two answer different questions and a reader told one number
/// cannot tell which they were given.
fn runtime_coverage(repo: &Path, language: &str) -> Option<Reading> {
    let toolchain = toolchain_name(repo, language);
    Some(match language {
        "go" => runtime_cov::go_coverage(repo, SUITE_TIMEOUT_SECONDS, &toolchain),
        "csharp" => runtime_cov::csharp_coverage(repo, SUITE_TIMEOUT_SECONDS, &toolchain),
        "java" => runtime_cov::java_coverage(repo, SUITE_TIMEOUT_SECONDS, &toolchain),
        "ruby" => runtime_cov::ruby_coverage(repo, SUITE_TIMEOUT_SECONDS, &toolchain),
        "javascript" | "typescript" =>
            runtime_cov::js_coverage(repo, SUITE_TIMEOUT_SECONDS, &toolchain),
        "python" => runtime_cov::python_coverage(repo, SUITE_TIMEOUT_SECONDS),
        "c" => runtime_cov::c_coverage(repo, SUITE_TIMEOUT_SECONDS, &toolchain),
        _ => return None,
    })
}

/// The toolchain that took a reading, so a number always says what measured it.
///
/// Probed by asking the tool itself, because the version on PATH is not always the version
/// a repository resolves: a wrapper in the project, or a version manager's shim, can put a
/// different one in front. A probe that will not run answers with a name rather than
/// nothing, so a reading is never left unattributed.
fn toolchain_name(repo: &Path, language: &str) -> String {
    let probe: &[&str] = match language {
        "go" => &["go", "version"],
        "rust" => &["cargo", "--version"],
        "csharp" => &["dotnet", "--version"],
        "java" => &["java", "-version"],
        "ruby" => &["ruby", "--version"],
        "python" => &["python3", "--version"],
        "javascript" | "typescript" => &["node", "--version"],
        "c" => &["cc", "--version"],
        _ => return format!("an unknown {language} toolchain"),
    };
    if runners::which(probe[0]).is_none() {
        return format!("no {} on PATH", probe[0]);
    }
    let command: Vec<String> = probe.iter().map(|part| part.to_string()).collect();
    let run = crate::runtime::run_untrusted(&command, repo, &[], 30.0);
    // Some print their version to stderr, which is why both streams are read.
    let output = run.output();
    output.lines().map(str::trim).find(|line| !line.is_empty())
        .map(|line| line.chars().take(120).collect())
        .unwrap_or_else(|| format!("an unnamed {language} toolchain"))
}

/// Every indicator this binary computes, before reconciliation against the canonical set.
fn measured(repo: &Path, language: &str, exec_tests: bool) -> Vec<Indicator> {
    let mut panel = Vec::new();
    panel.extend(indicators::git_ratios::analyze(repo)); // L1.1 - L1.8
    panel.push(indicators::config_presence::present_at(
        repo, &indicators::config_presence::PRECOMMIT)); // L1.9
    panel.push(indicators::config_presence::l1_10(repo)); // L1.10
    panel.push(indicators::config_presence::present_at(
        repo, &indicators::config_presence::CONTAINER)); // L1.11
    // L1.12. Dead code: a statement after a terminator, which is decidable from syntax
    // alone, and a definition nothing in the repository names, which is decidable only where
    // nothing can reach the name by a route a syntactic scan cannot follow.
    panel.push(indicators::dead_code::analyze(repo, language));
    // L1.13. Near-duplicate code, measured here rather than shelled out to a tool nobody
    // has: the reference used to call one, and it was installed on no machine that ever ran
    // the panel, so this column reported n/a on every repository ever measured.
    panel.push(indicators::duplication::analyze(repo, language));
    // L1.14. Committed credentials, over the files git tracks. Every rule is a regular
    // expression over the file's text, so a file counted as scanned WAS scanned end to end,
    // and a scan that opened no file refuses rather than reporting a clean bill of health.
    panel.push(indicators::secret_scan::analyze(repo, language));
    panel.push(indicators::type_escapes::analyze(repo, language)); // L1.15
    panel.push(indicators::whitespace::analyze(repo)); // L1.16
    panel.push(indicators::god_files::analyze(repo)); // L1.17 (all languages)
    // L1.19. The runtime half where the run executes tests and a runner exists for the
    // language; the static enumeration otherwise. The details line says which was taken,
    // because a share of decisions REACHED and a count of decisions FOUND are different
    // numbers and a reader given one cannot tell which.
    let runtime = if exec_tests { runtime_coverage(repo, language) } else { None };
    match runtime {
        Some(reading) => panel.push(Indicator {
            code: "L1.19".into(),
            label: "decision-space".into(),
            value: reading.value,
            band: reading.band,
            details: reading.details,
        }),
        None => panel.push(indicators::decision_space::analyze(repo, language)),
    }
    // L1.18. The mutable-state ratio, which reads the classifier below it for the bound:
    // state whose reaching set L1.18b could bound does not count toward the ratio.
    panel.push(indicators::mutable_state::analyze(repo, language));
    // L1.18b. The finite-testability verdict distribution. It reads no tool and runs
    // nothing: every number comes from the parse trees the census already walks.
    let state = crate::state::bounds::classify(repo, language);
    panel.push(Indicator {
        code: "L1.18b".into(),
        label: "finite-testability".into(),
        value: crate::state::bounds::value_of(&state),
        band: state.band.clone(),
        details: state.details.clone(),
    });
    // thread_surface, additive: every site where a compiler-enforced thread-safety
    // guarantee is overridden by hand or is simply absent. A fact about the syntax, never a
    // claim that a race exists.
    panel.push(indicators::thread_surface::analyze(repo, language));
    // interleaving_robustness, additive: of the concurrency surface flagged above, which
    // files no model checker touches. It reads the surface meter's own refusal rather than
    // inheriting a clean verdict from a reading that never happened.
    panel.push(indicators::interleaving::analyze(repo, language));
    // path_cover, additive: the fewest end-to-end runs that walk every branch.
    panel.push(indicators::path_cover::analyze(repo, language));
    panel.push(indicators::absolute_paths::analyze(repo)); // additive
    // L1.20, which RUNS the audited project's suite.
    //
    // A row is pushed either way, and the two reasons are DIFFERENT. A caller that
    // declined to run tests is not the same fact as a harness that cannot, and letting the
    // declined case fall through to the canonical reason would have said "not ported yet"
    // about an indicator that is ported and was simply not asked for.
    let reading = if exec_tests {
        test_determinism(repo, language)
    } else {
        // The reference's own words for the same refusal, so the two panels agree. A
        // clearer sentence is a change to make in the reference first.
        Reading { value: "not run".into(), band: "n/a".into(),
                  details: "test execution disabled".into() }
    };
    panel.push(Indicator {
        code: "L1.20".into(),
        label: "test-determinism".into(),
        value: reading.value,
        band: reading.band,
        details: reading.details,
    });
    panel
}

/// The panel as printed: one row per canonical indicator, measured or with its reason.
pub fn analyze(repo: &Path, language: &str, exec_tests: bool) -> Vec<Indicator> {
    coverage::reconcile(measured(repo, language, exec_tests))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The defect, at the level a consumer meets it. On a real repository the printed panel
    /// must carry every canonical code. Before the fix it carried 15 of 22 and said nothing
    /// about the other seven.
    #[test]
    fn the_printed_panel_covers_the_canonical_set() {
        let repo = Path::new(env!("CARGO_MANIFEST_DIR"));
        let codes: Vec<String> = analyze(repo, "rust", false).iter().map(|i| i.code.clone()).collect();
        for (code, _) in coverage::CANONICAL {
            assert!(codes.iter().any(|c| c == code), "{code} missing from the printed panel");
        }
    }

    /// The other direction, which is the one that rots quietly: an indicator this binary
    /// computes but the canonical set does not declare would be dropped from the output.
    /// Porting L1.18 without adding it to CANONICAL would compute the right answer and
    /// print nothing, so this test fails the moment the two lists drift apart.
    #[test]
    fn every_measured_indicator_is_declared_canonical() {
        let repo = Path::new(env!("CARGO_MANIFEST_DIR"));
        for ind in measured(repo, "rust", false) {
            assert!(
                coverage::declared(&ind.code).is_some(),
                "{} is computed but not declared in CANONICAL, so it would be dropped",
                ind.code
            );
        }
    }

    /// The canonical table is a claim about this binary, and a claim that drifts is worse
    /// than no claim. Every member of it must actually turn up in a real run.
    ///
    /// The table used to carry a per-indicator coverage flag and this test checked only the
    /// members flagged Measured. With L1.14 ported the flag has one value left, so it is
    /// gone and every member is checked.
    #[test]
    fn every_canonical_indicator_is_actually_produced() {
        let repo = Path::new(env!("CARGO_MANIFEST_DIR"));
        let produced: Vec<String> = measured(repo, "rust", false).iter().map(|i| i.code.clone()).collect();
        for (code, _) in coverage::CANONICAL {
            assert!(
                produced.iter().any(|c| c == code),
                "{code} is declared canonical but no run produced it"
            );
        }
    }
}
