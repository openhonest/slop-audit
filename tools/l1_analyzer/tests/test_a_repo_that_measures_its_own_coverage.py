"""We ran their suite under coverage, and their suite turned coverage on too.

Reported by a peer on 2026-08-28 from a real run. We measure decision-space coverage by
running the target repository's test suite under `coverage run --branch`. If that repository
already puts `--cov` in its pytest settings, pytest-cov starts a second coverage session
inside ours. Theirs wins, ours records nothing, and we report 0.0.

The repository is then put in the failing band for something it did not fail. pipeline-admin
scored 0.0 on the first run and its real branch coverage was 84.4 per cent. Turning on
coverage is the behaviour we are asking for, so we punished the practice we want.

We already pass `-p no:cacheprovider` for the same class of collision, at the same place.
`--no-cov` belongs beside it.

The footer then blamed the wrong thing. It said the runtime harness is Python-only, on a
Python repository, so a reader could not tell a genuine zero from our own collision.
"""

import pathlib

import pytest
from l1_analyzer import pytest_trace


def test_a_target_with_the_plugin_is_told_not_to_start_its_own_coverage():
    assert pytest_trace._stop_their_coverage(True) == ["--no-cov"]


def test_a_target_without_the_plugin_is_told_nothing():
    """The first version of this fix passed the flag unconditionally. A pytest with no
    pytest-cov reads it as an unknown argument and the whole run dies, so a wrong number
    became no number at all. Six of this package's own tests caught it."""
    assert pytest_trace._stop_their_coverage(False) == []


def test_the_answer_is_handed_in_rather_than_reached_for():
    """The second thing this repository caught. Written to probe the target itself, the
    function could only be tested by replacing a name inside this package, and a test that
    replaces what it is testing passes when the real thing is broken."""
    source = pathlib.Path(pytest_trace.__file__).read_text()
    body = source[source.index("def _stop_their_coverage"):]
    body = body[:body.index("\ndef ")]
    assert "_module_available" not in body.split('"""')[-1]


def test_the_flag_reaches_the_command():
    source = pathlib.Path(pytest_trace.__file__).read_text()
    invocation = source[source.index('"coverage", "run"'):]
    invocation = invocation[:invocation.index("])")]
    assert "_stop_their_coverage(" in invocation, invocation
    assert "no:cacheprovider" in invocation, "the two collision fixes drifted apart"


@pytest.mark.parametrize("output", [
    "No data was collected.",
    "Coverage.py warning: No data was collected. (no-data-collected)",
])
def test_an_empty_collection_is_named_as_ours_rather_than_theirs(output):
    """The reader has to be able to tell our failure from their zero. A repository whose
    suite ran and covered nothing is a real finding; a repository whose coverage we
    collided with is our bug, and both printed the same sentence."""
    verdict = pytest_trace._collection_was_empty(output)
    assert verdict
    assert "own coverage" in verdict or "collided" in verdict


def test_ordinary_output_is_not_read_as_a_collision():
    """A rule that saw a collision everywhere would excuse every real zero."""
    assert pytest_trace._collection_was_empty("3 passed in 0.10s") == ""
