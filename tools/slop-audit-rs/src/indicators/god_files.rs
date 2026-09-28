//! L1.17 god-file concentration: percentage of production files over 1000 CODE lines,
//! with large container literals (>= MIN_TABLE_LINES) subtracted so a data table is not
//! read as a logic pile. Ported from l1_analyzer.indicators._god_files.
//!
//! All nine languages. The reference scans a fixed ten-extension set regardless of the
//! repo's primary language, and discounts data literals per grammar (_LITERAL_NODES);
//! both tables live in lang.rs. A file whose extension has no grammar keeps its raw
//! line count, exactly as the reference's `_code_line_count` fallback does.

use crate::indicators::data_tables;
use crate::lang;
use crate::{band, bucket_reason, Indicator, is_file_entry, parser_for, py_round2, repo_has_packages, splitlines_len, walk_repo};
use std::collections::{BTreeMap, HashMap};
use std::path::{Path, PathBuf};
use tree_sitter::{Node, Parser};

/// _data_literal_lines: lines spanned by data tables under `node`. A counted table is not
/// recursed into, so nested tables are counted once rather than compounded.
///
/// WHAT COUNTS AS A TABLE IS `data_tables`, shared with L1.13, and this function held its own
/// copy of the rule until 2026-09-27. The copy had one of the rule's two arms: a container of
/// twelve lines or more is a table whatever it holds, and a SHORTER container every one of
/// whose elements is a literal is also a table. Missing the second arm, this reader called 17
/// of uuid-rs/uuid's lib.rs lines logic that the reference calls data, which put the file over
/// the thousand-line line and made the port read 3 god-files where the reference reads 2. The
/// reference had the same two copies and removed its own on 2026-09-01, recording that for
/// half a day one file was data to one indicator and code to the other. Nothing here caught
/// it, because until the Rust test regions came out both tools called lib.rs a god-file and
/// the 17-line disagreement never reached an answer.
///
/// An explicit stack, because this one stops AT a table rather than reading every node, which
/// is the one walk `nodes::descendants` cannot be asked for. Order does not matter to a sum.
fn data_literal_lines(node: Node, containers: &[&str], literals: &[&str]) -> usize {
    let mut total = 0;
    let mut stack = vec![node];
    while let Some(current) = stack.pop() {
        if data_tables::is_table(current, containers, literals) {
            total += current.end_position().row - current.start_position().row + 1;
            continue;
        }
        stack.extend(crate::nodes::children(current));
    }
    total
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
    let Some(spec) = crate::lang_spec::spec_for(key) else { return total };
    let parser = parsers.entry(key).or_insert_with(|| parser_for(key));
    match parser.parse(src, None) {
        Some(tree) => total - data_literal_lines(tree.root_node(), cfg.literal_nodes,
                                                 data_tables::literal_types(spec)) as i64,
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
    // min_depth(1) because `rglob` yields descendants only, and is_file_entry because
    // the reference's `_rglob_files` keeps files only. A directory whose name ends in a
    // source extension (node_modules/decimal.js is a real one) is not a file and not
    // unreadable, so neither tool measures it or counts it against the skipped total.
    for entry in walk_repo(repo) {
        if !is_file_entry(&entry) {
            continue;
        }
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
    // What the project itself says is not part of it, read once per repository.
    let disowned = crate::ignored_paths(repo);

    let mut parsers: HashMap<&'static str, Parser> = HashMap::new();
    let mut prod_files = 0i64;
    let mut god_files = 0i64;
    let mut big_files = 0i64;
    let mut skipped = 0usize;
    let mut scoped: BTreeMap<&'static str, i64> = BTreeMap::new();

    for (path, ext) in &candidates {
        // The shared scope rule and nothing else. It carried a second, local copy of
        // the machine-output test, which is now in that rule where the reference
        // keeps it.
        let reason = bucket_reason(path, repo, has_packages,
                                   crate::PRODUCTION_WITHOUT_CONFORMANCE,
                                   crate::PRODUCTION_BUCKETS, &disowned);
        let src = match std::fs::read(path) {
            Ok(bytes) => bytes,
            Err(_) => {
                skipped += 1;
                continue;
            }
        };
        if let Some(reason) = reason {
            // Raw size: disclose that a large file was scoped out. Not for a DISOWNED file,
            // because the reference never sees one: it drops what the project's own
            // `.gitignore` excludes before any bucket rule runs, so a disclosure here would
            // announce a scope-out of a file that is not part of the repository at all.
            if reason != crate::DISOWNED && splitlines_len(&src) > 1000 {
                *scoped.entry(reason).or_insert(0) += 1;
            }
            continue;
        }
        // A Rust file's own unit tests come out first, for the same reason the tests directory
        // is not in this count: a 1,302-line file holding 402 lines of test module is a
        // 900-line production file, and the scope this indicator declares itself under says
        // so. This reader opens files itself rather than through the shared production reader,
        // so it has to ask for the region blanking by name.
        let (src, region_lines) = crate::test_regions::blanked(&src, ext);
        let test_lines = region_lines.len();
        // Data tables discounted too: the god-file smell is a logic pile.
        let code = code_line_count(&src, ext, &mut parsers) - test_lines as i64;
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

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    /// A scratch repo under the system temp dir, named for the calling test so two
    /// tests never share one. Hand-rolled: the crate ships with no dev-dependency.
    fn scratch(name: &str) -> PathBuf {
        let dir =
            std::env::temp_dir().join(format!("slop-audit-rs-{}-{}", name, std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).expect("create scratch repo");
        dir
    }

    /// A directory whose name ends in a source extension (node_modules/decimal.js is a
    /// real one) is not a file and is not unreadable. It is skipped in silence:
    /// counting it as an unreadable file was a false disclosure in both tools.
    #[test]
    fn a_directory_named_like_a_source_file_is_skipped_in_silence() {
        let repo = scratch("dir-not-a-file");
        fs::write(repo.join("app.py"), "x = 1\n").unwrap();
        fs::create_dir(repo.join("decimal.js")).unwrap();
        fs::create_dir(repo.join("pkg.py")).unwrap();

        let out = analyze(&repo);
        fs::remove_dir_all(&repo).unwrap();
        assert!(!out.details.contains("unreadable"), "details: {}", out.details);
        assert_eq!(out.details, "0/1 files >1k LOC, 0 >4k LOC");
    }

    /// The honest disclosure survives the fix: a file the process cannot read is still
    /// counted and surfaced, and the directory beside it adds nothing to that count.
    #[test]
    #[cfg(unix)]
    fn a_genuinely_unreadable_file_is_still_disclosed() {
        use std::os::unix::fs::PermissionsExt;
        let repo = scratch("unreadable-file");
        fs::write(repo.join("app.py"), "x = 1\n").unwrap();
        fs::create_dir(repo.join("decimal.js")).unwrap();
        let blocked = repo.join("blocked.py");
        fs::write(&blocked, "y = 2\n").unwrap();
        fs::set_permissions(&blocked, fs::Permissions::from_mode(0o000)).unwrap();

        if fs::read(&blocked).is_ok() {
            // Running as root, which ignores the mode bits; nothing to prove here.
            fs::remove_dir_all(&repo).unwrap();
            return;
        }
        let out = analyze(&repo);
        fs::set_permissions(&blocked, fs::Permissions::from_mode(0o644)).unwrap();
        fs::remove_dir_all(&repo).unwrap();
        assert!(
            out.details.ends_with("1 file(s) unreadable and excluded"),
            "details: {}",
            out.details
        );
    }

    /// A SHORT container every one of whose elements is a literal is a data table too, and
    /// this reader used to hold its own copy of the rule with only the twelve-line arm. The
    /// copy called 17 of uuid-rs/uuid's lib.rs lines logic, which put that file over the
    /// thousand-line line, and the port read 3 god-files where the reference reads 2.
    #[test]
    fn a_short_container_of_nothing_but_literals_is_a_data_table() {
        let repo = scratch("short-table");
        // 1,000 lines of logic and a five-line list of literals: 1,005 lines raw, which is
        // over the line, and 1,000 code lines once the table comes off, which is not. So the
        // answer turns on the table being recognised, and it is recognised only by the arm this
        // reader's own copy of the rule was missing.
        let mut src = String::new();
        for n in 0..500 {
            src.push_str(&format!("def f{n}():\n    return {n}\n"));
        }
        src.push_str("ROWS = [\n    1,\n    2,\n    3,\n]\n");
        fs::write(repo.join("app.py"), &src).unwrap();
        let raw = crate::splitlines_len(src.as_bytes());
        let out = analyze(&repo);
        fs::remove_dir_all(&repo).unwrap();
        assert!(raw > 1000, "the file has to be over the line before the discount: {raw}");
        assert_eq!(out.details, "0/1 files >1k LOC, 0 >4k LOC", "raw lines: {raw}");
    }
}
