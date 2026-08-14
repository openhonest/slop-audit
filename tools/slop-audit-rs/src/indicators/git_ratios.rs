//! L1.1-L1.8 git-log commit-ratio indicators. Ported from
//! l1_analyzer.indicators.compute_git_indicators (+ _test_to_prod_ratio for L1.8);
//! validated equal on a repo with git history.
//!
//! Shape: `analyze(repo)` runs `git log --numstat` once and returns all eight
//! Indicators in order (L1.1..L1.8). `l1_01`..`l1_08` are thin wrappers that
//! return a single Indicator each (each re-runs the shared pass); they exist so a
//! caller can pull one indicator by name, matching the fan-out convention.

use crate::{band, source_files, Indicator};
use std::path::Path;
use std::process::Command;

// Extensions (with leading dot) that mark a touched path as documentation or code,
// mirroring l1_analyzer.indicators._classify_file. Doc is tested first.
const DOC_EXTS: &[&str] = &[".md", ".rst", ".adoc", ".txt", ".feature"];
const CODE_EXTS: &[&str] = &[
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".java", ".rb", ".rs", ".c", ".h",
    ".cpp", ".cs", ".kt", ".swift", ".php", "dockerfile", ".yml", ".yaml", ".json", ".toml",
];

// Source extensions (no leading dot; matches source_files' lowercased extension)
// for the L1.8 test/prod LOC split. Mirrors l1_analyzer.indicators._SRC_EXTS.
const SRC_EXTS: &[&str] = &[
    "py", "rs", "c", "h", "cpp", "js", "jsx", "mjs", "cjs", "ts", "tsx", "java", "cs",
    "go", "rb", "kt", "swift", "php",
];

const TEST_PATH_MARKERS: &[&str] = &["test", "tests", "spec", "specs", "__tests__"];
// A .NET test project is a sibling directory named <Project>.Tests, never a plain
// `tests/` parent. Mirrors _TEST_DOTTED_MARKERS.
const TEST_DOTTED_MARKERS: &[&str] = &["test", "tests", "spec", "specs"];
// The .NET and JVM file convention, in its original casing. Mirrors _TEST_STEM_SUFFIXES;
// the capital is what keeps `Latest.java` out.
const TEST_STEM_SUFFIXES: &[&str] = &["Test", "Tests", "Spec", "Specs"];

/// Format a float the way Python's `str(round(value, ndigits))` / json.dumps does:
/// rounded to `ndigits`, trailing zeros stripped, but always at least one decimal.
fn py_num(value: f64, ndigits: usize) -> String {
    let s = format!("{:.*}", ndigits, value);
    if !s.contains('.') {
        return s;
    }
    let mut t = s.trim_end_matches('0').to_string();
    if t.ends_with('.') {
        t.push('0');
    }
    t
}

/// Mirrors l1_analyzer.indicators._classify_file: "doc" | "code" | "other".
fn classify_file(path: &str) -> &'static str {
    let p = path.to_lowercase();
    if DOC_EXTS.iter().any(|e| p.ends_with(e)) {
        return "doc";
    }
    if CODE_EXTS.iter().any(|e| p.ends_with(e)) {
        return "code";
    }
    "other"
}

/// Mirrors l1_analyzer.indicators._is_test_file.
///
/// Two arms beyond the original ones carry the .NET and JVM conventions. Without them
/// L1.8 reported Newtonsoft.Json as "0 test / 193720 production LOC" for a repository
/// with 704 test files: the exact inverse of the truth, on a scored indicator.
fn is_test_file(path: &Path) -> bool {
    let parts_hit = path.components().any(|c| {
        c.as_os_str()
            .to_str()
            .map(|s| {
                let lowered = s.to_lowercase();
                TEST_PATH_MARKERS.contains(&lowered.as_str())
                    || TEST_DOTTED_MARKERS.iter().any(|m| lowered.ends_with(&format!(".{m}")))
            })
            .unwrap_or(false)
    });
    if parts_hit {
        return true;
    }
    let name = path
        .file_name()
        .and_then(|n| n.to_str())
        .map(|s| s.to_lowercase())
        .unwrap_or_default();
    if name.starts_with("test_") {
        return true;
    }
    let suffix = match path.extension().and_then(|e| e.to_str()) {
        Some(e) => format!(".{}", e.to_lowercase()),
        None => String::new(),
    };
    if name.ends_with(&format!("_test{suffix}"))
        || name.ends_with(&format!(".test{suffix}"))
        || name.ends_with(&format!(".spec{suffix}"))
    {
        return true;
    }
    // Path.stem: the file name with its final extension removed, original casing.
    let stem = path.file_stem().and_then(|s| s.to_str()).unwrap_or("");
    TEST_STEM_SUFFIXES.iter().any(|s| stem.ends_with(s))
}

