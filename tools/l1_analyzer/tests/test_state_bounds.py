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


def test_frozen_mode_matches_registered_golden_byte_for_byte(tmp_path):
    repo = _fixture(tmp_path)
    result = indicators.compute_source_indicators(
        repo, lang="auto", exec_tests=False, timeout_seconds=5, classify_state_bounds=False
    )
    assert "L1.18b" not in result  # off-mode adds nothing
    golden = json.loads(GOLDEN.read_text())
    assert json.dumps(result, sort_keys=True) == json.dumps(golden, sort_keys=True)


def test_on_mode_is_additive_l18_identical_plus_l18b(tmp_path):
    repo = _fixture(tmp_path)
    off = indicators.compute_source_indicators(repo, "auto", False, 5, classify_state_bounds=False)
    on = indicators.compute_source_indicators(repo, "auto", False, 5, classify_state_bounds=True)
    assert on["L1.18"] == off["L1.18"]                 # the registered number never moves
    assert set(on) - set(off) == {"L1.18b", "path_cover"}  # the additive enrichments


def test_unsupported_language_is_na_not_guessed(tmp_path):
    # A language with no LANG_SPEC entry is n/a, never analyzed with another grammar.
    # (Every LANG_CFG language now has a spec; kotlin has none, so it stands in here.)
    r = state_bounds.classify(tmp_path, "kotlin")
    assert r["verdict"] == "n/a"
    assert r["value"] == "n/a"
