//! Shared skeleton for the portable slop-audit port. Every indicator module exposes
//! `pub fn analyze(repo: &Path) -> Indicator` and builds only on the helpers here, so
//! indicators are independent files that never touch each other or main.rs.
//!
//! The contract for a port: match the pre-registered Python reference
//! (l1_analyzer) exactly. The Python module and its tests are the frozen spec.

use std::collections::HashSet;
use std::path::{Component, Path, PathBuf};
use tree_sitter::Node;

pub mod coverage;
pub mod panel;
pub mod indicators;
pub mod lang;
pub mod lang_cfg;
pub mod lang_spec;
mod lang_spec_check;
pub mod nodes;
pub mod runtime;
pub mod state;
pub mod test_regions;

pub use lang::parser_for;

/// Must equal l1_analyzer.indicators._IGNORE_DIRS.
pub const IGNORE_DIRS: &[&str] = &[
    ".git", "node_modules", "venv", ".venv", "env", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".tox", ".eggs", "site-packages", "target", "build",
    "dist", "vendor",
];

/// One indicator result, mirroring l1_analyzer's L1Result shape for display and diffing.
#[derive(Debug, Clone)]
pub struct Indicator {
    pub code: String,
    pub label: String,
    pub value: String,
    pub band: String,
    pub details: String,
}

/// True when any path component is a vendored/tooling dir. Matches Python's
/// `set(path.parts) & _IGNORE_DIRS`.
pub fn in_ignored_dir(path: &Path) -> bool {
    let ignore: HashSet<&str> = IGNORE_DIRS.iter().copied().collect();
    path.components().any(|c| match c {
        Component::Normal(os) => os.to_str().map(|s| ignore.contains(s)).unwrap_or(false),
        _ => false,
    })
}

/// Python's `Path.is_file()` for one walk entry: a regular file, or a symlink that
/// resolves to one. Every scan in this crate filters on this, mirroring the reference's
/// `_rglob_files`. Two things it gets right that a bare `entry.file_type().is_file()`
/// does not: walkdir reports the *link's* own type, so a symlinked source file would be
/// dropped here and read there; and a directory whose name ends in a source extension
/// (node_modules/decimal.js is a real one) is excluded on both sides, so it is neither
/// measured nor counted as an unreadable file.
pub fn is_file_entry(entry: &walkdir::DirEntry) -> bool {
    let file_type = entry.file_type();
    if file_type.is_symlink() {
        entry.path().is_file()
    } else {
        file_type.is_file()
    }
}

/// Every FILE under `repo`, skipping nested checkouts. The single walk every indicator
/// uses, mirroring l1_analyzer.indicators._rglob_files.
///
/// A directory below the root that carries its own `.git` is a different repository with
/// its own history and its own audit: a submodule working copy, a vendored clone, or a
/// git worktree. Measuring it reports code that is not in this commit. The tool caught
/// this on itself: an agent's worktree held an older checkout of this repository, and the
/// gate charged eleven type escapes that existed only in that second copy.
///
/// `.git` is a directory in a clone and a FILE in a worktree, so the test is existence,
/// not is_dir. `filter_entry` prunes the whole subtree, so the walk never descends into a
/// nested checkout at all. `min_depth(1)` keeps the root's own `.git` from pruning
/// everything.
pub fn walk_repo(repo: &Path) -> impl Iterator<Item = walkdir::DirEntry> + '_ {
    walkdir::WalkDir::new(repo)
        .min_depth(1)
        .into_iter()
        .filter_entry(|entry| {
            !entry.file_type().is_dir() || !entry.path().join(".git").exists()
        })
        .filter_map(Result::ok)
        .filter(is_file_entry)
}

