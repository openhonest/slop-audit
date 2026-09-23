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

/// The reason a canonical row is missing from a run, and there is only one of them.
///
/// A `Coverage` enum used to stand here with a second case, NotPorted, which was the honest
/// thing to carry while six indicators were implemented only in the Python reference. L1.14
/// was the last of them, and with every member of the table measured the second case became
/// unreachable. It is deleted rather than kept: a type with two cases and one reachable case
/// is a decision space of one wearing the clothes of two, which is the shape this binary's
/// own L1.19 counts.
///
/// Saying this beats an empty cell. The first version of the fix left it blank and
/// reintroduced the same silence in miniature, which is what the band test caught.
const NO_ROW: &str = "declared measured but this run produced no row; this is a defect in the \
                      binary, please report it";

/// The `band` cell for a row no run produced. Kept apart from every real band so a reader
/// never mistakes a missing indicator for a passing one.
const NO_BAND: &str = "not measured";

/// Every indicator the Slop Audit Layer 1 panel is defined to carry, in report order.
///
/// This is the contract with the Python reference: the two implementations must agree on
/// the key set before any question about agreeing on values is meaningful. Parity read
/// 16/16 for weeks across a set that silently excluded L1.18, because nothing compared the
/// key sets themselves.
///
/// Every member is measured here, as of 2026-09-23. The table used to carry a third column
/// saying which were not, and the column is gone because the answer became "none".
pub const CANONICAL: &[(&str, &str)] = &[
    ("L1.1", "commit-message-quality"),
    ("L1.2", "commit-size"),
    ("L1.3", "revert-ratio"),
    ("L1.4", "doc-line-ratio"),
    ("L1.5", "delete-add-ratio"),
    ("L1.6", "churn"),
    ("L1.7", "high-delete-commits"),
    ("L1.8", "test-to-prod-ratio"),
    ("L1.9", "pre-commit hooks"),
    ("L1.10", "CI/CD pipelines"),
    ("L1.11", "containerization"),
    // These three read NeedsTool("vulture"), NeedsTool("jscpd") and NeedsTool("gitleaks")
    // until 2026-09-21, and the advice was four weeks stale. On 2026-08-19 the spec started
    // defining each of them as an algorithm precise enough to reimplement, and the Python
    // reference computes all three natively; the three tools are named there as cross-checks
    // and nothing calls them. So a reader who installed vulture on this binary's advice got
    // nothing for it, because the reference it was sent to does not use vulture either. All
    // three are measured here now, and no row names a tool to install.
    ("L1.12", "dead-code"),
    ("L1.13", "duplication"),
    ("L1.14", "secret-scan"),
    ("L1.15", "type-escapes"),
    ("L1.16", "trailing-whitespace"),
    ("L1.17", "god-files"),
    ("L1.18", "mutable-state"),
    ("L1.18b", "finite-testability"),
    ("L1.19", "decision-space"),
    // Measured since 2026-09-21, when the decision was taken that this binary runs the
    // audited project's own suite. The panel always produces the row: either a reading, or
    // the reason the run did not take one.
    ("L1.20", "test-determinism"),
    // The additive checks. They are part of the reference panel, so they are part of the
    // contract: leaving them out of this table is how they stayed invisible while the
    // differ compared only the intersection of the two key sets.
    ("abs-paths", "absolute-paths"),
    ("path_cover", "path-cover"),
    ("thread_surface", "thread-surface"),
    ("interleaving_robustness", "interleaving-robustness"),
];

/// The canonical row for a code, or `None` if the code is not canonical.
pub fn declared(code: &str) -> Option<(&'static str, &'static str)> {
    CANONICAL
        .iter()
        .find(|(candidate, _)| *candidate == code)
        .map(|(c, label)| (*c, *label))
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
        .map(|(code, label)| {
            produced
                .iter()
                .find(|ind| ind.code == *code)
                .cloned()
                .unwrap_or_else(|| Indicator {
                    code: (*code).into(),
                    label: (*label).into(),
                    value: NO_BAND.into(),
                    band: NO_BAND.into(),
                    details: NO_ROW.into(),
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

    /// The regression test for the defect: every canonical indicator gets a row, whatever
    /// the run produced. Before the fix the panel carried 15 of 22 and said nothing about
    /// the other seven.
    #[test]
    fn every_canonical_indicator_gets_a_row() {
        let panel = reconcile(vec![indicator("L1.1")]);
        let codes: Vec<&str> = panel.iter().map(|i| i.code.as_str()).collect();
        for (code, _) in CANONICAL {
            assert!(codes.contains(code), "{code} missing from the panel");
        }
        assert_eq!(panel.len(), CANONICAL.len());
    }

    /// An indicator that produced nothing still gets a row, and the row says the binary is
    /// at fault.
    ///
    /// L1.18 is the one that made this a P1 rather than a formatting complaint: it went
    /// missing from the printed panel and nothing noticed. Every canonical indicator is
    /// measured now, so a missing row can only be a defect, and the row says so rather than
    /// leaving a reader to guess.
    #[test]
    fn an_indicator_that_produced_nothing_is_never_silently_absent() {
        let panel = reconcile(vec![]);
        let row = panel.iter().find(|i| i.code == "L1.14").expect("L1.14 row");
        assert_eq!(row.value, "not measured");
        assert_eq!(row.band, "not measured");
        assert!(row.details.contains("defect in the binary"), "{}", row.details);
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

    /// No row sends a reader to install a tool.
    ///
    /// Four reasons used to live here: not ported, install this tool, this binary does not
    /// run tests, and a defect. Three of them stopped being true one at a time, and one
    /// remains. Every one that named a tool was wrong about it, and a reason that sends a
    /// reader off to install something is worth a standing check.
    #[test]
    fn no_reason_names_a_tool_to_install() {
        for ind in reconcile(vec![]) {
            assert!(ind.details.contains("defect in the binary"), "{}", ind.details);
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
        for (code, _) in CANONICAL {
            assert!(seen.insert(*code), "{code} declared twice");
        }
        assert_eq!(CANONICAL[0].0, "L1.1");
        assert_eq!(declared("L1.14").unwrap().1, "secret-scan");
        assert_eq!(declared("L1.12").unwrap().1, "dead-code");
        assert!(declared("L1.99").is_none());
    }
}
