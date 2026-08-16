"""Behavioural spec for JS/TS async TOCTOU, wired to the REAL thread_surface scanner.

The language differs per scenario, so the Given returns a `Case` with its three fields
named. The When writes the file and returns the scan as `result`.
"""

from typing import TypedDict

from l1_analyzer import thread_surface
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/race_shapes_jsts.feature")

_AWAIT = (
    "class Cache {\n"
    "  async get(k) {\n"
    "    if (!this.store.has(k)) {\n"
    "      const v = await compute(k);\n"
    "      this.store.set(k, v);\n"
    "    }\n"
    "    return this.store.get(k);\n"
    "  }\n"
    "}\n"
)
_NO_AWAIT = (
    "class Cache {\n"
    "  get(k) {\n"
    "    if (!this.store.has(k)) {\n"
    "      this.store.set(k, compute(k));\n"
    "    }\n"
    "    return this.store.get(k);\n"
    "  }\n"
    "}\n"
)


class Case(TypedDict):
    """The three things a scenario states: the source, its language, its extension."""
    src: str
    lang: str
    ext: str


def _scan(tmp_path, case: Case):
    (tmp_path / f"case.{case['ext']}").write_text(case["src"])
    return thread_surface.scan(tmp_path, case["lang"])


@given("a TypeScript method that checks this.store, awaits, then writes this.store", target_fixture="case")
def given_ts_await() -> Case:
    return {"src": _AWAIT, "lang": "typescript", "ext": "ts"}


@given("a TypeScript method that checks this.store then writes it with no await", target_fixture="case")
def given_ts_noawait() -> Case:
    return {"src": _NO_AWAIT, "lang": "typescript", "ext": "ts"}


@given("a JavaScript method that checks this.store, awaits, then writes this.store", target_fixture="case")
def given_js_await() -> Case:
    return {"src": _AWAIT, "lang": "javascript", "ext": "js"}


@when("I scan for async TOCTOU", target_fixture="result")
def when_scan(tmp_path, case: Case):
    return _scan(tmp_path, case)


def _toctou(result):
    return [f for f in result["findings"] if f["kind"] == "async_toctou"]


@then(parsers.parse('an async TOCTOU is reported on "{recv}"'))
def then_toctou(result, recv):
    hits = _toctou(result)
    assert any(f["symbol"] == recv for f in hits), [f["symbol"] for f in hits]
    assert all(f["severity"] == "review" for f in hits)


@then("no async TOCTOU is reported")
def then_no_toctou(result):
    assert _toctou(result) == []
