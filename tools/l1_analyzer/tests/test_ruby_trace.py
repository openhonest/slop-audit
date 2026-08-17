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
went unproved for as long as `decision_space_coverage` pinned the interpreter, ran the suite,
read the resultset and decided the band inside one function.
`_coverage_verdict(covered, total, returncode, version)` and `_determinism_verdict(per_seed,
runner, runs, version)` are now the decisions on their own, taking plain values and doing no
I/O, and the tests at the end of this file assert them as `f(input) == expected`.

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


# --- the L1.19 verdict, extracted so its band table can be asserted as a value -----------
#
# Written before `_coverage_verdict` exists, so every one of these was red on AttributeError
# rather than on a band. The deleted tests reached this table only through a fake that wrote
# the resultset the module then read back, so what they proved was that the module can parse a
# file the test had written moments earlier.

def test_a_finished_run_yields_the_covered_share():
    r = ruby_trace._coverage_verdict(38, 40, 0, "ruby 3.3.0")
    assert r["value"] == 95.0 and r["band"] == "Healthy"
    assert "38/40 SimpleCov branches exercised by tests" in r["details"]
    assert "suite passed" in r["details"] and "ruby 3.3.0" in r["details"]


def test_a_failing_but_valid_suite_is_still_measured():
    # A non-zero exit means the suite ran and some tests failed. The branches they took are
    # real, so this is a measurement, and the exit is named so the reader knows the shape.
    r = ruby_trace._coverage_verdict(7, 10, 1, "ruby 3.3.0")
    assert r["value"] == 70.0 and r["band"] == "Not Healthy"
    assert "suite exit 1" in r["details"]


@pytest.mark.parametrize("covered,total,band", [
    (100, 100, "Healthy"),
    (901, 1000, "Healthy"),
    (90, 100, "Not Healthy"),   # exactly 90 is not above 90
    (60, 100, "Not Healthy"),   # exactly 60 is the floor of the middle band
    (599, 1000, "Slop"),
    (0, 100, "Slop"),           # a measured zero: branches exist and none were taken
])
def test_the_coverage_bands_are_decided_at_the_exact_edges(covered, total, band):
    assert ruby_trace._coverage_verdict(covered, total, 0, "ruby 3.3.0")["band"] == band


def test_a_timed_out_run_is_named_rather_than_scored():
    # Decided before the counts are read, and the counts a killed run leaves are the same zeroes
    # a suite with no branch data leaves. The reason must name the timeout, not prescribe a
    # change to the helper the suite may already have made.
    r = ruby_trace._coverage_verdict(0, 0, 124, "ruby 3.3.0")
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert "timed out" in r["details"] and "enable_coverage" not in r["details"]


def test_no_branch_data_is_absent_not_zero_percent():
    r = ruby_trace._coverage_verdict(0, 0, 0, "ruby 3.3.0")
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert "enable_coverage :branch" in r["details"] and "ruby 3.3.0" in r["details"]


# --- the L1.20 verdict, extracted so the per-seed outcomes can be handed over as values ---

_CLEAN = (0, "Finished in 0.1 seconds\n5 examples, 0 failures\n")
_FAILED = (1, "Finished in 0.1 seconds\n5 examples, 2 failures\n")


def test_every_run_clean_is_the_full_score_and_healthy():
    r = ruby_trace._determinism_verdict([_CLEAN] * 5, "rspec", 5, "ruby 3.3.0")
    assert r["value"] == "5/5" and r["band"] == "Healthy"
    assert "5 of 5 randomized-order runs passed cleanly" in r["details"]
    assert "ruby 3.3.0" in r["details"]


def test_one_run_short_is_not_healthy_and_two_short_is_slop():
    one = ruby_trace._determinism_verdict([_CLEAN] * 4 + [_FAILED], "rspec", 5, "ruby 3.3.0")
    assert one["value"] == "4/5" and one["band"] == "Not Healthy"
    two = ruby_trace._determinism_verdict([_CLEAN] * 3 + [_FAILED] * 2, "rspec", 5, "ruby 3.3.0")
    assert two["value"] == "3/5" and two["band"] == "Slop"


def test_a_failing_seed_is_named_with_the_runners_own_summary_line():
    r = ruby_trace._determinism_verdict([_CLEAN, _CLEAN, _FAILED, _CLEAN, _CLEAN], "rspec", 5, "ruby 3.3.0")
    assert r["value"] == "4/5"
    assert "seed 3: 5 examples, 2 failures" in r["details"]


def test_at_most_three_failing_seeds_are_named():
    r = ruby_trace._determinism_verdict([_FAILED] * 5, "rspec", 5, "ruby 3.3.0")
    assert r["value"] == "0/5" and r["band"] == "Slop"
    assert r["details"].count("seed ") == 3


def test_a_seed_that_timed_out_stops_the_count_and_names_that_seed():
    r = ruby_trace._determinism_verdict([_CLEAN, _CLEAN, (124, "")], "rspec", 5, "ruby 3.3.0")
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert "seed 3" in r["details"] and "timed out" in r["details"]


def test_a_seed_in_which_no_test_executed_is_not_a_failing_run():
    # The not-run guard. A missing gem is a broken project, not a flaky one, and counting it as
    # a failing run reports it as non-determinism.
    r = ruby_trace._determinism_verdict([(1, "Could not find gem 'rspec' in bundle")], "rspec", 5, "ruby 3.3.0")
    assert r["band"] == "n/a" and "did not run" in r["details"]
    assert "seed 1" in r["details"] and "exit 1" in r["details"]
    assert "Could not find gem 'rspec' in bundle" in r["details"] and "ruby 3.3.0" in r["details"]


def test_no_runs_at_all_is_absent_not_a_clean_sweep():
    # Zero clean out of zero runs satisfies `passing == runs`, which is how a measure that ran
    # nothing issues itself a clean bill. It is the absence of a measurement.
    r = ruby_trace._determinism_verdict([], "rspec", 0, "ruby 3.3.0")
    assert r["band"] == "n/a" and r["value"] == "n/a"
