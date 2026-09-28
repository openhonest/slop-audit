//! L1.14: how many distinct credentials are sitting in the tracked files. Ported from
//! l1_analyzer.secret_scan.
//!
//! Canon (03-layer1-indicators.md, L1.14): "Number of secrets detected by `gitleaks detect
//! --no-git` (or `trufflehog filesystem .`, or `detect-secrets scan`) run against the current
//! tree with the default ruleset. In a regulated enterprise any non-zero count is
//! disqualifying." Bands: 0 Healthy, 1-2 Not Healthy, >= 3 or any confirmed true positive Slop.
//!
//! The Slop band has two arms and this scanner can only evaluate one. The count arm is
//! mechanical. The confirmation arm needs someone to present the credential to its issuer and
//! see whether it is live, which this never does: no network call is made and no credential is
//! validated. The details line says so.
//!
//! A scan that opened no file refuses instead of reporting zero. Zero hits over zero files is
//! the same number as zero hits over a thousand, and `Healthy` is the field a reader looks at,
//! so the count arm read as a clean bill of health on a repository the scanner never opened.
//! It is reachable: this scanner reads the git index rather than the filesystem, so a tree
//! whose files are all untracked excludes every file before it is read. Of all the indicators
//! this is the worst one to fabricate, because its whole job is finding live credentials and
//! the answer it fabricates is "none".
//!
//! The known limits: a repository's own `.gitleaksignore` and any `[allowlist]` in a
//! `.gitleaks.toml` are NOT honoured, so a repository that has already triaged its findings
//! will read higher here than under gitleaks; lock files, minified bundles and vendored trees
//! are skipped; and history is not scanned, matching `--no-git`.

use std::collections::{HashMap, HashSet};
use std::io::Read;
use std::path::Path;

use crate::indicators::secret_rules::{py_suffix, scan_text};
use crate::Indicator;

/// Files whose content is machine-generated hashes or third-party code. gitleaks allowlists
/// the same shapes; without this a lockfile's integrity digests dominate the count.
const SKIP_NAMES: &[&str] = &[
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "Cargo.lock", "poetry.lock",
    "uv.lock", "Gemfile.lock", "composer.lock", "go.sum", "packages.lock.json",
];
const SKIP_SUFFIXES: &[&str] = &[".min.js", ".min.css", ".map", ".svg", ".woff", ".woff2"];
const MAX_BYTES: usize = 4_194_304;

/// The window the binary test reads. git decides the same way and from the same window, so a
/// file that hides its first NUL past this point reads as text here exactly as it does there.
const BINARY_PROBE_BYTES: usize = 8192;

const DOC_SUFFIXES: &[&str] = &[".md", ".markdown", ".rst", ".txt", ".adoc"];

/// One raw match, before matches of the same credential are grouped together.
pub struct Hit {
    pub rule: &'static str,
    pub value: String,
    pub file: String,
    pub line: usize,
    pub in_tests: bool,
    pub in_docs: bool,
}

/// A finding's shape without its content. An audit artefact that reprints the credential has
/// copied the leak into a second file, and so has a parity harness that diffs the values.
pub fn excerpt(value: &str) -> String {
    let head: String = value.chars().take(4).collect();
    format!("{head}... ({} chars)", value.chars().count())
}

/// The file's bytes, or nothing when it is binary, too large, or unreadable.
///
/// THE ORDER IS THE POINT. The binary test used to run after the whole file was read, so every
/// binary file in the tree was read in full and then discarded on the same NUL check. That
/// cost is invisible on a source repository and ruinous on one carrying assets: 45,303
/// committed PNGs across 1.0 GB did not finish scanning in ten minutes.
///
/// Deciding from the first chunk is content-based, which is why there is no extension list
/// here. A skip-list of `.png`, `.jpg`, `.pdf` is a whitelist that every new format re-opens.
fn read_text_bytes(path: &Path, max_bytes: usize) -> Option<Vec<u8>> {
    let mut handle = std::fs::File::open(path).ok()?;
    let mut head = vec![0u8; BINARY_PROBE_BYTES];
    let read = read_fully(&mut handle, &mut head)?;
    head.truncate(read);
    if head.contains(&0) {
        return None;
    }
    let mut raw = head;
    if read == BINARY_PROBE_BYTES {
        let mut rest = vec![0u8; max_bytes - BINARY_PROBE_BYTES + 1];
        let more = read_fully(&mut handle, &mut rest)?;
        rest.truncate(more);
        raw.extend_from_slice(&rest);
    }
    if raw.len() > max_bytes {
        None
    } else {
        Some(raw)
    }
}

