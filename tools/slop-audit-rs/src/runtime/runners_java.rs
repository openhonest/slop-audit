//! Java determinism, which reads the reports its runner writes rather than the log its own
//! command suppressed.
//!
//! Its own file because it is the one row that can read neither output nor exit code.
//! Both Maven commands pass a quiet flag, to keep an untrusted project's build chatter out
//! of the result, and that flag deletes the summary line every other row looks for. So the
//! console said nothing, the reader took nothing as no tests, and every Maven project came
//! back as a suite that never executed.
//!
//! One fact with two owners: the console log and the XML reports both claimed to say
//! whether tests ran, and the quiet flag silently retired one of them.

use super::determinism::{not_measured, tally, Attempt, Reading, RunWords};
use super::runners::which;
use crate::runtime::{run_untrusted, TIMED_OUT};
use std::path::Path;

// --------------------------------------------------------------------------
// Java, which reads the reports its runner writes rather than the log it suppressed.
// --------------------------------------------------------------------------

/// Surefire's own totals, the attributes it writes on every test-suite element.
const SUREFIRE_COUNTED: &[&str] = &["tests", "failures", "errors", "skipped"];

/// Every result file Surefire wrote, across every module.
///
/// Globbed over the whole tree so a multi-module build counts all its modules and not just
/// its root.
fn surefire_reports(repo: &Path) -> Vec<std::path::PathBuf> {
    let mut found = Vec::new();
    let mut stack = vec![repo.to_path_buf()];
    while let Some(dir) = stack.pop() {
        let Ok(entries) = std::fs::read_dir(&dir) else { continue };
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                stack.push(path);
            } else if path.parent().and_then(|p| p.file_name())
                          .and_then(|n| n.to_str()) == Some("surefire-reports")
                && path.file_name().and_then(|n| n.to_str())
                       .map(|n| n.starts_with("TEST-") && n.ends_with(".xml"))
                       .unwrap_or(false) {
                found.push(path);
            }
        }
    }
    found.sort();
    found
}

/// Delete the previous attempt's results before the next one starts.
///
/// Maven leaves them on disk. Without this, a seed that fails to compile inherits the
/// reports the seed before it wrote, and a suite that never ran this time reads as one
/// that ran and passed.
fn clear_surefire_reports(repo: &Path) {
    for report in surefire_reports(repo) {
        let _ = std::fs::remove_file(report);
    }
}

/// What Surefire recorded about the attempt that just finished: the counts line, or a
/// sentence saying why there is none.
///
/// Absent means no report at all, which is Maven never getting as far as running the
/// suite. Unreadable means it did and we cannot tell what happened, which is a broken
/// MEASUREMENT and not a broken project. They are different news and reach a reader
/// differently.
pub fn surefire_evidence(repo: &Path) -> Result<String, &'static str> {
    let reports = surefire_reports(repo);
    if reports.is_empty() {
        return Err("Surefire wrote no test report");
    }
    let mut totals = [0i64; 4];
    for report in reports {
        let Ok(xml) = std::fs::read_to_string(&report) else {
            return Err("a Surefire test report was unreadable");
        };
        let mut counted = false;
        for element in crate::runtime::coverage::xml_elements(&xml) {
            if element.name != "testsuite" {
                continue;
            }
            counted = true;
            for (index, name) in SUREFIRE_COUNTED.iter().enumerate() {
                totals[index] += crate::runtime::coverage::xml_attr(element.attrs, name)
                    .and_then(|v| v.parse::<i64>().ok())
                    .unwrap_or(0);
            }
        }
        if !counted {
            return Err("a Surefire test report was unreadable");
        }
    }
    if totals[0] == 0 {
        return Err("Surefire wrote no test report");
    }
    Ok(format!("Tests run: {}, Failures: {}, Errors: {}, Skipped: {}",
               totals[0], totals[1], totals[2], totals[3]))
}

