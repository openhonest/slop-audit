"""Finite-testability conformance for JavaScript.

Same predicate as TypeScript, minus type annotations. Class fields are declared with
field_definition (property name, not the TS `name` field); everything else — member
access, `in`, subscript, augmented assignment, top-level `let` module state — matches.
"""

import pytest
from l1_analyzer import state_bounds

VECTORS = [
    {"id": "value-indexed-cache", "state": "this.store", "verdict": "promiscuous", "drives_decision": True,
     "src": (
        "class Cache {\n"
        "  store = {};\n"
        "  put(k, v) { this.store[k] = v; }\n"
        "  get(k) { if (k in this.store) { return this.store[k]; } return null; }\n"
        "}\n")},
    {"id": "multi-writer-capped-counter", "state": "this.count", "verdict": "neutral", "drives_decision": True,
     "src": (
        "class Limiter {\n"
        "  count = 0;\n"
        "  incr() { if (this.count < 3) { this.count += 1; } }\n"
        "  reset() { this.count = 0; }\n"
        "  allowed() { return this.count < 3; }\n"
        "}\n")},
    {"id": "observe-only-recorder", "state": "this.emitted", "verdict": "neutral", "drives_decision": False,
     "src": (
        "class Recorder {\n"
        "  emitted = [];\n"
        "  record(e) { this.emitted.push(e); }\n"
        "  dump() { return this.emitted; }\n"
        "}\n")},
    {"id": "returned-raw-value", "state": "this.data", "verdict": "neutral", "drives_decision": False,
     "src": (
        "class Store {\n"
        "  data = {};\n"
        "  load(d) { this.data = d; }\n"
        "  snapshot() { return this.data; }\n"
        "}\n")},
    {"id": "invoked-only-collaborator", "state": "this.handler", "verdict": "neutral", "drives_decision": False,
     "src": (
        "class Router {\n"
        "  handler = null;\n"
        "  constructor(h) { this.handler = h; }\n"
        "  route(r) { return this.handler(r); }\n"
        "}\n")},
    {"id": "module-global-in-branch", "state": "seen", "verdict": "promiscuous", "drives_decision": True,
     "src": (
        "let seen = {};\n"
        "function visit(k) { seen[k] = true; }\n"
        "function already(k) { return k in seen; }\n")},
]


def _classify(tmp_path, src):
    (tmp_path / "case.js").write_text(src)
    return state_bounds.classify(tmp_path, "javascript")


def _finding(result, state):
    return next((f for f in result["findings"] if f["state"] == state), None)


@pytest.mark.parametrize("case", VECTORS, ids=[c["id"] for c in VECTORS])
def test_js_conformance_vector(tmp_path, case):
    result = _classify(tmp_path, case["src"])
    f = _finding(result, case["state"])
    assert f is not None, f"state {case['state']!r} not surfaced"
    assert f["verdict"] == case["verdict"], f"{case['id']}: verdict"
    assert f["drives_decision"] == case["drives_decision"], f"{case['id']}: drives_decision"
