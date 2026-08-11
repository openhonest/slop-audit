//! Portable slop-audit CLI. Runs each registered indicator and prints the panel.
use slop_audit_rs::indicators;
use std::path::Path;

fn main() {
    let repo = std::env::args().nth(1).expect("usage: slop-audit-rs <repo>");
    let repo = Path::new(&repo);
    let panel = vec![indicators::whitespace::analyze(repo)];
    for ind in &panel {
        println!("{:<7} {:<22} {:<10} {}", ind.code, ind.label, ind.value, ind.band);
    }
}