/// L1.8: lines of test code / lines of production code.
/// Mirrors l1_analyzer.indicators._test_to_prod_ratio.
fn test_to_prod_ratio(repo: &Path) -> Indicator {
    let mut test_loc = 0usize;
    let mut prod_loc = 0usize;
    for (path, text) in source_files(repo, SRC_EXTS) {
        let n = crate::py_splitlines(&text).len();
        if is_test_file(&path) {
            test_loc += n;
        } else {
            prod_loc += n;
        }
    }
    if prod_loc == 0 {
        return Indicator {
            code: "L1.8".into(),
            label: "test-to-prod-ratio".into(),
            value: "n/a".into(),
            band: "n/a".into(),
            details: "no production source files found".into(),
        };
    }
    let ratio = test_loc as f64 / prod_loc as f64;
    Indicator {
        code: "L1.8".into(),
        label: "test-to-prod-ratio".into(),
        value: py_num(ratio, 2),
        band: band(ratio, 0.4, 0.1, true).into(),
        details: format!("{test_loc} test / {prod_loc} production LOC"),
    }
}

const GIT_LABELS: [&str; 8] = [
    "doc-only-commits",
    "code-only-commits",
    "mixed-commits",
    "doc-line-ratio",
    "delete-add-ratio",
    "net-negative-commits",
    "high-delete-commits",
    "test-to-prod-ratio",
];

/// Build the eight n/a results used for both the git-failure and no-commits branches.
/// Mirrors the Python dict comprehensions (value 0, band n/a, shared details).
fn all_na(details: &str) -> Vec<Indicator> {
    (1..=8)
        .map(|i| Indicator {
            code: format!("L1.{i}"),
            label: GIT_LABELS[i - 1].into(),
            value: "0".into(),
            band: "n/a".into(),
            details: details.into(),
        })
        .collect()
}

/// Run `git log --numstat` once and return L1.1..L1.8 in order.
pub fn analyze(repo: &Path) -> Vec<Indicator> {
    let mut cmd = Command::new("git");
    cmd.arg("-C")
        .arg(repo)
        .arg("log")
        .arg("--numstat")
        .arg("--pretty=format:COMMIT %H");
    // since/until default to None (unbounded), matching the CLI defaults.

    let output = match cmd.output() {
        Ok(o) if o.status.success() => o,
        Ok(o) => {
            return all_na(&format!("git log failed: {}", o.status));
        }
        Err(error) => {
            return all_na(&format!("git log failed: {error}"));
        }
    };
    let out = String::from_utf8_lossy(&output.stdout);

    let mut total_commits = 0i64;
    let (mut doc_only, mut code_only, mut mixed) = (0i64, 0i64, 0i64);
    let (mut total_added, mut total_deleted) = (0i64, 0i64);
    let (mut doc_added, mut _code_added) = (0i64, 0i64);
    let (mut net_negative_commits, mut high_delete_commits) = (0i64, 0i64);

    let mut current_files: Vec<String> = Vec::new();
    let (mut current_add, mut current_del) = (0i64, 0i64);

    // Closes the in-progress commit into the running tallies. Mirrors close_commit().
    let mut close = |files: &mut Vec<String>, add: &mut i64, del: &mut i64| {
        if files.is_empty() {
            return;
        }
        total_commits += 1;
        let has_doc = files.iter().any(|f| classify_file(f) == "doc");
        let has_code = files.iter().any(|f| classify_file(f) == "code");
        if has_doc && !has_code {
            doc_only += 1;
        } else if has_code && !has_doc {
            code_only += 1;
        } else if has_doc && has_code {
            mixed += 1;
        }
        if *add != 0 || *del != 0 {
            total_added += *add;
            total_deleted += *del;
            if *del > *add {
                net_negative_commits += 1;
            }
            if *add > 0 && (*del as f64 / *add as f64) > 0.4 {
                high_delete_commits += 1;
            }
        }
        files.clear();
        *add = 0;
        *del = 0;
    };

    for line in out.lines() {
        if let Some(_hash) = line.strip_prefix("COMMIT ") {
            close(&mut current_files, &mut current_add, &mut current_del);
            continue;
        }
        if !line.contains('\t') {
            continue;
        }
        let parts: Vec<&str> = line.split('\t').collect();
        if parts.len() < 3 {
            continue;
        }
        let added_s = parts[0];
        let deleted_s = parts[1];
        let path = *parts.last().unwrap();
        current_files.push(path.to_string());
        let a = added_s.parse::<i64>();
        let d = deleted_s.parse::<i64>();
        if let (Ok(a), Ok(d)) = (a, d) {
            // isdigit() in Python is false for negatives; parse succeeds for "-5",
            // but numstat never emits negatives, so this matches in practice.
            if added_s.bytes().all(|b| b.is_ascii_digit())
                && deleted_s.bytes().all(|b| b.is_ascii_digit())
            {
                current_add += a;
                current_del += d;
                match classify_file(path) {
                    "doc" => doc_added += a,
                    "code" => _code_added += a,
                    _ => {}
                }
            }
        }
    }
    close(&mut current_files, &mut current_add, &mut current_del);

    if total_commits == 0 {
        return all_na("no commits in range");
    }

    let tc = total_commits as f64;
    let mut out_ind: Vec<Indicator> = Vec::with_capacity(8);

    let l1 = doc_only as f64 / tc * 100.0;
    out_ind.push(Indicator {
        code: "L1.1".into(),
        label: GIT_LABELS[0].into(),
        value: py_num(l1, 1),
        band: band(l1, 10.0, 1.0, true).into(),
        details: String::new(),
    });

    let l2 = code_only as f64 / tc * 100.0;
    out_ind.push(Indicator {
        code: "L1.2".into(),
        label: GIT_LABELS[1].into(),
        value: py_num(l2, 1),
        band: band(l2, 70.0, 85.0, false).into(),
        details: String::new(),
    });

    let l3 = mixed as f64 / tc * 100.0;
    out_ind.push(Indicator {
        code: "L1.3".into(),
        label: GIT_LABELS[2].into(),
        value: py_num(l3, 1),
        band: band(l3, 12.0, 3.0, true).into(),
        details: String::new(),
    });

    let l4 = if total_added > 0 {
        doc_added as f64 / total_added as f64 * 100.0
    } else {
        0.0
    };
    out_ind.push(Indicator {
        code: "L1.4".into(),
        label: GIT_LABELS[3].into(),
        value: py_num(l4, 1),
        band: band(l4, 25.0, 5.0, true).into(),
        details: format!("{doc_added} doc / {total_added} total lines added"),
    });

    let l5 = if total_added > 0 {
        total_deleted as f64 / total_added as f64 * 100.0
    } else {
        0.0
    };
    out_ind.push(Indicator {
        code: "L1.5".into(),
        label: GIT_LABELS[4].into(),
        value: py_num(l5, 1),
        band: band(l5, 60.0, 30.0, true).into(),
        details: String::new(),
    });

    let l6 = net_negative_commits as f64 / tc * 100.0;
    out_ind.push(Indicator {
        code: "L1.6".into(),
        label: GIT_LABELS[5].into(),
        value: py_num(l6, 1),
        band: band(l6, 15.0, 5.0, true).into(),
        details: String::new(),
    });

    let l7 = high_delete_commits as f64 / tc * 100.0;
    out_ind.push(Indicator {
        code: "L1.7".into(),
        label: GIT_LABELS[6].into(),
        value: py_num(l7, 1),
        band: band(l7, 20.0, 5.0, true).into(),
        details: String::new(),
    });

    out_ind.push(test_to_prod_ratio(repo));
    out_ind
}

