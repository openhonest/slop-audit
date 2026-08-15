//! The canonical indicator set, and the reason any member of it carries no measurement.
//!
//! The panel used to be whatever happened to compute. Six indicators were absent from the
//! output with no row at all, L1.18 among them, which is the headline indicator and the
//! thing finite testability means. A scorecard missing it read as complete.
//!
//! The defect was not the omission. It was that "not ported", "the external tool is absent"
//! and "it ran and found nothing" all reduced to the same observable, which is silence. A
//! consumer could not tell them apart and neither could a maintainer, which is why a release
//! shipping a superseded classifier was undetectable from its own output.
//!
//! So the canonical set is declared here as data, and every run emits one row per member.
//! An indicator that was not measured says why it was not measured. Absence is not
//! representable: a code that computes nothing still prints, and a code that is not in this
//! table cannot reach the panel at all.

use crate::Indicator;

/// Why an indicator carries no measurement. `Measured` means this binary computes it.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Coverage {
    Measured,
    /// Implemented in the Python reference, not yet ported to this binary.
    NotPorted,
    /// Needs a third-party tool the single-file binary deliberately does not bundle.
    NeedsTool(&'static str),
    /// Needs the target's own suite to run, which this binary does not do.
    NeedsTestRun,
}

impl Coverage {
    /// The `band` cell for an unmeasured row. Kept distinct from a real band so a reader
    /// never mistakes "not measured" for a grade. Every fallback row gets it, including the
    /// `Measured` case below, because a row with no band is exactly the silence this
    /// module exists to remove.
    pub fn band(self) -> &'static str {
        "not measured"
    }

    /// The `details` cell for an unmeasured row: the reason, in the reader's words.
    pub fn details(self) -> String {
        match self {
            // Reached only when an indicator declared Measured produced no row, which is a
            // defect in this binary rather than a known gap. Saying so beats an empty cell:
            // the first version of this fix left it blank and reintroduced the same silence
            // in miniature, which is what the band test caught.
            Coverage::Measured => {
                "declared measured but this run produced no row; this is a defect in the binary, \
                 please report it"
                    .into()
            }
            Coverage::NotPorted => {
                "not ported to the portable binary; run the Python reference for this indicator"
                    .into()
            }
            Coverage::NeedsTool(tool) => format!(
                "requires {tool}, which the single-file binary does not bundle; run the Python \
                 reference for this indicator"
            ),
            Coverage::NeedsTestRun => {
                "requires executing the target's own test suite, which this binary does not do"
                    .into()
            }
        }
    }
}

/// Every indicator the Slop Audit Layer 1 panel is defined to carry, in report order.
///
/// This is the contract with the Python reference: the two implementations must agree on
/// the key set before any question about agreeing on values is meaningful. Parity read
/// 16/16 for weeks across a set that silently excluded L1.18, because nothing compared the
/// key sets themselves.
pub const CANONICAL: &[(&str, &str, Coverage)] = &[
    ("L1.1", "commit-message-quality", Coverage::Measured),
    ("L1.2", "commit-size", Coverage::Measured),
    ("L1.3", "revert-ratio", Coverage::Measured),
    ("L1.4", "doc-line-ratio", Coverage::Measured),
    ("L1.5", "delete-add-ratio", Coverage::Measured),
    ("L1.6", "churn", Coverage::Measured),
    ("L1.7", "high-delete-commits", Coverage::Measured),
    ("L1.8", "test-to-prod-ratio", Coverage::Measured),
    ("L1.9", "pre-commit hooks", Coverage::Measured),
    ("L1.10", "CI/CD pipelines", Coverage::Measured),
    ("L1.11", "containerization", Coverage::Measured),
    ("L1.12", "dead-code", Coverage::NeedsTool("vulture")),
    ("L1.13", "duplication", Coverage::NeedsTool("jscpd")),
    ("L1.14", "secret-scan", Coverage::NeedsTool("gitleaks")),
    ("L1.15", "type-escapes", Coverage::Measured),
    ("L1.16", "trailing-whitespace", Coverage::Measured),
    ("L1.17", "god-files", Coverage::Measured),
    ("L1.18", "mutable-state", Coverage::NotPorted),
    ("L1.18b", "finite-testability", Coverage::NotPorted),
    ("L1.19", "decision-space", Coverage::Measured),
    ("L1.20", "test-determinism", Coverage::NeedsTestRun),
    // The additive checks. They are part of the reference panel, so they are part of the
    // contract: leaving them out of this table is how they stayed invisible while the
    // differ compared only the intersection of the two key sets.
    ("abs-paths", "absolute-paths", Coverage::Measured),
    ("path_cover", "path-cover", Coverage::NotPorted),
    ("thread_surface", "thread-surface", Coverage::NotPorted),
    ("interleaving_robustness", "interleaving-robustness", Coverage::NotPorted),
];