/// L1.20 for Java.
///
/// Its own entry point because what it reads is not the output: the quiet flag on its own
/// command deletes the line every other row looks for.
pub fn java_determinism(repo: &Path, runs: usize, timeout_seconds: f64,
                        jdk: &str) -> Reading {
    let wrapper = repo.join("mvnw");
    let maven = if wrapper.exists() {
        wrapper.display().to_string()
    } else if which("mvn").is_some() {
        "mvn".to_string()
    } else {
        return not_measured("needs Maven (mvn) on PATH or a ./mvnw wrapper in the repo");
    };
    if !repo.join("pom.xml").exists() {
        if repo.join("build.gradle").exists() || repo.join("build.gradle.kts").exists() {
            return not_measured("Gradle Java projects not yet supported by this harness");
        }
        return not_measured("needs a Maven build (no pom.xml found)");
    }

    let words = RunWords {
        unit: "seed",
        timed_out: "a seed timed out",
        no_runs: "no randomized-order runs were made; determinism not measured",
        describe: format!("randomized-order runs passed cleanly (under {jdk})"),
    };
    let attempts = (1..=runs).map(|_| {
        clear_surefire_reports(repo);
        let finished = run_untrusted(
            &[maven.clone(), "-q".into(), "-Dsurefire.runOrder=random".into(), "test".into()],
            repo, &[], timeout_seconds);
        let evidence = surefire_evidence(repo);
        Attempt {
            status: finished.status,
            isolation: finished.isolation,
            ran_tests: finished.status != TIMED_OUT && evidence.is_ok(),
            summary: evidence.clone().unwrap_or_default(),
            why_it_did_not_run: format!("{} under {jdk}",
                                        evidence.err().unwrap_or("")),
        }
    });
    tally(attempts, &words, timeout_seconds)
}

#[cfg(test)]
mod java_tests {
    use super::*;

