"""Each section of the facets report appears when there is something to put in it.

The report is ten conditional sections and the reader sees whichever ones have content. Not
one of those conditions was exercised: `--facets` against the module that renders it read a
72 per cent silence index, and the renderer's own branches were most of it.

What a missing section costs is not an error. It is a reader told less than the audit found,
on a page whose whole purpose is to say what was not measured, and nothing fails when a
heading stops appearing.

Read against a real module and a real test file rather than a built payload, because the
report's job is to render what the audit produces and a fixture of my own invention proves
only that the formatter can format my invention.
"""

import json

import pytest
from l1_analyzer import cli

_MODULE = '''"""A module with something in every category the report has a heading for."""


def pure_and_unproved(n: int) -> int:
    """Nothing calls this in the test file, so its facets have no evidence."""
    if n > 3:
        return n * 2
    return n


def undeclared(value):
    """No parameter type and no return type: a gap in the signature rather than in the
    reading, which the report keeps outside the silence index."""
    return value


def exercised(n: int) -> int:
    return n + 1
'''

_TESTS = '''from m import exercised


def test_exercised():
    assert exercised(1) == 2
'''


@pytest.fixture
def audited(tmp_path):
    (tmp_path / "m.py").write_text(_MODULE)
    (tmp_path / "test_m.py").write_text(_TESTS)
    return tmp_path / "m.py", (tmp_path / "test_m.py",)


def test_the_report_names_the_module_and_the_tests_it_read(audited, capsys):
    module, tests = audited
    assert cli._report_facets(module, tests, "text", 0) == 0
    printed = capsys.readouterr().out
    assert "m.py" in printed and "test_m.py" in printed


def test_the_report_gives_the_coverage_and_the_silence_index(audited, capsys):
    module, tests = audited
    cli._report_facets(module, tests, "text", 0)
    printed = capsys.readouterr().out
    assert "Coverage:" in printed and "Silence index:" in printed
    assert "closeable" in printed


def test_a_facet_with_no_evidence_is_listed_under_its_kind(audited, capsys):
    """The section that carries the finding. Each silent facet names the function and the
    line, because a count with no sites is a number a reader cannot act on."""
    module, tests = audited
    cli._report_facets(module, tests, "text", 0)
    printed = capsys.readouterr().out
    assert "pure_and_unproved" in printed


def test_a_gap_in_the_signature_is_kept_apart_from_a_gap_in_the_reading(audited, capsys):
    """Both sit outside the silence index and for different reasons a reader has to tell
    apart. One is closed by declaring a type and the other by writing a test."""
    module, tests = audited
    cli._report_facets(module, tests, "text", 0)
    printed = capsys.readouterr().out
    assert "undeclared" in printed
    assert "not counted in the Silence index" in printed or "outside the Silence index" in printed


def test_no_proof_is_requested_unless_the_caller_sets_a_cap(audited, capsys):
    """A request is what gets sent to a model, so how many are made is the caller's decision
    about money and about what leaves the machine."""
    module, tests = audited
    cli._report_facets(module, tests, "text", 0)
    assert "proof requests" not in capsys.readouterr().out


def test_a_cap_asks_for_proofs_and_each_carries_its_signature_and_gap(audited, capsys):
    module, tests = audited
    cli._report_facets(module, tests, "text", 3)
    printed = capsys.readouterr().out
    assert "proof requests" in printed
    assert "--prove-facet" in printed


def test_the_json_shape_carries_the_audit_and_the_requests(audited, capsys):
    module, tests = audited
    assert cli._report_facets(module, tests, "json", 2) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "proof_requests" in payload
    assert "facets" in payload


def test_the_json_shape_prints_nothing_a_reader_would_mistake_for_prose(audited, capsys):
    """It is machine output and the whole of it is one object. A heading printed beside it
    would break every consumer that parses the stream."""
    module, tests = audited
    cli._report_facets(module, tests, "json", 0)
    printed = capsys.readouterr().out
    assert printed.lstrip().startswith("{")


def test_a_module_that_does_not_parse_is_a_reason_rather_than_a_stack_trace(tmp_path, capsys):
    """It raised straight out of the command. `--facets` on a broken module printed a
    Python traceback where an adopter wanted a sentence, and the audit record already
    carried the field to say it in.

    The reason sits above the lists, because a reader told the reading did not happen must
    not read the lists below as a result."""
    (tmp_path / "m.py").write_text("def f(:\n")
    (tmp_path / "test_m.py").write_text("def test_nothing():\n    assert True\n")
    assert cli._report_facets(tmp_path / "m.py", (tmp_path / "test_m.py",), "text", 0) == 0
    printed = capsys.readouterr().out
    assert "does not parse" in printed
    assert "m.py" in printed
    assert "not measured" in printed


def test_a_test_file_that_does_not_parse_names_which_half_failed(tmp_path, capsys):
    """A suite is read as several files, so a reader told only that something did not parse
    has to go and find out which."""
    (tmp_path / "m.py").write_text("def f(n: int) -> int:\n    return n\n")
    (tmp_path / "test_m.py").write_text("def test_broken(:\n")
    cli._report_facets(tmp_path / "m.py", (tmp_path / "test_m.py",), "text", 0)
    assert "a test file does not parse" in capsys.readouterr().out


def test_the_report_names_the_build_that_produced_it(audited, capsys):
    """A published measurement whose reader cannot tell which build made it cannot be
    compared against another run."""
    module, tests = audited
    cli._report_facets(module, tests, "text", 0)
    assert "slop-audit-l1" in capsys.readouterr().out
