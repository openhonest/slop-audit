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
the zero-branches n/a and the per-seed failure surfacing. They went unproved for as long as
`decision_space_coverage` probed node, probed c8, ran the wrap, opened a temp directory, read
the summary and decided the band inside one function, because a fake was then the only way in.
`_coverage_verdict(branches, returncode, runtime, 300.0)` and `_determinism_verdict(per_seed, runner,
runtime, 300.0)` are now the decisions on their own, taking plain values and doing no I/O, and the
tests at the end of this file assert them as `f(input) == expected`.

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
    assert js_trace._installed_major(tmp_path, "jest") == (29, "")


def test_installed_major_is_unknown_with_a_reason_when_it_cannot_be_read(tmp_path):
    """Unknown is its own answer. The caller's guard read `major is not None and major < 30`,
    so a version nobody could read PROCEEDED to drive `jest --seed` at a jest that may not
    have the flag."""
    major, why = js_trace._installed_major(tmp_path, "jest")
    assert major is None and "could not be read" in why
    pkg_dir = tmp_path / "node_modules" / "jest"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "package.json").write_text("{not json")
    major, why = js_trace._installed_major(tmp_path, "jest")
    assert major is None and "valid JSON" in why


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
    assert js_trace.decision_space_coverage(tmp_path, 30, runtime_override=None)["band"] == "n/a"


@_NEEDS_NODE
def test_l19_na_when_node_modules_missing(tmp_path):
    _write_pkg(tmp_path, {"test": "vitest run"}, {})
    r = js_trace.decision_space_coverage(tmp_path, 30, runtime_override=None)
    assert r["band"] == "n/a" and "node_modules missing" in r["details"]


@_NEEDS_NODE
def test_l20_na_when_node_modules_missing(tmp_path):
    _write_pkg(tmp_path, {"test": "vitest run"}, {})
    r = js_trace.test_determinism(tmp_path, 5, 30, runtime_override=None)
    assert r["band"] == "n/a" and "node_modules missing" in r["details"]


@_NEEDS_NODE
def test_l20_na_when_runner_not_drivable(tmp_path):
    (tmp_path / "node_modules").mkdir()
    _write_pkg(tmp_path, {"test": "mocha"}, {"mocha": "^10.0.0"})
    r = js_trace.test_determinism(tmp_path, 5, 30, runtime_override=None)
    assert r["band"] == "n/a"
    assert "order-randomizing runner" in r["details"] and "mocha" in r["details"]


@_NEEDS_NODE
def test_l20_jest_below_30_is_na(tmp_path):
    (tmp_path / "node_modules" / "jest").mkdir(parents=True)
    (tmp_path / "node_modules" / "jest" / "package.json").write_text(json.dumps({"version": "29.7.0"}))
    _write_pkg(tmp_path, {"test": "jest"}, {"jest": "^29.0.0"})
    r = js_trace.test_determinism(tmp_path, 5, 30, runtime_override=None)
    assert r["band"] == "n/a" and "jest>=30" in r["details"]


# --- the L1.19 verdict, extracted so its band table can be asserted as a value -----------
#
# Written before `_coverage_verdict` exists, so every one of these was red on AttributeError
# rather than on a band. The deleted tests reached this table only through a fake that wrote
# the very summary file the module then read back, so what they proved was that the module can
# parse a file the test had written moments earlier. The claim they were defending is real and
# is restated here as `assert f(input) == expected`.

def _c8_branches(covered: int, total: int) -> dict:
    """The `total.branches` object a coverage summary carries. Every field is named at every
    call site: a default here would hide which number the band actually read.

    No `pct`. The report writes one and the verdict stopped reading it on 2026-09-23, when
    this language joined the shared verdict the other seven use: the share is computed from
    the counts, so a report whose own percentage disagreed with its own counts could no longer
    publish the percentage."""
    return {"total": total, "covered": covered, "skipped": total - covered}


def test_a_finished_run_yields_the_branch_share_the_runner_measured():
    r = js_trace._coverage_verdict(_c8_branches(38, 40), 0, "v22.3.0 via nvm", 300.0,
                                   "c8 branch counters (V8)")
    assert r["value"] == 95.0 and r["band"] == "Healthy"
    assert "38/40 decision branches exercised by tests" in r["details"]
    assert "c8 branch counters (V8)" in r["details"]
    assert "suite passed" in r["details"] and "v22.3.0 via nvm" in r["details"]


def test_the_line_names_whatever_actually_measured_the_run():
    """Three routes reach this verdict and only one of them is c8. The sentence said c8
    whatever had run, which is a claim about the measurement rather than about the code."""
    r = js_trace._coverage_verdict(_c8_branches(1, 2), 0, "v22.3.0", 300.0,
                                   "vitest v8 coverage")
    assert "vitest v8 coverage" in r["details"]
    assert "c8" not in r["details"]


