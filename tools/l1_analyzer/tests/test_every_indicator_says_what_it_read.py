"""Every panel entry carries a value, a band and a sentence saying what was read.

L1Result was declared `total=False`, so a producer could ship a band with no details and
nothing would say so. Three did. L1.9, L1.10 and L1.11 published a band and a value with
no details line, so a reader got Slop for the pre-commit indicator with no sentence naming
what was looked for or where. Every other indicator in the panel carries that sentence,
and the sentence is the difference between a grade and a measurement.

Making the type total is what turns the omission into a type error at the producer instead
of an empty cell on the card. The test is here because the type alone is not enforced at
runtime: it checks the real panel over a real repository.
"""

import pathlib

from l1_analyzer import indicators


def test_every_configuration_indicator_says_what_it_read():
    results = indicators.compute_config_indicators(pathlib.Path(__file__).resolve().parents[3])
    for key, result in sorted(results.items()):
        assert set(result) >= {"value", "band", "details"}, f"{key} publishes {sorted(result)}"
        assert result["details"].strip(), f"{key} publishes an empty details line"


def test_a_configuration_indicator_names_what_was_missing(tmp_path):
    """The case the missing sentence hurt: an empty repository. A band of Slop with no
    sentence tells a reader they failed without telling them what was looked for."""
    results = indicators.compute_config_indicators(tmp_path)
    assert results["L1.9"]["band"] == "Slop"
    assert ".pre-commit-config.yaml" in results["L1.9"]["details"]
    assert results["L1.11"]["band"] == "Slop"
    assert "Dockerfile" in results["L1.11"]["details"]


def test_the_result_type_requires_all_three_fields():
    """Declared total, so a producer that omits one is a type error rather than an empty
    cell nobody notices until a reader asks what the grade was based on."""
    assert indicators.L1Result.__total__ is True
    assert set(indicators.L1Result.__required_keys__) == {"value", "band", "details"}


def test_the_result_type_is_declared_once():
    """Two definitions of it stood in this package and disagreed. Both were named
    L1Result, both described the same published dict, and only one was ever made total, so
    a producer typed against the other was allowed to omit the details line."""
    from l1_analyzer import pytest_trace
    assert indicators.L1Result is pytest_trace.L1Result
