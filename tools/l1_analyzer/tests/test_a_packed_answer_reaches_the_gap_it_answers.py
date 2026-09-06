"""N gaps in one request, N answers back, and each answer on the gap it answers.

A batched ask has one failure the single ask cannot have: the answers arrive together and
something has to say which is which. Get that wrong and a proof for one function is compiled
against another, which would either fail to compile or, worse, compile and assert the wrong
thing about the wrong code.

So the model is asked to key each answer by the index it was given, and an answer whose index
is missing, repeated or out of range is dropped rather than guessed at. A dropped answer is a
gap nobody proposed for, which is a real outcome the sweep already counts; a misplaced answer
would be a finding about a function nobody read.

The output limit is the other new failure. One answer needed 2,048 tokens and twenty need
more, so a batch whose reply was cut off mid-list loses its tail silently. The limit scales
with the pack and the reply is validated per index, so a truncated reply costs the answers it
did not carry and nothing else.
"""

from __future__ import annotations

import json

from l1_analyzer import coverage_prove


def _gap(name: str) -> dict:
    return {"function": name, "function_source": f"fn {name}() -> bool {{ true }}",
            "signature": f"fn {name}() -> bool", "kind": "if", "line": 3,
            "return_type": "bool", "parameters": []}


_BODY = "let result = f();\nassert!(result, \"must be true\");"


def _reply(entries: list[dict]) -> dict:
    return {"text": json.dumps({"proofs": entries}), "reason": "", "cause": ""}


def test_each_answer_lands_on_the_gap_it_names():
    gaps = [_gap("alpha"), _gap("beta"), _gap("gamma")]
    answers = coverage_prove.answers_for(gaps, _reply([
        {"index": 2, "body": _BODY, "explanation": "gamma"},
        {"index": 0, "body": _BODY, "explanation": "alpha"},
        {"index": 1, "body": _BODY, "explanation": "beta"},
    ]))
    assert [a["explanation"] for a in answers] == ["alpha", "beta", "gamma"]


def test_a_gap_the_model_did_not_answer_gets_nothing_rather_than_a_neighbour():
    gaps = [_gap("alpha"), _gap("beta"), _gap("gamma")]
    answers = coverage_prove.answers_for(gaps, _reply([
        {"index": 0, "body": _BODY, "explanation": "alpha"},
        {"index": 2, "body": _BODY, "explanation": "gamma"},
    ]))
    assert answers[1] is None
    assert [a["explanation"] for a in answers if a] == ["alpha", "gamma"]


def test_an_index_outside_the_pack_is_dropped():
    """A reply naming a gap that was never sent is a reply about nothing, and filing it under
    the last real gap is how a proof ends up asserting about the wrong function."""
    answers = coverage_prove.answers_for([_gap("alpha")], _reply([
        {"index": 7, "body": _BODY, "explanation": "nowhere"},
    ]))
    assert answers == [None]


def test_a_repeated_index_keeps_the_first_and_drops_the_rest():
    """Two answers for one gap is the model contradicting itself. The first is kept because
    something has to be, and the second is dropped rather than silently overwriting it."""
    answers = coverage_prove.answers_for([_gap("alpha")], _reply([
        {"index": 0, "body": _BODY, "explanation": "first"},
        {"index": 0, "body": _BODY, "explanation": "second"},
    ]))
    assert answers[0]["explanation"] == "first"


def test_a_truncated_reply_costs_only_the_answers_it_did_not_carry():
    """The output limit's failure. A reply cut off mid-list is not valid JSON at all, so the
    whole pack goes unanswered rather than half of it landing on the wrong gaps."""
    gaps = [_gap("alpha"), _gap("beta")]
    cut = {"text": '{"proofs": [{"index": 0, "body": "let result', "reason": "", "cause": ""}
    assert coverage_prove.answers_for(gaps, cut) == [None, None]


def test_a_refusal_answers_nothing_and_says_so():
    """No key, no SDK, a declined request: the reply carries no text and every gap in the
    pack goes unanswered. The reason travels the way it already does for a single ask."""
    gaps = [_gap("alpha"), _gap("beta")]
    assert coverage_prove.answers_for(
        gaps, {"text": None, "reason": "no_key", "cause": ""}) == [None, None]


def test_an_answer_with_no_assertion_in_it_is_refused_like_any_other():
    """The gate that already exists for one answer, applied to each of N. A body that runs
    and asserts nothing would be a proof that measured nothing and published a clean bill."""
    answers = coverage_prove.answers_for([_gap("alpha")], _reply([
        {"index": 0, "body": "let result = f();", "explanation": "no assertion"},
    ]))
    assert answers == [None]
