"""Finite-testability conformance: the target contract for L1.18b.

These tests encode the shared, tool-neutral definition of finite-testability that
the Slop Audit meter must satisfy by measurement:

    ~/dev/honest/open-honest/honest-framework/specs/finite-testability.md
    (vendored meter-side at
     ~/dev/honest/adamzwasserman/registrations/FINITE-TESTABILITY-SPEC.md)

The predicate is PARTITION-COUNT, not value-count: state is testability-neutral
iff the production decisions reaching it partition its domain into a
statically-enumerable finite set of equivalence classes. An int that only meets
comparisons against constants is cheap; a value used as an unbounded lookup key
is not.

Every state resolves to exactly one of three verdicts:

    NEUTRAL     - reaching partition is a statically-enumerable finite set (or empty)
    PROMISCUOUS - reaching partition is *provably* unbounded (a proven finding)
    UNRESOLVED  - reaching-set undecidable within scope; fail-closed, disclosed

and to whether it drives-a-decision, so the meter can publish the two-dimensional
coverage matrix (spec section 7) whose UNRESOLVED-and-drives-a-decision cell is
the headline blind spot.

This is the live conformance suite for state_bounds.classify: it implements the
partition-count predicate (class/module scope, three verdicts, returns-are-output,
fail-close on unknown callee and dynamic dispatch). When the framework ships
finite-testability-vectors.json, the VECTORS table below is replaced by a load from
it; the case ids already match spec section 8.

Contract under test (state_bounds.classify(repo, "python") returns):
  - verdict: repo rollup, worst-first ("promiscuous" | "unresolved" | "neutral" | "n/a")
  - counts:  {"neutral": int, "promiscuous": int, "unresolved": int}
  - coverage: {verdict: {"observe_only": int, "drives_decision": int}} for all three verdicts
  - findings: one entry PER PIECE OF STATE (class/module scope), each with
        {"state": str, "verdict": str, "drives_decision": bool, "file": str, "line": int}
"""

import pytest
from l1_analyzer import state_bounds

# --- the ten locked conformance vectors (spec section 8) --------------------
# Each: the case id, a minimal Python source, the culprit state key, and the
# (verdict, drives_decision) the meter must report for that state.

