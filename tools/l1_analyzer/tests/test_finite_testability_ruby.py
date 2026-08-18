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
