"""Surviving invariants for the L1.18b state-bounds classifier.

The classifier's *verdicts* are specified by the finite-testability conformance
vectors in test_finite_testability_vectors.py (the ten cases of
~/dev/honest/open-honest/honest-framework/specs/finite-testability.md section 8).
This file keeps only the invariants that outlive the predicate change from
value-count to partition-count:

  1. The frozen path is stable: with classify_state_bounds=False the output equals
     the golden, byte for byte.

     THIS DOCSTRING USED TO CLAIM MORE THAN THAT, and the claim was false. It said
     the golden was "captured before the classifier existed", which would make it
     the guarantee that on-by-default cannot move a pre-registered run. git says
     otherwise: py_repo.json has been re-captured in six commits (f9640b7,
     61f4090, 4c2e805, f89508a, c5a1b97, 4b3ffdf), five of them on 2026-08-15
     alongside the very changes it was supposed to detect. In f89508a the L1.18
     off-mode value moved from 83.3 to 50.0 in the same commit that changed the
     analyzer, so a behaviour change and an expectation change arrived together
     and the suite was green on both sides.

     A golden re-captured beside the change it is meant to detect detects nothing.
     What it does enforce is real but narrower: the off-mode output does not drift
     between re-captures, and it does not drift with the capturing machine, because
     PATH is emptied so no optional tool can move it. The hash below is what makes
     a re-capture visible: "the expectation moved" and "the behaviour moved" are
     now two different reds instead of one silence.
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
# The golden's own content, pinned. Without this a re-capture is invisible: the diff that
# would have shown a behaviour change is committed as the new expectation and nothing is red.
# Update it deliberately, in the same commit as the re-capture, with the reason in the message.
# Re-captured 2026-08-17 for one field only: L1.19 moved from 2 to 1. The fixture holds a
# single `if self.enabled:`, and the old shared node set matched both the if_statement and
# the unnamed `if` keyword token inside it, so every `if` counted twice. 1 is the number a
# reader gives. Nothing else in the golden moved.
_GOLDEN_SHA256 = "162ce98db057df588658a0a17c155780dbe1de99adb82d0cf2f94d3f79a0491d"

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
# Only L1.13 still shells out. L1.12 and L1.14 went native on 2026-08-15, so the golden
# legitimately records real bands for them; guarding them here would now assert that a
# working indicator is absent. L1.12 and L1.14 were listed while they depended on vulture
# and gitleaks, which is also how they reported Healthy on a repository holding live
# secrets: the tool exits non-zero WHEN IT FINDS SOMETHING, and that exit was swallowed.
OPTIONAL_TOOL_INDICATORS = ("L1.13",)


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


# ----------------------------------------------------------------------------
# Negated membership: the same predicate, spelled two ways.
# ----------------------------------------------------------------------------

_MEMBERSHIP_SRC = """\
store = {{}}

def lookup(key):
    if key {op} store:
        return None
    return store.get(key)
"""


def _membership_finding(tmp_path, op: str) -> dict:
    """The single L1.18b finding for `store`, guarding a membership test spelled `op`."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "app.py").write_text(_MEMBERSHIP_SRC.format(op=op))
    findings = state_bounds.classify(tmp_path, "python")["findings"]
    return next(f for f in findings if f["state"] == "store")


def test_negating_a_membership_test_does_not_change_the_verdict(tmp_path):
    """`key in store` and `key not in store` partition the state identically, so a
    classifier that grades them differently can be moved from F to A by one word.

    tree-sitter emits `not in` as a SINGLE token of type "not in", not as a `not`
    wrapping an `in`. Matching on `c.type == "in"` therefore missed the negated form
    entirely: it fell through membership, reached the comparison arm, and was called
    finite and ordered. That is the cheapest gaming hole this classifier has had, and
    it inverted a published grade."""
    plain = _membership_finding(tmp_path / "a", "in")
    negated = _membership_finding(tmp_path / "b", "not in")
    assert plain["verdict"] == negated["verdict"]
    assert plain["partition"] == negated["partition"]


def test_a_membership_partition_is_not_ordered(tmp_path):
    """Set membership has no ordering, so limit testing cannot exploit it. Claiming
    otherwise is what let the negated form read as two ordered classes."""
    for op in ("in", "not in"):
        finding = _membership_finding(tmp_path / op.replace(" ", "_"), op)
        assert finding["partition"]["ordered"] is False, op


