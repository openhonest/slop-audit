//! Shared skeleton for the portable slop-audit port. Every indicator module exposes
//! `pub fn analyze(repo: &Path) -> Indicator` and builds only on the helpers here, so
//! indicators are independent files that never touch each other or main.rs.
//!
//! The contract for a port: match the pre-registered Python reference
//! (l1_analyzer) exactly. The Python module and its tests are the frozen spec.

use std::collections::HashSet;
use std::path::{Component, Path, PathBuf};
use tree_sitter::{Language, Node, Parser};

pub mod indicators;

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

/// Every file under `repo` whose lowercased extension is in `exts` and not in an ignored
/// dir, read as text with invalid bytes replaced (mirrors read_text(errors="ignore")).
pub fn source_files(repo: &Path, exts: &[&str]) -> Vec<(PathBuf, String)> {
    let want: HashSet<&str> = exts.iter().copied().collect();
    let mut out = Vec::new();
    for entry in walkdir::WalkDir::new(repo).into_iter().filter_map(Result::ok) {
        let path = entry.path();
        if !entry.file_type().is_file() || in_ignored_dir(path) {
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

/// A tree-sitter parser for `lang`. Grammars link statically; extend the match to add one.
pub fn parser_for(lang: &str) -> Parser {
    let language: Language = match lang {
        "python" => tree_sitter_python::LANGUAGE.into(),
        other => panic!("no grammar linked for {other}"),
    };
    let mut p = Parser::new();
    p.set_language(&language).expect("set grammar");
    p
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

/// Pure value-to-band map, identical to l1_analyzer.indicators.band.
pub fn band(value: f64, healthy: f64, slop: f64, higher_is_better: bool) -> &'static str {
    if higher_is_better {
        if value >= healthy { "Healthy" } else if value >= slop { "Not Healthy" } else { "Slop" }
    } else if value < healthy { "Healthy" } else if value < slop { "Not Healthy" } else { "Slop" }
}
