"""The proof requests and the gate, reached the way a caller reaches them.

`--facets` locates the silences. This is the pair of commands that turn one into a
demonstration: `--proof-cap N` asks for up to N isolated requests, and `--prove-facet`
runs one proposal through the gate.

Two commands rather than one, because the caller writes the test. A single command would
have to write it, and a tool that both proposes and accepts its own proposal has no gate at
all.
"""

import json
import textwrap

import pytest
from l1_analyzer import cli

MODULE = textwrap.dedent('''
    def band(n: int) -> str:
        if n > 10:
            return "high"
        return "low"
''').lstrip("\n")

TESTS = 'from m import band\n\n\ndef test_high():\n    assert band(20) == "high"\n'


@pytest.fixture
def project(tmp_path):
    (tmp_path / "m.py").write_text(MODULE)
    (tmp_path / "test_m.py").write_text(TESTS)
    return tmp_path


def _run(argv: list[str], capsys) -> tuple[int, str]:
    code = cli.main(argv)
    return code, capsys.readouterr().out


# --------------------------------------------------------------------------
# Asking for requests
# --------------------------------------------------------------------------

def test_no_requests_are_made_unless_the_caller_sets_a_cap(project, capsys):
    """The cap is a spending limit and a decision about what leaves the machine, so nothing
    is asked for by default."""
    _code, out = _run([str(project), "--facets", str(project / "m.py"),
                       str(project / "test_m.py"), "--format", "json"], capsys)
    assert json.loads(out)["proof_requests"] == []


def test_the_cap_bounds_what_is_asked(project, capsys):
    _code, out = _run([str(project), "--facets", str(project / "m.py"),
                       str(project / "test_m.py"), "--proof-cap", "1", "--format", "json"],
                      capsys)
    assert len(json.loads(out)["proof_requests"]) == 1


def test_a_request_carries_the_signature_and_not_the_source(project, capsys):
    _code, out = _run([str(project), "--facets", str(project / "m.py"),
                       str(project / "test_m.py"), "--proof-cap", "3", "--format", "json"],
                      capsys)
    requests = json.loads(out)["proof_requests"]
    assert requests
    assert all("def band(n: int) -> str" == r["signature"] for r in requests)
    assert MODULE not in out


def test_the_text_report_names_what_would_count_as_a_demonstration(project, capsys):
    """"Write a test" invites a passing one, and a passing one is not a proof."""
    _code, out = _run([str(project), "--facets", str(project / "m.py"),
                       str(project / "test_m.py"), "--proof-cap", "2"], capsys)
    assert "proof requests" in out
    assert "does NOT satisfy" in out


# --------------------------------------------------------------------------
# Running one through the gate
# --------------------------------------------------------------------------

def _prove(project, index: int, argument: str, expected: str, why: str) -> list[str]:
    return [str(project), "--prove-facet", str(project / "m.py"), str(project / "test_m.py"),
            str(index), argument, expected, why]


def test_a_failing_proposal_is_retained_and_the_command_succeeds(project, capsys):
    code, out = _run(_prove(project, 0, "0", "result == 'high'",
                            "claims zero bands high, which it does not"), capsys)
    assert code == 0
    assert "retained" in out.lower()


def test_a_passing_proposal_is_discarded_and_the_command_says_why(project, capsys):
    """The command does not fail: discarding a proposal is a correct outcome, not an error
    in the run. What it must not do is call it a proof."""
    code, out = _run(_prove(project, 0, "0", "result == 'low'", "zero bands low"), capsys)
    assert code == 0
    assert "discarded" in out.lower()
    assert "demonstrates no defect" in out
    assert "coverage" in out, (
        "a reader has to be told the test may still be worth adopting; the first version "
        "of this sentence claimed the suite already covered the region, which does not "
        "follow and was false the first time I ran it")


def test_a_malformed_proposal_names_the_field_to_correct(project, capsys):
    code, out = _run(_prove(project, 0, "1 +", "result", "broken"), capsys)
    assert code == 0
    assert "concrete_input" in out


def test_an_index_no_request_carries_is_refused(project, capsys):
    """An index out of range is the caller pointing at a silence that is not there, and
    proving something about a different one would be worse than refusing."""
    code, out = _run(_prove(project, 99, "0", "result", "x"), capsys)
    assert code == 1
    assert "99" in out


def test_the_retained_proof_is_printed_so_a_reader_can_adopt_it(project, capsys):
    """Umbra proves gaps and never edits a suite. Adopting a surviving proof is the
    reader's decision, so the test source has to reach them."""
    _code, out = _run(_prove(project, 0, "0", "result == 'high'", "x"), capsys)
    assert "def test_proof_0" in out
    assert (project / "test_m.py").read_text() == TESTS, "the gate wrote into the suite"


def test_the_gate_reports_as_json_when_asked(project, capsys):
    _code, out = _run(_prove(project, 0, "0", "result == 'high'", "x") + ["--format", "json"],
                      capsys)
    verdict = json.loads(out)
    assert verdict["retained"] is True
    assert verdict["outcome"] == "failed"
