"""Finite-testability conformance for Rust.

Rust has no classes. State is struct fields, declared on the struct and used as
`self.field` inside a separate `impl` block, so the impl is the analysis scope and
state is enumerated from its `self.field` usage. Maps read/write by method
(`insert`, `get`, `contains_key`) or by `[]` (a field-less index_expression);
a compound assignment is its own node; dynamic dispatch is `(self.handler)(r)`;
module state is a `static mut`. The verdict must not depend on any of that.

Red first: classify(repo, "rust") returns n/a until the rust spec lands.
"""

import pytest
from l1_analyzer import state_bounds

VECTORS = [
    {
        "id": "value-indexed-cache",
        "state": "self.store",
        "verdict": "promiscuous",
        "drives_decision": True,
        "src": (
            "use std::collections::HashMap;\n"
            "struct Cache { store: HashMap<String, i32> }\n"
            "impl Cache {\n"
            "  fn put(&mut self, k: String, v: i32) { self.store.insert(k, v); }\n"       # mutating method
            "  fn get(&self, k: &str) -> i32 {\n"
            "    if self.store.contains_key(k) { return self.store[k]; }\n"                # keyed read, unbounded key
            "    -1\n"
            "  }\n"
            "}\n"
        ),
    },
    {
        "id": "multi-writer-capped-counter",
        "state": "self.count",
        "verdict": "neutral",
        "drives_decision": True,
        "src": (
            "struct Limiter { count: i32 }\n"
            "impl Limiter {\n"
            "  fn incr(&mut self) { if self.count < 3 { self.count += 1; } }\n"            # compared to a constant
            "  fn reset(&mut self) { self.count = 0; }\n"
            "  fn allowed(&self) -> bool { self.count < 3 }\n"
            "}\n"
        ),
    },
    {
        "id": "observe-only-recorder",
        "state": "self.emitted",
        "verdict": "neutral",
        "drives_decision": False,
        "src": (
            "struct Recorder { emitted: Vec<i32> }\n"
            "impl Recorder {\n"
            "  fn record(&mut self, e: i32) { self.emitted.push(e); }\n"                  # written only
            "  fn dump(&self) -> Vec<i32> { self.emitted.clone() }\n"                     # handed back = output
            "}\n"
        ),
    },
    {
        "id": "returned-raw-value",
        "state": "self.data",
        "verdict": "neutral",
        "drives_decision": False,
        "src": (
            "struct Store { data: Vec<i32> }\n"
            "impl Store {\n"
            "  fn load(&mut self, d: Vec<i32>) { self.data = d; }\n"
            "  fn snapshot(&self) -> Vec<i32> { self.data.clone() }\n"                    # returned only
            "}\n"
        ),
    },
    {
        "id": "invoked-only-collaborator",
        "state": "self.handler",
        "verdict": "neutral",
        "drives_decision": False,
        "src": (
            "struct Router { handler: Box<dyn Fn(&str) -> String> }\n"
            "impl Router {\n"
            "  fn route(&self, r: &str) -> String { (self.handler)(r) }\n"                # invoked through a wrapper, result returned
            "}\n"
        ),
    },
    {
        "id": "pass-to-unknown-callee",
        "state": "self.config",
        "verdict": "unresolved",
        "drives_decision": True,
        "src": (
            "struct Router { config: Config }\n"
            "impl Router {\n"
            "  fn route(&self, r: &str) -> String { dispatch(&self.config, r) }\n"        # handed to an unknown callee
            "}\n"
        ),
    },
    {
        "id": "static-mut-module-counter",
        "state": "COUNT",
        "verdict": "neutral",
        "drives_decision": True,
        "src": (
            "static mut COUNT: i32 = 0;\n"
            "fn tick() -> bool { unsafe { COUNT += 1; COUNT < 100 } }\n"                  # write + compared to a constant
        ),
    },
]


def _classify(tmp_path, src):
    (tmp_path / "case.rs").write_text(src)
    return state_bounds.classify(tmp_path, "rust")


def _finding(result, state):
    return next((f for f in result.get("findings", []) if f.get("state") == state), None)


@pytest.mark.parametrize("case", VECTORS, ids=[c["id"] for c in VECTORS])
def test_rust_conformance_vector(tmp_path, case):
    result = _classify(tmp_path, case["src"])
    f = _finding(result, case["state"])
    assert f is not None, f"state {case['state']!r} not surfaced in findings"
    assert f["verdict"] == case["verdict"], f"{case['id']}: verdict"
    assert f["drives_decision"] == case["drives_decision"], f"{case['id']}: drives_decision"
