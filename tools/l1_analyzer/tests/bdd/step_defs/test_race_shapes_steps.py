"""Behavioural spec for the structural race-condition shapes (B1 non-atomic RMW, B2
check-then-act), wired to the REAL thread_surface scanner. Each Given returns the Rust
source as `src`; the When writes it and returns the scan as `result`.
"""

from l1_analyzer import thread_surface
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/race_shapes.feature")


def _scan(tmp_path, src):
    (tmp_path / "case.rs").write_text(src)
    return thread_surface.scan(tmp_path, "rust")


def _kinds(result, kind):
    return [f for f in result["findings"] if f["kind"] == kind]


@given("a method that loads self.count and then stores a value derived from it", target_fixture="src")
def given_rmw():
    return (
        "struct C { count: AtomicU64 }\n"
        "impl C {\n"
        "  fn bump(&self) {\n"
        "    let v = self.count.load(Ordering::SeqCst);\n"
        "    self.count.store(v + 1, Ordering::SeqCst);\n"
        "  }\n"
        "}\n"
    )


@given("a method that updates self.count with a single fetch_add", target_fixture="src")
def given_fetch_add():
    return (
        "struct C { count: AtomicU64 }\n"
        "impl C {\n"
        "  fn bump(&self) { self.count.fetch_add(1, Ordering::SeqCst); }\n"
        "}\n"
    )


@given("a method that checks self.seen then inserts into it", target_fixture="src")
def given_check_then_act():
    # &self (shared): the field is an interior-mutable / concurrent map, so two threads
    # can run this at once - the real TOCTOU target. (&mut self would be exclusive.)
    return (
        "struct C { seen: DashMap<u64, u64> }\n"
        "impl C {\n"
        "  fn note(&self, k: u64, v: u64) {\n"
        "    if !self.seen.contains_key(&k) { self.seen.insert(k, v); }\n"
        "  }\n"
        "}\n"
    )


@given("a method that checks a local map then inserts into it", target_fixture="src")
def given_local_check_then_act():
    return (
        "fn build() {\n"
        "  let mut local = HashMap::new();\n"
        "  if !local.contains_key(&1) { local.insert(1, 2); }\n"
        "}\n"
    )


@given("a method that branches on a Relaxed load of self.ready", target_fixture="src")
def given_relaxed_guard():
    return (
        "struct C { ready: AtomicBool }\n"
        "impl C {\n"
        "  fn poll(&self) { if self.ready.load(Ordering::Relaxed) { return; } }\n"
        "}\n"
    )


@given("a method that stores to self.count with Relaxed ordering", target_fixture="src")
def given_relaxed_store():
    return (
        "struct C { count: AtomicU64 }\n"
        "impl C {\n"
        "  fn tick(&self) { self.count.store(1, Ordering::Relaxed); }\n"
        "}\n"
    )


@when("I scan the Rust file for race shapes", target_fixture="result")
def when_scan(tmp_path, src):
    return _scan(tmp_path, src)


@then(parsers.parse('a non-atomic read-modify-write is reported on "{recv}"'))
def then_rmw(result, recv):
    hits = _kinds(result, "nonatomic_rmw")
    assert any(f["symbol"] == recv for f in hits), [f["symbol"] for f in hits]
    # B1 is the low-precision "candidate" tier (fires on correct lock-free code), so it
    # never carries the weight of a review-level finding.
    assert all(f["severity"] == "candidate" for f in hits)


@then("no non-atomic read-modify-write is reported")
def then_no_rmw(result):
    assert _kinds(result, "nonatomic_rmw") == []


@then(parsers.parse('a check-then-act is reported on "{recv}"'))
def then_cta(result, recv):
    hits = _kinds(result, "check_then_act")
    assert any(f["symbol"] == recv for f in hits), [f["symbol"] for f in hits]
    assert all(f["severity"] == "review" for f in hits)


@then("no check-then-act is reported")
def then_no_cta(result):
    assert _kinds(result, "check_then_act") == []


@then(parsers.parse('a relaxed guard is reported on "{recv}"'))
def then_relaxed_guard(result, recv):
    hits = _kinds(result, "relaxed_guard")
    assert any(f["symbol"] == recv for f in hits), [f["symbol"] for f in hits]
    assert all(f["severity"] == "review" for f in hits)


@then("no relaxed guard is reported")
def then_no_relaxed_guard(result):
    assert _kinds(result, "relaxed_guard") == []
