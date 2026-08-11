//! Portable slop-audit CLI. Runs every ported indicator and prints the panel. Each value is
//! validated equal to the pre-registered Python reference (l1_analyzer).
use slop_audit_rs::indicators;
use std::path::Path;

fn main() {
    let repo = std::env::args().nth(1).expect("usage: slop-audit-rs <repo>");
    let repo = Path::new(&repo);

    let mut panel = Vec::new();
    panel.extend(indicators::git_ratios::analyze(repo)); // L1.1 - L1.8
    panel.push(indicators::config_presence::l1_09(repo)); // L1.9
    panel.push(indicators::config_presence::l1_10(repo)); // L1.10
    panel.push(indicators::config_presence::l1_11(repo)); // L1.11
    panel.push(indicators::type_escapes::analyze(repo)); // L1.15 (python path)
    panel.push(indicators::whitespace::analyze(repo)); // L1.16
    panel.push(indicators::god_files::analyze(repo)); // L1.17 (python path)
    panel.push(indicators::absolute_paths::analyze(repo)); // additive

    for ind in &panel {
        println!("{:<9} {:<24} {:<12} {:<12} {}", ind.code, ind.label, ind.value, ind.band, ind.details);
    }
}
