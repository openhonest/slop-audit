"""Finite-testability conformance for C#.

C# indexes maps with `[]` (an element_access, key wrapped in a bracketed argument
list), tests membership with `.ContainsKey`, strips the parentheses off an `if`
condition, references instance fields by bare name, and wraps every call argument
in an `argument` node. The verdict a state resolves to must not depend on any of
that.

Instance-field state only: static/module state is a documented deferral (the meter
relies on class scope for C#), so no module-global vector appears here.
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
            "using System.Collections.Generic;\n"
            "class Cache {\n"
            "  Dictionary<string,int> store = new Dictionary<string,int>();\n"
            "  void Put(string k, int v) { store[k] = v; }\n"             # indexed write
            "  int Get(string k) {\n"
            "    if (store.ContainsKey(k)) { return store[k]; }\n"        # membership + indexed read, unbounded key
            "    return -1;\n"
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
            "  void Incr() { if (count < 3) { count += 1; } }\n"          # compared to a constant
            "  void Reset() { count = 0; }\n"
            "  bool Allowed() { return count < 3; }\n"
            "}\n"
        ),
    },
    {
        "id": "observe-only-recorder",
        "state": "emitted",
        "verdict": "neutral",
        "drives_decision": False,
        "src": (
            "using System.Collections.Generic;\n"
            "class Recorder {\n"
            "  List<string> emitted = new List<string>();\n"
            "  void Record(string e) { emitted.Add(e); }\n"              # written only
            "  List<string> Dump() { return emitted; }\n"                # returned = output
            "}\n"
        ),
    },
    {
        "id": "returned-raw-value",
        "state": "data",
        "verdict": "neutral",
        "drives_decision": False,
        "src": (
            "using System.Collections.Generic;\n"
            "class Store {\n"
            "  Dictionary<string,int> data = new Dictionary<string,int>();\n"
            "  void Load(Dictionary<string,int> d) { data = d; }\n"
            "  Dictionary<string,int> Snapshot() { return data; }\n"      # returned only
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
            "  void Configure(Config c) { config = c; }\n"                # single writer
            "  string Route(string r) { return Dispatch(config, r); }\n"  # handed to an unknown callee
            "}\n"
        ),
    },
]


def _classify(tmp_path, src):
    (tmp_path / "Case.cs").write_text(src)
    return state_bounds.classify(tmp_path, "csharp")


def _finding(result, state):
    return next((f for f in result.get("findings", []) if f.get("state") == state), None)


@pytest.mark.parametrize("case", VECTORS, ids=[c["id"] for c in VECTORS])
def test_csharp_conformance_vector(tmp_path, case):
    result = _classify(tmp_path, case["src"])
    f = _finding(result, case["state"])
    assert f is not None, f"state {case['state']!r} not surfaced in findings"
    assert f["verdict"] == case["verdict"], f"{case['id']}: verdict"
    assert f["drives_decision"] == case["drives_decision"], f"{case['id']}: drives_decision"