/// As many bytes as the buffer holds, or as many as the file has left, mirroring what one
/// `read(n)` returns on a Python file object. A short read from a regular file is not the end
/// of it, which is the one thing `Read::read` may do that `file.read(n)` may not.
fn read_fully(handle: &mut std::fs::File, buffer: &mut [u8]) -> Option<usize> {
    let mut filled = 0usize;
    while filled < buffer.len() {
        match handle.read(&mut buffer[filled..]) {
            Ok(0) => break,
            Ok(n) => filled += n,
            Err(error) if error.kind() == std::io::ErrorKind::Interrupted => continue,
            Err(_) => return None,
        }
    }
    Some(filled)
}

fn scannable(path: &Path) -> bool {
    let Some(name) = path.file_name().and_then(|n| n.to_str()) else { return false };
    !SKIP_NAMES.contains(&name) && !SKIP_SUFFIXES.iter().any(|end| name.ends_with(end))
}

/// The paths git tracks, or nothing when `repo` is not a git working tree.
///
/// The audit question is which credentials are COMMITTED: the canon's antipattern says they
/// "land on the default branch". A gitignored file is not on the branch; it is the auditor's
/// own workstation. Scanning the tree instead of the index charged 92 findings to one
/// repository from `.env` and a gitignored browser-console log, none of which any consumer of
/// that repository can ever see. This is a deliberate deviation from `gitleaks --no-git`,
/// which scans the filesystem, and it is disclosed in the details line.
fn tracked_files(repo: &Path) -> Option<HashSet<String>> {
    let out = std::process::Command::new("git")
        .args(["ls-files", "-z"])
        .current_dir(repo)
        .output()
        .ok()?;
    if !out.status.success() {
        return None;
    }
    Some(String::from_utf8_lossy(&out.stdout)
        .split('\0')
        .filter(|name| !name.is_empty())
        .map(|name| name.to_string())
        .collect())
}

/// L1.14 for one repository, over the current tree (never git history), which is what
/// `gitleaks detect --no-git` means. `lang` is accepted for a uniform indicator signature; a
/// committed credential is the same finding in any language and the provider rules are
/// language-independent.
///
/// The published number counts DISTINCT credentials, not occurrences. One key repeated down 75
/// lines of a log is one leaked key, and the canon's bands (0 / 1-2 / >= 3) only make sense
/// read that way.
/// Every raw match in the repository, with the files scanned, the files refused, and whether
/// the scope was the git index or the whole tree.
///
/// Its own function so the parity harness reads the same walk `analyze` reads. A dump that
/// re-walked the tree its own way would agree with the panel by coincidence.
pub fn walk(repo: &Path) -> (Vec<Hit>, usize, usize, bool) {
    let has_packages = crate::repo_has_packages(repo);
    let tracked = tracked_files(repo);
    // The reference's scope rule takes no `.gitignore` here, so neither does this one: a file
    // git ignores is untracked, and the index filter below has already dropped it.
    let disowned = HashSet::new();
    let mut raw_hits: Vec<Hit> = Vec::new();
    let (mut scanned, mut skipped) = (0usize, 0usize);

    for entry in crate::walk_repo(repo) {
        let path = entry.path();
        if crate::in_ignored_dir(path) || !scannable(path) {
            continue;
        }
        let relpath = match path.strip_prefix(repo) {
            Ok(rel) => rel.to_string_lossy().into_owned(),
            Err(_) => path.file_name().unwrap_or_default().to_string_lossy().into_owned(),
        };
        if let Some(tracked) = tracked.as_ref() {
            if !tracked.contains(&relpath) {
                continue;
            }
        }
        let Some(raw) = read_text_bytes(path, MAX_BYTES) else { skipped += 1; continue };
        scanned += 1;
        let bucket = crate::bucket_reason(path, repo, has_packages, crate::PRODUCTION,
                                          crate::PRODUCTION_BUCKETS, &disowned);
        let in_tests = matches!(bucket, Some("tests") | Some("test"));
        // A test can also be a REGION of a production file. Rust writes its unit tests inside
        // the file they test, so no path names them, and this scanner reported a twenty-
        // character AWS key written as a fixture in this crate's own secret_rules.rs as being
        // in production code. It is not excluded, because a credential is reported wherever it
        // sits; it is LABELLED, which is what this indicator does with every other test.
        let region_lines = if in_tests {
            std::collections::BTreeSet::new()
        } else {
            let suffix = py_suffix(
                path.file_name().and_then(|n| n.to_str()).unwrap_or("")).to_lowercase();
            crate::test_regions::blanked(&raw, &suffix).1
        };
        // A specification, a README or a design note is not production code. The scope helper
        // has a docs bucket but it fires only on a directory literally named `docs`, and this
        // repository's specification lives in `spec/`, so a credential in a fenced block
        // showing an ANTIPATTERN was reported as being in production code. Decided on the
        // extension rather than the directory: prose is prose wherever it is filed, and this
        // is the only indicator that scans files which are not code.
        let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("");
        let suffix = py_suffix(name).to_lowercase();
        let in_docs = !in_tests
            && (bucket == Some("docs") || DOC_SUFFIXES.contains(&suffix.as_str()));
        let text = crate::decode_ignoring_invalid(&raw);
        // The parser is handed the bytes of the DECODED text, not the bytes read off disk. The
        // two differ only for a file carrying something that is not valid UTF-8, where the
        // decode drops it, and then every span the parser returned would be shifted against
        // the offsets the patterns report.
        let bytes = text.as_bytes().to_vec();
        for (rule, line, value) in scan_text(&text, &bytes, name) {
            raw_hits.push(Hit { rule, value, file: relpath.clone(), line,
                                in_tests: in_tests || region_lines.contains(&line), in_docs });
        }
    }
    (raw_hits, scanned, skipped, tracked.is_some())
}

