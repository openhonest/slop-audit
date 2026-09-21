//! JavaScript and TypeScript determinism, whose runner is named in a MANIFEST rather than
//! by a path on disk.
//!
//! Its own file because the first question it asks is not which command to run but whether
//! this project's runner can be shuffled at all. A score over runs that were never
//! reordered would be a number nobody earned, so a project on a runner this harness cannot
//! drive is refused with that runner named.

use super::determinism::{not_measured, tally, Attempt, Reading, RunWords};
use super::runners::{command_for, first_line, which};
use crate::runtime::{run_untrusted, TIMED_OUT};
use std::path::Path;

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
        let filled = command_for(command, attempt, "");
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
