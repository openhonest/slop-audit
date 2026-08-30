"""A resolver returns one answer, not a pair of maybes.

`_toolchain` returned `(refusal, tools)` with a docstring saying exactly one is None. The
type said both are optional, which permits (None, None) and (a refusal, a toolchain) as
well, and nothing enforced the sentence in the docstring. Every caller then read
`tools["maven"]` on a value the annotation said could be None, so the two indicators that
run Java were a stack trace away from any change that made the resolver return early.

Tagged instead: the answer says which case it is, and the unrepresentable states are
unrepresentable rather than promised absent.
"""


import pytest
from l1_analyzer import java_trace


def test_a_repository_with_no_maven_answers_refused(tmp_path):
    answer = java_trace._toolchain(tmp_path, timeout_seconds=5)
    assert answer["ok"] is False


def test_a_refusal_carries_the_result_the_indicator_returns(tmp_path):
    answer = java_trace._toolchain(tmp_path, timeout_seconds=5)
    assert answer["ok"] is False
    assert answer["refusal"]["band"] and answer["refusal"]["details"]


def test_a_refusal_has_no_toolchain_to_read(tmp_path):
    """The half a caller must not reach for. It is absent rather than None, so reading it is
    a KeyError at the line that read it, not a None flowing into a subprocess call."""
    answer = java_trace._toolchain(tmp_path, timeout_seconds=5)
    with pytest.raises(KeyError):
        answer["tools"]


def test_both_indicators_return_the_refusal_rather_than_crashing(tmp_path):
    """What the pair risked. Both L1.19 and L1.20 index the toolchain immediately after the
    refusal check, so a resolver that returned (None, None) would raise inside the indicator
    rather than report why it could not measure."""
    for measure in (java_trace.decision_space_coverage, java_trace.test_determinism):
        result = measure(tmp_path, 5, None) if measure is java_trace.decision_space_coverage \
            else measure(tmp_path, 1, 5, None)
        assert result["band"] in {"n/a", "Not measured"} or result["value"] is None
