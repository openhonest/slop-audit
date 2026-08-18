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
    # `:=` is the commonest store in Go and was in no assign key, so a field read into a
    # short variable declaration reached no row and came back unresolved. Nothing decides on
    # the map here: it is bound once and copied out, which is observe-only.
    {"id": "short-var-declaration-store", "state": "Cache.store", "verdict": "neutral", "drives_decision": False,
     "src": (
        "package main\n"
        "type Cache struct { store map[string]int }\n"
        "func (c *Cache) Copy() map[string]int { m := c.store; return m }\n"
        "func (c *Cache) Reset() { c.store = nil }\n")},
    # Go's only loop is `for`, and its condition sits in no `condition` field: it is the
    # first named child. A bool field driving a loop is a two-class split like any `if`.
    {"id": "for-loop-truthiness", "state": "Pump.running", "verdict": "neutral", "drives_decision": True,
     "src": (
        "package main\n"
        "type Pump struct { running bool }\n"
        "func (p *Pump) Run() { for p.running { work() } }\n"
        "func (p *Pump) Stop() { p.running = false }\n")},
    # The three-clause header puts its condition in a for_clause, which is a branch node the
    # spec never named.
    {"id": "for-clause-condition", "state": "Gauge.live", "verdict": "neutral", "drives_decision": True,
     "src": (
        "package main\n"
        "type Gauge struct { live bool }\n"
        "func (g *Gauge) Run() { for i := 0; g.live; i++ { work(i) } }\n"
        "func (g *Gauge) Stop() { g.live = false }\n")},
    # `c.n++` is an inc_statement: a read-modify-write in no assign key at all.
    {"id": "increment-statement", "state": "Counter.n", "verdict": "neutral", "drives_decision": False,
     "src": (
        "package main\n"
        "type Counter struct { n int }\n"
        "func (c *Counter) Bump() { c.n++ }\n")},
    # `<-ch` is a unary_expression, and unary_expression is declared transparent, so a
    # channel receive walked through as if the element flowed on untouched. It does not: the
    # receive CONSUMES an element, and no row in the table describes that, so the honest
    # answer is that the reading stopped here.
    {"id": "channel-receive", "state": "Worker.jobs", "verdict": "unresolved", "drives_decision": True,
     "src": (
        "package main\n"
        "type Worker struct { jobs chan int }\n"
        "func (w *Worker) Next() int { return <-w.jobs }\n"
        "func (w *Worker) Init() { w.jobs = make(chan int) }\n")},
]


def _classify(tmp_path, src):
    (tmp_path / "case.go").write_text(src)
    return state_bounds.classify(tmp_path, "go")


def _finding(result, state):
    return next((f for f in result["findings"] if f["state"] == state), None)


@pytest.mark.parametrize("case", VECTORS, ids=[c["id"] for c in VECTORS])
def test_go_conformance_vector(tmp_path, case):
    result = _classify(tmp_path, case["src"])
    f = _finding(result, case["state"])
    assert f is not None, f"state {case['state']!r} not surfaced"
    assert f["verdict"] == case["verdict"], f"{case['id']}: verdict"
    assert f["drives_decision"] == case["drives_decision"], f"{case['id']}: drives_decision"
