"""Isolated proof requests, and the gate that decides whether a proposal proved anything.

The half of Umbra that turns a located silence into a demonstration. A silence says a test
could exist; a retained proof says one does, and it FAILS. The glossary is exact about the
gate: it validates and renders each proposed case as a runnable test, executes it in
isolation, and keeps only tests that genuinely fail or make the audited function error. A
passing test is discarded and a malformed proposal is rejected with a correction reason.

Two rules make this worth having rather than a way to let a model write tests.

The CALLER writes the test, not this module. A request carries the signature and the gap
and nothing else, so what leaves this machine is one function's shape rather than a
repository. That is why it is called an isolated request.

And nothing is believed. A proposal that passes proves the opposite of what was claimed:
the suite already covers the region, so there was no silence to close there. A proposal
that fails to compile proves nothing at all. Only a test that runs and fails is retained,
which is why the gate executes rather than reads.

Not every silence can become a failing test. The glossary calls the ones that can
model-ready: an input never tried, a branch nothing runs, an error case no one checks. An
unasserted return contract is a real gap and cannot be made to fail on demand, so nothing
is asked about it.
"""

import ast
import pathlib
import textwrap

import pytest
from l1_analyzer import facets, proof

MODULE = textwrap.dedent('''
    def band(n: int) -> str:
        """Three arms; the suite reaches one."""
        if n > 10:
            return "high"
        if n > 5:
            return "mid"
        return "low"


    def divide(numerator: int, denominator: int) -> float:
        if denominator == 0:
            raise ValueError("no denominator")
        return numerator / denominator
''').lstrip("\n")

TESTS = 'from m import band\n\n\ndef test_high():\n    assert band(20) == "high"\n'


@pytest.fixture(scope="module")
def audited(tmp_path_factory) -> tuple:
    root = tmp_path_factory.mktemp("proof")
    (root / "m.py").write_text(MODULE)
    (root / "test_m.py").write_text(TESTS)
    return root, facets.audit(root / "m.py", root / "test_m.py")


# --------------------------------------------------------------------------
# Which silences can be proved at all
# --------------------------------------------------------------------------

def test_the_model_ready_kinds_are_named_as_a_closed_set():
    assert proof.MODEL_READY_KINDS == (
        "unexercised_branch", "candidate_input_region", "exception_path")


def test_an_unasserted_return_contract_is_not_asked_about(audited):
    """Real, and it cannot be made to fail on demand: there is no input that makes "nobody
    checked the result" throw. Asking for a proof would be asking for a test that cannot
    exist, and getting one back would mean it proved something else."""
    _root, audit = audited
    kinds = {r["kind"] for r in proof.requests(audit, cap=20)}
    assert "unasserted_return_contract" not in kinds


def test_a_runtime_property_is_not_asked_about(audited):
    """A property is shown by watching the suite run, not by one new failing test."""
    _root, audit = audited
    assert "runtime_property" not in {r["kind"] for r in proof.requests(audit, cap=20)}


def test_only_silent_facets_become_requests(audited):
    """A facet with evidence has nothing left to prove."""
    _root, audit = audited
    asked = {(r["function"], r["detail"]) for r in proof.requests(audit, cap=20)}
    closed = {(f["function"], f["detail"]) for f in audit["facets"] if not f["silent"]}
    assert asked & closed == set()


def test_no_request_is_made_when_nothing_is_model_ready(tmp_path):
    """The glossary's case: an audit finds gaps and none of them are this kind."""
    (tmp_path / "m.py").write_text("def f(n: int) -> int:\n    return n\n")
    (tmp_path / "test_m.py").write_text("from m import f\n\n\ndef test_f():\n    f(1)\n")
    audit = facets.audit(tmp_path / "m.py", tmp_path / "test_m.py")
    assert [r for r in proof.requests(audit, cap=5) if r["kind"] == "unexercised_branch"] == []


# --------------------------------------------------------------------------
# What a request carries, and what it does not
# --------------------------------------------------------------------------