/// L1.14's panel row, built from the walk above.
pub fn analyze(repo: &Path, _lang: &str) -> Indicator {
    let (raw_hits, scanned, skipped, is_git) = walk(repo);

    let mut order: Vec<(&'static str, String)> = Vec::new();
    let mut grouped: HashMap<(&'static str, String), Vec<usize>> = HashMap::new();
    for (at, hit) in raw_hits.iter().enumerate() {
        let key = (hit.rule, hit.value.clone());
        grouped.entry(key.clone()).or_insert_with(|| { order.push(key); Vec::new() }).push(at);
    }
    let (mut total, mut tests_only, mut docs_only) = (0usize, 0usize, 0usize);
    for key in &order {
        let sites = &grouped[key];
        total += 1;
        // A credential that appears anywhere outside the test tree is a production finding,
        // however many fixtures also carry it. Documentation counts the same way, and only
        // when no site is a test site: one production copy makes it a production finding
        // however many pages also print it.
        let all_tests = sites.iter().all(|at| raw_hits[*at].in_tests);
        let all_docs = sites.iter().all(|at| raw_hits[*at].in_docs);
        if all_tests {
            tests_only += 1;
        } else if all_docs {
            docs_only += 1;
        }
    }
    let in_production = total - tests_only - docs_only;

    let scope_note = if is_git {
        "git-tracked files only".to_string()
    } else {
        "the whole tree: not a git working copy, so gitignored files cannot be excluded"
            .to_string()
    };
    // "distinct secret(s) ... in production code" counts FINDINGS, not files, and reading it
    // as a file count is how a one-file reading and a no-file reading looked alike in prose.
    let mut details = format!(
        "{total} distinct secret(s) in {} occurrence(s) across {scanned} scanned file(s); \
         {in_production} of the secret(s) are in production code, {docs_only} only in \
         documentation and {tests_only} only in the test tree; scope: {scope_note}; the \
         canon's second Slop arm, a confirmed true positive, is not evaluated: no credential \
         is validated against its issuer",
        raw_hits.len());
    // A count standing entirely outside production code can still be cleared, and the canon
    // says by whom and on what condition. Layer 1 cannot demonstrate a false positive, so it
    // names the route rather than taking it: a reader who is told only "Slop" reaches for the
    // one repair this project refuses, which is excluding a path until the number improves.
    if total > 0 && in_production == 0 {
        details.push_str(
            "; none of these sits in production code, so Layer 2 may still clear this count, \
             but only where every hit is demonstrably a false positive on a test fixture");
    }
    if skipped > 0 {
        details.push_str(&format!("; {skipped} file(s) unreadable or oversized and excluded"));
    }
    if scanned == 0 {
        // The refusal, in value and band rather than in the prose beneath them.
        details = format!(
            "not measured: no file was read. Scope: {scope_note}, and every candidate file was \
             excluded before it was opened. A count of zero here would be a clean bill of \
             health on a repository this scanner never read, which for a credential scanner is \
             the worst answer it could fabricate");
        if skipped > 0 {
            details.push_str(&format!("; {skipped} file(s) unreadable or oversized and excluded"));
        }
    }
    Indicator {
        code: "L1.14".into(),
        label: "secret-scan".into(),
        value: if scanned == 0 { "n/a".into() } else { total.to_string() },
        // The canon's count arm: 0 Healthy, 1-2 Not Healthy, >= 3 Slop.
        band: if scanned == 0 { "n/a".into() }
              else { crate::band(total as f64, 1.0, 3.0, false).into() },
        details,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    /// An AWS key, assembled from pieces rather than written out whole.
    ///
    /// A Rust unit test lives in the file it tests, so a credential spelled here is a
    /// credential in a production file: writing this one out raised THIS repository's own
    /// L1.14 to four secrets, one of them in production, and the scanner tripped over its own
    /// test. The scope rule cannot help, because there is no test directory to name.
    fn aws_key() -> String {
        format!("AKIA{}", "QWERTYUIOPASDFGH")
    }

    /// A tree under the system temp directory. No dev-dependency: adding one to reach
    /// `analyze`, which is the only function here that does I/O, would put a crate in the
    /// lockfile of a binary whose whole claim is that it is portable.
    ///
    /// It is not a git working copy, so every file in it is scanned and the details line says
    /// the scope was the whole tree.
    fn repo_with(stem: &str, files: &[(&str, &str)]) -> std::path::PathBuf {
        let root = std::env::temp_dir().join(format!("slop-l114-{stem}"));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(&root).expect("temp tree");
        for (name, body) in files {
            let path = root.join(name);
            if let Some(parent) = path.parent() {
                fs::create_dir_all(parent).expect("the directory");
            }
            fs::write(path, body).expect("the file");
        }
        root
    }

    #[test]
    fn a_repository_with_no_credential_is_healthy_and_says_what_it_read() {
        let root = repo_with("clean", &[("app.py", "def main():\n    return 1\n")]);
        let row = analyze(&root, "python");
        assert_eq!(row.value, "0");
        assert_eq!(row.band, "Healthy");
        assert!(row.details.contains("across 1 scanned file(s)"), "{}", row.details);
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn a_scan_that_opened_no_file_refuses_rather_than_reporting_zero() {
        // Zero hits over zero files is the same number as zero hits over a thousand, and for a
        // credential scanner "none" is the worst answer to fabricate.
        let root = repo_with("empty", &[]);
        let row = analyze(&root, "python");
        assert_eq!(row.value, "n/a");
        assert_eq!(row.band, "n/a");
        assert!(row.details.starts_with("not measured: no file was read"), "{}", row.details);
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn one_credential_in_three_places_is_one_leaked_credential() {
        let key = aws_key();
        let root = repo_with("repeated", &[
            ("a.py", &format!("KEY = \"{key}\"\n")),
            ("b.py", &format!("KEY = \"{key}\"\n")),
            ("c.py", &format!("# {key}\n")),
        ]);
        let row = analyze(&root, "python");
        assert_eq!(row.value, "1");
        assert_eq!(row.band, "Not Healthy");
        assert!(row.details.contains("1 distinct secret(s) in 3 occurrence(s)"), "{}", row.details);
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn a_credential_only_in_the_test_tree_is_counted_apart_from_production() {
        let root = repo_with("fixture", &[
            ("app.py", "def main():\n    return 1\n"),
            ("tests/conftest.py", &format!("import pytest\nKEY = \"{}\"\n", aws_key())),
        ]);
        let row = analyze(&root, "python");
        assert!(row.details.contains("0 of the secret(s) are in production code"),
                "{}", row.details);
        assert!(row.details.contains("1 only in the test tree"), "{}", row.details);
        // Layer 2 is named as the route, because a reader told only "Not Healthy" reaches for
        // the one repair this project refuses.
        assert!(row.details.contains("Layer 2 may still clear this count"), "{}", row.details);
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn a_lock_file_and_a_binary_are_not_read() {
        let root = repo_with("skipped", &[
            ("app.py", "x = 1\n"),
            ("package-lock.json", &format!("{{\"integrity\": \"{}\"}}\n", aws_key())),
        ]);
        fs::write(root.join("logo.png"), [0x89u8, 0x50, 0x4e, 0x47, 0x00, 0x0d])
            .expect("the binary file");
        let row = analyze(&root, "python");
        assert_eq!(row.value, "0");
        // The lock file is skipped before it is opened, so it is not counted as unreadable;
        // the binary is opened, found to hold a NUL, and disclosed.
        assert!(row.details.contains("across 1 scanned file(s)"), "{}", row.details);
        assert!(row.details.contains("1 file(s) unreadable or oversized"), "{}", row.details);
        let _ = fs::remove_dir_all(&root);
    }
}
