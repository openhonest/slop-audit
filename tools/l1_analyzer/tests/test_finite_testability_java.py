"""Finite-testability conformance for Java.

Java expresses the same predicate through a different surface. Maps are read and
mutated by method (`store.put`, `store.get`, `store.containsKey`), not by `[]` or
`in`; instance fields are referenced by bare name, not through a receiver; and a
compound assignment is an ordinary assignment node carrying a `+=` operator. The
verdict a state resolves to must not depend on any of that.

Instance-field state only: static/module state is a documented deferral (the meter
relies on class scope for Java), so no module-global vector appears here.
"""

import pytest
from l1_analyzer import state_bounds

VECTORS = [
    {
        "id": "value-indexed-cache",
        "state": "store",
        "verdict": "promiscuous",
        "drives_decision": True,
        "src": (
            "import java.util.*;\n"
            "class Cache {\n"
            "  Map<String,Integer> store = new HashMap<>();\n"
            "  void put(String k, int v) { store.put(k, v); }\n"          # mutating method
            "  Integer get(String k) {\n"
            "    if (store.containsKey(k)) { return store.get(k); }\n"     # keyed read on unbounded key
            "    return null;\n"
            "  }\n"
            "}\n"
        ),
    },
    {
        "id": "multi-writer-capped-counter",
        "state": "count",
        "verdict": "neutral",
        "drives_decision": True,
        "src": (
            "class Limiter {\n"
            "  int count = 0;\n"
            "  void incr() { if (count < 3) { count += 1; } }\n"          # compared to a constant
            "  void reset() { count = 0; }\n"
            "  boolean allowed() { return count < 3; }\n"
            "}\n"
        ),
    },
    {
        "id": "observe-only-recorder",
        "state": "emitted",
        "verdict": "neutral",
        "drives_decision": False,
        "src": (
            "import java.util.*;\n"
            "class Recorder {\n"
            "  List<String> emitted = new ArrayList<>();\n"
            "  void record(String e) { emitted.add(e); }\n"               # written only
            "  List<String> dump() { return emitted; }\n"                 # returned = output
            "}\n"
        ),
    },
    {
        "id": "returned-raw-value",
        "state": "data",
        "verdict": "neutral",
        "drives_decision": False,
        "src": (
            "import java.util.*;\n"
            "class Store {\n"
            "  Map<String,Integer> data = new HashMap<>();\n"
            "  void load(Map<String,Integer> d) { data = d; }\n"
            "  Map<String,Integer> snapshot() { return data; }\n"          # returned only
            "}\n"
        ),
    },
    {
        "id": "pass-to-unknown-callee",
        "state": "config",
        "verdict": "unresolved",
        "drives_decision": True,
        "src": (
            "class Router {\n"
            "  Config config = new Config();\n"
            "  void configure(Config c) { config = c; }\n"                # single writer
            "  String route(String r) { return dispatch(config, r); }\n"  # handed to an unknown callee
            "}\n"
        ),
    },
]


def _classify(tmp_path, src):
    (tmp_path / "Case.java").write_text(src)
    return state_bounds.classify(tmp_path, "java")


def _finding(result, state):
    return next((f for f in result["findings"] if f["state"] == state), None)


@pytest.mark.parametrize("case", VECTORS, ids=[c["id"] for c in VECTORS])
def test_java_conformance_vector(tmp_path, case):
    result = _classify(tmp_path, case["src"])
    f = _finding(result, case["state"])
    assert f is not None, f"state {case['state']!r} not surfaced in findings"
    assert f["verdict"] == case["verdict"], f"{case['id']}: verdict"
    assert f["drives_decision"] == case["drives_decision"], f"{case['id']}: drives_decision"
