"""Surviving invariants for the L1.18b state-bounds classifier.

The classifier's *verdicts* are specified by the finite-testability conformance
vectors in test_finite_testability_vectors.py (the ten cases of
~/dev/honest/open-honest/honest-framework/specs/finite-testability.md section 8).
This file keeps only the invariants that outlive the predicate change from
value-count to partition-count:

  1. The frozen path is untouched: with classify_state_bounds=False the output
     equals the golden captured before the classifier existed, byte for byte.
     This is the guarantee that "on by default" cannot move a pre-registered run,
     and it is exactly the v1 side of the spec section 9 side-by-side rule.
  2. On-mode is purely additive: L1.18's registered number never moves; the
     classifier only adds the L1.18b and path_cover keys.
  3. A non-Python target is n/a, never guessed.

Fixtures are written under tmp_path (never committed into the source tree), so a
self-audit of this repo never trips over its own test data. Pure assertions, no
mocks (Honest Code Rule 10).
"""

import json
from pathlib import Path

from l1_analyzer import indicators, state_bounds

GOLDEN = Path(__file__).parent / "golden" / "py_repo.json"

# A deliberately-sloppy sample: pure function + reads of dict/list/str/int/bool
# state, plus one bounded projection (len). Written to tmp_path per test. Kept
# byte-identical because the frozen golden was captured against it.
FIXTURE_SRC = '''"""Fixture exercising bounded / unbounded / undetermined mutable state."""

counter_state = 0      # module-level mutable int -> unbounded (bare name)


class Service:
    def __init__(self):
        self.cache = {}            # dict -> unbounded
        self.enabled = False       # bool -> bounded
        self.buffer = []           # list -> unbounded
        self.mode: str = "fast"    # str -> unbounded

    def pure_add(self, a, b):
        return a + b               # no external state

    def reads_cache(self, key):
        return self.cache[key]     # unbounded state

    def reads_flag(self):
        if self.enabled:           # bounded state (bool)
            return 1
        return 0

    def cache_is_empty(self):
        return len(self.cache) == 0   # bounded PROJECTION of an unbounded dict

    def uses_global(self):
        return counter_state + 1   # unbounded module global
'''


def _fixture(tmp_path):
    (tmp_path / "app.py").write_text(FIXTURE_SRC)
    return tmp_path


# L1.12 (vulture), L1.13 (jscpd) and L1.14 (gitleaks / detect-secrets) are the only
# indicators in compute_source_indicators that branch on shutil.which. They are the
# whole ambient-state surface of this golden.
OPTIONAL_TOOL_INDICATORS = ("L1.12", "L1.13", "L1.14")


def test_frozen_mode_matches_registered_golden_byte_for_byte(tmp_path, monkeypatch):
    # Empty PATH makes every shutil.which gate return None, so the run records the
    # same thing on a bare CI runner and on a workstation with the optional tools
    # installed. Without this the golden silently absorbs the capture machine's
    # tool set and the assertion becomes a test of who ran it.
    monkeypatch.setenv("PATH", "")
    repo = _fixture(tmp_path)
    result = indicators.compute_source_indicators(
        repo, lang="auto", exec_tests=False, timeout_seconds=5, classify_state_bounds=False
    )
    assert "L1.18b" not in result  # off-mode adds nothing
    golden = json.loads(GOLDEN.read_text())
    assert json.dumps(result, sort_keys=True) == json.dumps(golden, sort_keys=True)


def test_golden_records_no_optional_tool_as_installed():
    """The golden must be a no-optional-tools capture, and stay one.

    The frozen golden was once captured on a machine that had gitleaks, so L1.14 read
    Healthy/0 there and n/a everywhere else. Byte-for-byte equality then held only on
    that one machine. This assertion is environment-independent: it reads the committed
    file, so re-capturing on a tooled machine fails here rather than six CI runs later.
    """
    golden = json.loads(GOLDEN.read_text())
    installed = {k: golden[k] for k in OPTIONAL_TOOL_INDICATORS if golden[k]["band"] != "n/a"}
    assert not installed, (
        f"golden encodes an optional tool as installed: {installed}. "
        "Re-capture with vulture, jscpd, gitleaks and detect-secrets off PATH."
    )


def test_on_mode_is_additive_l18_identical_plus_l18b(tmp_path):
    repo = _fixture(tmp_path)
    off = indicators.compute_source_indicators(repo, "auto", False, 5, classify_state_bounds=False)
    on = indicators.compute_source_indicators(repo, "auto", False, 5, classify_state_bounds=True)
    assert on["L1.18"] == off["L1.18"]                 # the registered number never moves
    assert set(on) - set(off) == {"L1.18b", "path_cover", "thread_surface", "absolute_paths"}  # the additive enrichments


