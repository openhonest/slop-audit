"""The JS/TS runtime harness (L1.19 c8 branch coverage, L1.20 shuffled-order determinism).
The live harness needs Node and the project's runner, so here the run boundary is stubbed and
the deterministic pieces are asserted: branch-total parsing and the runtime naming, the
dependencies-not-installed and did-not-run guards, the c8-missing n/a, and per-seed failure
surfacing rather than a bare score. Pure assertions, no mocks of business logic."""

import json
import subprocess

from l1_analyzer import js_trace


def _cp(rc, stdout=""):
    return subprocess.CompletedProcess([], rc, stdout, "")


def _pkg(tmp_path, scripts=None, dev=None):
    (tmp_path / "node_modules").mkdir(exist_ok=True)
    (tmp_path / "package.json").write_text(json.dumps({
        "scripts": scripts if scripts is not None else {"test": "vitest run"},
        "devDependencies": dev if dev is not None else {"vitest": "^2.0.0", "c8": "^10.0.0"},
    }))


def _cover_run(monkeypatch, *, branches=None, test_rc=0, write_summary=True, c8=True):
    """Stub node --version, c8 presence, and the c8 wrap (writes a json-summary if asked)."""
    branches = branches if branches is not None else {"total": 40, "covered": 30, "pct": 75.0}

    def fake(cmd, cwd, env, timeout_seconds):
        if "c8" in cmd and "--version" in cmd:
            return _cp(0 if c8 else 1, "10.1.0" if c8 else "")
        if "--version" in cmd:  # node --version
            return _cp(0, "v20.11.0")
        if "c8" in cmd:  # the coverage wrap
            for arg in cmd:
                if arg.startswith("--reports-dir=") and write_summary:
                    reports = arg.split("=", 1)[1]
                    import os
                    os.makedirs(reports, exist_ok=True)
                    with open(os.path.join(reports, "coverage-summary.json"), "w") as fh:
                        json.dump({"total": {"branches": branches}}, fh)
            return _cp(test_rc, "coverage run")
        return _cp(0, "")

    monkeypatch.setattr(js_trace, "_node", lambda: "/usr/bin/node")
    monkeypatch.setattr(js_trace, "_run_untrusted", fake)


# --- L1.19 c8 branch coverage -------------------------------------------------

def test_l19_na_without_node(monkeypatch, tmp_path):
    monkeypatch.setattr(js_trace, "_node", lambda: None)
    assert js_trace.decision_space_coverage(tmp_path, 30)["band"] == "n/a"


def test_l19_na_when_node_modules_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(js_trace, "_node", lambda: "/usr/bin/node")
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"test": "vitest run"}}))
    r = js_trace.decision_space_coverage(tmp_path, 30)
    assert r["band"] == "n/a" and "node_modules missing" in r["details"]


def test_l19_reports_branch_coverage_and_names_the_runtime(monkeypatch, tmp_path):
    _pkg(tmp_path)
    _cover_run(monkeypatch, branches={"total": 40, "covered": 30, "pct": 75.0})
    r = js_trace.decision_space_coverage(tmp_path, 30)
    assert r["value"] == 75.0 and r["band"] == "Not Healthy"
    assert "branch coverage" in r["details"] and "v20.11.0" in r["details"]


def test_l19_na_when_c8_missing(monkeypatch, tmp_path):
    _pkg(tmp_path)
    _cover_run(monkeypatch, c8=False)
    r = js_trace.decision_space_coverage(tmp_path, 30)
    assert r["band"] == "n/a" and "needs c8" in r["details"]


def test_l19_na_when_no_summary_is_produced(monkeypatch, tmp_path):
    # a build error writes no summary: n/a with the reason, never a 0.0.
    _pkg(tmp_path)
    _cover_run(monkeypatch, write_summary=False, test_rc=1)
    r = js_trace.decision_space_coverage(tmp_path, 30)
    assert r["band"] == "n/a" and "produced no data" in r["details"]


