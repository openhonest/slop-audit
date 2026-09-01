"""A refusal an operator cannot act on is a refusal that stops the work.

Every refusal in this package names its repair. A missing C compiler says "needs a C
compiler (cc/gcc/clang) in PATH". A missing sanitizer says which rustup command installs
it. Ruby with no branch data says the exact line to add to the spec_helper.

Fifteen refusals said only "timed out". Not how long the run was given, not that the caller
chooses that number, not which flag raises it. The tool ships a default of three hundred
seconds per suite execution, so this is the refusal an adopter is most likely to hit, and it
was the only one they could do nothing about.

It cost us the two runtime indicators on our own repository. Our suite takes about five
minutes, and every audit we ever ran reported branch coverage and determinism as not
measured. Given the time it asks for, coverage is 88.2 per cent and determinism is five runs
out of five. Two real numbers, behind a sentence that never mentioned the flag.
"""

from l1_analyzer import disclosure


def test_the_note_names_the_time_that_was_allowed():
    """The number the operator has to raise. Without it they cannot tell a suite that needs
    one more second from one that needs an hour."""
    assert "300" in disclosure.timeout_note(300.0)


def test_the_note_names_the_flag_that_raises_it():
    assert "--timeout" in disclosure.timeout_note(300.0)


def test_a_whole_number_of_seconds_is_written_as_one():
    """The flag takes seconds. Printing 300.0 invites a reader to type it back with the
    decimal point, and the point is noise in a sentence about a stopwatch."""
    assert "300.0" not in disclosure.timeout_note(300.0)
    assert "300s" in disclosure.timeout_note(300.0)


def test_a_fractional_timeout_keeps_its_fraction():
    """A caller who asked for half a second gets told half a second. Rounding it to zero
    would name a number nobody set."""
    assert "0.5s" in disclosure.timeout_note(0.5)


def test_the_note_closes_the_sentence_it_is_joined_to():
    """Every refusal it appends to ends without punctuation, so the note supplies the full
    stop. Without it a reader gets "coverage could be measured It was allowed 300s"."""
    note = disclosure.timeout_note(300.0)
    assert note.startswith(". "), "it closes the sentence it is joined to"
    assert note.rstrip().endswith(".")


# --------------------------------------------------------------------------
# The two shared verdicts, which is where seven languages meet
# --------------------------------------------------------------------------

import inspect

import pytest
from l1_analyzer import pytest_trace


def test_the_shared_coverage_verdict_names_the_timeout_it_was_given():
    said = pytest_trace.coverage_verdict(
        covered=None, total=None, returncode=124, timeout_seconds=300.0,
        no_report="no report", nothing_to_cover="nothing", how="branches",
        toolchain="python3")
    assert "300s" in said["details"]
    assert "--timeout" in said["details"]


def test_the_shared_determinism_tally_names_it_too():
    said = pytest_trace.determinism_tally(
        [(124, "")], {"unit": "seed", "never_ran": "nothing ran", "no_runs": "no runs",
                      "describe": "runs passed"},
        lambda _out: True, lambda _out: "", timeout_seconds=300.0)
    assert "300s" in said["details"]
    assert "--timeout" in said["details"]


def test_a_verdict_that_did_not_time_out_says_nothing_about_the_flag():
    """A note on every result is one a reader learns to skip, which is how the one that
    mattered would be missed. It speaks only when the timeout is the reason."""
    said = pytest_trace.coverage_verdict(
        covered=8, total=10, returncode=0, timeout_seconds=300.0,
        no_report="no report", nothing_to_cover="nothing", how="branches",
        toolchain="python3")
    assert "--timeout" not in said["details"]


@pytest.mark.parametrize("shared", ["coverage_verdict", "determinism_tally"])
def test_neither_shared_verdict_defaults_the_timeout(shared):
    """The rule the coverage verdict already states about its own sentences: a runner that
    forgets to name its tool is refused rather than handed a generic sentence nobody can act
    on. The number it allowed is the same kind of fact."""
    parameter = inspect.signature(getattr(pytest_trace, shared)).parameters["timeout_seconds"]
    assert parameter.default is inspect.Parameter.empty
