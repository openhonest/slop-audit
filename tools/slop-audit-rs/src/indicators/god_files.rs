//! L1.17 god-file concentration: percentage of production files over 1000 CODE lines,
//! with large container literals (>= MIN_TABLE_LINES) subtracted so a data table is not
//! read as a logic pile. Ported from l1_analyzer.indicators._god_files.
//!
//! All nine languages. The reference scans a fixed ten-extension set regardless of the
//! repo's primary language, and discounts data literals per grammar (_LITERAL_NODES);
//! both tables live in lang.rs. A file whose extension has no grammar keeps its raw
//! line count, exactly as the reference's `_code_line_count` fallback does.

use crate::lang;
use crate::{
    band, bucket_reason, is_generated, parser_for, py_round2, repo_has_packages, splitlines_len,
    Indicator,
};
use std::collections::{BTreeMap, HashMap};
use std::path::{Path, PathBuf};
use tree_sitter::{Node, Parser};

// _GOD_FILE_IGNORE = ("tests", "test", "conformance"); extra scope-out beyond vendored.
const GOD_FILE_IGNORE: &[&str] = &["tests", "test", "conformance"];

// _MIN_TABLE_LINES: a literal must span at least this many lines to count as a table.
const MIN_TABLE_LINES: usize = 12;

/// _god_file_reason: shared production scoping plus the L1.17-specific generated
/// exclusion. Generated-exclusion lives here, NOT in the shared bucket_reason, so it
/// never changes the L1.18 or finite-testability measurements that flow through that
/// function.
fn god_file_reason(path: &Path, repo: &Path, has_packages: bool) -> Option<&'static str> {
    if let Some(reason) = bucket_reason(path, repo, has_packages, GOD_FILE_IGNORE) {
        return Some(reason);
    }
    let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("");
    if name.ends_with(".min.js") || name.ends_with(".min.css") || is_generated(path) {
        return Some("generated");
    }
    None
}

/// _data_literal_lines: lines spanned by large container literals under `node`. A
/// counted literal is not recursed into, so nested literals are counted once.
fn data_literal_lines(node: Node, literal_types: &[&str]) -> usize {
    let span = node.end_position().row - node.start_position().row + 1;
    if literal_types.contains(&node.kind()) && span >= MIN_TABLE_LINES {
        return span;
    }
    let mut cursor = node.walk();
    let mut sum = 0;
    for child in node.children(&mut cursor) {
        sum += data_literal_lines(child, literal_types);
    }
    sum
}

/// _code_line_count: total lines minus large data-literal lines. An extension with no
/// grammar, or a parse that fails, gets no discount and falls back to the raw count.
fn code_line_count(src: &[u8], ext: &str, parsers: &mut HashMap<&'static str, Parser>) -> i64 {
    let total = splitlines_len(src) as i64;
    let key = match lang::god_file_lang(ext) {
        Some(key) => key,
        None => return total,
    };
    let cfg = match lang::cfg(key) {
        Some(cfg) => cfg,
        None => return total,
    };
    let parser = parsers.entry(key).or_insert_with(|| parser_for(key));
    match parser.parse(src, None) {
        Some(tree) => total - data_literal_lines(tree.root_node(), cfg.literal_nodes) as i64,
        None => total,
    }
}

/// _with_skipped: append an honest note when some files could not be read.
fn with_skipped(details: String, skipped: usize) -> String {
    if skipped == 0 {
        details
    } else {
        format!("{details}; {skipped} file(s) unreadable and excluded")
    }
}

pub fn analyze(repo: &Path) -> Indicator {
    // Collect every candidate path, including vendored/ignored dirs, so a large
    // scoped-out file can still be disclosed (mirrors Python's rglob, which sees
    // ignored dirs). Each path is paired with the extension that matched it, which is
    // the key into the grammar table.
    let mut candidates: Vec<(PathBuf, &'static str)> = Vec::new();
    // min_depth(1) and no is_file() filter: `rglob` yields descendants only, and it
    // yields directories as well as files. A directory whose name ends in a source
    // extension (node_modules/decimal.js) therefore reaches the read and counts as
    // unreadable in the reference. Filtering to files here would drop it silently and
    // put the two tools' skipped-counts out of step.
    for entry in walkdir::WalkDir::new(repo).min_depth(1).into_iter().filter_map(Result::ok) {
        let path = entry.path();
        let name = match path.file_name().and_then(|n| n.to_str()) {
            Some(n) => n,
            None => continue,
        };
        if let Some(ext) = lang::GOD_FILE_EXTS.iter().find(|ext| name.ends_with(**ext)) {
            candidates.push((path.to_path_buf(), ext));
        }
    }
    let has_packages = repo_has_packages(repo);

    let mut parsers: HashMap<&'static str, Parser> = HashMap::new();
    let mut prod_files = 0i64;
    let mut god_files = 0i64;
    let mut big_files = 0i64;
    let mut skipped = 0usize;
    let mut scoped: BTreeMap<&'static str, i64> = BTreeMap::new();

    for (path, ext) in &candidates {
        let reason = god_file_reason(path, repo, has_packages);
        let src = match std::fs::read(path) {
            Ok(bytes) => bytes,
            Err(_) => {
                skipped += 1;
                continue;
            }
        };
        if let Some(reason) = reason {
            // Raw size: disclose that a large file was scoped out.
            if splitlines_len(&src) > 1000 {
                *scoped.entry(reason).or_insert(0) += 1;
            }
            continue;
        }
        // Data tables discounted: the god-file smell is a logic pile.
        let code = code_line_count(&src, ext, &mut parsers);
        prod_files += 1;
        if code > 1000 {
            god_files += 1;
        }
        if code > 4000 {
            big_files += 1;
        }
    }

    let god_pct = if prod_files > 0 {
        god_files as f64 / prod_files as f64 * 100.0
    } else {
        0.0
    };
    let band_value = if big_files > 0 {
        "Slop"
    } else {
        band(god_pct, 0.5, 2.0, false)
    };

    let mut note = format!("{god_files}/{prod_files} files >1k LOC, {big_files} >4k LOC");
    if !scoped.is_empty() {
        let joined: Vec<String> = scoped
            .iter()
            .map(|(reason, n)| format!("{n} >1k LOC scoped out ({reason})"))
            .collect();
        note.push_str("; ");
        note.push_str(&joined.join(", "));
    }

    Indicator {
        code: "L1.17".into(),
        label: "god-files".into(),
        value: py_round2(god_pct),
        band: band_value.into(),
        details: with_skipped(note, skipped),
    }
}
