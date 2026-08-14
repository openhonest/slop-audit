//! Additive check: hardcoded machine-specific absolute paths in source. Ported from
//! l1_analyzer.absolute_paths.scan; validated equal. Language-agnostic; no parser.
//!
//! Flags machine-specific roots (home/user dirs, temp/scratch, mounts, Windows drive
//! paths), never an HTTP route, XPath, or JSON pointer that merely starts with `/`.
//! Healthy at zero, Slop otherwise. This hand-rolls the Python regex so it needs no
//! regex dependency.

use crate::{in_ignored_dir, is_file_entry, py_splitlines, Indicator};
use std::collections::HashSet;
use std::path::Path;

// Same extension set as l1_analyzer.absolute_paths._CODE_EXTS (without the leading dot,
// as the skeleton's source_files expects).
const CODE_EXTS: &[&str] = &[
    "py", "rs", "c", "h", "cpp", "hpp", "js", "jsx", "mjs", "cjs", "ts", "tsx", "java",
    "cs", "rb", "go", "sh",
];

// Machine-specific unix roots, as literals. `/private/(?:tmp|var)/` is expanded to its
// two literal alternatives. Matches l1_analyzer.absolute_paths._UNIX_ROOTS.
const ROOTS: &[&str] = &[
    "/home/", "/Users/", "/root/", "/tmp/", "/private/tmp/", "/private/var/",
    "/var/folders/", "/mnt/", "/media/", "/opt/",
];

/// A path ends at whitespace or a closing quote/paren/bracket. Mirrors the regex
/// negated class `[^\s"'`)\]]`.
fn is_terminator(c: char) -> bool {
    c.is_whitespace() || matches!(c, '"' | '\'' | '`' | ')' | ']')
}

fn literal_at(chars: &[char], i: usize, lit: &str) -> bool {
    let lit: Vec<char> = lit.chars().collect();
    if i + lit.len() > chars.len() {
        return false;
    }
    chars[i..i + lit.len()] == lit[..]
}

/// Unix arm. Lookbehind `(?<![A-Za-z0-9._/-])`, a machine root, then `[^\s"'`)\]]+`.
/// The `+` is the point: a bare root identifies no machine. It names a convention, and
/// the only source that carries bare roots is a tool that lists them, this module
/// included.
/// Returns the match length in chars, or None.
fn unix_arm(chars: &[char], i: usize) -> Option<usize> {
    if i > 0 {
        let p = chars[i - 1];
        if p.is_ascii_alphanumeric() || matches!(p, '.' | '_' | '/' | '-') {
            return None;
        }
    }
    let root_len = ROOTS
        .iter()
        .find(|r| literal_at(chars, i, r))
        .map(|r| r.chars().count())?;
    let mut j = i + root_len;
    while j < chars.len() && !is_terminator(chars[j]) {
        j += 1;
    }
    if j == i + root_len {
        return None; // bare root: the `+` requires at least one trailing char
    }
    Some(j - i)
}

/// Windows arm. Lookbehind `(?<![A-Za-z0-9])`, `[A-Za-z]:\` then `[^\s"'`)\]]{2,}`.
/// Two characters are what separate a drive path from an escape sequence: a letter, a
/// colon and a one-character escape is a string escape in every language, not a drive.
/// Every real drive path keeps matching, down to a four-character directory at the
/// drive root. The worked examples live in the reference's tests, not in this comment;
/// a comment that exhibits a machine path is itself a finding. Returns the match length
/// in chars, or None.
fn windows_arm(chars: &[char], i: usize) -> Option<usize> {
    if i > 0 && chars[i - 1].is_ascii_alphanumeric() {
        return None;
    }
    if i + 3 > chars.len()
        || !chars[i].is_ascii_alphabetic()
        || chars[i + 1] != ':'
        || chars[i + 2] != '\\'
    {
        return None;
    }
    let mut j = i + 3;
    while j < chars.len() && !is_terminator(chars[j]) {
        j += 1;
    }
    if j < i + 5 {
        return None; // `{2,}`: one trailing char is an escape sequence, not a path
    }
    Some(j - i)
}

/// Count non-overlapping matches on one line, mirroring re.finditer with the unix arm
/// tried before the windows arm at each position.
fn count_line(line: &str) -> usize {
    let chars: Vec<char> = line.chars().collect();
    let mut n = 0;
    let mut i = 0;
    while i < chars.len() {
        match unix_arm(&chars, i).or_else(|| windows_arm(&chars, i)) {
            Some(len) => {
                n += 1;
                i += len;
            }
            None => i += 1,
        }
    }
    n
}

/// The repo's source files under the production scope: the same ("tests", "test")
/// exclusion L1.15, L1.17 and L1.19 use, applied here as `_read_text_files` applies it.
/// A test that proves a path detector fires has to contain the path it detects, so
/// scanning the test tree measures the fixtures, not the code.
fn production_files(repo: &Path) -> Vec<(std::path::PathBuf, String)> {
    const EXTRA_IGNORE: &[&str] = &["tests", "test"];
    let mut out = Vec::new();
    for entry in walkdir::WalkDir::new(repo).min_depth(1).into_iter().filter_map(Result::ok) {
        if !is_file_entry(&entry) {
            continue;
        }
        let path = entry.path();
        let ext = match path.extension().and_then(|e| e.to_str()) {
            Some(e) => e.to_lowercase(),
            None => continue,
        };
        if !CODE_EXTS.contains(&ext.as_str()) {
            continue;
        }
        if in_ignored_dir(path) {
            continue;
        }
        let ignored = path.components().any(|c| match c {
            std::path::Component::Normal(os) => {
                os.to_str().map(|s| EXTRA_IGNORE.contains(&s)).unwrap_or(false)
            }
            _ => false,
        });
        if ignored {
            continue;
        }
        if let Ok(bytes) = std::fs::read(path) {
            out.push((path.to_path_buf(), String::from_utf8_lossy(&bytes).into_owned()));
        }
    }
    out
}

pub fn analyze(repo: &Path) -> Indicator {
    let mut count = 0usize;
    let mut files_hit: HashSet<std::path::PathBuf> = HashSet::new();
    for (path, text) in production_files(repo) {
        let mut file_count = 0usize;
        for line in py_splitlines(&text) {
            file_count += count_line(line);
        }
        if file_count > 0 {
            count += file_count;
            files_hit.insert(path);
        }
    }
    let band = if count == 0 { "Healthy" } else { "Slop" };
    let details = if count == 0 {
        "no hardcoded machine-specific absolute paths".to_string()
    } else {
        format!(
            "{count} hardcoded machine-specific absolute path(s) across {} file(s)",
            files_hit.len()
        )
    };
    Indicator {
        code: "abs-paths".into(),
        label: "absolute-paths".into(),
        value: format!("{count}"),
        band: band.into(),
        details,
    }
}
