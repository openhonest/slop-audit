//! L1.19 decision space, static half: enumerate the finite decision points via
//! tree-sitter. Ported from l1_analyzer.indicators._compute_decision_space and the
//! test-execution-disabled path of _decision_space_l19.
//!
//! The exercised-coverage fraction needs a runtime trace of the target's own suite.
//! Until that harness is ported, this binary reports what the Python reference reports
//! under --no-exec: the enumeration, with coverage marked not measured. Never a
//! fabricated fraction.

use crate::lang;
use crate::{bucket_reason, Indicator, is_file_entry, parser_for, repo_has_packages, walk_repo};
use std::path::Path;
use tree_sitter::Node;

// _read_source_bytes(..., extra_ignore=("tests", "test")).

/// _DECISION_NODE_TYPES: control-flow branch node types across the supported grammars.
/// Exact-type matches (not substring) so short Ruby types like "if"/"case"/"when" are
/// safe.
/// One vocabulary per language, mirroring lang_vocab.DECISION_NODE_TYPES in the reference.
///
/// A single flat list stood here and was wrong twice over. It counted node kinds no
/// grammar in the row produces, and it counted the SWITCH rather than its ARMS. The spec
/// enumerates "dispatch table keys, match/case arms, and enum-driven branches": a switch
/// with four cases is four decision points, not one. Java undercounted for that reason,
/// 1034 against the reference's 1283 on junit4, while the flat list simultaneously
/// overcounted elsewhere by matching another language's spelling.
///
/// Nothing could see either fault until the corpus gained a repository per language on
/// 2026-08-19.
fn decision_node_types(language: &str) -> Option<&'static [&'static str]> {
    Some(match language {
        "c" => &["case_statement", "conditional_expression", "if_statement"],
        "csharp" => &[
            "conditional_expression",
            "if_statement",
            "switch_expression_arm",
            "switch_section",
        ],
        "go" => &[
            "communication_case",
            "default_case",
            "expression_case",
            "if_statement",
            "type_case",
        ],
        "java" => &["if_statement", "switch_label", "ternary_expression"],
        "javascript" | "typescript" => {
            &["if_statement", "switch_case", "switch_default", "ternary_expression"]
        }
        "python" => &[
            "case_clause",
            "conditional_expression",
            "elif_clause",
            "if_statement",
        ],
        "ruby" => &[
            "conditional",
            "elsif",
            "if",
            "if_modifier",
            "in_clause",
            "unless",
            "unless_modifier",
            "when",
        ],
        "rust" => &["if_expression", "match_arm"],
        _ => return None,
    })
}

fn count_decisions(node: Node, types: &[&str]) -> usize {
    let mut count = usize::from(types.contains(&node.kind()));
    let mut cursor = node.walk();
    // named_children, never children. An unnamed keyword token (`if`, `case`, `switch`)
    // sits inside the very node that already matched, and in Ruby it carries the SAME kind
    // string as the node, so walking every child counts every `if` twice. Anonymous tokens
    // are leaves, so skipping them loses no descendant.
    //
    // The Python reference fixed this and the port did not, which nothing could see until
    // the corpus gained a repository per language on 2026-08-19: the port then reported 981
    // decision points against the reference's 522 on gson, and 800 against 429 on ky.
    for child in node.named_children(&mut cursor) {
        count += count_decisions(child, types);
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

    // Subscript, not a default: a supported language that declares no decision vocabulary
    // is a gap in the table, and a gap must refuse rather than enumerate zero. The
    // reference makes the same choice at the same place, and says so.
    let types = match decision_node_types(language) {
        Some(types) => types,
        None => {
            return Indicator {
                code: "L1.19".into(),
                label: "decision-space".into(),
                value: "n/a".into(),
                band: "n/a".into(),
                details: format!("no decision vocabulary for {language}"),
            }
        }
    };

    let has_packages = repo_has_packages(repo);
    // What the project itself says is not part of it, read once per repository.
    let disowned = crate::ignored_paths(repo);
    let mut parser = parser_for(language);
    let mut decision_points = 0usize;
    let mut files = 0usize;
    let mut skipped = 0usize;

    // min_depth(1) and is_file_entry: see the note in god_files.rs. A directory whose
    // name ends in a source extension is not a file, so it is skipped in silence.
    for entry in walk_repo(repo) {
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
        if bucket_reason(path, repo, has_packages, crate::PRODUCTION,
                         crate::PRODUCTION_BUCKETS, &disowned).is_some() {
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
            decision_points += count_decisions(tree.root_node(), types);
        }
    }

    // The reference's own sentence, word for word. This said "not run by this reference
    // implementation", which is a phrase the reference never printed and which this binary
    // is not in any case, so the parity harness read a wording difference as a
    // disagreement about the number.
    let mut details = format!(
        "{decision_points} finite decision points enumerated across {files} files; \
         the share a test exercises is a different number and needs a test-execution trace"
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
