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
    // These three read NeedsTool("vulture"), NeedsTool("jscpd") and NeedsTool("gitleaks")
    // until 2026-09-21, and the advice was four weeks stale. On 2026-08-19 the spec started
    // defining each of them as an algorithm precise enough to reimplement, and the Python
    // reference computes all three natively; the three tools are named there as
    // cross-checks and nothing calls them. So a reader who installed vulture on this
    // binary's advice got nothing for it, because the reference it was sent to does not use
    // vulture either. They are in the same position as L1.18: this binary has not ported
    // them.
    ("L1.12", "dead-code", Coverage::NotPorted),
    ("L1.13", "duplication", Coverage::NotPorted),
    ("L1.14", "secret-scan", Coverage::NotPorted),
    ("L1.15", "type-escapes", Coverage::Measured),
    ("L1.16", "trailing-whitespace", Coverage::Measured),
    ("L1.17", "god-files", Coverage::Measured),
    ("L1.18", "mutable-state", Coverage::Measured),
    ("L1.18b", "finite-testability", Coverage::Measured),
    ("L1.19", "decision-space", Coverage::Measured),
    // Measured since 2026-09-21, when the decision was taken that this binary runs the
    // audited project's own suite. The panel always produces the row: either a reading, or
    // the reason the run did not take one.
    ("L1.20", "test-determinism", Coverage::Measured),
    // The additive checks. They are part of the reference panel, so they are part of the
    // contract: leaving them out of this table is how they stayed invisible while the
    // differ compared only the intersection of the two key sets.
    ("abs-paths", "absolute-paths", Coverage::Measured),
    ("path_cover", "path-cover", Coverage::Measured),
    ("thread_surface", "thread-surface", Coverage::Measured),
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

    /// An indicator this binary does not compute still gets a row saying so.
    ///
    /// L1.18 is the one that made this a P1 rather than a formatting complaint: it went
    /// missing from the printed panel and nothing noticed. It is measured now, so the check
    /// moved to interleaving_robustness, which is not. The rule it guards is about the shape of the
    /// panel and not about which indicator happens to be unported this week.
    #[test]
    fn an_unported_indicator_is_never_silently_absent() {
        let panel = reconcile(vec![]);
        let row = panel.iter().find(|i| i.code == "interleaving_robustness")
            .expect("interleaving_robustness row");
        assert_eq!(row.value, "not measured");
        assert_eq!(row.band, "not measured");
        assert!(row.details.contains("not ported"), "{}", row.details);
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
        // Two reasons remain, and they must stay distinguishable. A third, naming a tool
        // to install, and a fourth, saying this binary does not run tests, were both
        // removed when they stopped being true: the tools were replaced by algorithms, and
        // the binary now runs the suite.
        let not_ported = reason("interleaving_robustness");
        let defect = reason("L1.20");
        assert_ne!(not_ported, defect);
        assert!(not_ported.contains("not ported"), "{not_ported}");
        assert!(defect.contains("defect in the binary"), "{defect}");
        // No canonical row names a tool any more. Every one that did was wrong about it,
        // and a reason that sends a reader to install something is worth this check.
        for ind in panel {
            for tool in ["vulture", "jscpd", "gitleaks"] {
                assert!(!ind.details.contains(tool),
                        "{} still tells a reader to install {tool}", ind.code);
            }
        }
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
        assert_eq!(declared("interleaving_robustness").unwrap().2, Coverage::NotPorted);
        assert_eq!(declared("L1.18").unwrap().2, Coverage::Measured);
        assert!(declared("L1.99").is_none());
    }
}
