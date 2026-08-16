"""The Ruby runtime harness (L1.19 SimpleCov branch coverage, L1.20 randomized-order
determinism), tested at the points where it is a pure function of its input or a real
function of the real filesystem.

What this file used to contain, and why it does not: eight tests built on `_cover_run` and
`_det_run`, which replaced `_ruby`, `_bundle` and `_run_untrusted` so a fake wrote
`coverage/.resultset.json` and the module then read it back, and returned an RSpec summary
line the test author had typed. The assertion was that the module parses a file the test had
just written and echoes a string the test had just supplied. If RSpec changed its summary
wording or SimpleCov changed its resultset schema, all eight stayed green while the harness
broke in the field.

The claims they defended are real: the bands, the SimpleCov-not-started n/a with its exact
remedy, the nothing-ran guard, and per-seed failure surfacing instead of a bare score. They
are now proved by nothing, because `decision_space_coverage` pins the interpreter, runs the
suite, reads the resultset and decides the band inside one function. Extracting
`_determinism_verdict(per_seed, runner, runs, version)` and the matching coverage verdict is
filed as separate work.

This file is the least damaged of the four language harnesses, because `_branch_totals` and
`_detect_runner` were already extracted and already tested directly. Those tests are
untouched, and `_ran` and `_summary_line` — pure, and previously reached only through a fake
— are now asserted on their own terms.
"""

import shutil

import pytest
from l1_analyzer import ruby_trace

_NEEDS_RUBY = pytest.mark.skipif(
    shutil.which("ruby") is None or shutil.which("bundle") is None,
    reason="needs a real ruby and bundle on PATH; stubbed probes prove nothing")


def _branches(covered: int, total: int) -> dict:
    """A SimpleCov resultset whose single file has `covered` of `total` branch leaves hit.
    Real resultset layout, so `_branch_totals` walks it the way it walks SimpleCov's own."""
    subs = {f"[:then, {i}, 3, 4, 3, 10]": (1 if i < covered else 0) for i in range(total)}
    return {"RSpec": {"coverage": {"/app/x.rb": {"lines": [1], "branches": {"[:if, 0, 3, 4, 3, 20]": subs}}}}}


# --- SimpleCov branch totalling -----------------------------------------------

def test_branch_totals_counts_covered_leaves():
    covered, total = ruby_trace._branch_totals(_branches(3, 5))
    assert covered == 3 and total == 5


def test_branch_totals_ignores_old_line_only_format():
    old = {"RSpec": {"coverage": {"/app/x.rb": [1, 0, None]}}}
    assert ruby_trace._branch_totals(old) == (0, 0)


@pytest.mark.parametrize("covered,total", [(0, 10), (10, 10), (0, 0)])
def test_branch_totals_at_the_edges(covered, total):
    assert ruby_trace._branch_totals(_branches(covered, total)) == (covered, total)


# --- runner detection, against a real filesystem ------------------------------

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


# --- the not-run guard and the failure line, both pure ------------------------

def test_ran_counts_the_tests_the_runner_reported():
    assert ruby_trace._ran("rspec", "5 examples, 0 failures") == 5
    assert ruby_trace._ran("rspec", "Could not find gem 'rspec' in bundle") == 0


def test_summary_line_names_the_failure():
    assert ruby_trace._summary_line("rspec", "...\n5 examples, 2 failures\n") == "5 examples, 2 failures"


def test_summary_line_falls_back_to_the_first_line_when_nothing_ran():
    # This is what turns a bare 0/5 into a reason a reader can act on.
    out = "Could not find gem 'rspec' in bundle\nRun `bundle install`"
    assert ruby_trace._summary_line("rspec", out) == "Could not find gem 'rspec' in bundle"


# --- interpreter pinning, against a real environment --------------------------

def test_pin_falls_back_to_the_ambient_runtime_without_a_manager(monkeypatch, tmp_path):
    # An empty PATH is a real machine state: shutil.which finds no shim manager, so
    # resolve_via_shim genuinely declines and _pin genuinely takes its ambient branch. It also
    # finds no ruby and no bundle, which is the honest answer on such a machine.
    monkeypatch.setenv("PATH", "")
    assert ruby_trace._pin(tmp_path, 5) == (None, None, {}, "")


# --- the refusals reachable without faking anything ---------------------------

def test_l19_na_without_ruby(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", "")
    assert ruby_trace.decision_space_coverage(tmp_path, 30)["band"] == "n/a"


def test_l20_na_without_ruby(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", "")
    assert ruby_trace.test_determinism(tmp_path, 5, 30)["band"] == "n/a"


@_NEEDS_RUBY
def test_l19_na_when_no_runner_detected(tmp_path):
    r = ruby_trace.decision_space_coverage(tmp_path, 30)
    assert r["band"] == "n/a" and "no RSpec" in r["details"]


@_NEEDS_RUBY
def test_l20_na_when_no_runner_detected(tmp_path):
    r = ruby_trace.test_determinism(tmp_path, 5, 30)
    assert r["band"] == "n/a" and "no RSpec" in r["details"]
