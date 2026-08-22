"""Three probes that turned "I could not look" into an answer.

L1.21.8 flagged fourteen handlers in this package. Ten of them hand the absence to a caller
that turns it into an explicit refusal with a stated reason, which is the discipline this
whole tool runs on and is something the clause cannot see from one file. Those are declared
at the site.

These three are different, and each fails in its own way.

`_installed_major` returned None when it could not read the installed jest version, and the
caller's guard was `if major is not None and major < 30`. An unreadable version therefore
PROCEEDED, driving `jest --seed` at a jest that may not have the flag. That is the worst
shape of the three: not a wrong message but a measurement taken on an assumption.

`_module_available` returned False when the interpreter would not start, and the caller
then said "needs pytest and coverage.py in the target environment". The reader is sent to
install a package when the real problem is the interpreter they named.

`_make_target` returned None when the Makefile could not be read, and the caller then said
"no Makefile test/check target found". The Makefile may have had one.

The last two are refusals either way, so no number moves. What moves is whether the sentence
under the refusal is true, and a refusal that names the wrong cause sends a reader to fix
the wrong thing.
"""

import subprocess

import pytest
from l1_analyzer import c_trace, js_trace, pytest_trace

# --------------------------------------------------------------------------
# The installed version nobody could read
# --------------------------------------------------------------------------

def test_a_version_that_cannot_be_read_is_not_a_version_that_is_fine(tmp_path):
    """The guard read `major is not None and major < 30`, so an unreadable version fell
    through to the measurement. Unknown has to be its own answer."""
    major, reason = js_trace._installed_major(tmp_path, "jest")
    assert major is None
    assert reason.strip(), "the absence carried no reason, so the caller cannot state one"


def test_a_version_that_can_be_read_carries_no_reason(tmp_path):
    package = tmp_path / "node_modules" / "jest"
    package.mkdir(parents=True)
    (package / "package.json").write_text('{"version": "29.7.0"}')
    assert js_trace._installed_major(tmp_path, "jest") == (29, "")


def test_a_malformed_version_is_unknown_rather_than_zero(tmp_path):
    package = tmp_path / "node_modules" / "jest"
    package.mkdir(parents=True)
    (package / "package.json").write_text('{"version": "not-a-version"}')
    major, reason = js_trace._installed_major(tmp_path, "jest")
    assert major is None
    assert reason.strip()


def test_determinism_refuses_rather_than_driving_a_jest_it_could_not_identify(tmp_path):
    """The behaviour the guard was hiding. `jest --seed` needs jest 30, and running it
    against an unknown version produces a determinism figure nobody can stand behind."""
    (tmp_path / "package.json").write_text(
        '{"scripts": {"test": "jest"}, "devDependencies": {"jest": "^29.0.0"}}')
    (tmp_path / "node_modules").mkdir()
    result = js_trace.test_determinism(tmp_path, 3, 5.0, runtime_override=None)
    assert result["band"] == "n/a"
    assert "version" in result["details"].lower()


# --------------------------------------------------------------------------
# The interpreter that would not start
# --------------------------------------------------------------------------

def test_a_module_that_is_there_is_available():
    available, reason = pytest_trace._module_available("json", None)
    assert available is True
    assert reason == ""


def test_a_module_that_is_absent_says_so():
    available, reason = pytest_trace._module_available("a_module_nobody_has", None)
    assert available is False
    assert "a_module_nobody_has" in reason


def test_an_interpreter_that_will_not_start_is_not_a_missing_module(monkeypatch):
    """The reader is sent to install a package when the real problem is the interpreter
    they named. Two different repairs, and the sentence has to name the right one."""
    def refuse(*_args, **_kwargs):
        raise OSError("no such file or directory")

    monkeypatch.setattr(subprocess, "run", refuse)
    available, reason = pytest_trace._module_available("pytest", "/nowhere/python")
    assert available is False
    assert "interpreter" in reason.lower()
    assert "pytest" not in reason.split("interpreter")[0]


# --------------------------------------------------------------------------
# The Makefile nobody could read
# --------------------------------------------------------------------------

def test_a_makefile_target_that_is_there_is_found(tmp_path):
    (tmp_path / "Makefile").write_text("test:\n\techo hi\n")
    text, _name, why = c_trace._read_makefile(tmp_path)
    assert why == ""
    assert c_trace.make_target_in(text) == ("test", "")


def test_a_repository_with_no_makefile_says_that(tmp_path):
    text, _name, reason = c_trace._read_makefile(tmp_path)
    assert text == ""
    assert "no makefile" in reason.lower()


def test_a_makefile_with_no_test_target_says_that(tmp_path):
    """A different absence from the one above, and it comes from the decider rather than
    the reader: the file was read, and it declares nothing to run."""
    (tmp_path / "Makefile").write_text("build:\n\techo hi\n")
    text, _name, why = c_trace._read_makefile(tmp_path)
    target, reason = c_trace.make_target_in(text)
    assert why == "" and target is None
    assert "target" in reason.lower()


def test_a_makefile_that_cannot_be_read_is_not_a_makefile_with_no_target(tmp_path):
    """It may have had one. The refusal is the same either way, and the sentence under it
    is what sends a reader to the right repair."""
    makefile = tmp_path / "Makefile"
    makefile.write_text("test:\n\techo hi\n")
    makefile.chmod(0o000)
    try:
        text, _name, reason = c_trace._read_makefile(tmp_path)
    finally:
        makefile.chmod(0o644)
    if text:
        pytest.skip("this filesystem let the unreadable file be read anyway")
    assert "could not be read" in reason.lower()
