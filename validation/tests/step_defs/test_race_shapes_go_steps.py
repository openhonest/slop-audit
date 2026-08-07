"""Behavioural spec for Go goroutine captured-write races, wired to thread_surface."""

import pytest
from l1_analyzer import thread_surface
from pytest_bdd import parsers, given, scenarios, then, when

scenarios("../features/race_shapes_go.feature")


def _scan(tmp_path, src):
    (tmp_path / "case.go").write_text(src)
    return thread_surface.scan(tmp_path, "go")


@pytest.fixture
def ctx():
    return {}


@given("a Go function that spawns a goroutine writing captured `total` and `m`")
def given_captured(ctx, tmp_path):
    ctx["result"] = _scan(tmp_path,
        "package main\n"
        "func run() {\n"
        "    total := 0\n"
        "    m := map[string]int{}\n"
        "    go func() {\n"
        "        total += 1\n"
        "        m[\"k\"] = 1\n"
        "    }()\n"
        "}\n")


@given("a Go function whose goroutine writes only variables it declares")
def given_locals(ctx, tmp_path):
    ctx["result"] = _scan(tmp_path,
        "package main\n"
        "func run() {\n"
        "    go func() {\n"
        "        local := 0\n"
        "        local += 1\n"
        "        _ = local\n"
        "    }()\n"
        "}\n")


@given("a Go function whose goroutine locks a mutex before writing captured state")
def given_locked(ctx, tmp_path):
    ctx["result"] = _scan(tmp_path,
        "package main\n"
        "import \"sync\"\n"
        "func run(mu *sync.Mutex) {\n"
        "    total := 0\n"
        "    go func() {\n"
        "        mu.Lock()\n"
        "        total += 1\n"
        "        mu.Unlock()\n"
        "    }()\n"
        "}\n")


@when("I scan the Go file for race shapes")
def when_scan(ctx):
    pass


def _gsw(result):
    return [f for f in result["findings"] if f["kind"] == "goroutine_shared_write"]


@then(parsers.parse('a goroutine shared write is reported on "{name}"'))
def then_gsw(ctx, name):
    assert any(f["symbol"] == name for f in _gsw(ctx["result"])), [f["symbol"] for f in _gsw(ctx["result"])]


@then("no goroutine shared write is reported")
def then_no_gsw(ctx):
    assert _gsw(ctx["result"]) == []


@then("the goroutine shared write is a candidate")
def then_candidate(ctx):
    hits = _gsw(ctx["result"])
    assert hits and all(f["severity"] == "candidate" for f in hits), hits
