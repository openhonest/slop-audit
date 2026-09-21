//! L1.20 from a sequence of finished runs. Ported from pytest_trace.determinism_tally.
//!
//! One rule, nine languages. C# and Java spelled it out separately and the two were
//! identical statement for statement, differing only in a parameter name and their
//! strings. The duplication detector found it, on the first measurement of that package
//! the indicator had ever produced.
//!
//! No I/O here, so the whole rule can be asserted as a value.

use crate::runtime::{determinism_band, timeout_note, TIMED_OUT};

/// One indicator reading, in the shape the panel prints.
#[derive(Debug, Clone, PartialEq)]
pub struct Reading {
    pub value: String,
    pub band: String,
    pub details: String,
}

/// Not measured, and why. The reason is never optional: a refusal nobody can act on is the
/// silence this instrument exists to name.
pub fn not_measured(reason: impl Into<String>) -> Reading {
    Reading { value: "n/a".into(), band: "n/a".into(), details: reason.into() }
}

/// The vocabulary one language uses for a determinism run.
///
/// DATA, not behaviour. Java randomises by seed, so run three is seed three; `dotnet test`
/// has no seed flag and varies by scheduler, so run three is just run three. A C# reader
/// must not be told about seeds. The words differ and the RULES do not, which is why the
/// words travel as a value and the rules live in one function.
pub struct RunWords {
    /// What one attempt is called: "run", "seed".
    pub unit: &'static str,
    /// What a timed-out attempt is called.
    pub timed_out: &'static str,
    /// The sentence for zero attempts.
    pub no_runs: &'static str,
    /// The tail of the details line, after "N of M ".
    pub describe: String,
}

/// What one finished attempt tells the tally.
///
/// `ran_tests` and the two sentences are computed by the caller, because what counts as a
/// suite having run is the language's own question: Java reads its runner's XML reports,
/// Ruby reads the runner's own summary line, and a language that knows the answer before
/// it looks says so without reading anything.
pub struct Attempt {
    pub status: i32,
    /// Whether this attempt executed any tests at all. A compilation failure and a module
    /// with no tests both answer false, and neither is a determinism data point.
    pub ran_tests: bool,
    /// What to say about an attempt that ran and failed, so a low score arrives carrying
    /// its own reason instead of a bare number.
    pub summary: String,
    /// Why an attempt that did not run did not run.
    pub why_it_did_not_run: String,
}

