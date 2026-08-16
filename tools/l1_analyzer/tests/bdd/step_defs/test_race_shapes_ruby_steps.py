"""Behavioural spec for Ruby class-variable compound-update races, wired to thread_surface.

Each Given returns the source under test as the `src` fixture; the When writes it and
returns the scan as `result`.
"""

from l1_analyzer import thread_surface
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/race_shapes_ruby.feature")


def _scan(tmp_path, src):
    (tmp_path / "case.rb").write_text(src)
    return thread_surface.scan(tmp_path, "ruby")


@given("a threaded Ruby class that does @@count += 1", target_fixture="src")
def given_threaded_cv():
    return (
        "class Counter\n  @@count = 0\n  def bump\n    @@count += 1\n  end\nend\n"
        "Thread.new { Counter.new.bump }\n"
    )


@given("a Ruby class that does @@count += 1 with no threads", target_fixture="src")
def given_unthreaded_cv():
    return "class Counter\n  @@count = 0\n  def bump\n    @@count += 1\n  end\nend\n"


@given("a threaded Ruby method that increments a local variable", target_fixture="src")
def given_threaded_local():
    return (
        "def work\n  x = 0\n  x += 1\n  x\nend\n"
        "Thread.new { work }\n"
    )


@when("I scan the Ruby file for race shapes", target_fixture="result")
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
