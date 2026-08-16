"""Behavioural spec for Go goroutine captured-write races, wired to thread_surface.

Each Given returns the source under test as the `src` fixture; the When writes it and
returns the scan as `result`. No state is threaded by mutation, so every step declares
in its own signature exactly what it consumes and produces.
"""

from l1_analyzer import thread_surface
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/race_shapes_go.feature")


def _scan(tmp_path, src):
    (tmp_path / "case.go").write_text(src)
    return thread_surface.scan(tmp_path, "go")


@given("a Go function that spawns a goroutine writing captured `total` and `m`", target_fixture="src")
def given_captured():
    return (
        "package main\n"
        "func run() {\n"
        "    total := 0\n"
        "    m := map[string]int{}\n"
        "    go func() {\n"
        "        total += 1\n"
        "        m[\"k\"] = 1\n"
        "    }()\n"
        "}\n"
    )


@given("a Go function whose goroutine writes only variables it declares", target_fixture="src")
def given_locals():
    return (
        "package main\n"
        "func run() {\n"
        "    go func() {\n"
        "        local := 0\n"
        "        local += 1\n"
        "        _ = local\n"
        "    }()\n"
        "}\n"
    )


@given("a Go function whose goroutine locks a mutex before writing captured state", target_fixture="src")
def given_locked():
    return (
        "package main\n"
        "import \"sync\"\n"
        "func run(mu *sync.Mutex) {\n"
        "    total := 0\n"
        "    go func() {\n"
        "        mu.Lock()\n"
        "        total += 1\n"
        "        mu.Unlock()\n"
        "    }()\n"
        "}\n"
    )


@when("I scan the Go file for race shapes", target_fixture="result")
def when_scan(tmp_path, src):
    return _scan(tmp_path, src)


def _gsw(result):
    return [f for f in result["findings"] if f["kind"] == "goroutine_shared_write"]


@then(parsers.parse('a goroutine shared write is reported on "{name}"'))
def then_gsw(result, name):
    assert any(f["symbol"] == name for f in _gsw(result)), [f["symbol"] for f in _gsw(result)]


@then("no goroutine shared write is reported")
def then_no_gsw(result):
    assert _gsw(result) == []


@then("the goroutine shared write is a candidate")
def then_candidate(result):
    hits = _gsw(result)
    assert hits and all(f["severity"] == "candidate" for f in hits), hits
