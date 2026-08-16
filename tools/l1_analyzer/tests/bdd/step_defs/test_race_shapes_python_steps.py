"""Behavioural spec for Python race-condition shapes (B2 check-then-act), wired to the
REAL thread_surface scanner. Each Given returns the module source as `src`; the When
writes it and returns the scan as `result`.
"""

from l1_analyzer import thread_surface
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/race_shapes_python.feature")


def _scan(tmp_path, src):
    (tmp_path / "case.py").write_text(src)
    return thread_surface.scan(tmp_path, "python")


@given("a threaded module that checks then writes a shared dict", target_fixture="src")
def given_threaded_shared():
    return (
        "import threading\n"
        "CACHE = {}\n"
        "def get(k):\n"
        "    if k not in CACHE:\n"
        "        CACHE[k] = compute(k)\n"
        "    return CACHE[k]\n"
        "threading.Thread(target=get, args=(1,)).start()\n"
    )


@given("a single-threaded module that checks then writes a shared dict", target_fixture="src")
def given_singlethreaded_shared():
    return (
        "CACHE = {}\n"
        "def get(k):\n"
        "    if k not in CACHE:\n"
        "        CACHE[k] = compute(k)\n"
        "    return CACHE[k]\n"
    )


@given("a threaded module that checks then writes a local dict", target_fixture="src")
def given_threaded_local():
    return (
        "import threading\n"
        "def get(k):\n"
        "    local = {}\n"
        "    if k not in local:\n"
        "        local[k] = compute(k)\n"
        "    return local[k]\n"
        "threading.Thread(target=get, args=(1,)).start()\n"
    )


@given("a threaded module that does COUNTER += 1 on a global", target_fixture="src")
def given_global_rmw():
    return (
        "import threading\n"
        "COUNTER = 0\n"
        "def bump():\n"
        "    global COUNTER\n"
        "    COUNTER += 1\n"
        "threading.Thread(target=bump).start()\n"
    )


@given("a threaded module that increments a local counter", target_fixture="src")
def given_local_rmw():
    return (
        "import threading\n"
        "def work():\n"
        "    c = 0\n"
        "    c += 1\n"
        "    return c\n"
        "threading.Thread(target=work).start()\n"
    )


@when("I scan the Python file for race shapes", target_fixture="result")
def when_scan(tmp_path, src):
    return _scan(tmp_path, src)


def _rmw(result):
    return [f for f in result["findings"] if f["kind"] == "nonatomic_rmw"]


@then(parsers.parse('a non-atomic read-modify-write is reported on "{name}"'))
def then_rmw(result, name):
    assert any(f["symbol"] == name for f in _rmw(result)), [f["symbol"] for f in _rmw(result)]


@then("no non-atomic read-modify-write is reported")
def then_no_rmw(result):
    assert _rmw(result) == []


def _cta(result):
    return [f for f in result["findings"] if f["kind"] == "check_then_act"]


@then(parsers.parse('a check-then-act is reported on "{name}"'))
def then_cta(result, name):
    hits = _cta(result)
    assert any(f["symbol"] == name for f in hits), [f["symbol"] for f in hits]
    assert all(f["severity"] == "review" for f in hits)


@then("no check-then-act is reported")
def then_no_cta(result):
    assert _cta(result) == []
