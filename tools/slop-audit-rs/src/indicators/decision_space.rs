//! L1.19 decision space, static half: enumerate the finite decision points via
//! tree-sitter. Ported from l1_analyzer.indicators._compute_decision_space and the
//! test-execution-disabled path of _decision_space_l19.
//!
//! The exercised-coverage fraction needs a runtime trace of the target's own suite.
//! Until that harness is ported, this binary reports what the Python reference reports
//! under --no-exec: the enumeration, with coverage marked not measured. Never a
//! fabricated fraction.

use crate::lang;
use crate::{bucket_reason, parser_for, repo_has_packages, Indicator};
use std::path::Path;
use tree_sitter::Node;

// _read_source_bytes(..., extra_ignore=("tests", "test")).
const EXTRA_IGNORE: &[&str] = &["tests", "test"];

/// _DECISION_NODE_TYPES: control-flow branch node types across the supported grammars.
/// Exact-type matches (not substring) so short Ruby types like "if"/"case"/"when" are
/// safe.
const DECISION_NODE_TYPES: &[&str] = &[
    "if_statement",
    "if_expression",
    "if",
    "elif_clause",
    "else_if_clause",
    "conditional_expression",
    "ternary_expression",
    "switch_statement",
    "switch_expression",
    "switch_section",
    "switch_case",
    "expression_switch_statement",
    "type_switch_statement",
    "expression_case",
    "type_case",
    "default_case",
    "communication_case",
    "select_statement",
    "match_expression",
    "match_statement",
    "match_arm",
    "case_clause",
    "case",
    "when",
    "case_match",
    "in_clause",
];

fn count_decisions(node: Node) -> usize {
    let mut count = usize::from(DECISION_NODE_TYPES.contains(&node.kind()));
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        count += count_decisions(child);
    }
    count
}

pub fn analyze(repo: &Path, language: &str) -> Indicator {
    let cfg = match lang::cfg(language) {
        Some(cfg) => cfg,
        None => {
            return Indicator {
                code: "L1.19".into(),
                label: "decision-space".into(),
                value: "n/a".into(),
                band: "n/a".into(),
                details: format!("no tree-sitter config for {language}"),
            }
        }
    };

    let has_packages = repo_has_packages(repo);
    let mut parser = parser_for(language);
    let mut decision_points = 0usize;
    let mut files = 0usize;
    let mut skipped = 0usize;

    // min_depth(1) and no is_file() filter: see the note in god_files.rs. `rglob`
    // yields directories too, and an unreadable one is disclosed, not dropped.
    for entry in walkdir::WalkDir::new(repo).min_depth(1).into_iter().filter_map(Result::ok) {
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
        files += 1;
        if let Some(tree) = parser.parse(&src, None) {
            decision_points += count_decisions(tree.root_node());
        }
    }

    let mut details = format!(
        "{decision_points} finite decision points enumerated across {files} files; \
         exercised-coverage fraction requires a test-execution trace (not run by this \
         reference implementation)"
    );
    if skipped != 0 {
        details = format!("{details}; {skipped} file(s) unreadable and excluded");
    }
    details.push_str("; coverage not measured (test execution disabled)");

    Indicator {
        code: "L1.19".into(),
        label: "decision-space".into(),
        value: decision_points.to_string(),
        band: "n/a".into(),
        details,
    }
}