def test_a_request_carries_the_signature_rather_than_the_module(audited):
    """Isolation is the point. What leaves this machine is one function's shape and the
    gap, so a caller sending it to a model is not sending a repository."""
    _root, audit = audited
    request = next(r for r in proof.requests(audit, cap=20) if r["function"] == "band")
    assert request["signature"] == "def band(n: int) -> str"
    assert "return" not in request["signature"]
    assert MODULE not in str(request)


def test_a_request_names_the_import_the_test_will_use(audited):
    _root, audit = audited
    request = proof.requests(audit, cap=1)[0]
    assert request["module"] == "m"


def test_each_request_carries_the_index_the_gate_is_called_with(audited):
    _root, audit = audited
    made = proof.requests(audit, cap=20)
    assert [r["index"] for r in made] == list(range(len(made)))


def test_the_cap_bounds_what_is_asked(audited):
    _root, audit = audited
    assert len(proof.requests(audit, cap=2)) == 2
    assert proof.requests(audit, cap=0) == []


# --------------------------------------------------------------------------
# What the gate rejects before running anything
# --------------------------------------------------------------------------

@pytest.mark.parametrize(("field", "value"), [
    ("concrete_input", ""), ("concrete_input", "1 +"), ("concrete_input", "import os"),
    ("expected_property", ""), ("expected_property", "assert x =="),
    ("plain_explanation", ""),
])
def test_a_malformed_proposal_is_rejected_by_the_named_field(field, value):
    """Named, so the caller can correct that field and resubmit rather than guess."""
    proposal = {"concrete_input": "0", "expected_property": "result == 'low'",
                "plain_explanation": "zero is below five"}
    proposal[field] = value
    reason = proof.malformed(proposal)
    assert reason, f"{field}={value!r} was accepted"
    assert field in reason


def test_a_well_formed_proposal_is_not_rejected():
    assert proof.malformed({"concrete_input": "0", "expected_property": "result == 'low'",
                            "plain_explanation": "zero is below five"}) == ""


def test_a_proposal_that_would_run_a_statement_is_rejected():
    """`concrete_input` is an argument list. A statement there is a way to run something
    other than the function under audit, and the gate executes what it is given."""
    reason = proof.malformed({"concrete_input": "__import__('os').system('ls')",
                              "expected_property": "result", "plain_explanation": "x"})
    assert reason


# --------------------------------------------------------------------------
# What the gate renders
# --------------------------------------------------------------------------

def test_the_rendered_test_calls_the_function_and_asserts_the_property():
    request = {"index": 0, "kind": "candidate_input_region", "function": "band", "line": 2,
               "signature": "def band(n: int) -> str", "detail": "`n: int` region zero",
               "module": "m", "instruction": ""}
    rendered = proof.render(request, {"concrete_input": "0",
                                      "expected_property": "result == 'low'",
                                      "plain_explanation": "zero is below five"})
    assert "from m import band" in rendered
    assert "band(0)" in rendered
    assert "assert result == 'low'" in rendered


def test_the_rendered_test_carries_the_explanation_a_reader_will_need():
    request = {"index": 0, "kind": "exception_path", "function": "divide", "line": 10,
               "signature": "def divide(numerator: int, denominator: int) -> float",
               "detail": "raises ValueError", "module": "m", "instruction": ""}
    rendered = proof.render(request, {"concrete_input": "1, 0",
                                      "expected_property": "result",
                                      "plain_explanation": "a zero denominator raises"})
    assert "a zero denominator raises" in rendered


# --------------------------------------------------------------------------
# What the gate retains, after running it
# --------------------------------------------------------------------------

def test_a_test_that_fails_is_retained(audited):
    """The whole point. `band(0)` returns "low", so asserting "high" fails, and a failing
    test is a demonstration that the region was never covered."""
    root, audit = audited
    request = next(r for r in proof.requests(audit, cap=20)
                   if r["function"] == "band" and r["kind"] == "candidate_input_region")
    verdict = proof.verify(root / "m.py", request,
                           {"concrete_input": "0", "expected_property": "result == 'high'",
                            "plain_explanation": "claims zero bands high, which it does not"})
    assert verdict["retained"] is True
    assert verdict["outcome"] == "failed"


