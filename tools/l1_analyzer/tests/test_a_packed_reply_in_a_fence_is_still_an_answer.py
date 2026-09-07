"""A model that wraps its JSON in a code fence was answering into a void.

A packed request asks for one JSON object holding an answer per gap. Models routinely wrap
JSON in a markdown fence, and the single-gap path has stripped fences since it was written.
The packed path did not: it handed the fenced text straight to the JSON reader, which
refused it, and every answer in the pack was dropped.

Nothing recorded that. A refusal is written down when the model says nothing; this model
said 300 KB and the record stayed empty, so the sweep reported "the model replied with
nothing usable for 0 of them" and the zero is a count of declines that never happened.

Found on 2026-09-07 by the session auditing turso, on the first parallel run: eight workers,
500 gaps picked, 87 minutes of asking, three complete packed answers received, and every one
of 176 modules returning instantly with nothing to prove. Money spent, answers received,
nothing produced, and a stated reason that was arithmetic on an empty set.

Two repairs. The fence comes off through the same reader the single-gap path uses, because
two spellings of one parse is how the two drifted apart in the first place. And a reply that
cannot be read is written down, so a sweep can say that rather than describe a refusal that
did not happen.
"""

from __future__ import annotations

import json

from l1_analyzer import coverage_prove
from l1_analyzer import model_call as llm

_BODY = 'let result = f();\nassert!(result, "must hold");'


def _gap(name: str) -> dict:
    return {"function": name, "function_source": f"fn {name}() -> bool {{ true }}",
            "kind": "if", "line": 3, "return_type": "bool", "parameters": []}


def _fenced(entries: list[dict], tag: str = "json") -> dict:
    inner = json.dumps({"proofs": entries})
    return {"text": f"```{tag}\n{inner}\n```", "reason": "", "cause": ""}


def test_a_fenced_reply_is_read_like_any_other():
    """The defect. Three complete answers arrived and all three were dropped."""
    gaps = [_gap("alpha"), _gap("beta")]
    answers = coverage_prove.answers_for(gaps, _fenced([
        {"index": 0, "body": _BODY, "explanation": "alpha"},
        {"index": 1, "body": _BODY, "explanation": "beta"},
    ]))
    assert [a["explanation"] for a in answers] == ["alpha", "beta"]


def test_a_fence_with_no_language_on_it_is_read_too():
    answers = coverage_prove.answers_for([_gap("alpha")], _fenced(
        [{"index": 0, "body": _BODY, "explanation": "alpha"}], tag=""))
    assert answers[0]["explanation"] == "alpha"


def test_a_reply_nobody_can_read_is_written_down():
    """The half that let it run for 87 minutes. A refusal is recorded when the model says
    nothing, and this model said plenty; nothing recorded that what it said was unreadable,
    so the sweep described a refusal that never happened."""
    coverage_prove.LAST_REFUSAL["reason"] = ""
    answers = coverage_prove.answers_for(
        [_gap("alpha")], {"text": "not json at all", "reason": "", "cause": ""})
    assert answers == [None]
    assert coverage_prove.LAST_REFUSAL["reason"] == llm.DECLINED
    assert coverage_prove.LAST_REFUSAL["cause"], "the reason names nothing a reader can act on"


def test_a_reply_whose_top_level_key_is_missing_is_written_down_too():
    """A model that answered in a shape nobody asked for is not a model that declined."""
    coverage_prove.LAST_REFUSAL["reason"] = ""
    answers = coverage_prove.answers_for(
        [_gap("alpha")], {"text": json.dumps({"tests": []}), "reason": "", "cause": ""})
    assert answers == [None]
    assert coverage_prove.LAST_REFUSAL["reason"] == llm.DECLINED


def test_a_readable_reply_is_recorded_as_answered():
    coverage_prove.LAST_REFUSAL["reason"] = ""
    coverage_prove.answers_for([_gap("alpha")], _fenced(
        [{"index": 0, "body": _BODY, "explanation": "alpha"}]))
    assert coverage_prove.LAST_REFUSAL["reason"] == llm.ANSWERED


def test_a_sweep_that_declined_nothing_does_not_say_it_declined_nothing():
    """The sentence that ran for 87 minutes and explained nothing.

    A sweep that located gaps and proved none has three ways to get there and the report had
    two: the model refused, or the model answered unusably. This one bought answers, got
    them, and lost them between the reply and the proposal, so it printed "the model replied
    with nothing usable for 0 of them", which is a count of declines that never happened.

    Zero declines beside zero proven is not a reason. It is arithmetic on an empty set, and
    a reader given it has nowhere to go."""
    said = coverage_prove.sweep_detail(
        0, 176, 11867, {"declined": 0, "divergence": 0, "pass": 0}, "cargo", llm.DECLINED, "")
    assert "nothing usable for 0" not in said, said
    assert "no proposal" in said or "reached" in said, said


def test_a_sweep_the_model_really_declined_still_says_so():
    """The other direction. A model that answered unusably for eleven gaps is a real
    reading and the count belongs in it."""
    said = coverage_prove.sweep_detail(
        0, 3, 11, {"declined": 11, "divergence": 0, "pass": 0}, "cargo", llm.DECLINED, "")
    assert "11" in said
