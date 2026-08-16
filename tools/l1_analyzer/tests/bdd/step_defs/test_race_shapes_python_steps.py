"""Behavioural spec for Python race-condition shapes (B2 check-then-act), wired to the
REAL thread_surface scanner. State threads through a `ctx` fixture."""

import pytest
from l1_analyzer import thread_surface
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/race_shapes_python.feature")


def _scan(tmp_path, src):
    (tmp_path / "case.py").write_text(src)
    return thread_surface.scan(tmp_path, "python")


@pytest.fixture
def ctx():
    return {}


@given("a threaded module that checks then writes a shared dict")
def given_threaded_shared(ctx, tmp_path):
    ctx["src"] = (
        "import threading\n"
        "CACHE = {}\n"
        "def get(k):\n"
        "    if k not in CACHE:\n"
        "        CACHE[k] = compute(k)\n"
        "    return CACHE[k]\n"
        "threading.Thread(target=get, args=(1,)).start()\n"
    )
    ctx["repo"] = tmp_path


@given("a single-threaded module that checks then writes a shared dict")
def given_singlethreaded_shared(ctx, tmp_path):
    ctx["src"] = (
        "CACHE = {}\n"
        "def get(k):\n"
        "    if k not in CACHE:\n"
        "        CACHE[k] = compute(k)\n"
        "    return CACHE[k]\n"
    )
    ctx["repo"] = tmp_path


@given("a threaded module that checks then writes a local dict")
def given_threaded_local(ctx, tmp_path):
    ctx["src"] = (
        "import threading\n"
        "def get(k):\n"
        "    local = {}\n"
        "    if k not in local:\n"
        "        local[k] = compute(k)\n"
        "    return local[k]\n"
        "threading.Thread(target=get, args=(1,)).start()\n"
    )
    ctx["repo"] = tmp_path


@given("a threaded module that does COUNTER += 1 on a global")
def given_global_rmw(ctx, tmp_path):
    ctx["src"] = (
        "import threading\n"
        "COUNTER = 0\n"
        "def bump():\n"
        "    global COUNTER\n"
        "    COUNTER += 1\n"
        "threading.Thread(target=bump).start()\n"
    )
    ctx["repo"] = tmp_path


@given("a threaded module that increments a local counter")
def given_local_rmw(ctx, tmp_path):
    ctx["src"] = (
        "import threading\n"
        "def work():\n"
        "    c = 0\n"
        "    c += 1\n"
        "    return c\n"
        "threading.Thread(target=work).start()\n"
    )
    ctx["repo"] = tmp_path


@when("I scan the Python file for race shapes")
def when_scan(ctx):
    ctx["result"] = _scan(ctx["repo"], ctx["src"])


def _rmw(result):
    return [f for f in result["findings"] if f["kind"] == "nonatomic_rmw"]


@then(parsers.parse('a non-atomic read-modify-write is reported on "{name}"'))
def then_rmw(ctx, name):
    assert any(f["symbol"] == name for f in _rmw(ctx["result"])), [f["symbol"] for f in _rmw(ctx["result"])]


@then("no non-atomic read-modify-write is reported")
def then_no_rmw(ctx):
    assert _rmw(ctx["result"]) == []


def _cta(result):
    return [f for f in result["findings"] if f["kind"] == "check_then_act"]


@then(parsers.parse('a check-then-act is reported on "{name}"'))
def then_cta(ctx, name):
    hits = _cta(ctx["result"])
    assert any(f["symbol"] == name for f in hits), [f["symbol"] for f in hits]
    assert all(f["severity"] == "review" for f in hits)


@then("no check-then-act is reported")
def then_no_cta(ctx):
    assert _cta(ctx["result"]) == []