def test_a_test_that_passes_is_discarded(audited):
    """It asserts behaviour the function already has, so it demonstrates no defect.
    Retaining it would file a green test as a proof.

    What it does NOT show is that the existing suite covers the region. The first version
    of the reason said so, and that was false the first time I ran it."""
    root, audit = audited
    request = next(r for r in proof.requests(audit, cap=20) if r["function"] == "band")
    verdict = proof.verify(root / "m.py", request,
                           {"concrete_input": "0", "expected_property": "result == 'low'",
                            "plain_explanation": "zero bands low"})
    assert verdict["retained"] is False
    assert verdict["outcome"] == "passed"
    assert verdict["reason"].strip()


def test_a_test_that_makes_the_function_error_is_retained(audited):
    """The glossary's second retention case. `divide(1, 0)` raises, and the raise is the
    demonstration."""
    root, audit = audited
    request = next(r for r in proof.requests(audit, cap=20) if r["function"] == "divide")
    verdict = proof.verify(root / "m.py", request,
                           {"concrete_input": "1, 0", "expected_property": "result == 0",
                            "plain_explanation": "a zero denominator raises"})
    assert verdict["retained"] is True
    assert verdict["outcome"] == "errored"


def test_a_test_that_does_not_run_is_not_a_proof(audited):
    """A NameError in the assertion is the proposal being broken, not the function. Filing
    it as a demonstration would count the tool's own failure as a finding."""
    root, audit = audited
    request = next(r for r in proof.requests(audit, cap=20) if r["function"] == "band")
    verdict = proof.verify(root / "m.py", request,
                           {"concrete_input": "0", "expected_property": "nobody_defined_this",
                            "plain_explanation": "broken on purpose"})
    assert verdict["retained"] is False
    assert verdict["outcome"] == "broken"


def test_a_malformed_proposal_never_reaches_execution(audited):
    root, audit = audited
    request = next(r for r in proof.requests(audit, cap=20) if r["function"] == "band")
    verdict = proof.verify(root / "m.py", request,
                           {"concrete_input": "", "expected_property": "result",
                            "plain_explanation": "x"})
    assert verdict["retained"] is False
    assert verdict["outcome"] == "malformed"
    assert "concrete_input" in verdict["reason"]


def test_the_proof_runs_against_the_module_and_not_the_existing_suite(audited):
    """In isolation, as the glossary says. A proposal is one test in its own file, so a
    red suite elsewhere cannot make it look retained and a green one cannot hide it."""
    root, audit = audited
    request = next(r for r in proof.requests(audit, cap=20) if r["function"] == "band")
    verdict = proof.verify(root / "m.py", request,
                           {"concrete_input": "0", "expected_property": "result == 'high'",
                            "plain_explanation": "x"})
    assert "test_high" not in verdict["rendered"], "the existing suite leaked into the proof"
    assert verdict["rendered"].count("def test_") == 1, "more than the one proposed test ran"
    assert (root / "test_m.py").read_text() == TESTS, "the gate wrote into the user's suite"


# --------------------------------------------------------------------------
# The readers, called directly
# --------------------------------------------------------------------------

@pytest.mark.parametrize(("source", "function", "expected"), [
    ("def f(n: int) -> str:\n    return 'x'\n", "f", "def f(n: int) -> str"),
    ("def f(n):\n    return n\n", "f", "def f(n)"),
    ("def f(a, *, b: int = 1) -> None:\n    pass\n", "f", "def f(a, *, b: int=1) -> None"),
    ("def f(n: int) -> int:\n    return n\n", "absent", ""),
    ("", "f", ""),
])
def test_the_signature_is_read_without_the_body(source, function, expected):
    """The body is deliberately absent. A request that carried it would send the code under
    audit out of the machine, and a caller does not need it to supply an argument."""
    assert proof.signature_of(source, function) == expected


def test_a_module_with_no_functions_yields_no_signature():
    assert proof.signature_of("X = 1\n", "f") == ""


