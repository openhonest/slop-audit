"""The JS/TS runtime harness (L1.19 c8 branch coverage, L1.20 shuffled-order determinism),
tested at the points where it is a pure function of its input, a real function of the real
filesystem, or a real function of the real environment.

What this file used to contain, and why it does not: eleven tests built on `_cover_run` and
`_det_stub`, which replaced `_node` and `_run_untrusted` so that a fake wrote
`coverage-summary.json` and the module then read it back. The assertion was that the module
can parse a file the test had written moments earlier, and the vitest and jest summary strings
it matched on were the test author's, not the runner's. If vitest changed its wording or c8
changed its summary schema, all eleven stayed green while the harness broke in the field.

The claims those tests defended are real: the bands, the c8-missing n/a, the no-summary n/a,
the zero-branches n/a and the per-seed failure surfacing. They are now proved by nothing,
because `decision_space_coverage` probes node, probes c8, runs the wrap, opens a temp
directory, reads the summary and decides the band inside one function, so a fake is the only
way in. Extracting `_coverage_verdict(branches: dict, returncode: int, runtime: str)` and
`_determinism_verdict(per_seed, runner, runs, runtime)` turns them into
`assert f(input) == expected`, and is filed as separate work.

What is new here: the pure helpers those tests reached only indirectly are now asserted
directly, so the runner detection, the test-command reading, the installed-version reading,
the ran-marker and the failure summary are proved on their own terms.
"""

import json
import shutil

import pytest
from l1_analyzer import js_trace

_NEEDS_NODE = pytest.mark.skipif(shutil.which("node") is None,
                                 reason="needs a real node on PATH; a stubbed one proves nothing")


def _write_pkg(tmp_path, scripts: dict, dev: dict) -> None:
    """Write a real package.json. Both arguments are required: a default here would hide
    which shape each test used, and the shape is the input under test."""
    (tmp_path / "package.json").write_text(json.dumps({"scripts": scripts, "devDependencies": dev}))


# --- reading the project's own package.json -----------------------------------

def test_package_json_is_none_when_absent_or_malformed(tmp_path):
    assert js_trace._package_json(tmp_path) is None
    (tmp_path / "package.json").write_text("{not json")
    assert js_trace._package_json(tmp_path) is None


def test_package_json_reads_a_real_file(tmp_path):
    _write_pkg(tmp_path, {"test": "vitest run"}, {"vitest": "^2.0.0"})
    assert js_trace._package_json(tmp_path)["scripts"]["test"] == "vitest run"


def test_node_modules_present_reads_the_directory(tmp_path):
    assert not js_trace._node_modules_present(tmp_path)
    (tmp_path / "node_modules").mkdir()
    assert js_trace._node_modules_present(tmp_path)


# --- the test command and the runner ------------------------------------------

@pytest.mark.parametrize("script", ["", "   ", "echo \"Error: no test specified\" && exit 1"])
def test_test_command_is_none_for_no_real_script(script):
    # missing, empty, or the npm init placeholder that only prints an error.
    assert js_trace._test_command({"scripts": {"test": script}}) is None


def test_test_command_returns_the_project_script():
    assert js_trace._test_command({"scripts": {"test": "vitest run"}}) == "vitest run"


@pytest.mark.parametrize("pkg,expected", [
    ({"devDependencies": {"vitest": "^2.0.0"}, "scripts": {}}, "vitest"),
    ({"devDependencies": {"jest": "^30.0.0"}, "scripts": {}}, "jest"),
    ({"devDependencies": {}, "scripts": {"test": "vitest run"}}, "vitest"),
    ({"devDependencies": {"mocha": "^10.0.0"}, "scripts": {}}, "mocha"),
    ({"devDependencies": {}, "scripts": {"test": "echo hi"}}, None),
])
def test_detect_runner_reads_deps_and_script(pkg, expected):
    assert js_trace._detect_runner(pkg) == expected


def test_detect_runner_prefers_a_drivable_runner_over_an_undrivable_one():
    # A project carrying both must be driven by the one whose order can be shuffled.
    pkg = {"devDependencies": {"mocha": "^10.0.0", "vitest": "^2.0.0"}, "scripts": {}}
    assert js_trace._detect_runner(pkg) == "vitest"


# --- the installed version, read from the target's own node_modules -----------

def test_installed_major_reads_the_targets_own_copy(tmp_path):
    pkg_dir = tmp_path / "node_modules" / "jest"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "package.json").write_text(json.dumps({"version": "29.7.0"}))
    assert js_trace._installed_major(tmp_path, "jest") == 29


