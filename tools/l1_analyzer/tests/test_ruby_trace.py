"""The Ruby runtime harness (L1.19 SimpleCov branch coverage, L1.20 randomized-order
determinism). The live harness needs ruby + bundler + a target suite, so here the run
boundary and the tool-presence probes are stubbed and the deterministic pieces are asserted:
branch totalling, the not-run guard, the coverage-missing n/a, and per-seed failure
surfacing. Pure assertions, no mocks of business logic."""

import json
import subprocess

from l1_analyzer import ruby_trace


def _cp(rc, stdout=""):
    return subprocess.CompletedProcess([], rc, stdout, "")


_VERSION = "ruby 3.3.0p0 (2023-12-25 revision e5a195edf6) [arm64-darwin23]"


def _branches(covered, total):
    """A SimpleCov resultset whose single file has `covered` of `total` branch leaves hit."""
    subs = {f"[:then, {i}, 3, 4, 3, 10]": (1 if i < covered else 0) for i in range(total)}
    return {"RSpec": {"coverage": {"/app/x.rb": {"lines": [1], "branches": {"[:if, 0, 3, 4, 3, 20]": subs}}}}}


def _cover_run(monkeypatch, tmp_path, *, covered=8, total=10, write=True, test_rc=0):
    """Stub a suite run that writes coverage/.resultset.json, plus ruby --version. A spec/
    directory makes the runner resolve to RSpec."""
    (tmp_path / "spec").mkdir(exist_ok=True)

    def fake(cmd, cwd, env, timeout_seconds):
        if "--version" in cmd:
            return _cp(0, _VERSION)
        if write:
            cov = tmp_path / "coverage"
            cov.mkdir(exist_ok=True)
            (cov / ".resultset.json").write_text(json.dumps(_branches(covered, total)))
        return _cp(test_rc, "10 examples, 0 failures")

    monkeypatch.setattr(ruby_trace, "_ruby", lambda: "/usr/bin/ruby")
    monkeypatch.setattr(ruby_trace, "_bundle", lambda: "/usr/bin/bundle")
    monkeypatch.setattr(ruby_trace, "_run_untrusted", fake)


def _det_run(monkeypatch, tmp_path, *, rc=0, summary="5 examples, 0 failures"):
    """Stub a randomized-order suite run + ruby --version, with a spec/ directory present."""
    (tmp_path / "spec").mkdir(exist_ok=True)

    def fake(cmd, cwd, env, timeout_seconds):
        if "--version" in cmd:
            return _cp(0, _VERSION)
        return _cp(rc, summary)

    monkeypatch.setattr(ruby_trace, "_ruby", lambda: "/usr/bin/ruby")
    monkeypatch.setattr(ruby_trace, "_bundle", lambda: "/usr/bin/bundle")
    monkeypatch.setattr(ruby_trace, "_run_untrusted", fake)


# --- L1.19 SimpleCov branch coverage -----------------------------------------

def test_l19_na_without_ruby(monkeypatch, tmp_path):
    monkeypatch.setattr(ruby_trace, "_ruby", lambda: None)
    monkeypatch.setattr(ruby_trace, "_bundle", lambda: "/usr/bin/bundle")
    assert ruby_trace.decision_space_coverage(tmp_path, 30)["band"] == "n/a"


def test_l19_reports_branch_coverage_and_names_the_runtime(monkeypatch, tmp_path):
    _cover_run(monkeypatch, tmp_path, covered=8, total=10)
    r = ruby_trace.decision_space_coverage(tmp_path, 30)
    assert r["value"] == 80.0 and r["band"] == "Not Healthy"
    assert "SimpleCov branches" in r["details"] and "ruby 3.3.0" in r["details"]


def test_l19_na_when_resultset_not_produced(monkeypatch, tmp_path):
    # SimpleCov not started in spec_helper: n/a with the exact remedy, never a 0.0.
    _cover_run(monkeypatch, tmp_path, write=False)
    r = ruby_trace.decision_space_coverage(tmp_path, 30)
    assert r["band"] == "n/a" and "SimpleCov started in the suite's spec_helper" in r["details"]
    assert "ruby 3.3.0" in r["details"]


def test_l19_na_when_no_runner_detected(monkeypatch, tmp_path):
    monkeypatch.setattr(ruby_trace, "_ruby", lambda: "/usr/bin/ruby")
    monkeypatch.setattr(ruby_trace, "_bundle", lambda: "/usr/bin/bundle")
    r = ruby_trace.decision_space_coverage(tmp_path, 30)
    assert r["band"] == "n/a" and "no RSpec" in r["details"]


