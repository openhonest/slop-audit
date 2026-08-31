"""All three shapes of the L1.21 command report the same finding and exit the same way.

The clause check is opt-in and states an opinion, so running it and finding a violation IS
the gate failing. The hook shape always exited 1 on a finding and the other two returned 0
while printing violations, so a caller could not gate on them. That was fixed and nothing
held it: the command read an 81 per cent silence index against its own module, and these
branches were the largest block of it.

Three shapes because three readers. A person reads the per-clause document, a machine reads
one object, and an agent mid-edit reads where and what to do instead and reads nothing at
all when the file is clean. Silence on a clean write is the correct output: a hook that
congratulates an agent on every file teaches it to skip the output, and then the one that
matters is skipped too.
"""

import json

import pytest
from l1_analyzer import cli

_CLEAN = "def add(a: int, b: int) -> int:\n    return a + b\n"
_BROKEN = ("class Engine:\n"
           "    def run(self) -> int:\n"
           "        return 1\n"
           "\n"
           "\n"
           "class Car(Engine):\n"
           "    def go(self) -> int:\n"
           "        return self.run()\n")


@pytest.fixture
def clean(tmp_path):
    (tmp_path / "clean.py").write_text(_CLEAN)
    return tmp_path / "clean.py"


@pytest.fixture
def broken(tmp_path):
    (tmp_path / "broken.py").write_text(_BROKEN)
    return tmp_path / "broken.py"


def test_the_hook_shape_says_nothing_about_a_clean_file(clean, capsys):
    assert cli._report_honest_code([clean], "hook") == 0
    printed = capsys.readouterr()
    assert printed.out == "" and printed.err == ""


def test_the_hook_shape_writes_to_the_stream_a_hook_runner_reads(broken, capsys):
    """Standard error, where a hook runner puts what a blocked tool call said."""
    assert cli._report_honest_code([broken], "hook") == 1
    printed = capsys.readouterr()
    assert printed.err.strip()
    assert printed.out == ""


def test_the_hook_shape_says_where_and_what_to_do_instead(broken, capsys):
    cli._report_honest_code([broken], "hook")
    err = capsys.readouterr().err
    assert "broken.py" in err
    assert "instead:" in err


def test_the_text_shape_prints_the_per_clause_document(broken, capsys):
    assert cli._report_honest_code([broken], "text") == 1
    printed = capsys.readouterr().out
    assert "Conformity:" in printed


def test_the_text_shape_prints_a_document_for_a_clean_file_too(clean, capsys):
    """A person asking for the report wants it whether or not anything is wrong. Only the
    hook shape is silent, and only because an agent reads it on every write."""
    assert cli._report_honest_code([clean], "text") == 0
    assert "Conformity:" in capsys.readouterr().out


def test_one_file_returns_one_object_and_not_a_list_of_one(clean, capsys):
    """A consumer already reads that shape, and changing it to serve the batch case would
    break a working integration to add a feature."""
    cli._report_honest_code([clean], "json")
    assert isinstance(json.loads(capsys.readouterr().out), dict)


def test_several_files_return_a_list(clean, broken, capsys):
    cli._report_honest_code([clean, broken], "json")
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list) and len(payload) == 2


def test_every_shape_exits_one_on_a_finding(clean, broken, capsys):
    """The half that was broken. Two of the three printed violations and returned 0, so a
    caller could not gate on them, and a gate nobody can call is not a gate."""
    for shape in ("hook", "text", "json"):
        assert cli._report_honest_code([broken], shape) == 1, shape
        capsys.readouterr()


def test_every_shape_exits_zero_on_a_clean_file(clean, capsys):
    for shape in ("hook", "text", "json"):
        assert cli._report_honest_code([clean], shape) == 0, shape
        capsys.readouterr()


def test_a_file_nobody_could_read_is_named_rather_than_passed_over(tmp_path, capsys):
    """An unreadable file reported as clean is the exact failure this instrument exists to
    name, so the hook shape says which file and why instead of staying quiet."""
    (tmp_path / "m.py").write_text("def f(:\n")
    cli._report_honest_code([tmp_path / "m.py"], "hook")
    err = capsys.readouterr().err
    assert "m.py" in err
    assert "does not parse" in err


def test_one_clean_file_beside_a_broken_one_does_not_silence_the_broken_one(
        clean, broken, capsys):
    """Several files are measured in one process, which is the whole saving, and a batch
    that reports only its first file would make that saving cost a finding."""
    assert cli._report_honest_code([clean, broken], "hook") == 1
    assert "broken.py" in capsys.readouterr().err
