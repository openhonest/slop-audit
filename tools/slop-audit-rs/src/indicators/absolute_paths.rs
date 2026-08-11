//! Additive check: hardcoded machine-specific absolute paths in source. Ported from
//! l1_analyzer.absolute_paths.scan; validated equal. Language-agnostic; no parser.
//!
//! Flags machine-specific roots (home/user dirs, temp/scratch, mounts, Windows drive
//! paths), never an HTTP route, XPath, or JSON pointer that merely starts with `/`.
//! Healthy at zero, Slop otherwise. This hand-rolls the Python regex so it needs no
//! regex dependency.

use crate::{source_files, Indicator};
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

/// Unix arm. Lookbehind `(?<![A-Za-z0-9._/-])`, a machine root, then `[^\s"'`)\]]*`.
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
    Some(j - i)
}

/// Windows arm. Lookbehind `(?<![A-Za-z0-9])`, `[A-Za-z]:\` then `[^\s"'`)\]]+` (at
/// least one char). Returns the match length in chars, or None.
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
    if j == i + 3 {
        return None; // the `+` requires at least one trailing char
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

pub fn analyze(repo: &Path) -> Indicator {
    let mut count = 0usize;
    let mut files_hit: HashSet<std::path::PathBuf> = HashSet::new();
    for (path, text) in source_files(repo, CODE_EXTS) {
        let mut file_count = 0usize;
        for line in text.lines() {
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
