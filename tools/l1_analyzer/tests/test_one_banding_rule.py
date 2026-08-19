"""The two published banding rules are spelled once, not once per language.

L1.19 bands a coverage percentage and L1.20 bands a count of clean runs. Both rules are
published in the spec as ONE rule that all languages share, and cross-language
comparability is the whole claim the meter makes. Eight tracers each carried their own
copy of the coverage thresholds and seven carried their own copy of the determinism
thresholds. Every copy is a place where one language can start grading the same evidence
differently from another, and nothing in the suite would have said so: each tracer's test
asserts its own copy.

So the rules live in pytest_trace, which every other tracer already imports its shared
parts from, and these tests count the spellings.
"""

import pathlib
import re

import pytest
from l1_analyzer import pytest_trace

_PKG = pathlib.Path(pytest_trace.__file__).parent
_SOURCE = "\n".join(p.read_text() for p in _PKG.glob("*.py"))


def test_the_coverage_band_thresholds_are_spelled_once():
    sites = re.findall(r'"Healthy" if pct', _SOURCE)
    assert len(sites) == 1, f"{len(sites)} copies of the L1.19 band; languages can drift apart"


def test_the_determinism_band_thresholds_are_spelled_once():
    sites = re.findall(r'"Healthy" if passing', _SOURCE)
    assert len(sites) == 1, f"{len(sites)} copies of the L1.20 band; languages can drift apart"


@pytest.mark.parametrize(("pct", "band"), [
    (100.0, "Healthy"), (90.1, "Healthy"), (90.0, "Not Healthy"),
    (60.0, "Not Healthy"), (59.9, "Slop"), (0.0, "Slop"),
])
def test_the_coverage_band_holds_at_its_edges(pct, band):
    """90 itself is Not Healthy and 60 itself is Not Healthy: the published rule is
    strictly above 90, and at-or-above 60. Both edges are asserted so a copy that read
    one of them as inclusive would fail here rather than in one language's suite."""
    assert pytest_trace.coverage_band(pct) == band


@pytest.mark.parametrize(("passing", "runs", "band"), [
    (5, 5, "Healthy"), (4, 5, "Not Healthy"), (3, 5, "Slop"),
    (1, 1, "Healthy"), (0, 1, "Not Healthy"),
])
def test_the_determinism_band_holds_at_its_edges(passing, runs, band):
    """All clean is Healthy, one short is Not Healthy, anything worse is Slop. At one run
    the "one short" arm is zero clean, which the rule still calls Not Healthy; the callers
    refuse a zero denominator before reaching here, so no-runs never arrives as 0 of 0."""
    assert pytest_trace.determinism_band(passing, runs) == band
