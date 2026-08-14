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
//! Arguments are parsed by hand: a CLI parser crate would add weight to a binary whose
//! whole purpose is to be one small self-contained file.
use slop_audit_rs::{indicators, lang};
use std::path::Path;

fn usage() -> ! {
    eprintln!("usage: slop-audit-rs <repo> [--lang KEY] [--tsv]");
    std::process::exit(2);
}

fn main() {
    let mut repo_arg: Option<String> = None;
    let mut lang_arg: Option<String> = None;
    let mut tsv = false;

    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--tsv" => tsv = true,
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

    let mut panel = Vec::new();
    panel.extend(indicators::git_ratios::analyze(repo)); // L1.1 - L1.8
    panel.push(indicators::config_presence::l1_09(repo)); // L1.9
    panel.push(indicators::config_presence::l1_10(repo)); // L1.10
    panel.push(indicators::config_presence::l1_11(repo)); // L1.11
    panel.push(indicators::type_escapes::analyze(repo, &language)); // L1.15
    panel.push(indicators::whitespace::analyze(repo)); // L1.16
    panel.push(indicators::god_files::analyze(repo)); // L1.17 (all languages)
    panel.push(indicators::decision_space::analyze(repo, &language)); // L1.19 (static half)
    panel.push(indicators::absolute_paths::analyze(repo)); // additive

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
