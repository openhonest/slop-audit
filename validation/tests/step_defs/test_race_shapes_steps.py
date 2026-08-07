"""Behavioural spec for the structural race-condition shapes (B1 non-atomic RMW, B2
check-then-act), wired to the REAL thread_surface scanner. Each step writes a Rust file
and scans it; state threads through a `ctx` fixture.
"""

import pytest
from l1_analyzer import thread_surface
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/race_shapes.feature")


def _scan(tmp_path, src):
    (tmp_path / "case.rs").write_text(src)
    return thread_surface.scan(tmp_path, "rust")


def _kinds(result, kind):
    return [f for f in result["findings"] if f["kind"] == kind]


@pytest.fixture
def ctx():
    return {}


@given("a method that loads self.count and then stores a value derived from it")
def given_rmw(ctx, tmp_path):
    ctx["src"] = (
        "struct C { count: AtomicU64 }\n"
        "impl C {\n"
        "  fn bump(&self) {\n"
        "    let v = self.count.load(Ordering::SeqCst);\n"
        "    self.count.store(v + 1, Ordering::SeqCst);\n"
        "  }\n"
        "}\n"
    )
    ctx["repo"] = tmp_path


@given("a method that updates self.count with a single fetch_add")
def given_fetch_add(ctx, tmp_path):
    ctx["src"] = (
        "struct C { count: AtomicU64 }\n"
        "impl C {\n"
        "  fn bump(&self) { self.count.fetch_add(1, Ordering::SeqCst); }\n"
        "}\n"
    )
    ctx["repo"] = tmp_path


@given("a method that checks self.seen then inserts into it")
def given_check_then_act(ctx, tmp_path):
    ctx["src"] = (
        "struct C { seen: HashMap<u64, u64> }\n"
        "impl C {\n"
        "  fn note(&mut self, k: u64, v: u64) {\n"
        "    if !self.seen.contains_key(&k) { self.seen.insert(k, v); }\n"
        "  }\n"
        "}\n"
    )
    ctx["repo"] = tmp_path


@given("a method that checks a local map then inserts into it")
def given_local_check_then_act(ctx, tmp_path):
    ctx["src"] = (
        "fn build() {\n"
        "  let mut local = HashMap::new();\n"
        "  if !local.contains_key(&1) { local.insert(1, 2); }\n"
        "}\n"
    )
    ctx["repo"] = tmp_path


@when("I scan the Rust file for race shapes")
def when_scan(ctx):
    ctx["result"] = _scan(ctx["repo"], ctx["src"])


@then(parsers.parse('a non-atomic read-modify-write is reported on "{recv}"'))
def then_rmw(ctx, recv):
    hits = _kinds(ctx["result"], "nonatomic_rmw")
    assert any(f["symbol"] == recv for f in hits), [f["symbol"] for f in hits]
    # B1 is the low-precision "candidate" tier (fires on correct lock-free code), so it
    # never carries the weight of a review-level finding.
    assert all(f["severity"] == "candidate" for f in hits)


@then("no non-atomic read-modify-write is reported")
def then_no_rmw(ctx):
    assert _kinds(ctx["result"], "nonatomic_rmw") == []


@then(parsers.parse('a check-then-act is reported on "{recv}"'))
def then_cta(ctx, recv):
    hits = _kinds(ctx["result"], "check_then_act")
    assert any(f["symbol"] == recv for f in hits), [f["symbol"] for f in hits]
    assert all(f["severity"] == "review" for f in hits)


@then("no check-then-act is reported")
def then_no_cta(ctx):
    assert _kinds(ctx["result"], "check_then_act") == []
