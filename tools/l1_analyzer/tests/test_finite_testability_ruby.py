"""Finite-testability conformance for Ruby.

State is instance variables (@store), a distinct node type with no receiver. Maps
read/write by method (@store.key?, @store.push) or by [] (element_reference); a
compound assignment is operator_assignment; invoking a stored callable is
@handler.call, which is dynamic dispatch. The verdict must not depend on any of that.
"""

import pytest
from l1_analyzer import state_bounds

VECTORS = [
    {"id": "value-indexed-cache", "state": "@store", "verdict": "promiscuous", "drives_decision": True,
     "src": (
        "class Cache\n"
        "  def initialize; @store = {}; end\n"
        "  def put(k, v); @store[k] = v; end\n"
        "  def get(k)\n"
        "    return @store[k] if @store.key?(k)\n"
        "    nil\n"
        "  end\n"
        "end\n")},
    {"id": "multi-writer-capped-counter", "state": "@count", "verdict": "neutral", "drives_decision": True,
     "src": (
        "class Limiter\n"
        "  def initialize; @count = 0; end\n"
        "  def incr; @count += 1 if @count < 3; end\n"
        "  def reset; @count = 0; end\n"
        "  def allowed; @count < 3; end\n"
        "end\n")},
    {"id": "observe-only-recorder", "state": "@emitted", "verdict": "neutral", "drives_decision": False,
     "src": (
        "class Recorder\n"
        "  def initialize; @emitted = []; end\n"
        "  def record(e); @emitted.push(e); end\n"
        "  def dump; @emitted; end\n"
        "end\n")},
    {"id": "returned-raw-value", "state": "@data", "verdict": "neutral", "drives_decision": False,
     "src": (
        "class Store\n"
        "  def initialize; @data = {}; end\n"
        "  def load(d); @data = d; end\n"
        "  def snapshot; @data; end\n"
        "end\n")},
    {"id": "single-writer-dynamic-dispatch", "state": "@handler", "verdict": "unresolved", "drives_decision": True,
     "src": (
        "class Router\n"
        "  def initialize(h); @handler = h; end\n"
        "  def route(r); @handler.call(r); end\n"
        "end\n")},
    # `@xs << x` is the idiomatic append and Ruby parses it as a `binary` node, not a call,
    # so the `<<` sitting in the mutating-method set could never match: only the rare
    # `@xs.<<(x)` spelling could. In a modifier arm the append reached no row at all and
    # came back as a construct nobody had written a rule for.
    {"id": "shovel-append-in-a-modifier", "state": "@seen", "verdict": "promiscuous", "drives_decision": True,
     "src": (
        "class Dedup\n"
        "  def initialize; @seen = []; end\n"
        "  def add(x)\n"
        "    @seen << x unless @seen.include?(x)\n"
        "  end\n"
        "end\n")},
    # The same append with nothing else touching the array: written and never read back.
    {"id": "shovel-append-only", "state": "@rows", "verdict": "neutral", "drives_decision": False,
     "src": (
        "class Log\n"
        "  def initialize; @rows = []; end\n"
        "  def add(x)\n"
        "    @rows << x if x\n"
        "  end\n"
        "end\n")},
]


def _classify(tmp_path, src):
    (tmp_path / "case.rb").write_text(src)
    return state_bounds.classify(tmp_path, "ruby")


def _finding(result, state):
    return next((f for f in result["findings"] if f["state"] == state), None)


@pytest.mark.parametrize("case", VECTORS, ids=[c["id"] for c in VECTORS])
def test_ruby_conformance_vector(tmp_path, case):
    result = _classify(tmp_path, case["src"])
    f = _finding(result, case["state"])
    assert f is not None, f"state {case['state']!r} not surfaced"
    assert f["verdict"] == case["verdict"], f"{case['id']}: verdict"
    assert f["drives_decision"] == case["drives_decision"], f"{case['id']}: drives_decision"


def _classify_verdict(d, src: str) -> str:
    """The verdict for the single ivar in a one-file Ruby repository."""
    from l1_analyzer import state_bounds
    d.mkdir(parents=True, exist_ok=True)
    (d / "c.rb").write_text(src)
    r = state_bounds.classify(d, "ruby")
    return next((f["verdict"] for f in r["findings"]), "absent")


# --- the conditional-assignment cache (slop-audit-l4h) --------------------------
#
# A FALSE GREEN, which is the one direction this project treats as worse than a miss. One
# cache written two ways got opposite verdicts: `@cache[k] ||= compute(k)` read neutral while
# `@cache[k] = compute(k) unless @cache.key?(k)` read promiscuous. The `||=` is both the read
# and the write, and only the write was seen, so the commonest memoization shape in the
# language was the one spelling that could not be caught.

_EXPLICIT = ("class C\n  def initialize\n    @cache = {}\n  end\n"
             "  def get(k)\n    @cache[k] = compute(k) unless @cache.key?(k)\n    @cache[k]\n  end\n"
             "  def compute(k)\n    k.to_s\n  end\nend\n")
_CONDITIONAL = ("class C\n  def initialize\n    @cache = {}\n  end\n"
                "  def get(k)\n    @cache[k] ||= compute(k)\n  end\n"
                "  def compute(k)\n    k.to_s\n  end\nend\n")


def test_a_conditional_assignment_cache_reads_the_same_as_the_explicit_one(tmp_path):
    """The two spellings are one operation and must reach one verdict.

    Asserted as an equality rather than against a literal, because the point is not which
    verdict either shape gets; it is that a reader cannot change the answer by changing the
    notation. Whatever the memoization rule decides, it must decide it for both.
    """
    assert _classify_verdict(tmp_path / "a", _CONDITIONAL) == _classify_verdict(tmp_path / "b", _EXPLICIT)


def test_a_conditional_assignment_cache_is_not_cleared_without_a_premise(tmp_path):
    # The explicit form is promiscuous and has to earn a clear through the memoization rule's
    # premises. The conditional form was handed neutral with no premise checked at all.
    assert _classify_verdict(tmp_path / "c", _CONDITIONAL) == "promiscuous"


def test_a_conditional_assignment_to_a_bare_name_is_a_two_class_truthiness_split(tmp_path):
    """`@n ||= k` reads the ivar, and what it reads it for is a truthiness test.

    Two classes, bounded, so neutral is the right answer and not a false green. This is the
    counterpart to the keyed case above and the reason that one is promiscuous: there, the
    unbounded thing is the KEY the cache is indexed by, not the conditional operator. Written
    down because the two shapes share an operator and reach opposite verdicts, which is
    exactly the kind of pair a reader will assume is a bug.

    Asserted after being measured. The first version of this test claimed the verdict must
    not be neutral, which was a guess about a value I had not run.
    """
    src = ("class C\n  def initialize\n    @n = nil\n  end\n"
           "  def get(k)\n    @n ||= k\n  end\nend\n")
    from l1_analyzer import state_bounds
    d = tmp_path / "d"
    d.mkdir(parents=True, exist_ok=True)
    (d / "c.rb").write_text(src)
    finding = next(iter(state_bounds.classify(d, "ruby")["findings"]))
    assert finding["verdict"] == "neutral"
    assert finding["partition"]["classes"] == 2 and finding["partition"]["counted"] is True
