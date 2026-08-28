"""One step function bound to three scenarios was reported three times.

Reported by a peer on 2026-08-28, against the build from that morning. A pytest-bdd step can
carry more than one decorator, one per scenario it serves. Their `then_fk_preserved` carries
three, and their clause-15 total went from 14 to 16 on a day when nothing about that function
changed. The whole rise was that one site, counted three times.

I introduced it porting the clause. The Python-only reader collected FUNCTIONS carrying a
step decorator, which is one per function however many decorators it has. The ported reader
collects MARKERS and maps each back to the function it sits on, which is one per decorator.

The site is the finding. A reader sent to the same line three times learns nothing the first
visit did not tell them, and a count that moves when a step is bound to another scenario is
measuring the feature file rather than the code.
"""

from l1_analyzer import honest_code_markers as markers
from l1_analyzer import honest_code_read as read

_BODY = "\n".join(f"    step_{i}()" for i in range(35))


def _found(source: str, lang: str = "python") -> list[dict]:
    return markers.heavy_step_definitions(read.read_tree(source, lang)) or []


def test_a_step_bound_to_three_scenarios_is_reported_once():
    found = _found('@then("a")\n@then("b")\n@then("c")\n'
                   f"def then_fk_preserved(ctx):\n{_BODY}\n")
    assert [(f["symbol"], f["line"]) for f in found] == [("then_fk_preserved", 4)], found


def test_a_step_bound_to_one_scenario_is_still_reported():
    """The direction that must not move while removing a duplicate."""
    assert len(_found(f'@then("a")\ndef then_one(ctx):\n{_BODY}\n')) == 1


def test_two_different_steps_are_two_findings():
    """Deduplicating by function must not collapse two functions into one."""
    found = _found(f'@then("a")\ndef then_one(ctx):\n{_BODY}\n\n\n'
                   f'@then("b")\ndef then_two(ctx):\n{_BODY}\n')
    assert sorted(f["symbol"] for f in found) == ["then_one", "then_two"], found


def test_a_step_that_never_runs_is_also_reported_once():
    """The other finding this clause makes, on a function carrying two decorators."""
    found = _found('@when("a")\n@when("b")\nasync def when_it(ctx):\n    await go(ctx)\n')
    assert len(found) == 1, found
    assert "never runs" in found[0]["detail"]


def test_the_count_does_not_move_when_a_step_gains_a_scenario():
    """What the peer measured: their total rose by two on a day nothing changed in the
    code. A number that moves when a step is bound to another scenario is measuring the
    feature file."""
    one = _found(f'@then("a")\ndef then_it(ctx):\n{_BODY}\n')
    two = _found(f'@then("a")\n@then("b")\ndef then_it(ctx):\n{_BODY}\n')
    assert len(one) == len(two)


# ---------------------------------------------------------------------------
# The same shape in the other two clauses that read a marker
#
# The duplicate was not about steps. Every clause in this module collects markers and maps
# each back to the declaration it sits on, so any declaration carrying two markers is
# reported twice. A function can be registered for two lifecycle events, or carry two
# memoising decorators, as easily as a step can serve two scenarios.
#
# Found by checking the other two after fixing the one an adopter reported. One cause, so
# one fix: the clauses report the declaration, and a declaration is reported once.
# ---------------------------------------------------------------------------

import pytest


@pytest.mark.parametrize(("checker", "source", "symbol"), [
    (markers.lifecycle_hooks,
     '@atexit.register\n@app.on_event("startup")\ndef begin():\n    pass\n', "begin"),
    (markers.unmeasured_caches,
     "@lru_cache\n@cached\ndef price(sku):\n    return look_up(sku)\n", "price"),
])
def test_a_declaration_carrying_two_markers_is_reported_once(checker, source, symbol):
    found = checker(read.read_tree(source, "python")) or []
    assert [f["symbol"] for f in found] == [symbol], found


@pytest.mark.parametrize(("checker", "source", "count"), [
    (markers.lifecycle_hooks,
     '@atexit.register\ndef a():\n    pass\n\n\n@atexit.register\ndef b():\n    pass\n', 2),
    (markers.unmeasured_caches,
     "@lru_cache\ndef a():\n    pass\n\n\n@lru_cache\ndef b():\n    pass\n", 2),
])
def test_two_declarations_are_still_two_findings(checker, source, count):
    """Deduplicating by declaration must not collapse two declarations into one."""
    assert len(checker(read.read_tree(source, "python")) or []) == count


def test_a_cache_dependency_is_not_deduplicated_against_a_marker():
    """The two halves of that clause count different things. An import and a decorator on
    the same line number are not the same finding."""
    found = markers.unmeasured_caches(read.read_tree(
        "import redis\n\n\n@lru_cache\ndef price(sku):\n    return look_up(sku)\n",
        "python")) or []
    assert len(found) == 2, found
