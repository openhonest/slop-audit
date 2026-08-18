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
from l1_analyzer import state_bounds, state_partition

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
    {
        # `macro_invocation` swallows its arguments into an unparsed `token_tree`, so
        # `format!("{}", self.v.len())` holds no field_expression and no call_expression and
        # the reference inside it is invisible. Invisible read as absence is the failure this
        # analyzer exists to name, so the reading is refused rather than issued on the half
        # that could be read.
        "id": "reference-hidden-in-a-macro",
        "state": "self.v",
        "verdict": "unresolved",
        "drives_decision": True,
        "src": (
            "struct S { v: Vec<i32> }\n"
            "impl S {\n"
            "  fn set(&mut self) { self.v = Vec::new(); }\n"
            "  fn show(&self) -> String { format!(\"{}\", self.v.len()) }\n"
            "}\n"
        ),
    },
    {
        # `let r = &mut self.v; r.push(1);` writes the field through a local whose name has
        # no relation to it, so every rule that argues from where the FIELD's own references
        # sit is unsound from that line on.
        "id": "mutable-alias-of-a-field",
        "state": "self.v",
        "verdict": "unresolved",
        "drives_decision": True,
        "src": (
            "struct S { v: Vec<i32> }\n"
            "impl S {\n"
            "  fn set(&mut self) { self.v = Vec::new(); }\n"
            "  fn grow(&mut self) { let r = &mut self.v; r.push(1); }\n"
            "}\n"
        ),
    },
]


def _classify(tmp_path, src):
    (tmp_path / "case.rs").write_text(src)
    return state_bounds.classify(tmp_path, "rust")


def _finding(result, state):
    return next((f for f in result["findings"] if f["state"] == state), None)


@pytest.mark.parametrize("case", VECTORS, ids=[c["id"] for c in VECTORS])
def test_rust_conformance_vector(tmp_path, case):
    result = _classify(tmp_path, case["src"])
    f = _finding(result, case["state"])
    assert f is not None, f"state {case['state']!r} not surfaced in findings"
    assert f["verdict"] == case["verdict"], f"{case['id']}: verdict"
    assert f["drives_decision"] == case["drives_decision"], f"{case['id']}: drives_decision"


# --- the two silences Rust needs names for ------------------------------------
#
# A verdict of `unresolved` is not the whole answer. The reason is published beside it, and
# an adopter reads it to decide whose problem the silence is: a construct nobody taught the
# reader is our backlog, and a region the grammar hands back as tokens is a limit of the
# reading itself. Both of these used to report as `unmodeled_construct`, which sends the
# reader to write a dispatch row for a shape that has no parse tree to dispatch on.


def test_a_macro_body_is_named_as_an_unparsed_region(tmp_path):
    """Rust's macro arguments come back as a flat `token_tree`: no field_expression, no
    call_expression, and the token sequence does not even keep the field name attached to
    `self`. There is no row to write, because there is nothing parsed to match, so the
    silence has to say that rather than name a construct."""
    src = ("struct S { v: Vec<i32> }\n"
           "impl S {\n"
           "  fn set(&mut self) { self.v = Vec::new(); }\n"
           "  fn show(&self) -> String { format!(\"{}\", self.v.len()) }\n"
           "}\n")
    f = _finding(_classify(tmp_path, src), "self.v")
    assert f is not None
    assert f["verdict"] == "unresolved"
    assert f["silence"] == state_partition.UNPARSED_REGION


def test_a_mutable_borrow_of_a_field_is_named_as_an_alias(tmp_path):
    """`&mut self.v` hands the field out under a name the walk cannot follow. A shared borrow
    is a different fact and must stay transparent, which is why the marker is checked rather
    than the node type: `reference_expression` is on the wrapper list for `&self.v`."""
    src = ("struct S { v: Vec<i32> }\n"
           "impl S {\n"
           "  fn set(&mut self) { self.v = Vec::new(); }\n"
           "  fn grow(&mut self) { let r = &mut self.v; r.push(1); }\n"
           "}\n")
    f = _finding(_classify(tmp_path, src), "self.v")
    assert f is not None
    assert f["verdict"] == "unresolved"
    assert f["silence"] == state_partition.MUTABLE_ALIAS


def test_a_shared_borrow_stays_transparent(tmp_path):
    """The guard on the row above. `&self.v` cannot be written through, so it is the wrapper
    it has always been and the value flows on to whatever reads it - here a comparison
    against a constant, which is a two-class split and a decision."""
    src = ("struct S { n: i32 }\n"
           "impl S {\n"
           "  fn set(&mut self) { self.n = 0; }\n"
           "  fn big(&self) -> bool { *(&self.n) > 3 }\n"
           "}\n")
    f = _finding(_classify(tmp_path, src), "self.n")
    assert f is not None
    assert f["verdict"] == "neutral"
    assert f["drives_decision"] is True


def test_a_macro_that_names_nothing_of_ours_leaves_the_reading_alone(tmp_path):
    """The other guard. Refusing every state in a file that contains any macro at all would
    make the rule useless; what is refused is a state whose own name appears in the tokens."""
    src = ("struct S { n: i32 }\n"
           "impl S {\n"
           "  fn set(&mut self) { self.n = 0; }\n"
           "  fn big(&self) -> bool { println!(\"tick\"); self.n > 3 }\n"
           "}\n")
    f = _finding(_classify(tmp_path, src), "self.n")
    assert f is not None
    assert f["verdict"] == "neutral"
    assert f["drives_decision"] is True
