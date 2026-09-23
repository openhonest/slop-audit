//! Portable slop-audit CLI. Runs every ported indicator and prints the panel. Each value is
//! validated equal to the pre-registered Python reference (l1_analyzer).
//!
//! Usage: slop-audit-rs <repo> [--lang KEY] [--tsv]
//!
//! --lang is a LANG_CFG key (python, rust, c, java, typescript, csharp, javascript,
//! ruby, go). Omitted, it is detected from the file counts exactly as
//! detect_primary_language does.
//!
//! --tsv prints one tab-separated row per indicator, for the equality diff against the
//! Python reference (validate.py). The default is the aligned human panel.
//!
//! --census prints one tab-separated row per declaration site the state census counts,
//! rather than a panel. It grades nothing and is not in the usage line: it exists so the
//! census port can be diffed site by site against the reference on a real repository,
//! because a count that matches by luck and a count that matches by agreement look the
//! same from outside.
//!
//! Arguments are parsed by hand: a CLI parser crate would add weight to a binary whose
//! whole purpose is to be one small self-contained file.
use slop_audit_rs::{indicators, lang, panel, state};
use std::path::Path;

fn usage() -> ! {
    eprintln!("usage: slop-audit-rs <repo> [--lang KEY] [--tsv] [--no-exec] [--version]");
    eprintln!("  --no-exec  do not run the target's own test suite (it is run by default)");
    std::process::exit(2);
}

/// Which build this is, from the crate metadata cargo compiled in.
///
/// One source. A string literal here would be a second owner of the same fact with nothing
/// checking the two agreed, and the parity job's verdict that two implementations agree was
/// about two builds neither of them could name.
fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

fn main() {
    let mut repo_arg: Option<String> = None;
    let mut lang_arg: Option<String> = None;
    let mut tsv = false;
    let mut census = false;
    let mut exec_tests = true;
    let mut enumerate = false;
    let mut reads = false;
    let mut filters = false;
    let mut unreachable = false;
    let mut defs = false;

    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--tsv" => tsv = true,
            // Not in the usage line: it prints no panel and grades nothing. It dumps the
            // declaration sites this binary's census counts, one per row, so the port can
            // be diffed site by site against the Python reference on a real repository.
            // A count that matches by luck and a count that matches by agreement look the
            // same from the outside, and this is what tells them apart.
            // This binary RUNS the audited project's suite, by the decision of
            // 2026-09-21. The flag turns that off; there is no flag to turn it on, because
            // it is on.
            "--no-exec" => exec_tests = false,
            "--census" => census = true,
            // Beside --census, and for the same reason: this one dumps what the
            // CLASSIFIER'S walk reached, with the key each site yielded and the empty
            // string where it read a declaration and declined. The declines are the half
            // that matters: they are the only evidence the reader was there at all.
            "--enum" => enumerate = true,
            // The third of the same family. It dumps what the POSITION predicates say
            // about every node: is this a test expression, a presence test, a keyed read,
            // a call whose result nobody reads. Those readings are where the nine
            // grammars diverge most, and a rule that composes them is only as sound as
            // they are.
            "--reads" => reads = true,
            // The fourth of the family, and the one furthest from a node type: it dumps
            // what each false-positive rule said about each piece of state. Those rules
            // only ever CLEAR a finding, so a port that got them wrong reports more than
            // it measured, which is the one direction this instrument must not fail in.
            "--filters" => filters = true,
            // The fifth of the family: every statement that follows a terminator in the
            // same block, which is the half of L1.12 decidable from syntax alone.
            "--unreachable" => unreachable = true,
            // The sixth: every definition the collectors find, with the status that says
            // whether the reference scan may judge it at all.
            "--defs" => defs = true,
            // Before the repository check: it answers a question about the binary rather
            // than about a tree.
            "--version" => {
                println!("slop-audit-rs {}", version());
                return;
            }
            "--lang" => lang_arg = Some(args.next().unwrap_or_else(|| usage())),
            "-h" | "--help" => usage(),
            other if other.starts_with('-') => usage(),
            other => {
                if repo_arg.is_some() {
                    usage();
                }
                repo_arg = Some(other.to_string());
            }
        }
    }

    let repo = repo_arg.unwrap_or_else(|| usage());
    let repo = Path::new(&repo);
    let language = match lang_arg {
        Some(key) => {
            if lang::cfg(&key).is_none() {
                eprintln!(
                    "unknown language {key}; known keys: {}",
                    lang::LANGS.iter().map(|l| l.key).collect::<Vec<_>>().join(", ")
                );
                std::process::exit(2);
            }
            key
        }
        None => lang::detect_primary_language(repo).to_string(),
    };

    if enumerate {
        for (path, cands) in state::enumerate::walk(repo, &language) {
            for (site, key) in cands {
                println!("{path}\t{}\t{}\t{}\t{key}", site.kind, site.owner, site.name);
            }
        }
        return;
    }

    if reads {
        for (path, rows) in state::ref_reads::walk(repo, &language) {
            for row in rows {
                println!("{path}\t{}\t{}\t{}\t{}",
                         row.start, row.end, row.kind, row.flags.join(","));
            }
        }
        return;
    }

    if filters {
        for (path, rows) in state::filters::walk(repo, &language) {
            for row in rows {
                println!("{path}\t{}\t{}\t{}\t{}",
                         row.scope, row.key, row.refs, row.answers);
            }
        }
        return;
    }

    if unreachable {
        for (path, rows) in indicators::unreachable::walk(repo, &language) {
            for row in rows {
                println!("{path}\t{}\t{}", row.line, row.end_line);
            }
        }
        return;
    }

    if defs {
        // The facts a single file cannot answer are read once, the way the driver reads
        // them. A collector handed the wrong ones reports a different status, not a
        // different definition, which is the harder difference to see.
        let facts = indicators::dead_code_facts::repo_facts(repo, &language);
        for (path, d) in indicators::dead_code_defs::walk(repo, &language, &facts) {
            println!("{path}\t{}\t{}\t{}\t{}\t{}\t{}",
                     d.name, d.kind, d.line, d.end_line, d.status, d.reason);
        }
        return;
    }

    if census {
        for (path, sites) in state::census::walk(repo, &language) {
            for site in sites {
                println!("{path}\t{}\t{}\t{}", site.kind, site.owner, site.name);
            }
        }
        return;
    }

    // One row per canonical indicator, whether or not this binary computes it. An
    // indicator it cannot compute prints its reason; see src/coverage.rs.
    let panel = panel::analyze(repo, &language, exec_tests);

    if tsv {
        println!("lang\t{language}");
        for ind in &panel {
            println!("{}\t{}\t{}\t{}", ind.code, ind.value, ind.band, ind.details);
        }
        return;
    }

    println!("primary language: {language}");
    for ind in &panel {
        println!("{:<9} {:<24} {:<12} {:<12} {}", ind.code, ind.label, ind.value, ind.band, ind.details);
    }
}
