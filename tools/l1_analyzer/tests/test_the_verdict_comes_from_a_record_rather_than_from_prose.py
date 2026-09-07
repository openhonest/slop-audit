"""The retention gate asks pytest for a record, not for a paragraph.

The verdict on a generated proof was read out of pytest's human-readable output, and that was
patched three times in one day: once because a pytest version moved the exception's name off
the summary line, once because a transcript nobody could parse was filed in a noise bucket,
and once because the summary reason is cut to the terminal width and a partial match read as
a different exception.

Three repairs to one parser is the architecture rather than the bug. Prose is not a contract,
and every one of those failures was the same failure: a verdict derived from formatting that
pytest is free to change and does.

pytest already writes a record. `--junit-xml` is built in, needs no plugin, and puts the
exception's name in an attribute, so no width and no version applies to it. It is read first.

The prose readings stay, and stay named. They answer when no record was written, which
happens when pytest cannot start at all, and the outcome says which of the two answered so a
run that fell back to prose can be told from one that did not. A fallback nobody can see is
how the first three defects lasted as long as they did.
"""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest
from l1_analyzer import python_coverage_prove as pcp

_PROOFS = {
    "assertion": 'def proof_0():\n    result = 3\n    assert result == 4, "must be four"\n',
    "setup failure": 'def proof_0():\n    result = int("not a number")\n    assert result\n',
    "clean": "def proof_0():\n    assert 1 == 1\n",
}


def boundary(fn):
    """Mark this file's one edge, and change nothing about it."""
    return fn


@boundary
def _real_junit(tmp_path: Path, source: str) -> str:
    """One proof, run by a real interpreter, and the record pytest wrote about it."""
    proof = tmp_path / "test_l1_coverage_proof.py"
    proof.write_text(textwrap.dedent(source))
    report = tmp_path / "junit.xml"
    subprocess.run(
        ["python", "-m", "pytest", str(proof), "-q", "-p", "no:cacheprovider",
         "-o", "python_functions=proof_*", f"--junit-xml={report}"],
        cwd=tmp_path, capture_output=True, check=False)
    return report.read_text() if report.is_file() else ""


@pytest.mark.parametrize("kind,expect", [
    ("assertion", "divergence"),
    ("setup failure", "incidental"),
    ("clean", "pass"),
])
def test_the_record_answers_for_a_real_run(tmp_path, kind, expect):
    """Against a real interpreter and a real record, not a string this file wrote."""
    assert pcp.verdict_from_junit(_real_junit(tmp_path, _PROOFS[kind])) == expect


def test_the_record_is_read_at_any_terminal_width(tmp_path):
    """The defect this replaces. An attribute in an XML document has no width."""
    record = _real_junit(tmp_path, _PROOFS["assertion"])
    assert "AssertionError" in record
    assert pcp.verdict_from_junit(record) == "divergence"


def test_no_record_is_no_answer_rather_than_a_guess():
    """pytest writes nothing when it cannot start. That is not a verdict, and the prose
    readings are asked next rather than a verdict being invented here."""
    assert pcp.verdict_from_junit("") is None
    assert pcp.verdict_from_junit("<not xml at all") is None


def test_a_record_with_no_case_in_it_is_no_answer():
    """A document that parsed and holds no result is the same situation as no document."""
    assert pcp.verdict_from_junit('<?xml version="1.0"?><testsuites></testsuites>') is None