pub fn l1_01(repo: &Path) -> Indicator {
    analyze(repo).swap_remove(0)
}
pub fn l1_02(repo: &Path) -> Indicator {
    analyze(repo).swap_remove(1)
}
pub fn l1_03(repo: &Path) -> Indicator {
    analyze(repo).swap_remove(2)
}
pub fn l1_04(repo: &Path) -> Indicator {
    analyze(repo).swap_remove(3)
}
pub fn l1_05(repo: &Path) -> Indicator {
    analyze(repo).swap_remove(4)
}
pub fn l1_06(repo: &Path) -> Indicator {
    analyze(repo).swap_remove(5)
}
pub fn l1_07(repo: &Path) -> Indicator {
    analyze(repo).swap_remove(6)
}
pub fn l1_08(repo: &Path) -> Indicator {
    analyze(repo).swap_remove(7)
}

#[cfg(test)]
mod tests {
    use super::is_test_file;
    use std::path::Path;

    /// The .NET layout: tests live in <Project>.Tests, never a plain tests/ parent.
    /// Without this arm L1.8 reported Newtonsoft.Json as 0 test LOC against 193,720
    /// production LOC, for a repository with 704 test files.
    #[test]
    fn a_dotted_dotnet_test_project_is_test_code() {
        assert!(is_test_file(Path::new("Src/Newtonsoft.Json.Tests/Serialization/X.cs")));
    }

    /// The .NET and JVM file convention, in its original casing.
    #[test]
    fn a_capitalised_test_stem_is_test_code() {
        assert!(is_test_file(Path::new("src/JsonSerializerTests.cs")));
        assert!(is_test_file(Path::new("src/SmokeTest.java")));
        assert!(is_test_file(Path::new("src/ReaderSpec.scala")));
    }

    /// `Latest.java` ends with "test" once lowercased. The capital in the stem arm is
    /// what keeps production code out of the numerator.
    #[test]
    fn a_word_that_merely_ends_in_test_is_production_code() {
        assert!(!is_test_file(Path::new("src/Latest.java")));
        assert!(!is_test_file(Path::new("src/manifest.py")));
        assert!(!is_test_file(Path::new("src/Protest.cs")));
    }

    /// The arms that already worked keep working.
    #[test]
    fn the_original_conventions_still_match() {
        assert!(is_test_file(Path::new("tests/test_thing.py")));
        assert!(is_test_file(Path::new("pkg/thing_test.go")));
        assert!(is_test_file(Path::new("src/thing.spec.ts")));
        assert!(!is_test_file(Path::new("src/thing.ts")));
    }
}
