"""Tests for the gated L1.18b state-bounds classifier.

Two jobs:
  1. Prove the frozen path is untouched: with classify_state_bounds=False the
     output equals the golden captured before the classifier existed, byte for
     byte. This is the guarantee that "on by default" cannot compromise a
     pre-registered run.
  2. Exercise the classifier: bounded vs unbounded vs undetermined, the
     observed-projection downgrade, and the per-function findings. Pure
     assertions, no mocks.

Fixtures are written under tmp_path (never committed into the source tree), so a
self-audit of this repo never trips over its own test data.
"""

import json
from pathlib import Path

from l1_analyzer import indicators, state_bounds

GOLDEN = Path(__file__).parent / "golden" / "py_repo.json"

# A deliberately-sloppy sample: pure function + reads of dict/list/str/int/bool
# state, plus one bounded projection (len). Written to tmp_path per test.
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


def test_fixture_breakdown_is_three_unbounded_two_bounded(tmp_path):
    # __init__, reads_cache, uses_global -> unbounded; reads_flag, cache_is_empty -> bounded.
    result = state_bounds.classify(_fixture(tmp_path), "python")
    assert result["verdict"] == "infinite"
    assert result["unbounded_funcs"] == 3
    assert result["bounded_funcs"] == 2
    assert result["undetermined_funcs"] == 0


def test_findings_name_the_function_and_the_culprit_state(tmp_path):
    result = state_bounds.classify(_fixture(tmp_path), "python")
    by_func = {f["function"]: f for f in result["findings"]}
    assert by_func["reads_cache"]["verdict"] == "unbounded"
    assert by_func["reads_cache"]["state"] == ["self.cache"]
    assert by_func["reads_cache"]["file"] == "app.py"
    assert by_func["reads_cache"]["line"] > 0
    # Findings are ordered most-actionable first.
    assert result["findings"][0]["verdict"] == "unbounded"


def _classify_src(tmp_path, src):
    (tmp_path / "m.py").write_text(src)
    return state_bounds.classify(tmp_path, "python")


def test_dict_state_read_in_full_is_unbounded(tmp_path):
    src = "class S:\n    def __init__(self):\n        self.cache = {}\n    def get(self, k):\n        return self.cache[k]\n"
    r = _classify_src(tmp_path, src)
    assert r["unbounded_funcs"] >= 1
    assert r["verdict"] == "infinite"


def test_bool_state_is_bounded(tmp_path):
    src = "class S:\n    def __init__(self):\n        self.on = False\n    def check(self):\n        return 1 if self.on else 0\n"
    r = _classify_src(tmp_path, src)
    assert r["bounded_funcs"] >= 1
    assert r["unbounded_funcs"] == 0
    assert r["verdict"] == "finite"


def test_len_is_a_bounded_projection_of_an_unbounded_dict(tmp_path):
    src = "class S:\n    def __init__(self):\n        self.cache = {}\n    def empty(self):\n        return len(self.cache) == 0\n"
    r = _classify_src(tmp_path, src)
    # __init__ writes the dict (unbounded); empty() only reads len() (bounded).
    assert r["bounded_funcs"] >= 1


def test_unknown_assignment_is_undetermined(tmp_path):
    src = "class S:\n    def __init__(self):\n        self.thing = make_thing()\n    def use(self):\n        return self.thing.run()\n"
    r = _classify_src(tmp_path, src)
    assert r["undetermined_funcs"] >= 1
    assert r["unbounded_funcs"] == 0


def test_non_python_is_na_not_guessed(tmp_path):
    r = state_bounds.classify(tmp_path, "go")
    assert r["verdict"] == "n/a"
    assert r["value"] == "n/a"