def test_the_golden_itself_is_unchanged():
    """A re-capture must be a decision, not a side effect.

    The golden has been re-captured six times, five of them on one day beside the changes it
    existed to detect, and none of those re-captures was red anywhere. This is the guard that
    was missing: it fails when the file's bytes move, so re-capturing costs one deliberate
    edit here and cannot happen by accident.
    """
    import hashlib
    assert hashlib.sha256(GOLDEN.read_bytes()).hexdigest() == _GOLDEN_SHA256, (
        "the golden moved. If that is deliberate, update _GOLDEN_SHA256 in the same commit "
        "and say in the message what behaviour changed and why the expectation follows it.")


# --- the write side bounds the read side ------------------------------------
# A subscripted state can only ever hold the cells its WRITES create. The classifier
# judged each reference alone, so a read with an open key reported the state unbounded
# however narrow the set of cells actually was. `promiscuous` is defined as "reaching
# partition is provably unbounded (a proven finding)" and grades the repository F, so a
# two-key cache read back in a truthiness test was handed the instrument's most severe
# verdict on a false proof.

def _verdict_of(tmp_path, src, state):
    (tmp_path / "m.py").write_text(src)
    r = state_bounds.classify(tmp_path, "python")
    return next((f["verdict"] for f in r["findings"] if f["state"] == state), "absent")


_READ_BACK = "def get(k):\n    if CACHE.get(k):\n        return 1\n    return 0\n"


def test_a_cache_whose_writes_are_guarded_by_a_closed_set_is_bounded(tmp_path):
    """Two keys from a declared frozenset and a literal value. The read's key is open and
    stays open; it cannot observe a cell no write created."""
    src = ('KINDS = frozenset({"buy", "sell"})\nCACHE = {}\n'
           'def put(k):\n    if k in KINDS:\n        CACHE[k] = "open"\n' + _READ_BACK)
    assert _verdict_of(tmp_path, src, "CACHE") == "neutral"


def test_a_cache_written_under_literal_keys_alone_is_bounded(tmp_path):
    src = 'CACHE = {}\ndef put():\n    CACHE["buy"] = 1\n    CACHE["sell"] = 2\n' + _READ_BACK
    assert _verdict_of(tmp_path, src, "CACHE") == "neutral"


def test_one_unguarded_store_leaves_the_cache_promiscuous(tmp_path):
    """The bound is over EVERY write. One store with an open key and the cell set is
    unbounded again, whatever the other stores do."""
    src = ('KINDS = frozenset({"buy", "sell"})\nCACHE = {}\n'
           'def put(k):\n    if k in KINDS:\n        CACHE[k] = "open"\n'
           'def put_any(k, v):\n    CACHE[k] = v\n' + _READ_BACK)
    assert _verdict_of(tmp_path, src, "CACHE") == "promiscuous"


def test_a_store_guarded_by_a_set_that_is_not_declared_closed_stays_promiscuous(tmp_path):
    """`KINDS` here is a mutable list, so nothing bounds how many keys reach the store."""
    src = ('KINDS = ["buy", "sell"]\nCACHE = {}\n'
           'def put(k):\n    if k in KINDS:\n        CACHE[k] = "open"\n' + _READ_BACK)
    assert _verdict_of(tmp_path, src, "CACHE") == "promiscuous"


def test_a_keyed_read_reached_through_a_flowing_expression_carries_the_cell_bound(tmp_path):
    """The subscript row inside _flow, which no test reached. It referenced the cell bound
    without receiving it, so the first repository to take that path would have died with a
    NameError rather than returned a verdict. The state has to flow through something
    before being subscripted for the walk to arrive there, which `CACHE.copy()[k]` does and
    a plain `CACHE[k]` does not. Confirmed under a line trace: this input executes that row
    and my first attempt, `len(CACHE[k])`, did not."""
    src = ('KINDS = frozenset({"buy", "sell"})\nCACHE = {}\n'
           'def put(k):\n    if k in KINDS:\n        CACHE[k] = "open"\n'
           'def get(k):\n    if CACHE.copy()[k]:\n        return 1\n    return 0\n')
    assert _verdict_of(tmp_path, src, "CACHE") == "neutral"


def test_the_else_branch_of_a_membership_guard_bounds_nothing(tmp_path):
    """A store on the rejected side is reached by the keys the test threw out, which the
    declared set does not bound. Walking up from it must find no guard."""
    src = ('KINDS = frozenset({"buy", "sell"})\nCACHE = {}\n'
           'def put(k, v):\n    if k in KINDS:\n        pass\n    else:\n        CACHE[k] = v\n' + _READ_BACK)
    assert _verdict_of(tmp_path, src, "CACHE") == "promiscuous"