    fn report_dir(name: &str) -> std::path::PathBuf {
        let root = std::env::temp_dir().join(format!("slop-sf-{}-{name}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(root.join("target").join("surefire-reports")).unwrap();
        root
    }

    fn write_report(root: &Path, name: &str, body: &str) {
        std::fs::write(
            root.join("target").join("surefire-reports").join(format!("TEST-{name}.xml")),
            body).unwrap();
    }

    #[test]
    fn the_counts_come_from_the_reports_not_from_the_console() {
        // Both Maven commands pass a quiet flag, which suppresses the summary line a
        // marker reader looks for. Every Maven project reported a suite that never ran.
        let root = report_dir("counts");
        write_report(&root, "band.BandTest",
            r#"<testsuite name="band.BandTest" tests="7" failures="2" errors="1" skipped="0"/>"#);
        let evidence = surefire_evidence(&root);
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(evidence, Ok("Tests run: 7, Failures: 2, Errors: 1, Skipped: 0".into()));
    }

    #[test]
    fn every_module_in_a_multi_module_build_is_counted() {
        let root = report_dir("multi");
        std::fs::create_dir_all(root.join("web").join("target").join("surefire-reports"))
            .unwrap();
        write_report(&root, "a.ATest",
            r#"<testsuite name="a" tests="3" failures="0" errors="0" skipped="1"/>"#);
        std::fs::write(
            root.join("web").join("target").join("surefire-reports").join("TEST-b.xml"),
            r#"<testsuite name="b" tests="4" failures="1" errors="0" skipped="0"/>"#).unwrap();
        let evidence = surefire_evidence(&root);
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(evidence, Ok("Tests run: 7, Failures: 1, Errors: 0, Skipped: 1".into()));
    }

    #[test]
    fn no_report_and_an_unreadable_one_are_different_news() {
        // One means Maven never got as far as running the suite. The other means it did
        // and we cannot tell what happened, which is a broken measurement rather than a
        // broken project.
        let absent = report_dir("absent");
        assert_eq!(surefire_evidence(&absent), Err("Surefire wrote no test report"));
        let _ = std::fs::remove_dir_all(&absent);

        let broken = report_dir("broken");
        write_report(&broken, "band.BandTest", "<testsuite tests=");
        assert_eq!(surefire_evidence(&broken), Err("a Surefire test report was unreadable"));
        let _ = std::fs::remove_dir_all(&broken);
    }

    #[test]
    fn a_report_of_no_tests_is_a_suite_that_did_not_run() {
        let root = report_dir("empty");
        write_report(&root, "band.BandTest",
            r#"<testsuite name="band" tests="0" failures="0" errors="0" skipped="0"/>"#);
        let evidence = surefire_evidence(&root);
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(evidence, Err("Surefire wrote no test report"));
    }

    #[test]
    fn the_previous_attempts_reports_are_cleared_before_the_next_one() {
        // Maven leaves them on disk. A seed that fails to compile would otherwise inherit
        // the counts of the seed before it and be scored as a suite that ran and passed.
        let root = report_dir("stale");
        write_report(&root, "band.BandTest",
            r#"<testsuite name="band" tests="7" failures="0" errors="0" skipped="0"/>"#);
        clear_surefire_reports(&root);
        let evidence = surefire_evidence(&root);
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(evidence, Err("Surefire wrote no test report"));
    }
}

#[cfg(test)]
mod java_live {
    //! The Java row against a real Maven project it builds itself.
    //!
    //! This is the row whose defect this session found: a suite that ran and passed was
    //! reported as having executed none, because the quiet flag on its own command deleted
    //! the line the reader looked for. A live test is the only kind that would have caught
    //! it, and there was none.

    use super::*;

    const POM: &str = include_str!("../../tests/fixtures/jacoco-pom.xml");

    fn maven_project() -> Option<std::path::PathBuf> {
        which("mvn")?;
        let root = std::env::temp_dir().join(format!(
            "slop-jvdet-{}-{}", std::process::id(),
            std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_nanos()).unwrap_or(0)));
        let _ = std::fs::remove_dir_all(&root);
        let main = root.join("src").join("main").join("java").join("band");
        let test = root.join("src").join("test").join("java").join("band");
        std::fs::create_dir_all(&main).ok()?;
        std::fs::create_dir_all(&test).ok()?;
        std::fs::write(root.join("pom.xml"), POM).ok()?;
        std::fs::write(main.join("Band.java"),
            "package band;\n\npublic final class Band {\n\
             \x20   public static String classify(int n) {\n\
             \x20       if (n < 0) { return \"neg\"; }\n\
             \x20       return \"pos\";\n\
             \x20   }\n}\n").ok()?;
        std::fs::write(test.join("BandTest.java"),
            "package band;\n\nimport static org.junit.jupiter.api.Assertions.assertEquals;\n\
             import org.junit.jupiter.api.Test;\n\n\
             class BandTest {\n\
             \x20   @Test void positive() { assertEquals(\"pos\", Band.classify(3)); }\n}\n")
            .ok()?;
        Some(root)
    }

    #[test]
    fn a_real_maven_suite_that_passes_is_the_whole_count_and_not_a_refusal() {
        // The defect, at the level a reader meets it. Against the harness as it stood,
        // this read "the suite did not run".
        let Some(root) = maven_project() else {
            eprintln!("skipped: mvn is not on PATH");
            return;
        };
        let reading = java_determinism(&root, 3, 900.0, "a jdk");
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(reading.value, "3/3", "{}", reading.details);
        assert_eq!(reading.band, "Healthy");
        assert!(!reading.details.contains("did not run"), "{}", reading.details);
    }

    #[test]
    fn a_real_module_with_no_tests_is_refused_rather_than_scored() {
        let Some(root) = maven_project() else {
            eprintln!("skipped: mvn is not on PATH");
            return;
        };
        let _ = std::fs::remove_dir_all(root.join("src").join("test"));
        let reading = java_determinism(&root, 3, 900.0, "a jdk");
        let _ = std::fs::remove_dir_all(&root);
        assert_eq!(reading.band, "n/a", "{}", reading.details);
        assert!(reading.details.contains("did not run"), "{}", reading.details);
    }
}