/// Every file under `repo` whose lowercased extension is in `exts` and not in an ignored
/// dir, read as text with invalid bytes replaced (mirrors read_text(errors="ignore")).
pub fn source_files(repo: &Path, exts: &[&str]) -> Vec<(PathBuf, String)> {
    let want: HashSet<&str> = exts.iter().copied().collect();
    // What the project's own `.gitignore` excludes, read once. The whole-repository scope
    // removes no directory by name, and this walk is what L1.8 and L1.16 read; without it
    // a checkout that had once been built counted its generated output as the repository's
    // own lines, and on one corpus entry that was 5,913 lines of production code.
    let disowned = ignored_paths(repo);
    let has_packages = repo_has_packages(repo);
    let mut out = Vec::new();
    for entry in walk_repo(repo) {
        let path = entry.path();
        // Through the SHARED scope rule, with the whole-repository scope's empty exclude and
        // bucket lists, so this walk cannot drift from the production ones about what a
        // vendored tree, a disowned tree or machine output is.
        if bucket_reason(path, repo, has_packages, &[], WHOLE_REPO_BUCKETS,
                         &disowned).is_some() {
            continue;
        }
        let ext = match path.extension().and_then(|e| e.to_str()) {
            Some(e) => e.to_lowercase(),
            None => continue,
        };
        if !want.contains(ext.as_str()) {
            continue;
        }
        if let Ok(bytes) = std::fs::read(path) {
            out.push((path.to_path_buf(), String::from_utf8_lossy(&bytes).into_owned()));
        }
    }
    out
}

/// Conventional build/test/dev tooling recognised by filename, not by directory.
/// Must equal l1_analyzer.indicators._TOOLING_FILES.
pub const TOOLING_FILES: &[&str] = &["setup.py", "noxfile.py", "conftest.py", "tasks.py", "manage.py"];

/// _GENERATED_MARKERS: header sentinels that machine-generated source carries.
pub const GENERATED_MARKERS: &[&str] = &[
    "@generated",
    "Code generated by",
    "Generated by the protocol buffer compiler",
];

/// _repo_has_packages: any __init__.py outside a vendored/tooling dir. Tells a loose
/// dev/entry-point script from a flat script-only repo.
pub fn repo_has_packages(repo: &Path) -> bool {
    walk_repo(repo).any(|e| {
        e.path().file_name().and_then(|n| n.to_str()) == Some("__init__.py")
            && !in_ignored_dir(e.path())
    })
}

/// _is_generated: the file's header marks it machine-generated. Reads only the head,
/// so a hand-written file that mentions the phrase deep inside is unaffected; an
/// unreadable file is treated as not generated.
pub fn is_generated(path: &Path) -> bool {
    let bytes = match std::fs::read(path) {
        Ok(b) => b,
        Err(_) => return false,
    };
    let head = String::from_utf8_lossy(&bytes[..bytes.len().min(2048)]).into_owned();
    GENERATED_MARKERS.iter().any(|m| head.contains(m))
}

/// True when a tool wrote this file rather than a person: it declares itself generated in
/// its header, or it is a minified bundle.
///
/// ONE function, as the reference has it, so the call sites cannot drift into disagreeing
/// about what machine output is. They had: the god-file count asked about a minified name
/// AND a generated header, the shared scope rule asked only about the header, and a
/// seventeen-line minified script counted as somebody's production code in the
/// test-to-production ratio.
pub fn is_machine_output(path: &Path) -> bool {
    let minified = path
        .file_name()
        .and_then(|n| n.to_str())
        .map(|n| n.ends_with(".min.js") || n.ends_with(".min.css"))
        .unwrap_or(false);
    minified || is_generated(path)
}

/// Must equal l1_analyzer.indicators._TEST_DIR_MARKERS. The two markers that name a test
/// directory. Everything else in an `extra` scope-out list is matched on the nose; these
/// two are also matched case-insensitively and as a dotted suffix, because C# names a test
/// project `<Project>.Tests` and an exact match never catches `Src/Newtonsoft.Json.Tests/`.
pub const TEST_DIR_MARKERS: &[&str] = &["test", "tests"];

/// Markers that corroborate a test directory by file content. Mirrors
/// _TEST_FRAMEWORK_MARKERS.
const TEST_FRAMEWORK_MARKERS: &[&str] = &[
    "import pytest", "import unittest", "from unittest", "@pytest",
    "org.junit", "org.testng", "using Xunit", "using NUnit",
    "Microsoft.VisualStudio.TestTools", "[TestMethod]", "[Fact]", "@Test",
    "\"testing\"", "#[test]", "#[cfg(test)]",
    "require 'rspec'", "require \"rspec\"", "minitest", "describe(",
    "from vitest", "require('mocha')",
];

