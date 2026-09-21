//! What a reading of a repository's state looks like when it comes back. Ported from
//! l1_analyzer.state_reading.
//!
//! These are the shapes a caller HOLDS rather than the walk that fills them. In the
//! reference every one of these fields was an assumption until they were written down: the
//! reading was handed over as a mapping of anything to anything, so nothing could say
//! whether the findings were a list or the counts a table.

use crate::state::census::Census;
use crate::state::partition::Partition;
use crate::state::sites::Site;
use std::collections::{BTreeMap, BTreeSet};

/// One state finding, as the partition reader receives it.
///
/// The reference held this as a mapping of anything to anything: nine fields, written by
/// two builders and read by four modules, and every read was an assumption. Twenty-one of
/// those reads were indexing an untyped value as far as the type checker could tell.
#[derive(Debug, Clone)]
pub struct Finding {
    pub state: String,
    pub verdict: &'static str,
    pub drives_decision: bool,
    pub file: String,
    pub line: usize,
    pub silence: &'static str,
    pub construct: String,
    /// The line the CONSTRUCT was read off, not where the state was bound, so a reader is
    /// sent to the shape the finding names. The two are usually different, and publishing
    /// the binding line named a shape at a line that does not hold it.
    pub silence_line: usize,
    pub partition: Partition,
}

/// What the classifier made of one file, and what it walked to get there.
///
/// `visited` and `judged` are the two halves the old coverage number could not separate.
/// `visited` is every declaration the enumerators REACHED, admitted or declined; `judged`
/// is the subset that yielded a state key which then reached a verdict. A declaration in
/// neither is one nothing looked at, and only that is a gap in the reading.
///
/// They are sets of census-vocabulary sites, not counts, because the comparison happens
/// against the census's own per-file site set and a count cannot be intersected.
#[derive(Debug, Clone, Default)]
pub struct FileRead {
    pub findings: Vec<Finding>,
    pub visited: BTreeSet<Site>,
    pub judged: BTreeSet<Site>,
}

/// One reference the reader could not decide, and the shape that stopped it.
///
/// `line` is the SILENT REFERENCE's line, not the state's binding line. The two are
/// usually different, and publishing the binding line named a shape at a line that does
/// not hold it, which makes the backlog this list exists to be unworkable.
///
/// `construct` is empty on every reason but an unmodelled construct, and on that one it
/// names the syntax shape no dispatch row covered. Without it the reader is told a rule is
/// missing and not which one, which is a complaint rather than a backlog.
#[derive(Debug, Clone)]
pub struct SilenceSite {
    pub file: String,
    pub line: usize,
    pub state: String,
    pub reason: &'static str,
    pub construct: String,
}

/// What the reader could not decide, over one repository.
///
/// The reference held this as a mapping of anything to anything, so the card's read of the
/// sites was an assumption, and the card is where the silence sites ARE the whole report on
/// a repository that was refused a grade.
#[derive(Debug, Clone, Default)]
pub struct Silence {
    pub count: usize,
    pub fraction: f64,
    pub by_reason: BTreeMap<&'static str, usize>,
    pub sites: Vec<SilenceSite>,
}

/// The whole reading of a repository's state.
#[derive(Debug, Clone)]
pub struct StateReading {
    /// The word a card prints beside the number. It was written on every reading and named
    /// nowhere, so the field the card reads first was the field nothing described.
    pub verdict: String,
    pub band: String,
    pub counts: BTreeMap<&'static str, usize>,
    /// A number when the meter ran, and ABSENT when it did not.
    ///
    /// The reference declared this a number and its refusal wrote the string "n/a" into
    /// it, so the one field that says whether the reading happened at all held two types
    /// and every reader had to ask which it got. Absence is a case here, which is what the
    /// contract always meant.
    pub resolvable_fraction: Option<f64>,
    pub silence: Silence,
    pub census: Census,
    pub findings: Vec<Finding>,
    pub details: String,
}

/// The silence index: the share of state the analyzer could not decide, and every site.
///
/// Reported BESIDE the grade and never inside it. A state we did not decide is not
/// evidence about the audited code, so counting it as a defect reports our own blind spot
/// as their fault, which is the failure this measure exists to stop.
///
/// Sites are listed in full rather than capped, because the reader's next move is to open
/// each one and decide whether to make that boundary readable, and a sampled list cannot
/// support that.
///
/// `by_reason` always carries EVERY reason key, so a consumer reading a zero knows the
/// analyzer looked and found none, rather than guessing whether the key was omitted.
pub fn silence_summary(findings: &[Finding], total: usize) -> Silence {
    let silent: Vec<&Finding> = findings.iter().filter(|f| !f.silence.is_empty()).collect();
    let mut by_reason: BTreeMap<&'static str, usize> =
        crate::state::partition::SILENCE_REASONS.iter().map(|r| (*r, 0)).collect();
    for f in &silent {
        *by_reason.entry(f.silence).or_insert(0) += 1;
    }
    Silence {
        count: silent.len(),
        // Nought over zero state is vacuously true and deliberately kept: no state means
        // nothing went unread. The vacuity checker flags this as a fabricated affirmative
        // and it is a FALSE POSITIVE, because the failure it guards against, a repository
        // the classifier never read, is caught by the census rather than here. Replacing
        // the constant with absence broke three census tests that say exactly that.
        fraction: if total == 0 {
            0.0
        } else {
            (silent.len() as f64 / total as f64 * 1000.0).round() / 1000.0
        },
        by_reason,
        sites: silent.iter().map(|f| SilenceSite {
            file: f.file.clone(),
            // The reference's line, falling back to the state's own when the finding
            // carries none. The finding KEEPS the binding line, because that is the right
            // answer about the state; only the site follows the reference.
            line: if f.silence_line > 0 { f.silence_line } else { f.line },
            state: f.state.clone(),
            reason: f.silence,
            construct: f.construct.clone(),
        }).collect(),
    }
}