VECTORS = [
    {
        "id": "observe-only-recorder",
        "state": "self.emitted",
        "verdict": "neutral",
        "drives_decision": False,
        "src": (
            "class Recorder:\n"
            "    def __init__(self):\n"
            "        self.emitted = []\n"
            "    def record(self, event):\n"
            "        self.emitted.append(event)\n"   # written only
            "    def dump(self):\n"
            "        return self.emitted\n"          # returned = output, not a decision
        ),
    },
    {
        "id": "value-indexed-cache",
        "state": "self.store",
        "verdict": "promiscuous",
        "drives_decision": True,
        "src": (
            "class Cache:\n"
            "    def __init__(self):\n"
            "        self.store = {}\n"
            "    def put(self, key, val):\n"
            "        self.store[key] = val\n"
            "    def get(self, key):\n"
            "        if key in self.store:\n"        # membership over an unbounded key domain
            "            return self.store[key]\n"
            "        return None\n"
        ),
    },
    {
        "id": "multi-writer-capped-counter",
        "state": "self.count",
        "verdict": "neutral",
        "drives_decision": True,
        "src": (
            "class Limiter:\n"
            "    def __init__(self):\n"
            "        self.count = 0\n"
            "    def incr(self):\n"
            "        if self.count < 3:\n"           # compared only against a constant -> 2 classes
            "            self.count += 1\n"
            "    def reset(self):\n"
            "        self.count = 0\n"               # a second writer; domain still {0..3}
            "    def allowed(self):\n"
            "        return self.count < 3\n"
        ),
    },
    {
        "id": "raw-int-vs-constant",
        "state": "self.level",
        "verdict": "neutral",
        "drives_decision": True,
        "src": (
            "class Threshold:\n"
            "    def __init__(self):\n"
            "        self.level = 0\n"
            "    def set(self, x):\n"
            "        self.level = x\n"
            "    def tier(self):\n"
            "        if self.level >= 10:\n"         # partition = comparison count + 1
            "            return 'high'\n"
            "        return 'low'\n"
        ),
    },
    {
        "id": "single-writer-local-but-dynamic-dispatch",
        "state": "self.handler",
        "verdict": "unresolved",
        "drives_decision": True,
        "src": (
            "class Router:\n"
            "    def __init__(self, handler):\n"
            "        self.handler = handler\n"       # single writer, local
            "    def route(self, req):\n"
            "        return self.handler(req)\n"     # callee set unbounded -> undecidable
        ),
    },
    {
        "id": "returned-raw-value",
        "state": "self.data",
        "verdict": "neutral",
        "drives_decision": False,
        "src": (
            "class Store:\n"
            "    def __init__(self):\n"
            "        self.data = {}\n"
            "    def load(self, d):\n"
            "        self.data = d\n"
            "    def snapshot(self):\n"
            "        return self.data\n"             # returned only -> the caller's concern
        ),
    },
    {
        "id": "module-global-in-branch",
        "state": "_seen",
        "verdict": "promiscuous",
        "drives_decision": True,
        "src": (
            "_seen = {}\n"
            "def visit(key):\n"
            "    _seen[key] = True\n"                # shared write
            "def already(key):\n"
            "    if key in _seen:\n"                 # into an unbounded-key decision
            "        return True\n"
            "    return False\n"
        ),
    },
    {
        "id": "pass-to-unknown-callee",
        "state": "self.value",
        "verdict": "unresolved",
        "drives_decision": True,
        "src": (
            "class Pipe:\n"
            "    def __init__(self):\n"
            "        self.value = 0\n"
            "    def set(self, v):\n"
            "        self.value = v\n"
            "    def run(self, sink):\n"
            "        sink(self.value)\n"             # passed to an unknown callee (the HC-P018 construct)
        ),
    },
    {
        "id": "closed-set-dispatch",
        "state": "self.mode",
        "verdict": "neutral",
        "drives_decision": True,
        "src": (
            "class Dispatcher:\n"
            "    MODES = frozenset({'fast', 'slow', 'auto'})\n"
            "    def __init__(self):\n"
            "        self.mode = 'fast'\n"
            "    def set(self, m):\n"
            "        self.mode = m\n"
            "    def handle(self):\n"
            "        if self.mode in self.MODES:\n"  # dispatch over a declared closed set
            "            return self.mode\n"
            "        return 'default'\n"
        ),
    },
    {
        "id": "bounded-enum-accumulator-driving-branch",
        "state": "self.level",
        "verdict": "neutral",
        "drives_decision": True,
        "src": (
            "from enum import Enum\n"
            "class Level(Enum):\n"
            "    LOW = 1\n"
            "    MED = 2\n"
            "    HIGH = 3\n"
            "class Escalator:\n"
            "    def __init__(self):\n"
            "        self.level = Level.LOW\n"
            "    def raise_to(self, new):\n"
            "        if new.value > self.level.value:\n"   # bounded enum drives a branch
            "            self.level = new\n"
        ),
    },
    {
        # The dual of closed-set-dispatch: the STATE is the closed set, and an
        # unbounded value is tested for membership in it. The partition is the
        # fixed finite set, so it is NEUTRAL, not promiscuous. Regression for the
        # honest-framework false positive on `FIXABLE_RULES = frozenset()`.
        "id": "closed-set-membership",
        "state": "allowed",
        "verdict": "neutral",
        "drives_decision": True,
        "src": (
            "allowed = frozenset({'a', 'b', 'c'})\n"
            "def check(x):\n"
            "    if x in allowed:\n"                        # x unbounded, but `allowed` is a closed set
            "        return True\n"
            "    return False\n"
        ),
    },
    {
        # A constant tuple of SYMBOLIC constants (not literals) is still a fixed,
        # finite collection: membership against it is a finite partition. Regression
        # for the requests false positive on `status_code in REDIRECT_STATI`, where
        # REDIRECT_STATI = (codes.moved, ...) is a Final tuple of named constants.
        "id": "symbolic-constant-membership",
        "state": "self.status_code",
        "verdict": "neutral",
        "drives_decision": True,
        "src": (
            "MOVED = 301\n"
            "FOUND = 302\n"
            "REDIRECT_STATI = (MOVED, FOUND)\n"             # tuple of symbolic constants, not literals
            "class Response:\n"
            "    def __init__(self):\n"
            "        self.status_code = 0\n"
            "    def set(self, code):\n"
            "        self.status_code = code\n"
            "    def is_redirect(self):\n"
            "        return self.status_code in REDIRECT_STATI\n"
        ),
    },
]


