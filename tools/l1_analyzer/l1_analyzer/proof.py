"""Isolated proof requests, and the gate that decides whether a proposal proved anything.

The half of Umbra that turns a located silence into a demonstration. A silence says a test
could exist; a retained proof says one does, and it FAILS.

Two rules make this worth having rather than a way to let a model write tests.

The CALLER writes the test. A request carries the signature and the gap and nothing else,
so what leaves this machine is one function's shape rather than a repository. That is what
`isolated` means, and it is why `requests` does not take the source.

Nothing is believed. A proposal that PASSES proves the opposite of what was claimed: the
suite already reaches there, so there was no silence to close. A proposal that will not run
proves nothing at all. Only a test that runs and fails, or makes the audited function
error, is retained. That is why the gate executes rather than reads.

Not every silence can become a failing test. An unasserted return contract is a real gap
with no input that makes "nobody checked the result" throw, so nothing is asked about it. A
runtime property is shown by watching the suite run rather than by one new test.
"""

import ast
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TypedDict

from l1_analyzer.facets import Audit, Facet, import_root

# The kinds a failing test can demonstrate: an input never tried, a branch nothing runs, an
# error case no one checks. Umbra calls these model-ready.
MODEL_READY_KINDS = ("unexercised_branch", "candidate_input_region", "exception_path")

# What the caller is asked to produce, per kind. The instruction says what would COUNT as a
# demonstration, because "write a test" invites a passing one and a passing one is not a
# proof.
_INSTRUCTIONS = {
    "unexercised_branch": ("Supply arguments that enter this branch, and assert a property "
                           "of the result that the branch does NOT satisfy."),
    "candidate_input_region": ("Supply an argument in this region, and assert a property of "
                              "the result that the function does NOT satisfy for it."),
    "exception_path": ("Supply arguments that reach this raise. The exception escaping is "
                       "itself the demonstration, so assert anything about the result."),
}

_MAX_FIELD = 400


class ProofRequest(TypedDict):
    """One located silence, isolated. Nothing here identifies the repository or carries a
    line of its source beyond the one signature the test has to call."""

    index: int
    kind: str
    function: str
    line: int
    signature: str
    detail: str
    module: str
    instruction: str


class Proposal(TypedDict):
    """What a caller sends back. `concrete_input` is an argument list and
    `expected_property` is one expression about `result`."""

    concrete_input: str
    expected_property: str
    plain_explanation: str


class Verdict(TypedDict):
    """Whether the proposal demonstrated the silence, and what happened when it ran."""

    retained: bool
    outcome: str
    reason: str
    rendered: str


def signature_of(source: str, function: str) -> str:
    """The `def` line of one function, without its body.

    The body is deliberately absent. A request that carried it would be sending the code
    under audit out of the machine, and the caller does not need it to supply an argument."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function:
            arguments = ast.unparse(node.args)
            returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
            return f"def {node.name}({arguments}){returns}"
    return ""


def model_ready(audit: Audit) -> list[Facet]:
    """The silent facets a failing test could demonstrate, in the order they were found."""
    return [f for f in audit["facets"]
            if f["silent"] and f["kind"] in MODEL_READY_KINDS]


def requests(audit: Audit, cap: int) -> list[ProofRequest]:
    """One isolated request per model-ready silence, up to the cap.

    The cap is the caller's spending limit, and it is theirs rather than a default here: a
    request is what gets sent to a model, so how many are made is a decision about money
    and about what leaves the machine.

    Below zero it is still a refusal to spend. Slicing with it asked for everything but the
    last few, which turns the strongest possible limit into an almost unlimited request."""
    if cap <= 0:
        return []
    module = Path(audit["module"])
    source = module.read_text()
    name = ".".join(module.resolve().relative_to(
        import_root(module).resolve()).with_suffix("").parts)
    return [{
        "index": index, "kind": facet["kind"], "function": facet["function"],
        "line": facet["line"], "signature": signature_of(source, facet["function"]),
        "detail": facet["detail"], "module": name,
        "instruction": _INSTRUCTIONS[facet["kind"]],
    } for index, facet in enumerate(model_ready(audit)[:cap])]


def malformed(proposal: Proposal) -> str:
    """Why this proposal cannot be rendered, or the empty string when it can.

    The field is named, so a caller can correct that one and resubmit rather than guess.
    Both code fields must parse as EXPRESSIONS: the gate executes what it renders, and a
    statement in an argument list is a way to run something other than the function under
    audit."""
    for field, wrapper in (("concrete_input", "f({})"), ("expected_property", "({})")):
        text = proposal.get(field, "")
        if not text.strip():
            return f"{field} is empty; it has to carry the code the test will run"
        if len(text) > _MAX_FIELD:
            return f"{field} is longer than {_MAX_FIELD} characters"
        try:
            parsed = ast.parse(wrapper.format(text), mode="eval")
        except SyntaxError as error:
            return f"{field} does not parse as an expression: {error.msg}"
        if _reaches_out(parsed):
            return (f"{field} calls import, exec, eval or open; a proof runs the audited "
                    "function and nothing else")
    if not proposal.get("plain_explanation", "").strip():
        return "plain_explanation is empty; a proof nobody can read is not a demonstration"
    return ""


def _reaches_out(tree: ast.AST) -> bool:
    """Whether an expression calls something that runs code or touches the filesystem."""
    forbidden = {"__import__", "exec", "eval", "open", "compile", "input", "getattr"}
    return any(isinstance(node, ast.Name) and node.id in forbidden for node in ast.walk(tree))


def render(request: ProofRequest, proposal: Proposal) -> str:
    """The proposal as one runnable test file.

    It imports the module and nothing else. The existing suite is not read and not written:
    a red suite elsewhere must not make this look retained, and a green one must not hide
    it."""
    return (
        f'"""{proposal["plain_explanation"]}\n\n'
        f'Proposed against {request["function"]}:{request["line"]} — {request["detail"]}.\n'
        f'"""\n\n'
        f'from {request["module"]} import {request["function"]}\n\n\n'
        f"def test_proof_{request['index']}():\n"
        f'    result = {request["function"]}({proposal["concrete_input"]})\n'
        f'    assert {proposal["expected_property"]}\n')