@pytest.mark.parametrize("covered,total,returncode,value,band,says", [
    # A non-zero exit means the suite ran and some tests failed. The branches they took are
    # real, so this is a measurement, and the exit is named so the reader knows the shape.
    pytest.param(7, 10, 1, 70.0, "Not Healthy", "suite exit 1",
                 id="a-failing-but-valid-run-is-still-measured"),
    # Zero branches is an absence, not a zero per cent: a tree with nothing to cover has not
    # been measured badly, it has not been measured.
    pytest.param(0, 0, 0, "n/a", "n/a", "no enumerable decision branches",
                 id="zero-countable-branches-is-absent-not-zero-per-cent"),
])
def test_the_verdict_reads_each_shape_of_finished_run(covered, total, returncode, value,
                                                      band, says):
    r = js_trace._coverage_verdict(_c8_branches(covered, total), returncode, "v22.3.0", 300.0,
                                   "c8 branch counters (V8)")
    assert r["value"] == value and r["band"] == band
    assert says in r["details"]


@pytest.mark.parametrize("covered,total,band", [
    (1, 1, "Healthy"),
    (9001, 10000, "Healthy"),
    (9, 10, "Not Healthy"),        # exactly 90 is not above 90
    (6, 10, "Not Healthy"),        # exactly 60 is the floor of the middle band
    (5999, 10000, "Slop"),
    (0, 2, "Slop"),                # a measured zero: branches exist and none were taken
])
def test_the_coverage_bands_are_decided_at_the_exact_edges(covered, total, band):
    r = js_trace._coverage_verdict(_c8_branches(covered, total), 0, "node", 300.0,
                                   "c8 branch counters (V8)")
    assert r["band"] == band


def test_a_timed_out_run_is_named_rather_than_scored():
    # Decided before any total is read: a killed run wrote no summary, so there is nothing to
    # hand over but an empty object, and the verdict must reach its answer without it.
    r = js_trace._coverage_verdict(None, 124, "node", 300.0, "c8 branch counters (V8)")
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert "timed out" in r["details"]




# --- the L1.20 verdict, extracted so the per-seed outcomes can be handed over as values ---

_CLEAN = (0, "Test Files  1 passed (1)\nTests  12 passed (12)")
_FAILED = (1, "Test Files  1 failed (1)\nTests  2 failed | 10 passed (12)")


def test_every_run_clean_is_the_full_score_and_healthy():
    r = js_trace._determinism_verdict([_CLEAN] * 5, "vitest", "v22.3.0", 300.0)
    assert r["value"] == "5/5" and r["band"] == "Healthy"
    assert "5 of 5 shuffled-order vitest runs passed cleanly" in r["details"]
    assert "v22.3.0" in r["details"]


def test_one_run_short_is_not_healthy_and_two_short_is_slop():
    one = js_trace._determinism_verdict([_CLEAN] * 4 + [_FAILED], "vitest", "node", 300.0)
    assert one["value"] == "4/5" and one["band"] == "Not Healthy"
    two = js_trace._determinism_verdict([_CLEAN] * 3 + [_FAILED] * 2, "vitest", "node", 300.0)
    assert two["value"] == "3/5" and two["band"] == "Slop"


def test_a_failing_seed_is_named_with_the_line_that_says_why():
    r = js_trace._determinism_verdict([_CLEAN, _CLEAN, _FAILED, _CLEAN, _CLEAN], "vitest", "node", 300.0)
    assert r["value"] == "4/5"
    assert "seed 3: Test Files  1 failed (1)" in r["details"]


def test_at_most_three_failing_seeds_are_named():
    r = js_trace._determinism_verdict([_FAILED] * 5, "vitest", "node", 300.0)
    assert r["value"] == "0/5" and r["band"] == "Slop"
    assert r["details"].count("seed ") == 3


def test_a_seed_that_timed_out_stops_the_count_and_names_that_seed():
    r = js_trace._determinism_verdict([_CLEAN, _CLEAN, (124, "")], "vitest", "node", 300.0)
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert "seed 3" in r["details"] and "timed out" in r["details"]


def test_a_seed_whose_runner_executed_no_suite_is_not_a_failing_run():
    # The not-run guard. npm failing to find the runner is a broken project, not a flaky one,
    # and counting it as a failing run reports it as non-determinism.
    r = js_trace._determinism_verdict([(1, "npm error could not determine executable")], "vitest", "v22.3.0", 300.0)
    assert r["band"] == "n/a" and "did not run" in r["details"]
    assert "seed 1" in r["details"] and "vitest" in r["details"] and "v22.3.0" in r["details"]


def test_no_runs_at_all_is_absent_not_a_clean_sweep():
    # Zero clean out of zero runs satisfies `passing == runs`, which is how a measure that ran
    # nothing issues itself a clean bill. It is the absence of a measurement.
    r = js_trace._determinism_verdict([], "vitest", "node", 300.0)
    assert r["band"] == "n/a" and r["value"] == "n/a"
