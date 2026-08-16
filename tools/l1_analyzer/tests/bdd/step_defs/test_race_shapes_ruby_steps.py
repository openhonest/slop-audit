"""Behavioural spec for Ruby class-variable compound-update races, wired to thread_surface."""

import pytest
from l1_analyzer import thread_surface
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/race_shapes_ruby.feature")


def _scan(tmp_path, src):
    (tmp_path / "case.rb").write_text(src)
    return thread_surface.scan(tmp_path, "ruby")


@pytest.fixture
def ctx():
    return {}


@given("a threaded Ruby class that does @@count += 1")
def given_threaded_cv(ctx, tmp_path):
    ctx["result"] = _scan(tmp_path,
        "class Counter\n  @@count = 0\n  def bump\n    @@count += 1\n  end\nend\n"
        "Thread.new { Counter.new.bump }\n")


@given("a Ruby class that does @@count += 1 with no threads")
def given_unthreaded_cv(ctx, tmp_path):
    ctx["result"] = _scan(tmp_path,
        "class Counter\n  @@count = 0\n  def bump\n    @@count += 1\n  end\nend\n")


@given("a threaded Ruby method that increments a local variable")
def given_threaded_local(ctx, tmp_path):
    ctx["result"] = _scan(tmp_path,
        "def work\n  x = 0\n  x += 1\n  x\nend\n"
        "Thread.new { work }\n")


@when("I scan the Ruby file for race shapes")
def when_scan(ctx):
    pass


def _rmw(result):
    return [f for f in result["findings"] if f["kind"] == "nonatomic_rmw"]


@then(parsers.parse('a non-atomic read-modify-write is reported on "{name}"'))
def then_rmw(ctx, name):
    assert any(f["symbol"] == name for f in _rmw(ctx["result"])), [f["symbol"] for f in _rmw(ctx["result"])]


@then("no non-atomic read-modify-write is reported")
def then_no_rmw(ctx):
    assert _rmw(ctx["result"]) == []
