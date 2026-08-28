"""The footer told a reader both rows were unmeasured, then quoted one of the measurements.

This file replaces test_the_footer_names_the_reason_it_was_given.py, written for the previous
fix, where one sentence carried one reason. Every case that file held is here, asserted
against the sentence for the row it belongs to.

Reported by the same adopter, on the run that proved the previous fix worked. Their coverage
row read 84.4 in the table. Three inches below, the footer said:

    Those rows read n/a here: 211/250 decision branches exercised by tests

So it announced that both rows are unmeasured and gave a measurement as the reason. One
sentence, written for two rows at once, picked by one condition. That held while the two rows
always failed together, and it stopped holding the moment one of them started working.

It is the previous footer bug one level down. That one named a single cause for every failed
run. This one has a single sentence for two different rows.

A reader wants the plain version, per row. Coverage ran and here is the number. Determinism
did not run and here is why. The row they know nothing about is the one the sentence has to
be about.
"""

from l1_analyzer import card

_COVERAGE = "L1.19"
_DETERMINISM = "L1.20"


def _ran(coverage: dict, determinism: dict) -> dict:
    return card.build_card("demo", "python",
                           {_COVERAGE: coverage, _DETERMINISM: determinism},
                           ran_tests=True, analyzer_version="test")


_MEASURED_COVERAGE = {"band": "Caution", "value": 84.4,
                      "details": "211/250 decision branches exercised by tests"}
_UNMEASURED_COVERAGE = {"band": "n/a", "value": "n/a",
                        "details": "the suite could not be run"}
_MEASURED_DETERMINISM = {"band": "Healthy", "value": "stable",
                         "details": "three runs agreed"}
_UNMEASURED_DETERMINISM = {"band": "n/a", "value": "n/a",
                           "details": "needs pytest-randomly in the target environment"}


def test_a_measured_row_is_not_described_as_unmeasured():
    """The sentence the adopter was shown, on a run where coverage measured fine."""
    footer = card.footer_for(_ran(_MEASURED_COVERAGE, _UNMEASURED_DETERMINISM))
    assert "Those rows read n/a" not in footer
    assert "84.4" in footer or "measured" in footer


def test_the_row_that_did_not_run_is_named_and_given_its_own_reason():
    footer = card.footer_for(_ran(_MEASURED_COVERAGE, _UNMEASURED_DETERMINISM))
    assert "L1.20" in footer
    assert "pytest-randomly" in footer


def test_the_measurement_is_never_offered_as_the_reason_for_not_measuring():
    """What made the sentence self-contradicting: it quoted the coverage detail as the
    explanation for both rows being absent."""
    footer = card.footer_for(_ran(_MEASURED_COVERAGE, _UNMEASURED_DETERMINISM))
    before_reason = footer.split("211/250")[0] if "211/250" in footer else footer
    assert "read n/a" not in before_reason


def test_the_other_way_round_works_too():
    """Determinism can run where coverage does not. One sentence for two rows could not
    say so in either direction."""
    footer = card.footer_for(_ran(_UNMEASURED_COVERAGE, _MEASURED_DETERMINISM))
    assert "L1.19" in footer
    assert "the suite could not be run" in footer


def test_both_measured_says_so_without_naming_a_reason():
    footer = card.footer_for(_ran(_MEASURED_COVERAGE, _MEASURED_DETERMINISM))
    assert "n/a" not in footer


def test_neither_measured_names_both_reasons():
    footer = card.footer_for(_ran(_UNMEASURED_COVERAGE, _UNMEASURED_DETERMINISM))
    assert "the suite could not be run" in footer
    assert "pytest-randomly" in footer


def test_a_row_that_gave_no_reason_is_reported_as_having_given_none():
    footer = card.footer_for(_ran(_MEASURED_COVERAGE,
                                  {"band": "n/a", "value": "n/a", "details": ""}))
    assert "did not say" in footer


def test_a_run_that_executed_nothing_still_says_that_instead():
    """The website, which is a third case and not a failure of either row."""
    quiet = card.build_card("demo", "python",
                            {_COVERAGE: _UNMEASURED_COVERAGE}, ran_tests=False,
                            analyzer_version="test")
    assert "never executes" in card.footer_for(quiet)