def test_model_ready_keeps_the_silent_facets_a_test_could_demonstrate():
    audit = {"facets": [
        {"kind": "unexercised_branch", "function": "f", "line": 1, "detail": "if", "silent": True},
        {"kind": "unexercised_branch", "function": "g", "line": 2, "detail": "if", "silent": False},
        {"kind": "unasserted_return_contract", "function": "h", "line": 3, "detail": "d",
         "silent": True},
        {"kind": "runtime_property", "function": "i", "line": 4, "detail": "purity holds",
         "silent": True},
    ]}
    assert [f["function"] for f in proof.model_ready(audit)] == ["f"]


def test_model_ready_on_an_audit_with_no_facets_asks_nothing():
    assert proof.model_ready({"facets": []}) == []


def test_a_negative_cap_asks_for_nothing(audited):
    """A cap is a spending limit. Below zero it is still a refusal to spend, and slicing
    with it would silently ask for everything but the last few."""
    _root, audit = audited
    assert proof.requests(audit, cap=-1) == []


@pytest.mark.parametrize("expression", [
    "__import__('os')", "exec('x=1')", "eval('1')", "open('f')", "getattr(o, 'x')",
])
def test_an_expression_that_runs_code_or_touches_the_disk_is_refused(expression):
    assert proof._reaches_out(ast.parse(expression, mode="eval")) is True


def test_an_ordinary_expression_is_not_refused():
    assert proof._reaches_out(ast.parse("band(0)", mode="eval")) is False
    assert proof._reaches_out(ast.parse("1", mode="eval")) is False


@pytest.mark.parametrize(("returncode", "output", "outcome"), [
    (0, "", "passed"),
    (1, "E       assert 'low' == 'high'", "failed"),
    (1, "E       AssertionError: no", "failed"),
    (1, "E       NameError: name 'x' is not defined", "broken"),
    (1, ">       assert nobody_defined_this\nE       NameError: nope", "broken"),
    (1, "m.py:11: ValueError", "errored"),
    (2, "", "broken"),
    (-9, "", "broken"),
])
def test_what_a_finished_run_showed_is_read_from_the_complaint_lines(returncode, output, outcome):
    """Read from the lines pytest prefixes with `E`. Reading the whole output matched the
    echoed source line, so a NameError in the proposal was filed as a demonstration and the
    tool's own failure counted as a finding."""
    assert proof.read_outcome(returncode, output, pathlib.Path("m.py")) == outcome


def test_a_field_longer_than_the_limit_is_rejected():
    """A proposal is one argument list and one assertion. Anything longer is a program, and
    the gate executes what it renders."""
    reason = proof.malformed({"concrete_input": "0", "expected_property": "1 + " * 300 + "1",
                              "plain_explanation": "x"})
    assert "expected_property" in reason


# --------------------------------------------------------------------------
# The readers are functions, shown rather than assumed
# --------------------------------------------------------------------------

_PROPOSAL = {"concrete_input": "0", "expected_property": "result == 'low'",
             "plain_explanation": "zero bands low"}
_REQUEST = {"index": 0, "kind": "candidate_input_region", "function": "band", "line": 2,
            "signature": "def band(n: int) -> str", "detail": "`n: int` region zero",
            "module": "m", "instruction": ""}


@pytest.mark.parametrize(("reader", "arguments"), [
    (proof.signature_of, ("def f(n: int) -> str:\n    return 'x'\n", "f")),
    (proof.model_ready, ({"facets": []},)),
    (proof.malformed, (_PROPOSAL,)),
    (proof.render, (_REQUEST, _PROPOSAL)),
    (proof.read_outcome, (0, "", pathlib.Path("m.py"))),
])
def test_a_reader_called_twice_the_same_way_answers_the_same_way(reader, arguments):
    assert reader(*arguments) == reader(*arguments)


def test_requests_called_twice_answers_the_same_way(audited):
    _root, audit = audited
    assert proof.requests(audit, cap=3) == proof.requests(audit, cap=3)
