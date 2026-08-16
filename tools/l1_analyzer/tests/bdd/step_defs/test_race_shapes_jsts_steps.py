"""Behavioural spec for JS/TS async TOCTOU, wired to the REAL thread_surface scanner."""

import pytest
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


@pytest.fixture
def ctx():
    return {}


def _scan(tmp_path, src, lang, ext):
    (tmp_path / f"case.{ext}").write_text(src)
    return thread_surface.scan(tmp_path, lang)


@given("a TypeScript method that checks this.store, awaits, then writes this.store")
def given_ts_await(ctx, tmp_path):
    ctx["result"] = _scan(tmp_path, _AWAIT, "typescript", "ts")


@given("a TypeScript method that checks this.store then writes it with no await")
def given_ts_noawait(ctx, tmp_path):
    ctx["result"] = _scan(tmp_path, _NO_AWAIT, "typescript", "ts")


@given("a JavaScript method that checks this.store, awaits, then writes this.store")
def given_js_await(ctx, tmp_path):
    ctx["result"] = _scan(tmp_path, _AWAIT, "javascript", "js")


@when("I scan for async TOCTOU")
def when_scan(ctx):
    pass  # scan happened in the given step (language differs per scenario)


def _toctou(result):
    return [f for f in result["findings"] if f["kind"] == "async_toctou"]


@then(parsers.parse('an async TOCTOU is reported on "{recv}"'))
def then_toctou(ctx, recv):
    hits = _toctou(ctx["result"])
    assert any(f["symbol"] == recv for f in hits), [f["symbol"] for f in hits]
    assert all(f["severity"] == "review" for f in hits)


@then("no async TOCTOU is reported")
def then_no_toctou(ctx):
    assert _toctou(ctx["result"]) == []
