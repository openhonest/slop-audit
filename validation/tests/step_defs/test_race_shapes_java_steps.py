"""Behavioural spec for Java shared mutable static state, wired to thread_surface."""

import pytest
from l1_analyzer import thread_surface
from pytest_bdd import parsers, given, scenarios, then, when

scenarios("../features/race_shapes_java.feature")


def _scan(tmp_path, src):
    (tmp_path / "C.java").write_text(src)
    return thread_surface.scan(tmp_path, "java")


@pytest.fixture
def ctx():
    return {}


@given("a Java class with a non-final static Map field")
def given_static(ctx, tmp_path):
    ctx["result"] = _scan(tmp_path, "class C { static Map<String,Integer> cache = new HashMap<>(); }\n")


@given("a Java class with a static final Map field")
def given_final(ctx, tmp_path):
    ctx["result"] = _scan(tmp_path, "class C { static final Map<String,Integer> CONST = new HashMap<>(); }\n")


@given("a Java class with a non-static Map field")
def given_instance(ctx, tmp_path):
    ctx["result"] = _scan(tmp_path, "class C { private Map<String,Integer> cache = new HashMap<>(); }\n")


@given("a Java class with a static ConcurrentHashMap field")
def given_concurrent(ctx, tmp_path):
    ctx["result"] = _scan(tmp_path, "class C { static ConcurrentHashMap<String,Integer> cache = new ConcurrentHashMap<>(); }\n")


@when("I scan the Java file for race shapes")
def when_scan(ctx):
    pass


def _smf(result):
    return [f for f in result["findings"] if f["kind"] == "static_mutable_field"]


@then(parsers.parse('a static mutable field is reported on "{name}"'))
def then_smf(ctx, name):
    assert any(f["symbol"] == name for f in _smf(ctx["result"])), [f["symbol"] for f in _smf(ctx["result"])]


@then("no static mutable field is reported")
def then_no_smf(ctx):
    assert _smf(ctx["result"]) == []
