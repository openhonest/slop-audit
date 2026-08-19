"""A test the batch classifier never reported is not a compile error.

`batch.get(i, "error")` recorded an index the classifier did not mention as `error`,
which is the bucket for a test that failed to compile. Those are different facts. The
classifier reads `pass` and `FAILED` lines out of the runner's output, so a missing index
means the runner said nothing about that test: it was not run, or its line was not
matched, or the output was truncated. Filing it under a compile error is an answer
written for a different input.

Honest Code's Dispatch Tables Close Open Input asks for the subscript and a raise, or a
named miss the caller must handle. This takes the named miss, because the caller is a
counting loop that must finish the batch: one silent test does not justify abandoning the
other forty, and a bucket nobody can confuse with a compile error is what makes the count
readable.

The distinction is not cosmetic. `error` is noise that the proof loop expects and
tolerates; `unreported` is the analyzer losing track of a test it generated and ran, and
a run where that number is not zero is a run whose totals do not add up.
"""

from l1_analyzer import coverage_prove


def test_unreported_is_its_own_outcome_bucket():
    assert "unreported" in coverage_prove._OUTCOMES
    assert "error" in coverage_prove._OUTCOMES


def test_a_classified_index_keeps_its_own_verdict():
    """The guard. Naming the miss must not change what a reported test is called."""
    assert coverage_prove._batch_status({0: "pass", 1: "fail"}, 0) == "pass"
    assert coverage_prove._batch_status({0: "pass", 1: "fail"}, 1) == "fail"


def test_an_index_the_classifier_never_mentioned_reads_as_unreported():
    assert coverage_prove._batch_status({0: "pass"}, 7) == "unreported"
    assert coverage_prove._batch_status({}, 0) == "unreported"


def test_unreported_is_not_error():
    """The whole point. A compile error is a thing the runner told us; an unreported index
    is a thing it did not."""
    assert coverage_prove._batch_status({0: "pass"}, 9) != "error"