/// The cardinality distribution over state that decides something, plus the count of
/// partitions whose size could not be recovered.
///
/// The unordered class counts are published as the raw list rather than a summary
/// statistic, because the bound that turns a cardinality into a grade has to be set from a
/// distribution, and a mean cannot answer where real code sits.
#[derive(Debug, Clone, Default)]
pub struct PartitionSummary {
    pub deciding_states: usize,
    pub uncounted: usize,
    pub ordered_classes: Vec<i64>,
    pub unordered_classes: Vec<i64>,
}

pub fn partition_summary(findings: &[Finding]) -> PartitionSummary {
    let deciding: Vec<&Finding> = findings
        .iter()
        .filter(|f| f.verdict == crate::state::partition::NEUTRAL && f.drives_decision)
        .collect();
    let counted: Vec<&&Finding> = deciding.iter().filter(|f| f.partition.counted).collect();
    let mut ordered: Vec<i64> = counted.iter().filter(|f| f.partition.ordered)
        .map(|f| f.partition.classes).collect();
    let mut unordered: Vec<i64> = counted.iter().filter(|f| !f.partition.ordered)
        .map(|f| f.partition.classes).collect();
    ordered.sort_unstable();
    unordered.sort_unstable();
    PartitionSummary {
        deciding_states: deciding.len(),
        uncounted: deciding.len() - counted.len(),
        ordered_classes: ordered,
        unordered_classes: unordered,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::state::partition::{EXTERNAL_BOUNDARY, NEUTRAL, UNMODELED_CONSTRUCT};

    fn finding(silence: &'static str, line: usize, silence_line: usize) -> Finding {
        Finding {
            state: "cache".into(),
            verdict: NEUTRAL,
            drives_decision: true,
            file: "m.py".into(),
            line,
            silence,
            construct: String::new(),
            silence_line,
            partition: Partition { classes: 2, ordered: true, counted: true },
        }
    }

    #[test]
    fn every_reason_key_is_present_so_a_zero_means_the_analyzer_looked() {
        let summary = silence_summary(&[finding("", 1, 0)], 1);
        for reason in crate::state::partition::SILENCE_REASONS {
            assert!(summary.by_reason.contains_key(reason), "{reason} missing");
        }
        assert_eq!(summary.count, 0);
    }

    #[test]
    fn a_site_is_reported_at_the_reference_that_was_silent_not_at_the_binding() {
        // The two are usually different, and publishing the binding line names a shape at
        // a line that does not hold it, which makes the backlog unworkable.
        let summary = silence_summary(&[finding(EXTERNAL_BOUNDARY, 4, 19)], 1);
        assert_eq!(summary.sites[0].line, 19);
    }

    #[test]
    fn a_finding_with_no_reference_line_falls_back_to_the_states_own() {
        let summary = silence_summary(&[finding(EXTERNAL_BOUNDARY, 4, 0)], 1);
        assert_eq!(summary.sites[0].line, 4);
    }

    #[test]
    fn no_state_at_all_reads_as_nothing_went_unread() {
        // Vacuously true and deliberately kept. The failure this could hide, a repository
        // the classifier never read, is caught by the census instead.
        assert_eq!(silence_summary(&[], 0).fraction, 0.0);
    }

    #[test]
    fn the_fraction_is_the_share_of_state_the_reader_could_not_decide() {
        let findings = [finding(EXTERNAL_BOUNDARY, 1, 0), finding("", 2, 0),
                        finding("", 3, 0), finding("", 4, 0)];
        assert_eq!(silence_summary(&findings, 4).fraction, 0.25);
    }

    #[test]
    fn sites_are_listed_in_full_because_the_readers_next_move_is_to_open_each_one() {
        let findings: Vec<Finding> =
            (1..=40).map(|n| finding(UNMODELED_CONSTRUCT, n, n)).collect();
        assert_eq!(silence_summary(&findings, 40).sites.len(), 40);
    }

    #[test]
    fn a_state_that_decides_nothing_is_not_in_the_cardinality_distribution() {
        let mut quiet = finding("", 1, 0);
        quiet.drives_decision = false;
        let summary = partition_summary(&[quiet]);
        assert_eq!(summary.deciding_states, 0);
        assert!(summary.ordered_classes.is_empty());
    }

    #[test]
    fn an_uncounted_partition_is_counted_as_uncounted_and_not_as_a_cardinality() {
        let mut unknown = finding("", 1, 0);
        unknown.partition = crate::state::partition::UNKNOWN;
        let summary = partition_summary(&[unknown]);
        assert_eq!(summary.deciding_states, 1);
        assert_eq!(summary.uncounted, 1);
        assert!(summary.ordered_classes.is_empty() && summary.unordered_classes.is_empty());
    }

    #[test]
    fn ordered_and_unordered_cardinalities_are_published_apart() {
        // The bound that turns a cardinality into a grade is set from a distribution, and
        // limit testing defeats the ordered half, so mixing them would set it from noise.
        let mut wide = finding("", 1, 0);
        wide.partition = Partition { classes: 9, ordered: false, counted: true };
        let summary = partition_summary(&[finding("", 1, 0), wide]);
        assert_eq!(summary.ordered_classes, vec![2]);
        assert_eq!(summary.unordered_classes, vec![9]);
    }
}
