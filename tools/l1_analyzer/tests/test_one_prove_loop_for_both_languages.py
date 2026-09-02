"""Both coverage provers drive a gap the same way, and the copy hid inside a bigger function.

A prover finds a branch no test reaches, asks a model for one test, runs it, and keeps the
test only if it fails against the code as written. Two of them exist, one for Rust and one
for Python, and a note in the source said they were compared statement for statement in
August and are not the same shape.

The measurement compared whole functions and the duplication is path to path. Rust's module
loop has two paths: batch every proposal into one crate and compile once, or, when the batch
does not compile, fall back to proving each gap on its own. That fallback is Python's whole
loop. Compared function to function, twenty-six lines against eleven with four alike; the
eleven are inside the twenty-six.

The batch is real and stays Rust's own. Compiling a crate once for twenty proofs is worth a
path of its own, and pytest has no equivalent, so there is nothing for Python to share there.
What both need is the loop underneath it.

Three rules live in that loop and none of them may drift. Repair at most the number of times
the caller allowed, which is a budget and the second budget rule this package has had two
copies of. Count every outcome including a decline, because a model call that produced
nothing still cost money. Retain only a divergence, which is the whole discipline: a test
that passes against the code as written has proven nothing.
"""

import pytest
from l1_analyzer import prove_gap


def _gap(name: str) -> dict:
    return {"function": name, "line": 3, "kind": "branch", "return_type": "int"}


def _answer(body: str) -> dict:
    return {"body": body, "explanation": f"{body} takes the other branch"}


class _Runs:
    """A stand-in for building and running a generated test, recording what it was asked."""

    def __init__(self, verdicts: list[str]):
        self.verdicts = verdicts
        self.sources: list[str] = []

    def __call__(self, gap, proposal, source):
        self.sources.append(source)
        return self.verdicts[min(len(self.sources) - 1, len(self.verdicts) - 1)], "output"


def _prove(gap, run, *, propose=None, repair=None, rounds=2):
    return prove_gap.prove_one(
        gap,
        propose=propose or (lambda g: _answer(g["function"])),
        render=lambda body: f"test({body})",
        run=run,
        repair=repair or (lambda g, source, output: _answer("repaired")),
        repairable="error",
        rounds=rounds,
    )


def test_a_model_that_declined_is_a_named_outcome_and_nothing_is_run():
    """Counted, not passed over. A call that produced nothing still cost money, and a
    prover that dropped it would report a hit rate over calls it did not admit making."""
    runs = _Runs(["divergence"])
    status, explanation, source = _prove(_gap("band"), runs, propose=lambda g: None)
    assert status == "declined"
    assert (explanation, source) == ("", "")
    assert runs.sources == []


def test_a_test_that_fired_first_time_is_not_repaired():
    runs = _Runs(["divergence"])
    status, _explanation, _source = _prove(_gap("band"), runs)
    assert status == "divergence"
    assert len(runs.sources) == 1


def test_a_test_that_would_not_build_is_repaired_and_run_again():
    runs = _Runs(["error", "divergence"])
    status, _explanation, _source = _prove(_gap("band"), runs)
    assert status == "divergence"
    assert runs.sources == ["test(band)", "test(repaired)"]


def test_repair_stops_at_the_number_of_rounds_the_caller_allowed():
    """A budget rule, and the second one this package has had two copies of. Without it a
    model that keeps producing code that will not build spends without a ceiling."""
    runs = _Runs(["error"])
    status, _explanation, _source = _prove(_gap("band"), runs, rounds=2)
    assert status == "error"
    assert len(runs.sources) == 3, "the first attempt and two repairs"


def test_a_model_that_declines_to_repair_stops_the_loop():
    """Asking again after a refusal spends a call to be told no twice."""
    runs = _Runs(["error"])
    status, _explanation, _source = _prove(_gap("band"), runs,
                                           repair=lambda g, s, o: None, rounds=5)
    assert status == "error"
    assert len(runs.sources) == 1


def test_the_explanation_comes_from_the_proposal_that_was_last_run():
    """A repaired proposal explains the test that actually ran. Reporting the first
    proposal's words beside the last proposal's verdict describes a test nobody ran."""
    runs = _Runs(["error", "divergence"])
    _status, explanation, source = _prove(_gap("band"), runs)
    assert "repaired" in explanation
    assert source == "test(repaired)"


# --------------------------------------------------------------------------
# The per-gap loop around it
# --------------------------------------------------------------------------

def test_every_outcome_is_counted_and_only_a_divergence_is_kept():
    """The retention discipline the whole tool rests on. A test that passes against the code
    as written has proven nothing, and counting it would report a hit rate of one."""
    verdicts = {"a": "divergence", "b": "pass", "c": "declined", "d": "incidental"}
    retained, outcomes = prove_gap.prove_each(
        [_gap(name) for name in "abcd"],
        lambda gap: (verdicts[gap["function"]], "why", "source"),
        lambda gap, explanation, source: {"function": gap["function"]},
        outcomes=dict.fromkeys(["divergence", "pass", "declined", "incidental"], 0))
    assert [r["function"] for r in retained] == ["a"]
    assert outcomes == {"divergence": 1, "pass": 1, "declined": 1, "incidental": 1}


def test_a_module_with_no_gaps_retains_nothing_and_counts_nothing():
    retained, outcomes = prove_gap.prove_each(
        [], lambda gap: ("divergence", "", ""), lambda gap, e, s: {},
        outcomes={"divergence": 0})
    assert retained == []
    assert outcomes == {"divergence": 0}


def test_an_outcome_the_caller_did_not_name_is_refused_rather_than_dropped():
    """The tally is the caller's, one word per language, and a verdict missing from it is a
    prover and a report that disagree about what can happen. Counting it under a key nobody
    declared would file an unknown answer under a name written for a different one."""
    with pytest.raises(KeyError):
        prove_gap.prove_each([_gap("a")], lambda gap: ("surprise", "", ""),
                             lambda gap, e, s: {}, outcomes={"divergence": 0})