/// L1.20 from a sequence of finished runs.
///
/// The count comes from the OUTCOMES rather than from a requested number of runs, so the
/// value reports what actually happened. No outcomes at all is not measured: zero clean out
/// of zero satisfies "every run passed" and would band Healthy, which is the zero
/// denominator lie this instrument exists to refuse.
///
/// `attempts` is consumed lazily, so a caller may hand over an iterator that runs the suite
/// one attempt at a time. Returning on the first terminal outcome is then what stops the
/// remaining attempts from each burning a full timeout.
pub fn tally<I>(attempts: I, words: &RunWords, timeout_seconds: f64) -> Reading
where
    I: IntoIterator<Item = Attempt>,
{
    let mut passing = 0usize;
    let mut made = 0usize;
    let mut failing: Vec<String> = Vec::new();

    for attempt in attempts {
        made += 1;
        if attempt.status == TIMED_OUT {
            return not_measured(format!(
                "{} ({} {made}); determinism not measured{}",
                words.timed_out, words.unit, timeout_note(timeout_seconds)));
        }
        if !attempt.ran_tests {
            return not_measured(format!(
                "the suite did not run ({} {made}: {}); determinism not measured",
                words.unit, attempt.why_it_did_not_run));
        }
        if attempt.status == 0 {
            passing += 1;
        } else {
            failing.push(format!("{} {made}: {}", words.unit, attempt.summary));
        }
    }

    if made == 0 {
        return not_measured(words.no_runs);
    }
    let mut details = format!("{passing} of {made} {}", words.describe);
    if !failing.is_empty() {
        let shown: Vec<String> = failing.into_iter().take(3).collect();
        details.push_str(&format!("; runs with failures: {}", shown.join("; ")));
    }
    Reading {
        value: format!("{passing}/{made}"),
        band: determinism_band(passing, made).into(),
        details,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn words() -> RunWords {
        RunWords {
            unit: "seed",
            timed_out: "a seed timed out",
            no_runs: "no randomized-order runs were made; determinism not measured",
            describe: "randomized-order runs passed cleanly (under a runtime)".into(),
        }
    }

    fn clean() -> Attempt {
        Attempt { status: 0, ran_tests: true, summary: "Tests run: 12".into(),
                  why_it_did_not_run: String::new() }
    }

    fn failed() -> Attempt {
        Attempt { status: 1, ran_tests: true, summary: "Tests run: 12, Failures: 2".into(),
                  why_it_did_not_run: String::new() }
    }

    #[test]
    fn every_run_clean_is_the_whole_count_and_healthy() {
        let reading = tally((0..5).map(|_| clean()), &words(), 300.0);
        assert_eq!(reading.value, "5/5");
        assert_eq!(reading.band, "Healthy");
    }

    #[test]
    fn a_failing_run_is_named_with_its_own_counts() {
        // A low score has to arrive carrying its own reason. A bare number sends a reader
        // to look for something the run already knew.
        let reading = tally(vec![clean(), failed()], &words(), 300.0);
        assert_eq!(reading.value, "1/2");
        assert!(reading.details.contains("seed 2: Tests run: 12, Failures: 2"),
                "{}", reading.details);
    }

    #[test]
    fn at_most_three_failing_runs_are_named() {
        let reading = tally((0..5).map(|_| failed()), &words(), 300.0);
        assert_eq!(reading.details.matches("seed ").count(), 3);
    }

    #[test]
    fn a_run_that_executed_no_tests_is_not_a_determinism_result() {
        // A compilation failure is not flakiness. Nought of five here would read as a
        // flaky suite, which is a claim about the audited code rather than about us.
        let attempts = vec![clean(), Attempt {
            status: 1, ran_tests: false, summary: String::new(),
            why_it_did_not_run: "no tests executed under a runtime".into() }];
        let reading = tally(attempts, &words(), 300.0);
        assert_eq!(reading.band, "n/a");
        assert!(reading.details.contains("seed 2"));
        assert!(reading.details.contains("did not run"));
    }

    #[test]
    fn a_timed_out_run_names_its_seed_and_the_seconds_it_was_allowed() {
        let attempts = vec![clean(), Attempt {
            status: TIMED_OUT, ran_tests: false, summary: String::new(),
            why_it_did_not_run: String::new() }];
        let reading = tally(attempts, &words(), 300.0);
        assert_eq!(reading.band, "n/a");
        assert!(reading.details.contains("seed 2"));
        assert!(reading.details.contains("allowed 300s"), "{}", reading.details);
    }

    #[test]
    fn no_runs_at_all_is_absent_and_never_a_clean_sweep() {
        // Nought of nought satisfies "every run passed". It must not band Healthy.
        let reading = tally(Vec::new(), &words(), 300.0);
        assert_eq!(reading.band, "n/a");
        assert_eq!(reading.value, "n/a");
    }

    #[test]
    fn a_terminal_run_stops_the_remaining_runs_from_being_made() {
        // The attempts are consumed lazily, so the verdict returning at the second one is
        // what stops the third, fourth and fifth from each burning a full timeout.
        let made = std::cell::Cell::new(0);
        let attempts = (0..5).map(|n| {
            made.set(made.get() + 1);
            if n == 1 {
                Attempt { status: TIMED_OUT, ran_tests: false, summary: String::new(),
                          why_it_did_not_run: String::new() }
            } else {
                clean()
            }
        });
        let reading = tally(attempts, &words(), 300.0);
        assert_eq!(reading.band, "n/a");
        assert_eq!(made.get(), 2, "the remaining runs must not be spent");
    }

    #[test]
    fn the_count_comes_from_what_happened_and_not_from_what_was_asked_for() {
        let reading = tally(vec![clean(), clean(), clean()], &words(), 300.0);
        assert_eq!(reading.value, "3/3");
    }
}
