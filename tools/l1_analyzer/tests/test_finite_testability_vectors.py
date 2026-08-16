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
        # The callee is selected by getattr from an OPEN name argument: the target set is
        # unbounded and single-writer + local do not rescue it (the HC-P018 construct).
        # It is the NAME that is open, not the fact that something is invoked - see
        # invoked-only-collaborator for the case this must not be confused with.
        "id": "single-writer-local-but-dynamic-dispatch",
        "state": "self._name",
        "verdict": "unresolved",
        "drives_decision": True,
        "src": (
            "class Router:\n"
            "    def __init__(self, name):\n"
            "        self._name = name\n"            # single writer, local
            "    def route(self, arg):\n"
            "        return getattr(self, self._name)(arg)\n"   # open name -> unbounded target set
        ),
    },
    {
        # Call-target position is compositional, exactly as return position is. self.app is
        # bound once and its only non-assignment use is as the target of a call whose result
        # is returned. No decision reads its VALUE to select an arm, so its reaching-set is
        # empty. What the collaborator does when it runs is the collaborator's own
        # finite-testability. The arguments passed THROUGH the call still reach an unbounded
        # target and stay unresolved in their own right - that is untouched.
        "id": "invoked-only-collaborator",
        "state": "self.app",
        "verdict": "neutral",
        "drives_decision": False,
        "src": (
            "class Middleware:\n"
            "    def __init__(self, app):\n"
            "        self.app = app\n"
            "    async def handle(self, scope, receive, send):\n"
            "        return await self.app(scope, receive, send)\n"
        ),
    },
    {
        # Closing the question rather than assuming it: a path from the state to a decision
        # DOES exist here, because the host branches on what the collaborator returned. The
        # meter follows the call result instead of fail-closing. The partition is the host's
        # own arm count - a collaborator whose answer takes one arm against one whose answer
        # takes the other - so two classes: neutral, but drives a decision.
        "id": "invoked-result-reaches-a-condition",
        "state": "self._check",
        "verdict": "neutral",
        "drives_decision": True,
        "src": (
            "class Guard:\n"
            "    def __init__(self, check):\n"
            "        self._check = check\n"
            "    def allow(self, req):\n"
            "        if self._check(req):\n"
            "            return 'ok'\n"
            "        return 'deny'\n"
        ),
    },
    {
        # Premise check 1. The invoked slot is assigned in more than one place, so which
        # callee is live at the call site depends on invisible history: runtime rebinding of
        # dispatch. Bound-once is what separates an injected collaborator from a rebindable
        # dispatch slot, so this stays fail-closed.
        "id": "rebound-call-target",
        "state": "self._h",
        "verdict": "unresolved",
        "drives_decision": True,
        "src": (
            "class Router:\n"
            "    def __init__(self, handler):\n"
            "        self._h = handler\n"
            "    def swap(self, handler):\n"
            "        self._h = handler\n"            # a second binding site
            "    def route(self, req):\n"
            "        return self._h(req)\n"
        ),
    },
    {
        # Premise check 2. The host writes THROUGH the slot, so the collaborator at the call
        # site is not provably the value that was injected, and the host now depends on the
        # collaborator's internal shape, which it cannot enumerate. Stays fail-closed.
        "id": "collaborator-mutated-through-the-slot",
        "state": "self._sink",
        "verdict": "unresolved",
        "drives_decision": True,
        "src": (
            "class Host:\n"
            "    def __init__(self, sink):\n"
            "        self._sink = sink\n"
            "    def configure(self):\n"
            "        self._sink.limit = 10\n"        # reaching in through the slot
            "    def run(self, req):\n"
            "        return self._sink(req)\n"
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
        # Regression: calling the RESULT of a method on state (a decorator / builder /
        # fluent chain, e.g. FastAPI's `app.get(path)(handler)` in call form) invokes
        # what the method returns, not the state. That is not the state being
        # dispatched, so it must not fail-close to UNRESOLVED.
        "id": "method-result-invoked-is-not-state-dispatch",
        "state": "self.registry",
        "verdict": "neutral",
        "drives_decision": False,
        "src": (
            "class Server:\n"
            "    def __init__(self):\n"
            "        self.registry = build()\n"
            "    def wire(self, handler):\n"
            "        self.registry.route('/x')(handler)\n"   # calls route()'s result, not self.registry
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
    {
        # A constant assigned once from an IMMUTABLE constructor (its return is a
        # MappingProxyType, seen by a one-level follow), never mutated, never called,
        # is a one-value domain: NEUTRAL even when passed to an unknown function,
        # because no callee can mutate an immutable value. Resolves declared state
        # machines on the evidence, reading no framework declaration.
        "id": "immutable-constant-passed-to-function",
        "state": "registry",
        "verdict": "neutral",
        "drives_decision": True,
        "src": (
            "from types import MappingProxyType\n"
            "def make(t):\n"
            "    return MappingProxyType(t)\n"
            "def lookup(table, k):\n"
            "    return table[k]\n"
            "registry = make({'a': 1, 'b': 2})\n"          # module constant from an immutable ctor
            "def get(k):\n"
            "    return lookup(registry, k)\n"              # passed to an unknown function, never mutated
        ),
    },
    {
        # The soundness guard: a MUTABLE value assigned once and passed to an unknown
        # callee stays UNRESOLVED. Single-assignment is not enough; the callee could
        # mutate a mutable dict, so the meter cannot certify it bounded.
        "id": "mutable-value-passed-to-unknown-callee",
        "state": "self.buf",
        "verdict": "unresolved",
        "drives_decision": True,
        "src": (
            "class Sink:\n"
            "    def __init__(self):\n"
            "        self.buf = {}\n"
            "    def run(self, sink):\n"
            "        sink(self.buf)\n"
        ),
    },
]


def _classify(tmp_path, src):
    (tmp_path / "case.py").write_text(src)
    return state_bounds.classify(tmp_path, "python")


def _finding(result, state):
    return next((f for f in result["findings"] if f["state"] == state), None)


@pytest.mark.parametrize("case", VECTORS, ids=[c["id"] for c in VECTORS])
def test_conformance_vector(tmp_path, case):
    result = _classify(tmp_path, case["src"])
    f = _finding(result, case["state"])
    assert f is not None, f"state {case['state']!r} not surfaced in findings"
    assert f["verdict"] == case["verdict"], f"{case['id']}: verdict"
    assert f["drives_decision"] == case["drives_decision"], f"{case['id']}: drives_decision"


# --- structural contract (spec sections 3 and 7) ----------------------------

# The three vectors the structural contract below is built from, named so that renaming a
# vector id breaks the selection loudly instead of silently returning a two-state repo.
_MIXED_IDS = ("raw-int-vs-constant", "value-indexed-cache", "pass-to-unknown-callee")


def _one_of_each(tmp_path):
    """A repo holding one neutral, one promiscuous, and one unresolved state."""
    src = "".join(
        next(c for c in VECTORS if c["id"] == wanted)["src"] + "\n\n"
        for wanted in _MIXED_IDS
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