/// The canonical row for a code, or `None` if the code is not canonical.
pub fn declared(code: &str) -> Option<(&'static str, &'static str, Coverage)> {
    CANONICAL
        .iter()
        .find(|(candidate, _, _)| *candidate == code)
        .map(|(c, label, cov)| (*c, *label, *cov))
}

/// One row per canonical indicator, in report order, whatever the run produced.
///
/// A measured indicator keeps its computed row. An unmeasured one gets a row carrying its
/// reason. A produced code outside the canonical set is a programming error and is dropped
/// rather than printed, because the panel's shape is the contract; `produced_are_canonical`
/// is the test that keeps that from happening silently.
pub fn reconcile(produced: Vec<Indicator>) -> Vec<Indicator> {
    CANONICAL
        .iter()
        .map(|(code, label, cov)| {
            produced
                .iter()
                .find(|ind| ind.code == *code)
                .cloned()
                .unwrap_or_else(|| Indicator {
                    code: (*code).into(),
                    label: (*label).into(),
                    value: "not measured".into(),
                    band: cov.band().into(),
                    details: cov.details(),
                })
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn indicator(code: &str) -> Indicator {
        Indicator {
            code: code.into(),
            label: "x".into(),
            value: "1.0".into(),
            band: "Healthy".into(),
            details: "measured".into(),
        }
    }

    /// The regression test for the defect: every canonical indicator gets a row, including
    /// the six this binary cannot compute. Before the fix the panel simply omitted them.
    #[test]
    fn every_canonical_indicator_gets_a_row() {
        let panel = reconcile(vec![indicator("L1.1")]);
        let codes: Vec<&str> = panel.iter().map(|i| i.code.as_str()).collect();
        for (code, _, _) in CANONICAL {
            assert!(codes.contains(code), "{code} missing from the panel");
        }
        assert_eq!(panel.len(), CANONICAL.len());
    }

    /// L1.18 is the one that made this a P1 rather than a formatting complaint.
    #[test]
    fn the_headline_indicator_is_never_silently_absent() {
        let panel = reconcile(vec![]);
        let l18 = panel.iter().find(|i| i.code == "L1.18").expect("L1.18 row");
        assert_eq!(l18.value, "not measured");
        assert_eq!(l18.band, "not measured");
        assert!(l18.details.contains("not ported"), "{}", l18.details);
    }

    /// An unmeasured row must never look like a grade. "not measured" is not a band, and a
    /// reader scanning the band column must not read a missing indicator as a passing one.
    #[test]
    fn unmeasured_rows_do_not_claim_a_band() {
        for ind in reconcile(vec![]) {
            assert_eq!(ind.band, "not measured", "{} claimed a band", ind.code);
            assert!(!ind.details.is_empty(), "{} gave no reason", ind.code);
        }
    }

    /// The three reasons stay distinguishable. Collapsing them back into one string would
    /// reintroduce the defect in a form that still passes the other tests.
    #[test]
    fn each_reason_reads_differently() {
        let panel = reconcile(vec![]);
        let reason = |code: &str| {
            panel.iter().find(|i| i.code == code).unwrap().details.clone()
        };
        let not_ported = reason("L1.18");
        let needs_tool = reason("L1.14");
        let needs_run = reason("L1.20");
        assert_ne!(not_ported, needs_tool);
        assert_ne!(needs_tool, needs_run);
        assert_ne!(not_ported, needs_run);
        assert!(needs_tool.contains("gitleaks"), "{needs_tool}");
    }

    /// A measured indicator keeps its own row untouched.
    #[test]
    fn measured_rows_survive_reconciliation() {
        let panel = reconcile(vec![indicator("L1.5")]);
        let l5 = panel.iter().find(|i| i.code == "L1.5").unwrap();
        assert_eq!(l5.value, "1.0");
        assert_eq!(l5.band, "Healthy");
    }

    /// Report order is the contract, so a diff against the Python reference lines up.
    #[test]
    fn canonical_order_is_stable_and_unique() {
        let mut seen = std::collections::HashSet::new();
        for (code, _, _) in CANONICAL {
            assert!(seen.insert(*code), "{code} declared twice");
        }
        assert_eq!(CANONICAL[0].0, "L1.1");
        assert_eq!(declared("L1.18").unwrap().2, Coverage::NotPorted);
        assert!(declared("L1.99").is_none());
    }
}
