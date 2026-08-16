"""Behavioural spec for L1.1-L1.8 (git-history indicators), wired to the REAL
analyzer. Each step builds a real git repository with the described history and
calls compute_git_indicators. There is no in-memory reimplementation of the git
formulas (the old steps recomputed doc/total in the test and asserted that against
the feature's number, which cannot catch a bug in the analyzer). State is threaded
through a per-scenario `ctx` fixture, not module globals.
"""

import subprocess

import pytest
from l1_analyzer.indicators import compute_git_indicators
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/l1_git.feature")


@pytest.fixture
def ctx():
    return {}


def _git(r, *a):
    subprocess.run(["git", "-C", str(r), *a], check=True, capture_output=True)


def _commit(r, m):
    subprocess.run(
        ["git", "-C", str(r), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", m],
        check=True, capture_output=True,
    )


def _init(tmp_path):
    _git(tmp_path, "init", "-q")
    return tmp_path


def _add(repo, name, text):
    (repo / name).write_text(text)
    _git(repo, "add", "-A")


def _rows(datatable):
    header, *body = datatable
    return [dict(zip(header, row)) for row in body]


def _commit_kind(repo, kind, i):
    if kind == "doc":
        _add(repo, f"doc{i}.md", "a\n"); _commit(repo, f"doc{i}")
    elif kind == "code":
        _add(repo, f"code{i}.py", "x = 1\n"); _commit(repo, f"code{i}")
    elif kind == "mixed":
        _add(repo, f"mix{i}.py", "x = 1\n"); _add(repo, f"mix{i}.md", "a\n"); _commit(repo, f"mix{i}")


# --- given ------------------------------------------------------------------

@given("a git history with:")
def given_history(ctx, datatable, tmp_path):
    repo = _init(tmp_path)
    header = datatable[0]
    rows = _rows(datatable)
    if "kind" in header:
        i = 0
        for r in rows:
            for _ in range(int(r["count"])):
                _commit_kind(repo, r["kind"], i); i += 1
    elif "delta_kind" in header:
        counts = {r["delta_kind"]: int(r["count"]) for r in rows}
        pos, neg = counts.get("positive", 0), counts.get("net-negative", 0)
        seed_lines = 120 * max(neg, 1)
        _add(repo, "big.py", "x = 1\n" * seed_lines); _commit(repo, "seed")   # positive #1
        for i in range(pos - 1):
            _add(repo, f"p{i}.py", "y = 2\n" * 5); _commit(repo, f"pos{i}")
        lines = seed_lines
        for i in range(neg):
            lines -= 100
            (repo / "big.py").write_text("x = 1\n" * max(lines, 1)); _git(repo, "add", "-A"); _commit(repo, f"neg{i}")
    elif "delete_ratio" in header:
        # A high-delete commit (analyzer definition) adds lines AND deletes >40% of
        # them: current_add>0 and current_del/current_add>0.4. A pure deletion has
        # current_add==0 and is net-negative, not high-delete. So each high commit
        # rewrites a seeded 50-line file into 100 different lines (50 del / 100 add
        # = 0.5, and not net-negative). The seeds are pure-add low commits.
        counts = {r["delete_ratio"]: int(r["count"]) for r in rows}
        high, low = counts.get(">40%", 0), counts.get("<40%", 0)
        for i in range(high):
            _add(repo, f"hi{i}.py", "".join(f"old{j}\n" for j in range(50))); _commit(repo, f"seed{i}")
        for i in range(low - high):
            _add(repo, f"low{i}.py", "y = 2\n" * 20); _commit(repo, f"low{i}")
        for i in range(high):
            (repo / f"hi{i}.py").write_text("".join(f"new{j}\n" for j in range(100)))
            _git(repo, "add", "-A"); _commit(repo, f"high{i}")
    ctx["repo"] = repo


@given("a git history with only code commits")
def given_only_code(ctx, tmp_path):
    repo = _init(tmp_path)
    for i in range(5):
        _add(repo, f"c{i}.py", "x = 1\n"); _commit(repo, f"c{i}")
    ctx["repo"] = repo


@given("a git history with added lines:")
def given_added_lines(ctx, datatable, tmp_path):
    repo = _init(tmp_path)
    for r in _rows(datatable):
        ext = "md" if r["kind"] == "doc" else "py"
        _add(repo, f"{r['kind']}.{ext}", "line\n" * int(r["lines"]))
    _commit(repo, "added lines")
    ctx["repo"] = repo


@given("a git history with code deltas:")
def given_deltas(ctx, datatable, tmp_path):
    repo = _init(tmp_path)
    r = _rows(datatable)[0]
    added, deleted = int(r["added"]), int(r["deleted"])
    _add(repo, "a.py", "x = 1\n" * added); _commit(repo, "seed")
    (repo / "a.py").write_text("x = 1\n" * (added - deleted)); _git(repo, "add", "-A"); _commit(repo, "delete")
    ctx["repo"] = repo


@given(parsers.parse("a repo with {prod:d} prod LOC and {test:d} test LOC"))
def given_loc(ctx, prod, test, tmp_path):
    repo = _init(tmp_path)
    _add(repo, "app.py", "x = 1\n" * prod)
    _add(repo, "test_app.py", "y = 2\n" * test)
    _commit(repo, "seed")
    ctx["repo"] = repo


# --- when / then ------------------------------------------------------------

@when(parsers.parse("I compute L1.{num:d}"))
def when_compute(ctx, num):
    ctx["result"] = compute_git_indicators(ctx["repo"], None, None)
    ctx["num"] = num


@then(parsers.parse("L1.{num:d} is {val:f}"))
def then_val(ctx, num, val):
    assert ctx["result"][f"L1.{num}"]["value"] == pytest.approx(val, abs=0.05)


@then(parsers.parse("the band is {band}"))
def then_band(ctx, band):
    assert ctx["result"][f"L1.{ctx['num']}"]["band"] == band
