"""Behavioural spec for Java shared mutable static state, wired to thread_surface.

Each Given returns the source under test as the `src` fixture; the When writes it and
returns the scan as `result`.
"""

from l1_analyzer import thread_surface
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/race_shapes_java.feature")


def _scan(tmp_path, src):
    (tmp_path / "C.java").write_text(src)
    return thread_surface.scan(tmp_path, "java")


@given("a Java class with a non-final static Map field", target_fixture="src")
def given_static():
    return "class C { static Map<String,Integer> cache = new HashMap<>(); }\n"


@given("a Java class with a static final Map field", target_fixture="src")
def given_final():
    return "class C { static final Map<String,Integer> CONST = new HashMap<>(); }\n"


@given("a Java class with a non-static Map field", target_fixture="src")
def given_instance():
    return "class C { private Map<String,Integer> cache = new HashMap<>(); }\n"


@given("a Java class with a static ConcurrentHashMap field", target_fixture="src")
def given_concurrent():
    return "class C { static ConcurrentHashMap<String,Integer> cache = new ConcurrentHashMap<>(); }\n"


@when("I scan the Java file for race shapes", target_fixture="result")
def when_scan(tmp_path, src):
    return _scan(tmp_path, src)


def _smf(result):
    return [f for f in result["findings"] if f["kind"] == "static_mutable_field"]


@then(parsers.parse('a static mutable field is reported on "{name}"'))
def then_smf(result, name):
    assert any(f["symbol"] == name for f in _smf(result)), [f["symbol"] for f in _smf(result)]


@then("no static mutable field is reported")
def then_no_smf(result):
    assert _smf(result) == []