def test_l19_bands_follow_the_spec(monkeypatch, tmp_path):
    _pkg(tmp_path)
    _cover_run(monkeypatch, branches={"total": 40, "covered": 39, "pct": 95.0})
    assert js_trace.decision_space_coverage(tmp_path, 30)["band"] == "Healthy"
    _cover_run(monkeypatch, branches={"total": 40, "covered": 16, "pct": 40.0})
    assert js_trace.decision_space_coverage(tmp_path, 30)["band"] == "Slop"


def test_l19_na_when_no_branches(monkeypatch, tmp_path):
    _pkg(tmp_path)
    _cover_run(monkeypatch, branches={"total": 0, "covered": 0, "pct": 100.0})
    r = js_trace.decision_space_coverage(tmp_path, 30)
    assert r["band"] == "n/a" and "no enumerable decision branches" in r["details"]


# --- L1.20 shuffled-order determinism -----------------------------------------

def _det_stub(monkeypatch, output, rc=0):
    monkeypatch.setattr(js_trace, "_node", lambda: "/usr/bin/node")
    monkeypatch.setattr(
        js_trace, "_run_untrusted",
        lambda cmd, **k: _cp(0, "v20.11.0") if "--version" in cmd else _cp(rc, output),
    )


def test_l20_all_green_is_healthy(monkeypatch, tmp_path):
    _pkg(tmp_path)
    _det_stub(monkeypatch, "Test Files  3 passed (3)\nTests  12 passed (12)", rc=0)
    r = js_trace.test_determinism(tmp_path, 5, 30)
    assert r["value"] == "5/5" and r["band"] == "Healthy"
    assert "vitest" in r["details"] and "v20.11.0" in r["details"]


def test_l20_na_when_node_modules_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(js_trace, "_node", lambda: "/usr/bin/node")
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"test": "vitest run"}}))
    r = js_trace.test_determinism(tmp_path, 5, 30)
    assert r["band"] == "n/a" and "node_modules missing" in r["details"]


def test_l20_na_when_runner_not_drivable(monkeypatch, tmp_path):
    _pkg(tmp_path, scripts={"test": "mocha"}, dev={"mocha": "^10.0.0"})
    monkeypatch.setattr(js_trace, "_node", lambda: "/usr/bin/node")
    r = js_trace.test_determinism(tmp_path, 5, 30)
    assert r["band"] == "n/a"
    assert "order-randomizing runner" in r["details"] and "mocha" in r["details"]


def test_l20_na_when_suite_did_not_run(monkeypatch, tmp_path):
    # no runner ran-marker means the runner binary was missing or nothing executed: n/a, not 0/5.
    _pkg(tmp_path)
    _det_stub(monkeypatch, "npm error could not determine executable to run", rc=1)
    r = js_trace.test_determinism(tmp_path, 5, 30)
    assert r["band"] == "n/a" and "did not run" in r["details"]


def test_l20_surfaces_failing_seed_not_a_bare_score(monkeypatch, tmp_path):
    _pkg(tmp_path)
    _det_stub(monkeypatch, "Test Files  1 failed (3)\nTests  2 failed | 10 passed (12)", rc=1)
    r = js_trace.test_determinism(tmp_path, 5, 30)
    assert r["value"] == "0/5" and r["band"] == "Slop" and "seed 1" in r["details"]


def test_l20_jest_below_30_is_na(monkeypatch, tmp_path):
    _pkg(tmp_path, scripts={"test": "jest"}, dev={"jest": "^29.0.0"})
    (tmp_path / "node_modules" / "jest").mkdir(parents=True, exist_ok=True)
    (tmp_path / "node_modules" / "jest" / "package.json").write_text(json.dumps({"version": "29.7.0"}))
    monkeypatch.setattr(js_trace, "_node", lambda: "/usr/bin/node")
    r = js_trace.test_determinism(tmp_path, 5, 30)
    assert r["band"] == "n/a" and "jest>=30" in r["details"]


def test_suite_ran_detects_execution():
    assert js_trace._suite_ran("vitest", "Test Files  1 passed (1)")
    assert js_trace._suite_ran("jest", "Tests:       3 passed, 3 total")
    assert not js_trace._suite_ran("vitest", "npm error could not determine executable")
