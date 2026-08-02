"""Behavioural spec for L1.12-L1.17 (external-tool and text/structural indicators),
wired to the REAL analyzer.

External indicators (L1.12-L1.14) run real stub binaries on a controlled PATH: a
genuine executable at the process boundary, the way the analyzer invokes the tool,
not a mock of the analyzer. Text indicators (L1.15-L1.17) build real files and call
the real scanners. No formula is reimplemented in the test. State is threaded
through a per-scenario `ctx` fixture, not module globals.
"""

import os

import pytest
from l1_analyzer import indicators
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/l1_external.feature")
scenarios("../features/l1_text.feature")


@pytest.fixture
def ctx():
    return {}


def _stub(bindir, name, body):
    bindir.mkdir(parents=True, exist_ok=True)
    f = bindir / name
    f.write_text("#!/bin/sh\n" + body + "\n")
    f.chmod(0o755)


def _on_path(monkeypatch, bindir):
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])


# --- L1.12-L1.14: real stub binaries on PATH --------------------------------

@given(parsers.parse("vulture reports {n:d} unreachable symbols"))
def given_vulture(ctx, n, tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("x = 1\n")
    _stub(tmp_path / "bin", "vulture", "".join("echo 'a.py:1: unused'\n" for _ in range(n)))
    _on_path(monkeypatch, tmp_path / "bin")
    ctx["repo"] = tmp_path


@given(parsers.parse("the clone detector reports {pct:f}% duplication"))
def given_clones(ctx, pct, tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("x = 1\n")
    _stub(tmp_path / "bin", "jscpd", f"echo 'Total duplication: {pct} %'")
    _on_path(monkeypatch, tmp_path / "bin")
    ctx["repo"] = tmp_path


@given(parsers.parse("gitleaks reports {n:d} secret findings"))
def given_secrets(ctx, n, tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("x = 1\n")
    _stub(tmp_path / "bin", "gitleaks", "".join("echo '{\"RuleID\":\"x\"}'\n" for _ in range(n)))
    _on_path(monkeypatch, tmp_path / "bin")
    ctx["repo"] = tmp_path


# --- L1.15-L1.17: real files, real scanners ---------------------------------

@given(parsers.parse("a {total:d} LOC TS codebase with {esc:d} `# type: ignore` or `any`"))
def given_escapes(ctx, total, esc, tmp_path):
    body = "let x: any = 1;\n" * esc + "const y = 2;\n" * (total - esc)
    (tmp_path / "a.ts").write_text(body)
    ctx["repo"], ctx["lang"] = tmp_path, "typescript"


@given(parsers.parse("a codebase where {ws:d} of {total:d} production lines end with spaces"))
def given_ws(ctx, ws, total, tmp_path):
    body = "x = 1  \n" * ws + "y = 2\n" * (total - ws)
    (tmp_path / "a.py").write_text(body)
    ctx["repo"] = tmp_path


@given(parsers.parse("{god:d} of {total:d} production files are >1000 LOC"))
def given_god(ctx, god, total, tmp_path):
    for i in range(god):
        (tmp_path / f"big{i}.py").write_text("x = 1\n" * 1001)
    for i in range(total - god):
        (tmp_path / f"small{i}.py").write_text("x = 1\n" * 10)
    ctx["repo"] = tmp_path


@given(parsers.parse("one {size:d} LOC file in a {tree:d} LOC tree"))
def given_one_god(ctx, size, tree, tmp_path):
    (tmp_path / "huge.py").write_text("x = 1\n" * size)
    remaining = max(tree - size, 0)
    per_file = 50
    for i in range(remaining // per_file):
        (tmp_path / f"s{i}.py").write_text("x = 1\n" * per_file)
    ctx["repo"] = tmp_path


# --- when / then ------------------------------------------------------------

@when(parsers.parse("I compute L1.{num:d}"))
def when_compute(ctx, num):
    repo = ctx["repo"]
    if num in (12, 13, 14):
        ctx["result"] = indicators._compute_external_indicators(repo, "python")[f"L1.{num}"]
    elif num == 15:
        ctx["result"] = indicators._compute_type_escapes(repo, ctx["lang"])
    elif num == 16:
        ctx["result"] = indicators._trailing_whitespace(repo)
    elif num == 17:
        ctx["result"] = indicators._god_files(repo)
    else:
        raise AssertionError(f"no L1.{num} wiring in this suite")
    ctx["num"] = num


@then(parsers.parse("L1.{num:d} is {val:f} per KLOC"))
def then_val_kloc(ctx, num, val):
    assert ctx["result"]["value"] == pytest.approx(val, abs=0.05)


@then(parsers.parse("L1.{num:d} is {val:f}"))
def then_val(ctx, num, val):
    assert ctx["result"]["value"] == pytest.approx(val, abs=0.05)


@then(parsers.parse("the band is {band}"))
def then_band(ctx, band):
    assert ctx["result"]["band"] == band
