//! What each language RUNS to produce a coverage report, and what it refuses before it
//! runs anything. Split from `runtime::coverage`, which decides what a report says.
//!
//! EXECUTES THE AUDITED PROJECT'S CODE, by the decision of 2026-09-21. Every refusal here
//! comes BEFORE a number: a missing toolchain, a suite that would not build, a coverage
//! tool the project has not enabled. Reporting nought for any of those would publish a
//! fact about the measurement as a fact about the code.

use super::coverage::{
    c8_totals, cobertura_totals, coveragepy_totals, jacoco_totals, json_object, json_string,
    go_total, simplecov_totals, verdict, CoverageWords, Totals,
};
use crate::runtime::determinism::{not_measured, Reading};
use crate::runtime::runners::{
    first_line, python_interpreter, ran_tests, runner_for, variant_for, which,
};
use crate::runtime::{run_untrusted, TIMED_OUT};
use std::path::Path;

/// A JaCoCo-instrumented pom, shared with the determinism live test rather than written
/// twice. Two copies of one fixture is two things to keep in step.
#[cfg(test)]
const JACOCO_POM: &str = include_str!("../../tests/fixtures/jacoco-pom.xml");

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

/// L1.19 for Ruby: SimpleCov branch coverage from the suite's own resultset.
///
/// SimpleCov CANNOT BE INJECTED from outside. It has to be started in the project's own
/// test helper, before anything it measures is required, so a project that has not done
/// that is refused with the line a reader would add rather than measured at nought.
pub fn ruby_coverage(repo: &Path, timeout_seconds: f64, version: &str) -> Reading {
    if which("bundle").is_none() || which("ruby").is_none() {
        return not_measured("needs Ruby and Bundler (ruby, bundle) in PATH");
    }
    let ruby = runner_for("ruby").expect("ruby has a row");
    let Some(variant) = variant_for(ruby, repo) else {
        return not_measured(
            "no RSpec (spec/, .rspec, or rspec in Gemfile.lock) or Minitest \
             (test/ + Rakefile) suite detected");
    };
    // The coverage run takes no seed: one run, and the resultset it leaves behind.
    let command: Vec<String> = variant.command.iter()
        .filter(|part| !part.contains("{seed}") && **part != "--seed" && **part != "--order"
                       && **part != "random")
        .map(|part| part.to_string())
        .collect();
    let resultset = repo.join("coverage").join(".resultset.json");
    let _ = std::fs::remove_file(&resultset);
    let run = run_untrusted(&command, repo, &[], timeout_seconds);

    let words = CoverageWords {
        no_report: "Ruby branch coverage needs SimpleCov started in the suite's test \
                    helper (coverage/.resultset.json not produced)",
        nothing_to_cover: "SimpleCov recorded no branch data; add \
                           `SimpleCov.enable_coverage :branch` before `SimpleCov.start`",
        how: "SimpleCov branches",
        toolchain: version.to_string(),
        substitution: "",
    };
    if run.status == TIMED_OUT || !resultset.exists() {
        return verdict(None, run.status, &words, timeout_seconds);
    }
    let Ok(json) = std::fs::read_to_string(&resultset) else {
        return not_measured("SimpleCov resultset was unreadable");
    };
    // Absent means the resultset carries no branch data at all, which is what SimpleCov
    // writes when a project has not enabled branch coverage. Zero is the nothing-to-cover
    // sentence, and the two send a reader to the same one line of their test helper.
    let totals = simplecov_totals(&json).unwrap_or(Totals { covered: 0, total: 0 });
    verdict(Some(totals), run.status, &words, timeout_seconds)
}

