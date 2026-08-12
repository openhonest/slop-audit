"""Finite-testability conformance for Go.

Go has no classes: state is struct fields, and methods are top-level funcs bound to a
struct by a named receiver (c, l, r ...) declared per method, so state is grouped by
receiver TYPE and keyed <Type>.<field>. Maps read/write by index or builtin; an
assignment target is wrapped in an expression_list; membership is the comma-ok idiom
(_, ok := m[k]); a func-typed field called is dynamic dispatch.
"""

import pytest
from l1_analyzer import state_bounds

VECTORS = [
    {"id": "value-indexed-cache", "state": "Cache.store", "verdict": "promiscuous", "drives_decision": True,
     "src": (
        "package main\n"
        "type Cache struct { store map[string]int }\n"
        "func (c *Cache) Put(k string, v int) { c.store[k] = v }\n"
        "func (c *Cache) Get(k string) int {\n"
        "  if _, ok := c.store[k]; ok { return c.store[k] }\n"
        "  return -1\n"
        "}\n")},
    {"id": "multi-writer-capped-counter", "state": "Limiter.count", "verdict": "neutral", "drives_decision": True,
     "src": (
        "package main\n"
        "type Limiter struct { count int }\n"
        "func (l *Limiter) Incr() { if l.count < 3 { l.count += 1 } }\n"
        "func (l *Limiter) Reset() { l.count = 0 }\n")},
    {"id": "observe-only-recorder", "state": "Recorder.emitted", "verdict": "neutral", "drives_decision": False,
     "src": (
        "package main\n"
        "type Recorder struct { emitted map[int]bool }\n"
        "func (r *Recorder) Record(e int) { r.emitted[e] = true }\n"
        "func (r *Recorder) Dump() map[int]bool { return r.emitted }\n")},
    {"id": "returned-raw-value", "state": "Store.data", "verdict": "neutral", "drives_decision": False,
     "src": (
        "package main\n"
        "type Store struct { data map[string]int }\n"
        "func (s *Store) Load(d map[string]int) { s.data = d }\n"
        "func (s *Store) Snapshot() map[string]int { return s.data }\n")},
    {"id": "invoked-only-collaborator", "state": "Router.handler", "verdict": "neutral", "drives_decision": False,
     "src": (
        "package main\n"
        "type Router struct { handler func(string) string }\n"
        "func (r *Router) Route(req string) string { return r.handler(req) }\n")},
    {"id": "pass-to-unknown-callee", "state": "Gate.config", "verdict": "unresolved", "drives_decision": True,
     "src": (
        "package main\n"
        "type Gate struct { config int }\n"
        "func (g *Gate) Route(r int) int { return dispatch(g.config, r) }\n")},
]


def _classify(tmp_path, src):
    (tmp_path / "case.go").write_text(src)
    return state_bounds.classify(tmp_path, "go")


def _finding(result, state):
    return next((f for f in result.get("findings", []) if f.get("state") == state), None)


@pytest.mark.parametrize("case", VECTORS, ids=[c["id"] for c in VECTORS])
def test_go_conformance_vector(tmp_path, case):
    result = _classify(tmp_path, case["src"])
    f = _finding(result, case["state"])
    assert f is not None, f"state {case['state']!r} not surfaced"
    assert f["verdict"] == case["verdict"], f"{case['id']}: verdict"
    assert f["drives_decision"] == case["drives_decision"], f"{case['id']}: drives_decision"