def test_l19_bands_follow_the_spec(monkeypatch, tmp_path):
    _cover_run(monkeypatch, tmp_path, covered=95, total=100)
    assert ruby_trace.decision_space_coverage(tmp_path, 30)["band"] == "Healthy"
    _cover_run(monkeypatch, tmp_path, covered=40, total=100)
    assert ruby_trace.decision_space_coverage(tmp_path, 30)["band"] == "Slop"


# --- L1.20 randomized-order determinism --------------------------------------

def test_l20_all_green_is_healthy(monkeypatch, tmp_path):
    _det_run(monkeypatch, tmp_path, rc=0, summary="5 examples, 0 failures")
    r = ruby_trace.test_determinism(tmp_path, 5, 30)
    assert r["value"] == "5/5" and r["band"] == "Healthy" and "ruby 3.3.0" in r["details"]


def test_l20_na_when_nothing_ran(monkeypatch, tmp_path):
    # no summary line means the suite did not build or has no tests: n/a, not 0/5.
    _det_run(monkeypatch, tmp_path, rc=1, summary="Could not find gem 'rspec' in bundle")
    r = ruby_trace.test_determinism(tmp_path, 5, 30)
    assert r["band"] == "n/a" and "did not run" in r["details"] and "ruby 3.3.0" in r["details"]


def test_l20_surfaces_failing_seed_not_a_bare_score(monkeypatch, tmp_path):
    _det_run(monkeypatch, tmp_path, rc=1, summary="5 examples, 2 failures")
    r = ruby_trace.test_determinism(tmp_path, 5, 30)
    assert r["value"] == "0/5" and r["band"] == "Slop"
    assert "seed 1" in r["details"] and "2 failures" in r["details"]


def test_l20_na_when_no_runner_detected(monkeypatch, tmp_path):
    monkeypatch.setattr(ruby_trace, "_ruby", lambda: "/usr/bin/ruby")
    monkeypatch.setattr(ruby_trace, "_bundle", lambda: "/usr/bin/bundle")
    r = ruby_trace.test_determinism(tmp_path, 5, 30)
    assert r["band"] == "n/a" and "no RSpec" in r["details"]


# --- structural helpers -------------------------------------------------------

def test_detect_runner_prefers_rspec(tmp_path):
    (tmp_path / "spec").mkdir()
    (tmp_path / "test").mkdir()
    (tmp_path / "Rakefile").write_text("")
    assert ruby_trace._detect_runner(tmp_path) == "rspec"


def test_detect_runner_minitest_needs_test_dir_and_rakefile(tmp_path):
    (tmp_path / "test").mkdir()
    (tmp_path / "Rakefile").write_text("")
    assert ruby_trace._detect_runner(tmp_path) == "minitest"


def test_detect_runner_rspec_from_gemfile_lock(tmp_path):
    (tmp_path / "Gemfile.lock").write_text("    rspec (3.13.0)\n")
    assert ruby_trace._detect_runner(tmp_path) == "rspec"


def test_detect_runner_none_when_no_suite(tmp_path):
    assert ruby_trace._detect_runner(tmp_path) is None


def test_branch_totals_counts_covered_leaves():
    covered, total = ruby_trace._branch_totals(_branches(3, 5))
    assert covered == 3 and total == 5


def test_branch_totals_ignores_old_line_only_format():
    old = {"RSpec": {"coverage": {"/app/x.rb": [1, 0, None]}}}
    assert ruby_trace._branch_totals(old) == (0, 0)


# --- explicit-shim pinning ----------------------------------------------------

def test_pin_prepends_the_resolved_ruby_bin(monkeypatch, tmp_path):
    rbin = tmp_path / "rbenv" / "bin"
    rbin.mkdir(parents=True)
    (rbin / "ruby").write_text("")
    (rbin / "bundle").write_text("")
    monkeypatch.setattr(ruby_trace, "resolve_via_shim", lambda repo, tool, t: (str(rbin / "ruby"), "rbenv which ruby"))
    ruby, bundle, env, prov = ruby_trace._pin(tmp_path, 5)
    assert ruby == str(rbin / "ruby") and bundle == str(rbin / "bundle")
    assert env["PATH"].startswith(str(rbin)) and "rbenv which ruby" in prov


def test_pin_falls_back_to_ambient_without_a_manager(monkeypatch, tmp_path):
    monkeypatch.setattr(ruby_trace, "resolve_via_shim", lambda *a: (None, ""))
    monkeypatch.setattr(ruby_trace, "_ruby", lambda: "/usr/bin/ruby")
    monkeypatch.setattr(ruby_trace, "_bundle", lambda: "/usr/bin/bundle")
    assert ruby_trace._pin(tmp_path, 5) == ("/usr/bin/ruby", "/usr/bin/bundle", {}, "")