def _classify(tmp_path, src):
    (tmp_path / "case.py").write_text(src)
    return state_bounds.classify(tmp_path, "python")


def _finding(result, state):
    return next((f for f in result.get("findings", []) if f.get("state") == state), None)


@pytest.mark.parametrize("case", VECTORS, ids=[c["id"] for c in VECTORS])
def test_conformance_vector(tmp_path, case):
    result = _classify(tmp_path, case["src"])
    f = _finding(result, case["state"])
    assert f is not None, f"state {case['state']!r} not surfaced in findings"
    assert f["verdict"] == case["verdict"], f"{case['id']}: verdict"
    assert f["drives_decision"] == case["drives_decision"], f"{case['id']}: drives_decision"


# --- structural contract (spec sections 3 and 7) ----------------------------

def _one_of_each(tmp_path):
    """A repo holding one neutral, one promiscuous, and one unresolved state."""
    src = "".join(
        c["src"] + "\n\n"
        for c in VECTORS
        if c["id"] in ("raw-int-vs-constant", "value-indexed-cache", "pass-to-unknown-callee")
    )
    (tmp_path / "mixed.py").write_text(src)
    return state_bounds.classify(tmp_path, "python")


def test_verdict_vocabulary_is_three_valued(tmp_path):
    r = _one_of_each(tmp_path)
    assert set(r["counts"]) == {"neutral", "promiscuous", "unresolved"}
    assert r["counts"]["promiscuous"] >= 1
    assert r["counts"]["unresolved"] >= 1
    assert r["counts"]["neutral"] >= 1


def test_coverage_matrix_is_two_dimensional_and_decomposed(tmp_path):
    # Mandatory, decomposable, never a bare scalar (spec section 7).
    r = _one_of_each(tmp_path)
    cov = r["coverage"]
    assert set(cov) == {"neutral", "promiscuous", "unresolved"}
    for verdict in cov:
        assert set(cov[verdict]) == {"observe_only", "drives_decision"}


def test_headline_blind_spot_is_unresolved_and_drives_a_decision(tmp_path):
    # pass-to-unknown-callee is UNRESOLVED and drives a decision: the cell where the
    # score is both a lower bound and consequential (spec section 7).
    r = _one_of_each(tmp_path)
    assert r["coverage"]["unresolved"]["drives_decision"] >= 1


def test_analysis_scope_is_the_class_not_the_function(tmp_path):
    # The capped counter is written by two methods and read by a third, but it is
    # ONE piece of state. Class/module scope means one finding, not three.
    counter = next(c for c in VECTORS if c["id"] == "multi-writer-capped-counter")
    r = _classify(tmp_path, counter["src"])
    count_findings = [f for f in r["findings"] if f["state"] == "self.count"]
    assert len(count_findings) == 1


def test_returns_are_output_not_promiscuity(tmp_path):
    # A dict that is only ever returned is NEUTRAL: covering the returned domain
    # is the caller's concern (spec section 4). Value-count would call it unbounded.
    returned = next(c for c in VECTORS if c["id"] == "returned-raw-value")
    r = _classify(tmp_path, returned["src"])
    f = _finding(r, "self.data")
    assert f is not None and f["verdict"] == "neutral"
