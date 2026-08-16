"""Finite-testability conformance for TypeScript.

The same partition-count predicate as the Python suite, expressed in TypeScript:
instance state is a class field read/written through `this`, membership is `k in S`
(a binary expression), a dict is indexed `S[k]`, dynamic dispatch is `this.f(x)`.
The verdict a state resolves to must not depend on the surface language.

Red first: `classify(repo, "typescript")` returns n/a until the TypeScript spec
lands, so every case here fails until the classifier is language-parameterized.
"""

import pytest
from l1_analyzer import state_bounds

VECTORS = [
    {
        "id": "value-indexed-cache",
        "state": "this.store",
        "verdict": "promiscuous",
        "drives_decision": True,
        "src": (
            "class Cache {\n"
            "  store: Record<string, number> = {};\n"
            "  put(k: string, v: number) { this.store[k] = v; }\n"
            "  get(k: string) {\n"
            "    if (k in this.store) { return this.store[k]; }\n"   # unbounded key membership
            "    return null;\n"
            "  }\n"
            "}\n"
        ),
    },
    {
        "id": "multi-writer-capped-counter",
        "state": "this.count",
        "verdict": "neutral",
        "drives_decision": True,
        "src": (
            "class Limiter {\n"
            "  count = 0;\n"
            "  incr() { if (this.count < 3) { this.count += 1; } }\n"   # compared to a constant
            "  reset() { this.count = 0; }\n"
            "  allowed() { return this.count < 3; }\n"
            "}\n"
        ),
    },
    {
        "id": "observe-only-recorder",
        "state": "this.emitted",
        "verdict": "neutral",
        "drives_decision": False,
        "src": (
            "class Recorder {\n"
            "  emitted: string[] = [];\n"
            "  record(e: string) { this.emitted.push(e); }\n"          # written only
            "  dump() { return this.emitted; }\n"                      # returned = output
            "}\n"
        ),
    },
    {
        "id": "returned-raw-value",
        "state": "this.data",
        "verdict": "neutral",
        "drives_decision": False,
        "src": (
            "class Store {\n"
            "  data: Record<string, number> = {};\n"
            "  load(d: Record<string, number>) { this.data = d; }\n"
            "  snapshot() { return this.data; }\n"                     # returned only
            "}\n"
        ),
    },
    {
        "id": "invoked-only-collaborator",
        "state": "this.handler",
        "verdict": "neutral",
        "drives_decision": False,
        "src": (
            "class Router {\n"
            "  handler: (r: string) => string;\n"
            "  constructor(h: (r: string) => string) { this.handler = h; }\n"
            "  route(r: string) { return this.handler(r); }\n"        # invoked, result returned
            "}\n"
        ),
    },
    {
        "id": "module-global-in-branch",
        "state": "seen",
        "verdict": "promiscuous",
        "drives_decision": True,
        "src": (
            "let seen: Record<string, boolean> = {};\n"
            "function visit(k: string) { seen[k] = true; }\n"          # shared write
            "function already(k: string) { return k in seen; }\n"      # unbounded key membership
        ),
    },
]


def _classify(tmp_path, src):
    (tmp_path / "case.ts").write_text(src)
    return state_bounds.classify(tmp_path, "typescript")


def _finding(result, state):
    return next((f for f in result["findings"] if f["state"] == state), None)


@pytest.mark.parametrize("case", VECTORS, ids=[c["id"] for c in VECTORS])
def test_ts_conformance_vector(tmp_path, case):
    result = _classify(tmp_path, case["src"])
    f = _finding(result, case["state"])
    assert f is not None, f"state {case['state']!r} not surfaced in findings"
    assert f["verdict"] == case["verdict"], f"{case['id']}: verdict"
    assert f["drives_decision"] == case["drives_decision"], f"{case['id']}: drives_decision"