/// L1.19 for JavaScript and TypeScript: branch coverage from c8 over the project's own
/// test command.
pub fn js_coverage(repo: &Path, timeout_seconds: f64, runtime: &str) -> Reading {
    if which("npx").is_none() || which("node").is_none() {
        return not_measured("needs node and npx in PATH");
    }
    let Ok(manifest) = std::fs::read_to_string(repo.join("package.json")) else {
        return not_measured("no package.json found");
    };
    let Some(scripts) = json_object(&manifest, "scripts") else {
        return not_measured("no test command in package.json (scripts.test)");
    };
    let Some(test_command) = json_string(scripts, "test") else {
        return not_measured("no test command in package.json (scripts.test)");
    };
    if !repo.join("node_modules").is_dir() {
        return not_measured(
            "node_modules is not installed; this harness runs a project's own suite and \
             installs nothing");
    }

    let scratch = scratch_dir("jscov");
    let reports = scratch.join("reports");
    let _ = std::fs::create_dir_all(&reports);
    let mut command: Vec<String> = vec![
        "npx".into(), "--no-install".into(), "c8".into(),
        "--reporter=json-summary".into(),
        format!("--reports-dir={}", reports.display()),
        format!("--temp-directory={}", scratch.join("tmp").display()),
    ];
    // The project's own test command, split the way a shell would split it.
    command.extend(test_command.split_whitespace().map(str::to_string));
    let run = run_untrusted(&command, repo, &[], timeout_seconds);

    let words = CoverageWords {
        no_report: "coverage produced no data",
        nothing_to_cover: "c8 reported no branches to cover",
        how: "c8 branch counters (V8)",
        toolchain: runtime.to_string(),
        substitution: "",
    };
    let summary = reports.join("coverage-summary.json");
    if run.status == TIMED_OUT || !summary.exists() {
        let status = run.status;
        let output = run.output();
        let _ = std::fs::remove_dir_all(&scratch);
        if status == TIMED_OUT {
            return verdict(None, status, &words, timeout_seconds);
        }
        // c8 writes the summary for every file that ran, even when some tests fail. No
        // summary means the suite did not build or ran no tests.
        return not_measured(format!(
            "coverage produced no data (test command exit {status}): {}",
            first_line(&output)));
    }
    let totals = std::fs::read_to_string(&summary).ok().and_then(|json| c8_totals(&json));
    let _ = std::fs::remove_dir_all(&scratch);
    match totals {
        None => not_measured("coverage summary had no branch totals"),
        some => verdict(some, run.status, &words, timeout_seconds),
    }
}

/// L1.19 for Python: branch coverage from coverage.py over the project's own suite.
///
/// The suite runs under the PROJECT'S interpreter, because the package and its test
/// dependencies live there.
pub fn python_coverage(repo: &Path, timeout_seconds: f64) -> Reading {
    let Some((interpreter, provenance)) = python_interpreter(repo) else {
        return not_measured("needs a Python interpreter in PATH");
    };
    let scratch = scratch_dir("pycov");
    let _ = std::fs::create_dir_all(&scratch);
    let data_file = scratch.join(".coverage");
    let report_file = scratch.join("coverage.json");
    let env = [("COVERAGE_FILE".to_string(), data_file.display().to_string())];

    let run = run_untrusted(
        &[interpreter.clone(), "-m".into(), "coverage".into(), "run".into(),
          "--branch".into(), "-m".into(), "pytest".into(), "-q".into(),
          "-p".into(), "no:cacheprovider".into()],
        repo, &env, timeout_seconds);

    let words = CoverageWords {
        no_report: "coverage produced no data",
        nothing_to_cover: "coverage.py found no branches to cover",
        how: "coverage.py branch totals",
        toolchain: provenance.clone(),
        substitution: "",
    };
    // pytest's own exit codes say whether the suite ran at all, and a percentage over a
    // run that never happened reads as real-but-terrible coverage.
    if run.status == TIMED_OUT {
        let _ = std::fs::remove_dir_all(&scratch);
        return verdict(None, TIMED_OUT, &words, timeout_seconds);
    }
    if run.status != 0 && run.status != 1 {
        let why = match run.status {
            2 => "the run was interrupted",
            3 => "pytest hit an internal error",
            4 => "pytest usage or collection error",
            5 => "pytest collected no tests",
            _ => "pytest exited with an unrecognised code",
        };
        let status = run.status;
        let _ = std::fs::remove_dir_all(&scratch);
        return not_measured(format!(
            "the test suite did not complete a valid run ({why}, exit {status}); \
             coverage not measured"));
    }
    // Our own step, over data the run wrote: fast, and not the audited project's code.
    let _ = run_untrusted(
        &[interpreter, "-m".into(), "coverage".into(), "json".into(),
          "-o".into(), report_file.display().to_string()],
        repo, &env, timeout_seconds.min(120.0));
    let totals = std::fs::read_to_string(&report_file).ok()
        .and_then(|json| coveragepy_totals(&json));
    let _ = std::fs::remove_dir_all(&scratch);
    match totals {
        None => not_measured("coverage report was unreadable"),
        some => verdict(some, run.status, &words, timeout_seconds),
    }
}

