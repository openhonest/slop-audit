//! L1.15 type-escape density: count tree-sitter leaf nodes whose exact text is one of
//! the language's escape tokens, plus comment nodes carrying an ignore-marker, over
//! kLOC. Ported from l1_analyzer.indicators._compute_type_escapes and
//! _count_type_escapes_in_tree.
//!
//! Language-driven: the escape tokens come from lang::LangCfg, so the four untyped or
//! no-escape-hatch languages (Ruby, JavaScript, Rust, C) report n/a exactly as the
//! reference does, and the five typed ones each use their own tokens.

use crate::lang;
use crate::{
    band, bucket_reason, is_file_entry, parser_for, py_round2, repo_has_packages,
    splitlines_count_str, Indicator,
};
use std::path::Path;
use tree_sitter::Node;

// _COMMENT_TYPE_ESCAPES (language agnostic; substring match on a comment node).
const COMMENT_ESCAPES: &[&str] = &[
    "# type: ignore",
    "// @ts-ignore",
    "/* @ts-ignore",
    "@SuppressWarnings",
];
// _read_source_bytes(..., extra_ignore=("tests", "test")).
const EXTRA_IGNORE: &[&str] = &["tests", "test"];

/// True if any ancestor is a string node. A leaf inside a string is data, not an
/// annotation: `("Any",)` in a pattern table, an "object" key in a C# message, a
/// "dynamic" label. None of them opt out of a type checker.
fn in_string(node: Node) -> bool {
    let mut parent = node.parent();
    while let Some(n) = parent {
        if n.kind().contains("string") {
            return true;
        }
        parent = n.parent();
    }
    false
}

/// _count_type_escapes_in_tree: a leaf whose exact text is an escape token and is not
/// inside a string, plus a comment node that BEGINS with an ignore-marker. A comment
/// that merely mentions the marker while explaining the rule is documentation.
fn count_escapes_in_tree(node: Node, src: &[u8], escape_tokens: &[&str]) -> usize {
    let mut count = 0usize;
    if node.child_count() == 0 {
        let text = String::from_utf8_lossy(&src[node.byte_range()]);
        if escape_tokens.contains(&text.as_ref()) && !in_string(node) {
            count += 1;
        }
    }
    if node.kind().contains("comment") {
        let text = String::from_utf8_lossy(&src[node.byte_range()]);
        if COMMENT_ESCAPES.iter().any(|p| text.trim_start().starts_with(p)) {
            count += 1;
        }
    }
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        count += count_escapes_in_tree(child, src, escape_tokens);
    }
    count
}

fn na(details: String) -> Indicator {
    Indicator {
        code: "L1.15".into(),
        label: "type-escapes".into(),
        value: "n/a".into(),
        band: "n/a".into(),
        details,
    }
}

pub fn analyze(repo: &Path, language: &str) -> Indicator {
    let cfg = match lang::cfg(language) {
        Some(cfg) => cfg,
        None => return na(format!("no tree-sitter config for {language}")),
    };
    if cfg.type_escape_patterns.is_empty() {
        // Untyped or no configured escape hatch (Ruby, JavaScript, Rust, C).
        return na(format!("type-escape density not applicable for {language}"));
    }

    let has_packages = repo_has_packages(repo);
    let mut parser = parser_for(language);
    let mut escape_count = 0usize;
    let mut total_loc = 0usize;
    let mut skipped = 0usize;

    // min_depth(1) and is_file_entry: see the note in god_files.rs. A directory whose
    // name ends in a source extension is not a file, so it is skipped in silence.
    for entry in walkdir::WalkDir::new(repo).min_depth(1).into_iter().filter_map(Result::ok) {
        if !is_file_entry(&entry) {
            continue;
        }
        let path = entry.path();
        let name = match path.file_name().and_then(|n| n.to_str()) {
            Some(n) => n,
            None => continue,
        };
        if !cfg.extensions.iter().any(|ext| name.ends_with(ext)) {
            continue;
        }
        if bucket_reason(path, repo, has_packages, EXTRA_IGNORE).is_some() {
            continue;
        }
        let src = match std::fs::read(path) {
            Ok(bytes) => bytes,
            Err(_) => {
                skipped += 1;
                continue;
            }
        };
        total_loc += splitlines_count_str(&String::from_utf8_lossy(&src));
        if let Some(tree) = parser.parse(&src, None) {
            escape_count += count_escapes_in_tree(tree.root_node(), &src, cfg.type_escape_patterns);
        }
    }

    let density = if total_loc > 1000 {
        escape_count as f64 / (total_loc as f64 / 1000.0)
    } else {
        0.0
    };
    let mut details = format!("{escape_count} escapes in ~{}kLOC", total_loc / 1000);
    if skipped != 0 {
        details = format!("{details}; {skipped} file(s) unreadable and excluded");
    }
    Indicator {
        code: "L1.15".into(),
        label: "type-escapes".into(),
        value: py_round2(density),
        band: band(density, 1.0, 5.0, false).into(),
        details,
    }
}
