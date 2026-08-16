"""The Python runtime harness (L1.19 decision-space coverage, L1.20 seed determinism),
tested at the points where it is a pure function of its input or a real function of the real
filesystem.

What this file used to contain, and why it does not: six tests that replaced `_run_untrusted`
with `lambda *a, **k: CompletedProcess([], rc, stdout, "")` and asserted the band that came
back. Because the fake ignored its arguments, the harness could have invoked pytest with the
wrong flags, against the wrong interpreter, in the wrong directory, and every one of them
would still have passed. A seventh replaced `subprocess.run` outright to assert which
executable was passed, which checks the call rather than the result, and restated a fact
`test_interpreter_selects_the_named_python_over_the_default` already proves without a fake.

The claim those tests were written to defend is real and important: exit codes 2, 3, 4, 5 and
124 must produce n/a with a reason, never a 0.0 that reads as measured-and-terrible coverage.
The claim is now proved by nothing. The reason is module shape: `decision_space_coverage`
runs the suite, opens a temp directory, shells out a second time for `coverage json`, reads
the report and decides the band inside one function, so the exit-code table can only be
reached through a fake. Extracting
`_coverage_verdict(returncode: int, totals: dict, provenance: str) -> L1Result` turns all six
into `assert f(input) == expected`. That extraction is filed as separate work.
"""

import sys

from l1_analyzer import pytest_trace


# --- the refusals that need no fake -------------------------------------------

def test_l19_is_na_without_a_python_target(tmp_path):
    result = pytest_trace.decision_space_coverage(tmp_path, "rust", 5)
    assert result["band"] == "n/a"


# --- pure parsing -------------------------------------------------------------

def test_pytest_summary_reads_the_last_counts_line():
    out = "collected 1222 items\n....\n3 failed, 1219 passed in 10.0s\n"
    assert pytest_trace._pytest_summary(out) == "3 failed, 1219 passed in 10.0s"
    assert pytest_trace._pytest_summary("no counts here") == "no summary line"


def test_interpreter_selects_the_named_python_over_the_default():
    # None (the named Nothing) resolves to the analyzer's own interpreter; a path is used verbatim.
    assert pytest_trace._interpreter(None) == sys.executable
    assert pytest_trace._interpreter("/opt/persistum/.venv/bin/python") == "/opt/persistum/.venv/bin/python"


# --- directory-insensitive interpreter detection, against a real filesystem ----

def test_detect_target_interpreter_finds_a_repo_venv(tmp_path):
    assert pytest_trace.detect_target_interpreter(tmp_path) is None
    venv = tmp_path / ".venv" / "bin"
    venv.mkdir(parents=True)
    (venv / "python").write_text("")   # existence is all detection needs
    assert pytest_trace.detect_target_interpreter(tmp_path) == str(venv / "python")


def test_resolve_interpreter_precedence(tmp_path):
    # 1. an explicit override wins over everything.
    exe, prov = pytest_trace.resolve_interpreter(tmp_path, "/x/py")
    assert exe == "/x/py" and "--python" in prov
    # 2. else the target repo's own venv (this is what makes the audit dir-insensitive).
    venv = tmp_path / ".venv" / "bin"
    venv.mkdir(parents=True)
    (venv / "python").write_text("")
    exe, prov = pytest_trace.resolve_interpreter(tmp_path, None)
    assert exe == str(venv / "python") and "target venv" in prov
    # 3. else the analyzer's own interpreter (a repo with no venv).
    exe, prov = pytest_trace.resolve_interpreter(tmp_path / "no-venv-here", None)
    assert exe == sys.executable and "analyzer" in prov


# --- explicit shim resolution -------------------------------------------------

def test_resolve_via_shim_none_when_no_manager(monkeypatch, tmp_path):
    # An empty PATH is a real machine state, not a fake: shutil.which genuinely finds no
    # version manager, so every shim is genuinely skipped and the ambient fallback is the
    # real answer. The previous version of this test replaced shutil.which itself, which
    # proved only that the module calls the function the test had just written.
    monkeypatch.setenv("PATH", "")
    assert pytest_trace.resolve_via_shim(tmp_path, "ruby", 5) == (None, "")