#[cfg(test)]
mod live_coverage {
    //! The three remaining runners against real projects they build themselves.

    use super::*;

    #[test]
    fn a_real_ruby_suite_measures_its_branches_through_simplecov() {
        if which("bundle").is_none() || which("ruby").is_none() {
            eprintln!("skipped: ruby or bundler is not on PATH");
            return;
        }
        let root = scratch_dir("rbcov");
        std::fs::create_dir_all(root.join("lib")).unwrap();
        std::fs::create_dir_all(root.join("test")).unwrap();
        // rake, minitest and simplecov are DECLARED: bundler hides the default gems.
        std::fs::write(root.join("Gemfile"),
            "source \"https://rubygems.org\"\ngem \"rake\"\ngem \"minitest\"\ngem \"simplecov\"\n")
            .unwrap();
        std::fs::write(root.join("Rakefile"),
            "require \"rake/testtask\"\nRake::TestTask.new(:test) do |t|\n\
             \x20 t.libs << \"lib\" << \"test\"\n\
             \x20 t.test_files = FileList[\"test/**/*_test.rb\"]\nend\n").unwrap();
        std::fs::write(root.join("lib").join("band.rb"),
            "def band(n)\n  return \"neg\" if n < 0\n  return \"zero\" if n == 0\n  \"pos\"\nend\n")
            .unwrap();
        // SimpleCov started BEFORE the library is required, which is the only way it can
        // see the code it measures.
        std::fs::write(root.join("test").join("band_test.rb"),
            "require \"simplecov\"\nSimpleCov.enable_coverage :branch\nSimpleCov.start\n\
             require \"minitest/autorun\"\nrequire \"band\"\n\
             class BandTest < Minitest::Test\n\
             \x20 def test_positive\n    assert_equal \"pos\", band(3)\n  end\nend\n").unwrap();
        let installed = run_untrusted(
            &["bundle".into(), "install".into(), "--path".into(), "vendor/bundle".into()],
            &root, &[], 600.0);
        if installed.status != 0 {
            let _ = std::fs::remove_dir_all(&root);
            eprintln!("skipped: the bundle would not install");
            return;
        }
        let reading = ruby_coverage(&root, 600.0, "a ruby");
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(reading.value, "50.0", "{}", reading.details);
        assert!(reading.details.contains("2/4 decision branches"), "{}", reading.details);
    }