/// The file-NAME half of the test-file conventions. Mirrors _test_file_by_name.
/// Excludes the path-component arm on purpose: using it would let a renamed directory
/// corroborate itself, which is the circularity this exists to break.
pub fn test_file_by_name(path: &Path) -> bool {
    let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("").to_lowercase();
    let stem = path.file_stem().and_then(|n| n.to_str()).unwrap_or("").to_lowercase();
    name.starts_with("test_") || name.starts_with("test-") || name.starts_with("test.")
        || stem.ends_with("_test") || stem.ends_with("-test") || stem.ends_with(".test")
        || stem.ends_with(".spec") || stem.ends_with("_spec") || stem.ends_with("-spec")
        || crate::indicators::git_ratios::TEST_STEM_SUFFIXES.iter().any(|sfx| {
            path.file_stem().and_then(|n| n.to_str()).map(|s| s.ends_with(sfx)).unwrap_or(false)
        })
}

/// True when a directory named like a test directory actually holds test code.
/// Mirrors _test_dir_corroborated.
///
/// A directory NAMED like a test directory is believed only if its contents corroborate
/// the claim. Without this, renaming a production package to `Core.Tests` removes it from
/// L1.15, L1.17 and L1.19 and flips the gate, with zero bytes of code changed. The
/// instrument's primary consumer is an AI, which optimises exactly what it is told to,
/// so a scope rule reading a free-to-forge name is an instruction to rename.
///
/// One-directional on purpose: a directory that fails to corroborate is MEASURED, never
/// dropped, so the rule cannot be turned into a cheaper score.
pub fn test_dir_corroborated(directory: &Path) -> bool {
    for entry in walkdir::WalkDir::new(directory).into_iter().filter_map(Result::ok) {
        if !is_file_entry(&entry) {
            continue;
        }
        if test_file_by_name(entry.path()) {
            return true;
        }
        if let Ok(bytes) = std::fs::read(entry.path()) {
            let head = String::from_utf8_lossy(&bytes[..bytes.len().min(4096)]).into_owned();
            if TEST_FRAMEWORK_MARKERS.iter().any(|m| head.contains(m)) {
                return true;
            }
        }
    }
    false
}

/// The ancestor directory of `path` whose own name is `component`. Mirrors _claiming_dir.
fn claiming_dir<'a>(path: &'a Path, component: &str) -> Option<&'a Path> {
    let mut current = path.parent();
    while let Some(dir) = current {
        if dir.file_name().and_then(|n| n.to_str()) == Some(component) {
            return Some(dir);
        }
        current = dir.parent();
    }
    None
}

/// _component_scoped_out: one path component is scoped out by `marker`. Exact for a
/// general marker; for a test marker, `Tests`, `tests`, `Foo.Tests` and `Foo.Test` count.
pub fn component_scoped_out(component: &str, marker: &str) -> bool {
    if component == marker {
        return true;
    }
    if !TEST_DIR_MARKERS.contains(&marker) {
        return false;
    }
    let lowered = component.to_lowercase();
    lowered == marker || lowered.ends_with(&format!(".{marker}"))
}

