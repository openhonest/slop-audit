"""What `_prove_one` hands back is a string, so a declined proposal cannot reach a reader.

It returned the whole model answer, or None when the model declined. The caller then read
`proposal["explanation"]` on the retained path, which is correct because only a divergence
retains and a divergence has a proposal. Nothing checked that: the bucket is a plain string,
so no reader of the type could see the connection, and the invariant lived in two functions
agreeing about which bucket names imply a proposal.

The explanation is the only field any caller read. Returning it flattens the pair to a
string that is empty when there is nothing to explain.
"""

import pathlib

from l1_analyzer import coverage_prove as cp
from l1_analyzer import python_coverage_prove as pcp

_GAP = {"function": "f", "line": 3, "parameters": [], "return_type": "int",
        "signature": "fn f() -> int", "branch": "the else arm", "module": "m",
        "source": "fn f() -> int { 1 }"}


def _proposal():
    return {"body": "assert f() == 2", "explanation": "f returns 1 where the doc says 2"}


def test_a_declined_python_proposal_explains_nothing():
    bucket, explanation, source = pcp._prove_one(
        pathlib.Path("."), "python3", _GAP, "m", 3, 1.0,
        propose_fn=lambda gap, path: None,
        repair_fn=lambda *a: None,
        run_fn=lambda *a: (0, ""))
    assert (bucket, explanation, source) == ("declined", "", "")


def test_a_declined_rust_proposal_explains_nothing():
    bucket, explanation, source = cp._prove_one(
        pathlib.Path("."), "src/m.rs", _GAP, 3, 1.0,
        propose_fn=lambda gap: None,
        repair_fn=lambda *a: None,
        run_fn=lambda *a: ("pass", ""),
        refine_fn=lambda *a: "divergence")
    assert (bucket, explanation, source) == ("declined", "", "")


def test_a_retained_python_divergence_carries_the_model_s_own_words():
    bucket, explanation, _source = pcp._prove_one(
        pathlib.Path("."), "python3", _GAP, "m", 3, 1.0,
        propose_fn=lambda gap, path: _proposal(),
        repair_fn=lambda *a: None,
        run_fn=lambda *a: (1, "FAILED t.py::proof_0 - AssertionError: boom"))
    assert bucket == "divergence"
    assert explanation == "f returns 1 where the doc says 2"