def test_installed_major_is_none_when_it_cannot_be_read(tmp_path):
    assert js_trace._installed_major(tmp_path, "jest") is None
    pkg_dir = tmp_path / "node_modules" / "jest"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "package.json").write_text("{not json")
    assert js_trace._installed_major(tmp_path, "jest") is None


# --- the ran-marker and the failure line --------------------------------------

def test_suite_ran_detects_execution():
    assert js_trace._suite_ran("vitest", "Test Files  1 passed (1)")
    assert js_trace._suite_ran("jest", "Tests:       3 passed, 3 total")
    assert not js_trace._suite_ran("vitest", "npm error could not determine executable")


def test_failure_summary_names_a_reason_rather_than_a_bare_score():
    out = "RUN  v2.0.0\nTest Files  1 failed (3)\nTests  2 failed | 10 passed (12)"
    assert js_trace._failure_summary(out) == "Test Files  1 failed (3)"


def test_failure_summary_falls_back_to_the_first_line():
    assert js_trace._failure_summary("something broke\nsecond line") == "something broke"


# --- nvm sourcing, against the real environment and real files ----------------

def test_nvm_dir_detects_nvm_sh(monkeypatch, tmp_path):
    monkeypatch.setenv("NVM_DIR", str(tmp_path / "nvm"))
    assert js_trace._nvm_dir() is None                      # no nvm.sh yet
    (tmp_path / "nvm").mkdir()
    (tmp_path / "nvm" / "nvm.sh").write_text("")
    assert js_trace._nvm_dir() == tmp_path / "nvm"


def test_wrap_sources_nvm_and_preserves_the_command(monkeypatch, tmp_path):
    # A real NVM_DIR holding a real nvm.sh, not a replaced _nvm_dir. The env var and the file
    # are the whole of what _nvm_dir reads, so this reaches the same branch honestly.
    nvm = tmp_path / ".nvm"
    nvm.mkdir()
    (nvm / "nvm.sh").write_text("")
    monkeypatch.setenv("NVM_DIR", str(nvm))
    wrapped = js_trace._wrap(tmp_path, ["npx", "c8", "--version"])
    assert wrapped[0:2] == ["bash", "-c"]
    assert "nvm.sh" in wrapped[2] and "nvm use" in wrapped[2] and 'exec "$@"' in wrapped[2]
    assert wrapped[3] == "nvm" and wrapped[4:] == ["npx", "c8", "--version"]   # command preserved


def test_wrap_is_a_noop_without_nvm(monkeypatch, tmp_path):
    monkeypatch.setenv("NVM_DIR", str(tmp_path / "absent"))   # no nvm.sh under it
    assert js_trace._wrap(tmp_path, ["node", "--version"]) == ["node", "--version"]


# --- the refusals reachable without faking anything ---------------------------

def test_l19_na_without_node(monkeypatch, tmp_path):
    # An empty PATH is a real machine state: shutil.which genuinely finds no node.
    monkeypatch.setenv("PATH", "")
    assert js_trace.decision_space_coverage(tmp_path, 30)["band"] == "n/a"


@_NEEDS_NODE
def test_l19_na_when_node_modules_missing(tmp_path):
    _write_pkg(tmp_path, {"test": "vitest run"}, {})
    r = js_trace.decision_space_coverage(tmp_path, 30)
    assert r["band"] == "n/a" and "node_modules missing" in r["details"]


@_NEEDS_NODE
def test_l20_na_when_node_modules_missing(tmp_path):
    _write_pkg(tmp_path, {"test": "vitest run"}, {})
    r = js_trace.test_determinism(tmp_path, 5, 30)
    assert r["band"] == "n/a" and "node_modules missing" in r["details"]


@_NEEDS_NODE
def test_l20_na_when_runner_not_drivable(tmp_path):
    (tmp_path / "node_modules").mkdir()
    _write_pkg(tmp_path, {"test": "mocha"}, {"mocha": "^10.0.0"})
    r = js_trace.test_determinism(tmp_path, 5, 30)
    assert r["band"] == "n/a"
    assert "order-randomizing runner" in r["details"] and "mocha" in r["details"]


@_NEEDS_NODE
def test_l20_jest_below_30_is_na(tmp_path):
    (tmp_path / "node_modules" / "jest").mkdir(parents=True)
    (tmp_path / "node_modules" / "jest" / "package.json").write_text(json.dumps({"version": "29.7.0"}))
    _write_pkg(tmp_path, {"test": "jest"}, {"jest": "^29.0.0"})
    r = js_trace.test_determinism(tmp_path, 5, 30)
    assert r["band"] == "n/a" and "jest>=30" in r["details"]