/// _extra_reason: the first `extra` marker any path component is scoped out by.
pub fn extra_reason(path: &Path, extra: &[&'static str]) -> Option<&'static str> {
    let parts: Vec<&str> = path
        .components()
        .filter_map(|c| match c {
            Component::Normal(os) => os.to_str(),
            _ => None,
        })
        .collect();
    for marker in extra {
        for component in &parts {
            if !component_scoped_out(component, marker) {
                continue;
            }
            // A TEST marker must also be corroborated by the claiming directory.
            if TEST_DIR_MARKERS.contains(marker) {
                if let Some(dir) = claiming_dir(path, component) {
                    if !test_dir_corroborated(dir) {
                        continue;
                    }
                }
            }
            return Some(marker);
        }
    }
    None
}

/// Every source file of one language that the named scope keeps, parsed once, with the path
/// findings are reported against and the count that could not be read.
///
/// ONE WALK. Four readers had written their own by the time the state analysis landed, and
/// each was a chance to scope differently from the others: the census and the classifier
/// must read the same FILES or their counts are not comparable, and a port that scoped them
/// separately would make a scoping difference look like a reading difference.
pub fn parsed_files(repo: &Path, lang: &str, extra: &[&'static str])
    -> (Vec<(String, tree_sitter::Tree, Vec<u8>)>, usize) {
    let Some(cfg) = lang::cfg(lang) else { return (Vec::new(), 0) };
    let has_packages = repo_has_packages(repo);
    // What the project itself says is not part of it.
    let disowned = ignored_paths(repo);
    let mut parser = parser_for(lang);
    let mut out = Vec::new();
    let mut skipped = 0usize;
    for entry in walk_repo(repo) {
        let path = entry.path();
        if !is_file_entry(&entry) {
            continue;
        }
        let Some(ext) = path.extension().and_then(|e| e.to_str()) else { continue };
        if !cfg.extensions.contains(&format!(".{}", ext.to_lowercase()).as_str()) {
            continue;
        }
        if bucket_reason(path, repo, has_packages, extra, PRODUCTION_BUCKETS, &disowned)
            .is_some() {
            continue;
        }
        let Ok(src) = std::fs::read(path) else { skipped += 1; continue };
        // A REGION of the file, not only a whole file. Rust puts its unit tests inside the
        // file they test, so no path names them and eight indicators read them as production
        // code. Parsed AFTER the blanking, so no reader below sees a test at all.
        let ext = format!(".{}", ext.to_lowercase());
        let (src, _region_lines) = test_regions::blanked(&src, &ext);
        let Some(tree) = parser.parse(&src, None) else { skipped += 1; continue };
        let rel = path.strip_prefix(repo).unwrap_or(path).to_string_lossy().into_owned();
        out.push((rel, tree, src));
    }
    (out, skipped)
}

/// The production scope's parsed files, which is what every indicator below L1.17 reads.
pub fn production_files(repo: &Path, lang: &str)
    -> (Vec<(String, tree_sitter::Tree, Vec<u8>)>, usize) {
    parsed_files(repo, lang, PRODUCTION)
}

/// Bytes as text, with invalid sequences DROPPED rather than replaced.
///
/// This is what the reference's decode with errors ignored does, and the difference from a
/// lossy conversion is not cosmetic in either direction. A lossy conversion puts a
/// replacement character where the invalid bytes were, which SPLITS a word that the reference
/// joins: prose carrying a typographic apostrophe gave thirteen words the reference records
/// and three the port invented. Stripping every replacement character afterwards fixes that
/// and breaks the other way, because a document may legitimately CONTAIN one: one file holds
/// `S` and `L` either side of a real replacement character, and stripping it joined them into
/// a word neither the file nor the reference has.
///
/// So the invalid bytes are skipped where they sit, and every valid character is kept
/// whatever it is.
pub fn decode_ignoring_invalid(raw: &[u8]) -> String {
    let mut out = String::with_capacity(raw.len());
    let mut rest = raw;
    loop {
        match std::str::from_utf8(rest) {
            Ok(valid) => {
                out.push_str(valid);
                return out;
            }
            Err(error) => {
                let (valid, after) = rest.split_at(error.valid_up_to());
                out.push_str(std::str::from_utf8(valid).expect("the valid prefix"));
                // One byte when the error does not say how many, which is what an
                // unexpected end of input reports.
                let skip = error.error_len().unwrap_or(1);
                if after.len() <= skip {
                    return out;
                }
                rest = &after[skip..];
            }
        }
    }
}

/// scope.PRODUCTION: the code under audit. A test tree is not the artifact being graded,
/// and a check that fires on its own fixtures measures the fixtures.
///
/// ONE OWNER. Four readers each held their own copy of this two-word list, which is four
/// chances for one of them to measure a scope nobody wrote down. The reference routes every
/// reader through one table for the same reason.
pub const PRODUCTION: &[&str] = &["tests", "test"];

/// The judgment-call exclusions the production scopes make beyond a directory name: docs,
/// conventional tooling files, and a loose script at the repository root.
///
/// A PARAMETER, because the whole-repository scope makes none of them. The reference gates
/// each on this list and the port applied all three unconditionally, which was invisible
/// only because the whole-repository walk did not call the shared rule at all.
pub const PRODUCTION_BUCKETS: &[&str] = &["docs", "tooling", "root-script"];

/// The whole-repository scope removes no directory and makes no judgment call: for L1.8 and
/// L1.16 the test tree IS the subject, and a reading that skipped the docs, the tooling
/// files and the loose scripts would answer a narrower question under the wider one's name.
pub const WHOLE_REPO_BUCKETS: &[&str] = &[];

/// scope.PRODUCTION_WITHOUT_CONFORMANCE: the same, and a conformance tree as well.
///
/// A conformance directory holds law and spec scaffolding and test doubles, so it is
/// production for neither the state meters nor the god-file count: nobody hand-piles logic
/// into an append-only conformance table.
pub const PRODUCTION_WITHOUT_CONFORMANCE: &[&str] = &["tests", "test", "conformance"];

/// _bucket_reason: why this source file is scoped out of the audit, or None to keep
/// it. General and structural: it references no specific project. Disclosed, never
/// silent.
/// The reason a file is out of scope because the project's own `.gitignore` excludes it.
///
/// Named, because it is the one reason a reader must never be TOLD about: the reference
/// drops these files before any bucket rule runs, so it has no bucket for them and cannot
/// disclose one.
pub const DISOWNED: &str = "disowned";

/// `disowned` is what the project's own `.gitignore` excludes, resolved once per repository
/// by `ignored_paths`. It is a PARAMETER of the shared scope reader rather than a filter each
/// walk remembers to apply, because five of the eight walks did not: a corpus checkout that
/// had once been built carried 198 generated C# files under `obj/`, and the binary read all
/// of them as production while the reference read none, reporting 249 files where the
/// reference reported 135 and three god-files where it found none.
pub fn bucket_reason(
    path: &Path,
    repo: &Path,
    has_packages: bool,
    extra: &[&'static str],
    buckets: &[&str],
    disowned: &HashSet<PathBuf>,
) -> Option<&'static str> {
    // What the project itself says is not part of it. Checked before anything structural,
    // because a disowned tree is disowned whatever its directory names say.
    if !disowned.is_empty() {
        if let Ok(resolved) = path.canonicalize() {
            if disowned.contains(&resolved) {
                return Some(DISOWNED);
            }
        }
    }
    let parts: HashSet<&str> = path
        .components()
        .filter_map(|c| match c {
            Component::Normal(os) => os.to_str(),
            _ => None,
        })
        .collect();
    if parts.iter().any(|p| IGNORE_DIRS.contains(p)) {
        return Some("vendored");
    }
    // The reason is the matched directory name itself, as in the reference.
    if let Some(reason) = extra_reason(path, extra) {
        return Some(reason);
    }
    if buckets.contains(&"docs") && parts.contains("docs") {
        return Some("docs");
    }
    if buckets.contains(&"tooling") {
        if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
            if TOOLING_FILES.contains(&name) {
                return Some("tooling");
            }
        }
    }
    // Machine output is not the author's code. Measuring its mutable state, its type escapes
    // or its conformity reports on a code generator nobody in this repository wrote. The
    // marker is the toolchain's own declaration, read from the header only.
    //
    // In the SHARED rule, as the reference has it, rather than added on by the one reader
    // that remembered: a minified script carrying a generator banner counted as seventeen
    // lines of somebody's production code in the test-to-production ratio.
    if is_machine_output(path) {
        return Some("generated");
    }
    // A loose top-level source file sitting beside packages (the repo has packages and
    // its root is not itself one) is a dev/entry-point script, not the library. A flat,
    // script-only repo keeps its root scripts: they are the code.
    if buckets.contains(&"root-script") && has_packages && path.parent() == Some(repo)
        && !repo.join("__init__.py").exists() {
        return Some("root-script");
    }
    None
}

/// `bytes.splitlines()` in Python: every line, without its boundary. A line closes at each
/// ASCII line boundary (\n \r \r\n \v \f \x1c \x1d \x1e), with no trailing empty line after
/// a final boundary.
///
/// One owner for that boundary set, because the count and the lines themselves are the same
/// question. `splitlines_len` used to hold its own copy of the rule, and test_regions needs
/// the lines: two copies would have let a file carrying a lone \r be one length to the line
/// counter and another to the reader comparing lines.
pub fn splitlines_bytes(bytes: &[u8]) -> Vec<&[u8]> {
    fn is_boundary(b: u8) -> bool {
        matches!(b, b'\n' | b'\r' | 0x0b | 0x0c | 0x1c | 0x1d | 0x1e)
    }
    let n = bytes.len();
    let mut i = 0;
    let mut lines = Vec::new();
    while i < n {
        let start = i;
        while i < n && !is_boundary(bytes[i]) {
            i += 1;
        }
        lines.push(&bytes[start..i]);
        if i < n {
            if bytes[i] == b'\r' && i + 1 < n && bytes[i + 1] == b'\n' {
                i += 2;
            } else {
                i += 1;
            }
        }
    }
    lines
}

/// Length of `bytes.splitlines()` in Python.
pub fn splitlines_len(bytes: &[u8]) -> usize {
    splitlines_bytes(bytes).len()
}

/// `str.splitlines()` in Python: every line, split on the full Unicode boundary set a
/// decoded string carries. Beyond the ASCII boundaries `splitlines_len` handles, that
/// is NEL (U+0085), LINE SEPARATOR (U+2028) and PARAGRAPH SEPARATOR (U+2029).
///
/// Rust's own `str::lines()` splits on `\n` alone, so it disagrees with the reference
/// on any file carrying a lone `\r`, a form feed, or one of those three. Nothing in
/// this crate may count lines of file text with `str::lines()`; use this instead. The
/// difference is not hypothetical: it first showed up as a two-line drift in L1.8 and
/// a missed L1.16 hit.
pub fn py_splitlines(s: &str) -> Vec<&str> {
    fn is_boundary(c: char) -> bool {
        matches!(
            c,
            '\n' | '\r' | '\u{0b}' | '\u{0c}' | '\u{1c}' | '\u{1d}' | '\u{1e}'
                | '\u{85}' | '\u{2028}' | '\u{2029}'
        )
    }
    let mut lines = Vec::new();
    let mut start = 0usize;
    let mut iter = s.char_indices().peekable();
    while let Some((i, c)) = iter.next() {
        if !is_boundary(c) {
            continue;
        }
        lines.push(&s[start..i]);
        // \r\n closes one line, not two.
        if c == '\r' && iter.peek().map(|(_, next)| *next) == Some('\n') {
            iter.next();
            start = i + '\r'.len_utf8() + '\n'.len_utf8();
        } else {
            start = i + c.len_utf8();
        }
    }
    if start < s.len() {
        lines.push(&s[start..]);
    }
    lines
}

/// Length of `str.splitlines()`.
pub fn splitlines_count_str(s: &str) -> usize {
    py_splitlines(s).len()
}

/// `round(x, 2)` as the reference's JSON prints it: shortest round-trip, always with a
/// decimal point. Every ported percentage and density renders through this, so a value
/// diffs against the reference as text.
pub fn py_round2(x: f64) -> String {
    let rounded = (x * 100.0).round() / 100.0;
    let mut s = format!("{rounded}");
    if !s.contains('.') && !s.contains('e') {
        s.push_str(".0");
    }
    s
}

/// Count descendant nodes (inclusive) whose kind is `kind`.
pub fn count_kind(node: Node, kind: &str) -> usize {
    let mut n = usize::from(node.kind() == kind);
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        n += count_kind(child, kind);
    }
    n
}

/// A float written the way Python writes one, for any details line the two tools compare.
///
/// The two languages already agree on every fraction: both print the shortest text that reads
/// back as the same number. They disagree on ONE shape, a value with nothing after the point,
/// where Python writes `1.0` and Rust writes `1`.
///
/// It went unseen for as long as it did because it needs a repository with NO state at all:
/// the resolvable fraction is then exactly one and the silence exactly nought, and every
/// corpus repository has state, so every fraction came out with digits after the point and the
/// two spellings agreed. A one-file crate with no mutable state found it in a second.
pub fn py_float(value: f64) -> String {
    if value.fract() == 0.0 {
        format!("{value}.0")
    } else {
        format!("{value}")
    }
}

/// Pure value-to-band map, identical to l1_analyzer.indicators.band.
pub fn band(value: f64, healthy: f64, slop: f64, higher_is_better: bool) -> &'static str {
    if higher_is_better {
        if value >= healthy { "Healthy" } else if value >= slop { "Not Healthy" } else { "Slop" }
    } else if value < healthy { "Healthy" } else if value < slop { "Not Healthy" } else { "Slop" }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    /// The boundary set Python's `str.splitlines()` uses, and the one Rust's
    /// `str::lines()` does not. Each case is the reference's answer, taken from
    /// CPython: `len("a\vb".splitlines()) == 2`, and so on for the rest.
    #[test]
    fn py_splitlines_matches_the_reference_boundaries() {
        let cases: &[(&str, usize)] = &[
            ("a\nb", 2),
            ("a\nb\n", 2),
            ("", 0),
            ("\n", 1),
            ("a\r\nb", 2),   // \r\n closes one line, not two
            ("a\rb", 2),     // lone \r: str::lines() would say 1
            ("a\u{0b}b", 2), // vertical tab
            ("a\u{0c}b", 2), // form feed
            ("a\u{1c}b", 2),
            ("a\u{1d}b", 2),
            ("a\u{1e}b", 2),
            ("a\u{85}b", 2),   // NEL
            ("a\u{2028}b", 2), // LINE SEPARATOR
            ("a\u{2029}b", 2), // PARAGRAPH SEPARATOR
            ("a\tb", 1),       // tab is not a boundary
        ];
        for (input, want) in cases {
            assert_eq!(
                py_splitlines(input).len(),
                *want,
                "py_splitlines({input:?})"
            );
        }
        assert_eq!(py_splitlines("a\r\nb\rc\u{2028}d"), vec!["a", "b", "c", "d"]);
    }

    /// C# convention is a project directory named `<Project>.Tests`, which an exact
    /// component match never catches, so every C# repository's test tree was measured as
    /// production code by L1.15, L1.17, L1.19 and the absolute-path check. A component is
    /// a test directory when, lowercased, it equals "tests"/"test" or ends ".tests"/".test".
    #[test]
    fn a_dotted_csharp_test_project_is_scoped_out() {
        let root = std::env::temp_dir().join(format!("slop-scope-{}", std::process::id()));
        let _ = fs::remove_dir_all(&root);
        // A real test project: its contents corroborate the name.
        fs::create_dir_all(root.join("Src/Newtonsoft.Json.Tests/Schema")).unwrap();
        fs::write(root.join("Src/Newtonsoft.Json.Tests/Schema/T.cs"), "using Xunit;\n[Fact] void A(){}\n").unwrap();
        // Production code, and two words that merely contain a marker.
        fs::create_dir_all(root.join("Src/Newtonsoft.Json")).unwrap();
        fs::write(root.join("Src/Newtonsoft.Json/Serializer.cs"), "class Serializer {}\n").unwrap();
        fs::create_dir_all(root.join("Src/Contests")).unwrap();
        fs::write(root.join("Src/Contests/Entry.cs"), "class Entry {}\n").unwrap();

        const EXTRA: &[&str] = &["tests", "test"];
        let nothing = HashSet::new();
        let scoped =
            |rel: &str| bucket_reason(&root.join(rel), &root, false, EXTRA, PRODUCTION_BUCKETS, &nothing);
        assert_eq!(scoped("Src/Newtonsoft.Json.Tests/Schema/T.cs"), Some("tests"));
        assert_eq!(scoped("Src/Newtonsoft.Json/Serializer.cs"), None);
        assert_eq!(scoped("Src/Contests/Entry.cs"), None);

        let _ = fs::remove_dir_all(&root);
    }

    /// The aperture-capture vector, closed. Renaming a production package to `Core.Tests`
    /// used to remove it from every source indicator and flip the gate, with zero bytes of
    /// code changed. A directory named like a test directory is now believed only if its
    /// contents corroborate the claim.
    #[test]
    fn a_renamed_production_directory_is_still_measured() {
        let root = std::env::temp_dir().join(format!("slop-rename-{}", std::process::id()));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(root.join("Core.Tests")).unwrap();
        fs::write(root.join("Core.Tests/app.py"), "from typing import Any\nCACHE = {}\n").unwrap();

        const EXTRA: &[&str] = &["tests", "test"];
        let nothing = HashSet::new();
        assert_eq!(
            bucket_reason(&root.join("Core.Tests/app.py"), &root, false, EXTRA,
                          PRODUCTION_BUCKETS, &nothing), None);

        // The same directory, with one real test file in it, is believed.
        fs::write(root.join("Core.Tests/test_app.py"), "def test_x(): pass\n").unwrap();
        assert_eq!(
            bucket_reason(&root.join("Core.Tests/app.py"), &root, false, EXTRA,
                          PRODUCTION_BUCKETS, &nothing),
            Some("tests"));

        let _ = fs::remove_dir_all(&root);
    }

    /// The bytes splitter agrees with the str splitter wherever both apply, so the two
    /// paths cannot drift apart on the ASCII boundaries they share.
    #[test]
    fn the_two_splitters_agree_on_ascii_boundaries() {
        for input in ["a\nb", "a\nb\n", "", "\n", "a\r\nb", "a\rb", "a\u{0c}b", "a\u{1e}b"] {
            assert_eq!(splitlines_len(input.as_bytes()), py_splitlines(input).len(), "{input:?}");
        }
    }
}

#[cfg(test)]
mod walk_tests {
    use super::walk_repo;
    use std::fs;

    /// A directory below the root carrying its own `.git` is a different repository.
    /// Measuring it reports code that is not in this commit. The tool caught this on
    /// itself: an agent worktree held an older checkout and the gate charged eleven type
    /// escapes that existed only there.
    #[test]
    fn a_nested_checkout_is_not_walked() {
        let root = std::env::temp_dir().join(format!("slop-walk-{}", std::process::id()));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(root.join(".git")).unwrap();
        fs::write(root.join("mine.py"), "x = 1\n").unwrap();

        // A vendored clone: .git is a directory.
        fs::create_dir_all(root.join("vendored-clone/.git")).unwrap();
        fs::write(root.join("vendored-clone/theirs.py"), "y = 2\n").unwrap();

        // A git worktree: .git is a FILE, which is the shape that produced the false
        // reading, so existence is the test rather than is_dir.
        fs::create_dir_all(root.join("agent-worktree/pkg")).unwrap();
        fs::write(root.join("agent-worktree/.git"), "gitdir: /elsewhere\n").unwrap();
        fs::write(root.join("agent-worktree/pkg/theirs.py"), "z = 3\n").unwrap();

        let names: Vec<String> = walk_repo(&root)
            .filter_map(|e| e.path().file_name()?.to_str().map(str::to_string))
            .filter(|n| n.ends_with(".py"))
            .collect();
        assert_eq!(names, vec!["mine.py".to_string()], "walked {names:?}");

        let _ = fs::remove_dir_all(&root);
    }
}

/// Every path this repository's own `.gitignore` excludes, resolved.
///
/// An audit measures what the project says is part of it. A `.gitignore` entry is that
/// statement, written by whoever put it there: a build directory, a vendored dependency, a
/// scratch tree kept for reference. Reading them reports code the project has declared is
/// not its own, and a fresh clone then reads differently from the working copy.
///
/// What forced it in the reference: a repository held a `python.botched` directory beside
/// `python`, 262 MB and 20,743 files, ignored at line 19 of its `.gitignore`. It carried
/// the only three pieces of provably unbounded state in the whole measurement, so the
/// repository read as not exhaustively testable on the strength of code the project had
/// disowned.
///
/// IGNORED, NOT UNTRACKED, and the difference is the whole rule. Both a build directory
/// and a module written five minutes ago are untracked. Only the first carries a statement
/// that it is not part of the project. Skipping untracked files would make this instrument
/// blind to uncommitted work, which is the work a developer most wants measured: an audit
/// that goes quiet on what you just wrote reports on the past.
///
/// An empty set where there is no git, so the walk reads everything. A tarball, an
/// extracted archive and a vendored copy are all real audit subjects, and refusing them
/// would turn a working reading into no reading at all.
pub fn ignored_paths(repo: &Path) -> HashSet<PathBuf> {
    let run = std::process::Command::new("git")
        .args(["ls-files", "--others", "--ignored", "--exclude-standard", "-z"])
        .current_dir(repo)
        .output();
    let Ok(out) = run else { return HashSet::new() };
    if !out.status.success() {
        return HashSet::new();
    }
    String::from_utf8_lossy(&out.stdout)
        .split('\0')
        .filter(|name| !name.is_empty())
        .filter_map(|name| repo.join(name).canonicalize().ok())
        .collect()
}
