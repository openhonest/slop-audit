"""Finite-testability conformance for C.

C has no classes and no methods: the only state is file-scope variables (globals and
statics). They are referenced by bare name; an array is indexed a[k]; membership and
maps do not exist; a function pointer held in a global and then called is dynamic
dispatch. Instance state does not apply, so every vector here is module state.
"""

import pytest

from l1_analyzer import state_bounds

VECTORS = [
    {"id": "value-indexed-cache", "state": "cache", "verdict": "promiscuous", "drives_decision": True,
     "src": (
        "static int cache[256];\n"
        "void put(int k, int v) { cache[k] = v; }\n"
        "int get(int k) { return cache[k]; }\n")},
    {"id": "multi-writer-capped-counter", "state": "count", "verdict": "neutral", "drives_decision": True,
     "src": (
        "static int count = 0;\n"
        "void incr(void) { if (count < 3) { count += 1; } }\n"
        "void reset(void) { count = 0; }\n")},
    {"id": "observe-only-accumulator", "state": "total", "verdict": "neutral", "drives_decision": False,
     "src": (
        "static int total = 0;\n"
        "void record(int amount) { total += amount; }\n")},
    {"id": "function-pointer-dynamic-dispatch", "state": "handler", "verdict": "unresolved", "drives_decision": True,
     "src": (
        "typedef int (*Handler)(int);\n"
        "static Handler handler;\n"
        "int route(int r) { return handler(r); }\n")},
    {"id": "pass-to-unknown-callee", "state": "config", "verdict": "unresolved", "drives_decision": True,
     "src": (
        "static int config = 0;\n"
        "int route(int r) { return process(config, r); }\n")},
]


def _classify(tmp_path, src):
    (tmp_path / "case.c").write_text(src)
    return state_bounds.classify(tmp_path, "c")


def _finding(result, state):
    return next((f for f in result.get("findings", []) if f.get("state") == state), None)


@pytest.mark.parametrize("case", VECTORS, ids=[c["id"] for c in VECTORS])
def test_c_conformance_vector(tmp_path, case):
    result = _classify(tmp_path, case["src"])
    f = _finding(result, case["state"])
    assert f is not None, f"state {case['state']!r} not surfaced"
    assert f["verdict"] == case["verdict"], f"{case['id']}: verdict"
    assert f["drives_decision"] == case["drives_decision"], f"{case['id']}: drives_decision"