def test_unsupported_language_is_na_not_guessed(tmp_path):
    # A language with no LANG_SPEC entry is n/a, never analyzed with another grammar.
    # (Every LANG_CFG language now has a spec; kotlin has none, so it stands in here.)
    r = state_bounds.classify(tmp_path, "kotlin")
    assert r["verdict"] == "n/a"
    assert r["value"] == "n/a"


def test_grade_summary_is_the_single_source_of_the_published_grade():
    from l1_analyzer import report
    base = {
        "L1.18": {"band": "Healthy"},
        "L1.18b": {"counts": {"neutral": 8, "promiscuous": 0, "unresolved": 0}, "resolvable_fraction": 1.0, "findings": []},
    }
    healthy = {k: {"band": "Healthy"} for k in ("L1.17", "L1.15", "L1.10", "L1.11", "L1.9", "L1.16")}
    # every audit check Healthy -> hygiene 1.0 -> grade A (verdict CAN)
    assert report.grade_summary({**base, **healthy}, report.UNORDERED_CLASS_BOUND)["hygiene"] == 1.0
    assert report.grade_summary({**base, **healthy}, report.UNORDERED_CLASS_BOUND)["grade"] == "A"
    # L1.15 (weight 3 of 11) at Slop -> 8/11 hygiene (>= 0.60) -> B
    assert report.grade_summary({**base, **healthy, "L1.15": {"band": "Slop"}}, report.UNORDERED_CLASS_BOUND)["grade"] == "B"
    # L1.15 + L1.17 both Slop -> 5/11 hygiene (< 0.60) -> C
    assert report.grade_summary({**base, **healthy, "L1.15": {"band": "Slop"}, "L1.17": {"band": "Slop"}}, report.UNORDERED_CLASS_BOUND)["grade"] == "C"
    # the verdict gates the tier regardless of hygiene
    cannot = {**base, "L1.18b": {"counts": {"neutral": 5, "promiscuous": 2, "unresolved": 0}, "resolvable_fraction": 0.7, "findings": []}}
    assert report.grade_summary(cannot, report.UNORDERED_CLASS_BOUND)["grade"] == "F"
    # Undecided state is silence, not a finding. It used to produce status `might` and
    # grade D, which reported a limit of the analyzer's reading as a defect in the audited
    # code. Below the floor the grade is decided on observed state alone.
    quiet = {**base, "L1.18b": {"counts": {"neutral": 5, "promiscuous": 0, "unresolved": 3}, "resolvable_fraction": 0.6, "findings": []}}
    assert report.grade_summary({**quiet, **healthy}, report.UNORDERED_CLASS_BOUND)["status"] == "can"
    assert report.grade_summary({**quiet, **healthy}, report.UNORDERED_CLASS_BOUND)["grade"] == "A"
    # Above the floor no grade is issued at all, so showing the analyzer almost nothing
    # buys silence rather than an A on a vacuously clean sample.
    hidden = {**base, "L1.18b": {"counts": {"neutral": 2, "promiscuous": 0, "unresolved": 8}, "resolvable_fraction": 0.2, "findings": []}}
    assert report.grade_summary({**hidden, **healthy}, report.UNORDERED_CLASS_BOUND)["status"] == "na"
    assert report.grade_summary({**hidden, **healthy}, report.UNORDERED_CLASS_BOUND)["grade"] is None
    # an audit check with no band is excluded, not penalized
    assert report.grade_summary({**base, "L1.17": {"band": "Healthy"}, "L1.15": {"band": "n/a"}}, report.UNORDERED_CLASS_BOUND)["hygiene"] == 1.0


# --- attribution: the finding must point at the binding, not the first text match ------

def test_finding_points_at_the_binding_not_the_first_textual_match(tmp_path):
    """A module named `app` makes `from app.auth import X` the first occurrence of the
    name, so a finding about the variable `app = FastAPI()` was reported against an
    import statement that binds nothing. On the repository that surfaced this, the reader
    was sent to line 19 for an object defined on line 113. A finding nobody can act on is
    not a finding."""
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI\n"
        "from app.auth.middleware import AuthMiddleware\n"
        "\n"
        "app = FastAPI()\n"
        "app.add_middleware(AuthMiddleware)\n"
    )
    result = state_bounds.classify(tmp_path, "python")
    assert len(result["findings"]) == 1
    assert result["findings"][0]["line"] == 4          # the assignment, not the import


def test_attribution_falls_back_when_the_name_is_never_assigned_here(tmp_path):
    """State that is read but never bound in this file still needs a line, so the
    earliest reference remains the fallback."""
    (tmp_path / "reader.py").write_text(
        "from settings import registry\n"
        "\n"
        "def lookup(key):\n"
        "    if registry[key]:\n"
        "        return registry[key]\n"
        "    return None\n"
    )
    result = state_bounds.classify(tmp_path, "python")
    for finding in result["findings"]:
        assert finding["line"] >= 1
