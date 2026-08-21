"""L1.21 reached two ways: as an optional clause of the full audit, and as a hook.

The two callers want opposite things. The audit wants one number for a repository, and it
is opt-in because nineteen clauses over a large tree is a cost a caller chooses rather than
one imposed on every run.

The hook wants the opposite: one file, no number, and only what the agent has to change. It
fires on every write, so it must be fast, it must say nothing at all when the file is
clean, and it must exit in a way a hook runner reads as "stop and fix this".
"""

import json

import pytest
from l1_analyzer import cli

DIRTY = ("SETTINGS = {'timeout': 30}\n\n\n"
         "def send(channel, data, timeout=30):\n"
         "    if channel == 'email':\n        return one(data)\n"
         "    elif channel == 'sms':\n        return two(data)\n"
         "    elif channel == 'push':\n        return three(data)\n"
         "    return None\n")

CLEAN = ('"""Nothing here for any clause to find."""\n\n\n'
         "def band(n: int, table: dict) -> str:\n"
         '    return "high" if n > table["high"] else "low"\n')


def _run(argv: list[str], capsys) -> tuple[int, str, str]:
    code = cli.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# --------------------------------------------------------------------------
# The hook
# --------------------------------------------------------------------------

def test_a_clean_file_prints_nothing_and_succeeds(tmp_path, capsys):
    """Silence is the right output on a clean write. A hook that congratulates the agent on
    every file teaches it to skip the output, and then the one that matters is skipped."""
    (tmp_path / "m.py").write_text(CLEAN)
    code, out, err = _run(["--honest-code", str(tmp_path / "m.py")], capsys)
    assert code == 0
    assert out.strip() == ""
    assert err.strip() == ""


def test_a_dirty_file_names_what_to_change_and_fails(tmp_path, capsys):
    (tmp_path / "m.py").write_text(DIRTY)
    code, _out, err = _run(["--honest-code", str(tmp_path / "m.py")], capsys)
    assert code == 1
    assert "L1.21.1" in err
    assert "instead:" in err


def test_the_findings_go_to_stderr_so_a_hook_can_feed_them_back(tmp_path, capsys):
    """A hook runner shows the agent what a blocked tool call wrote to stderr. Printing to
    stdout would put the feedback where nothing reads it."""
    (tmp_path / "m.py").write_text(DIRTY)
    _code, out, err = _run(["--honest-code", str(tmp_path / "m.py")], capsys)
    assert err.strip()
    assert out.strip() == ""


def test_a_file_that_does_not_parse_is_reported_rather_than_passed(tmp_path, capsys):
    """A file nobody could read is not a file with no violations."""
    (tmp_path / "broken.py").write_text("def f(\n")
    code, _out, err = _run(["--honest-code", str(tmp_path / "broken.py")], capsys)
    assert code == 1
    assert "does not parse" in err


def test_the_full_report_is_available_for_a_person(tmp_path, capsys):
    """The hook wants two lines per finding. A person reading one file wants the clauses
    that held and the ones nobody could decide, which the hook deliberately omits."""
    (tmp_path / "m.py").write_text(DIRTY)
    _code, out, _err = _run(["--honest-code", str(tmp_path / "m.py"), "--format", "text"],
                            capsys)
    assert "L1.21.17" in out
    assert "not decided" in out.lower()


def test_the_assessment_is_available_as_json(tmp_path, capsys):
    (tmp_path / "m.py").write_text(DIRTY)
    _code, out, _err = _run(["--honest-code", str(tmp_path / "m.py"), "--format", "json"],
                            capsys)
    assessment = json.loads(out)
    assert assessment["decided_clauses"] < 19
    assert assessment["conformity"] < 100


def test_a_path_that_is_not_there_is_refused(tmp_path, capsys):
    with pytest.raises(SystemExit):
        cli.main(["--honest-code", str(tmp_path / "absent.py")])


# --------------------------------------------------------------------------
# The optional clause of the full audit
# --------------------------------------------------------------------------

def test_the_full_audit_does_not_run_l1_21_by_default(tmp_path, capsys):
    """Nineteen clauses over a large tree is a cost a caller chooses. Running it unasked
    would make every audit slower for a number most callers did not request."""
    (tmp_path / "m.py").write_text(DIRTY)
    _code, out, _err = _run([str(tmp_path), "--format", "json", "--no-exec"], capsys)
    assert "honest_code" not in json.loads(out)["results"]


def test_the_full_audit_runs_l1_21_when_asked(tmp_path, capsys):
    (tmp_path / "m.py").write_text(DIRTY)
    _code, out, _err = _run([str(tmp_path), "--format", "json", "--no-exec",
                             "--honest-code-clauses"], capsys)
    entry = json.loads(out)["results"]["honest_code"]
    assert entry["band"] in ("Healthy", "Not Healthy", "Slop")
    assert entry["value"] < 100


def test_the_panel_entry_names_the_clauses_nobody_decided(tmp_path, capsys):
    """The whole reason to trust the share. A reader has to be able to see what it covers
    rather than assume it covered nineteen."""
    (tmp_path / "m.py").write_text(CLEAN)
    _code, out, _err = _run([str(tmp_path), "--format", "json", "--no-exec",
                             "--honest-code-clauses"], capsys)
    assert "L1.21.17" in json.loads(out)["results"]["honest_code"]["details"]