    #[test]
    fn a_ruby_suite_without_simplecov_is_refused_with_the_line_to_add() {
        // SimpleCov cannot be injected from outside: it has to be started in the project's
        // own test helper. Reporting nought would read as terrible coverage rather than as
        // coverage nobody measured.
        if which("bundle").is_none() || which("ruby").is_none() {
            eprintln!("skipped: ruby or bundler is not on PATH");
            return;
        }
        let root = scratch_dir("rbnocov");
        std::fs::create_dir_all(root.join("lib")).unwrap();
        std::fs::create_dir_all(root.join("test")).unwrap();
        std::fs::write(root.join("Gemfile"),
            "source \"https://rubygems.org\"\ngem \"rake\"\ngem \"minitest\"\n").unwrap();
        std::fs::write(root.join("Rakefile"),
            "require \"rake/testtask\"\nRake::TestTask.new(:test) do |t|\n\
             \x20 t.libs << \"lib\" << \"test\"\n\
             \x20 t.test_files = FileList[\"test/**/*_test.rb\"]\nend\n").unwrap();
        std::fs::write(root.join("lib").join("band.rb"),
            "def band(n)\n  return \"neg\" if n < 0\n  \"pos\"\nend\n").unwrap();
        std::fs::write(root.join("test").join("band_test.rb"),
            "require \"minitest/autorun\"\nrequire \"band\"\n\
             class BandTest < Minitest::Test\n\
             \x20 def test_positive\n    assert_equal \"pos\", band(3)\n  end\nend\n").unwrap();
        let installed = run_untrusted(
            &["bundle".into(), "install".into(), "--path".into(), "vendor/bundle".into()],
            &root, &[], 600.0);
        if installed.status != 0 {
            let _ = std::fs::remove_dir_all(&root);
            eprintln!("skipped: the bundle would not install");
            return;
        }
        let reading = ruby_coverage(&root, 600.0, "a ruby");
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(reading.band, "n/a", "{}", reading.details);
        assert!(reading.details.contains("SimpleCov"), "{}", reading.details);
    }

    #[test]
    fn a_real_python_suite_measures_its_branches() {
        let Some(uv) = which("uv") else {
            eprintln!("skipped: uv is not on PATH");
            return;
        };
        let root = scratch_dir("pyruncov");
        std::fs::create_dir_all(&root).unwrap();
        // Three arms, a test reaching two, so the figure is short by construction.
        std::fs::write(root.join("band.py"),
            "def band(n):\n    if n < 0:\n        return \"neg\"\n\
             \x20   if n == 0:\n        return \"zero\"\n    return \"pos\"\n").unwrap();
        std::fs::write(root.join("test_band.py"),
            "from band import band\n\n\ndef test_positive():\n    assert band(3) == \"pos\"\n")
            .unwrap();
        let made = run_untrusted(
            &[uv.display().to_string(), "venv".into(), ".venv".into()], &root, &[], 300.0);
        let installed = run_untrusted(
            &[uv.display().to_string(), "pip".into(), "install".into(), "--quiet".into(),
              "pytest".into(), "coverage".into()],
            &root, &[("VIRTUAL_ENV".into(), root.join(".venv").display().to_string())],
            600.0);
        if made.status != 0 || installed.status != 0 {
            let _ = std::fs::remove_dir_all(&root);
            eprintln!("skipped: the environment would not build");
            return;
        }
        let reading = python_coverage(&root, 600.0);
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(reading.value, "50.0", "{}", reading.details);
        assert!(reading.details.contains("2/4 decision branches"), "{}", reading.details);
    }

    #[test]
    fn a_python_suite_that_collects_nothing_is_refused_rather_than_scored() {
        // A percentage over a run that never happened reads as real-but-terrible coverage.
        let Some(uv) = which("uv") else {
            eprintln!("skipped: uv is not on PATH");
            return;
        };
        let root = scratch_dir("pynocov");
        std::fs::create_dir_all(&root).unwrap();
        std::fs::write(root.join("band.py"), "def band(n):\n    return n\n").unwrap();
        let made = run_untrusted(
            &[uv.display().to_string(), "venv".into(), ".venv".into()], &root, &[], 300.0);
        let installed = run_untrusted(
            &[uv.display().to_string(), "pip".into(), "install".into(), "--quiet".into(),
              "pytest".into(), "coverage".into()],
            &root, &[("VIRTUAL_ENV".into(), root.join(".venv").display().to_string())],
            600.0);
        if made.status != 0 || installed.status != 0 {
            let _ = std::fs::remove_dir_all(&root);
            eprintln!("skipped: the environment would not build");
            return;
        }
        let reading = python_coverage(&root, 600.0);
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(reading.band, "n/a", "{}", reading.details);
        assert!(reading.details.contains("collected no tests"), "{}", reading.details);
    }
}