def read_outcome(returncode: int, output: str, module: Path) -> str:
    """What running the rendered test showed.

    `failed` is the assertion the proposal made, which is a demonstration. `errored` is the
    audited function raising, which is the other one. `broken` is the proposal itself not
    running, and filing that as a finding would count the tool's own failure as a
    silence."""
    if returncode == 0:
        return "passed"
    # pytest prefixes the failing lines with `E`. Reading the whole output instead matched
    # the echoed source line, so a NameError in the proposal was filed as a demonstration:
    # the tool's own failure counted as a finding.
    complaints = [line for line in output.splitlines() if line.startswith("E ")]
    asserted = any(re.match(r"E\s+(assert\b|AssertionError)", line) for line in complaints)
    inside = re.search(rf"\b{re.escape(module.name)}:\d+", output) is not None
    if inside:
        return "errored"
    if asserted:
        return "failed"
    return "broken"


def verify(module: Path, request: ProofRequest, proposal: Proposal) -> Verdict:
    """Render the proposal, run it alone, and keep it only if it demonstrated something.

    Nothing is written into the caller's test file. Umbra proves gaps and never edits a
    suite; adopting a surviving proof is the reader's own decision."""
    module = Path(module)
    reason = malformed(proposal)
    if reason:
        return {"retained": False, "outcome": "malformed", "reason": reason, "rendered": ""}

    rendered = render(request, proposal)
    root = import_root(module)
    with tempfile.TemporaryDirectory(prefix="l1-proof-") as directory:
        candidate = Path(directory) / f"test_proof_{request['index']}.py"
        candidate.write_text(rendered)
        run = subprocess.run(
            [sys.executable, "-m", "pytest", str(candidate), "-q", "-p", "no:cacheprovider",
             "--no-header", "-x"],
            cwd=root, capture_output=True, text=True, timeout=300, check=False)
    outcome = read_outcome(run.returncode, run.stdout + run.stderr, module)
    return {
        "retained": outcome in ("failed", "errored"),
        "outcome": outcome,
        "reason": _WHY[outcome],
        "rendered": rendered,
    }


_WHY = {
    "failed": "the test ran and failed, which demonstrates the silence",
    "errored": "the audited function raised, which demonstrates the silence",
    # The first version of this sentence said the suite already covered the region. It does
    # not follow and it was false in the first case I ran: the proposal asserted behaviour
    # the function has rather than behaviour it lacks. A passing test says nothing about the
    # existing suite at all.
    "passed": ("the test passed, so it demonstrates no defect at this site. It asserts "
               "behaviour the function already has. Adopting it would close the silence as "
               "coverage, but it is not a proof of anything"),
    "broken": ("the test did not run, so it demonstrates nothing about the audited "
               "function"),
    "malformed": "the proposal could not be rendered",
}
