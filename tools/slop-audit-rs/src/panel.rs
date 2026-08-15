//! Building the panel for a repository.
//!
//! Lifted out of `main` so the shape of the output is testable. While it lived in `main`
//! nothing could assert what the binary actually emits, which is how six indicators went
//! missing from the output without a single test noticing.

use crate::{coverage, indicators, Indicator};
use std::path::Path;

/// Every indicator this binary computes, before reconciliation against the canonical set.
fn measured(repo: &Path, language: &str) -> Vec<Indicator> {
    let mut panel = Vec::new();
    panel.extend(indicators::git_ratios::analyze(repo)); // L1.1 - L1.8
    panel.push(indicators::config_presence::l1_09(repo)); // L1.9
    panel.push(indicators::config_presence::l1_10(repo)); // L1.10
    panel.push(indicators::config_presence::l1_11(repo)); // L1.11
    panel.push(indicators::type_escapes::analyze(repo, language)); // L1.15
    panel.push(indicators::whitespace::analyze(repo)); // L1.16
    panel.push(indicators::god_files::analyze(repo)); // L1.17 (all languages)
    panel.push(indicators::decision_space::analyze(repo, language)); // L1.19 (static half)
    panel.push(indicators::absolute_paths::analyze(repo)); // additive
    panel
}

/// The panel as printed: one row per canonical indicator, measured or with its reason.
pub fn analyze(repo: &Path, language: &str) -> Vec<Indicator> {
    coverage::reconcile(measured(repo, language))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The defect, at the level a consumer meets it. On a real repository the printed panel
    /// must carry every canonical code. Before the fix it carried 15 of 22 and said nothing
    /// about the other seven.
    #[test]
    fn the_printed_panel_covers_the_canonical_set() {
        let repo = Path::new(env!("CARGO_MANIFEST_DIR"));
        let codes: Vec<String> = analyze(repo, "rust").iter().map(|i| i.code.clone()).collect();
        for (code, _, _) in coverage::CANONICAL {
            assert!(codes.iter().any(|c| c == code), "{code} missing from the printed panel");
        }
    }

    /// The other direction, which is the one that rots quietly: an indicator this binary
    /// computes but the canonical set does not declare would be dropped from the output.
    /// Porting L1.18 without adding it to CANONICAL would compute the right answer and
    /// print nothing, so this test fails the moment the two lists drift apart.
    #[test]
    fn every_measured_indicator_is_declared_canonical() {
        let repo = Path::new(env!("CARGO_MANIFEST_DIR"));
        for ind in measured(repo, "rust") {
            assert!(
                coverage::declared(&ind.code).is_some(),
                "{} is computed but not declared in CANONICAL, so it would be dropped",
                ind.code
            );
        }
    }

    /// Coverage::Measured is a claim about this binary, and a claim that drifts is worse
    /// than no claim. Anything declared Measured must actually turn up in a real run.
    #[test]
    fn declared_measured_indicators_are_actually_measured() {
        let repo = Path::new(env!("CARGO_MANIFEST_DIR"));
        let produced: Vec<String> = measured(repo, "rust").iter().map(|i| i.code.clone()).collect();
        for (code, _, cov) in coverage::CANONICAL {
            if *cov == coverage::Coverage::Measured {
                assert!(
                    produced.iter().any(|c| c == code),
                    "{code} is declared Measured but no run produced it"
                );
            }
        }
    }
}
