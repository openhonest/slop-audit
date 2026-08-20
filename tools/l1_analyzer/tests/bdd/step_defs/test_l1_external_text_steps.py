"""Behavioural spec for L1.12-L1.17 (external-tool and text/structural indicators),
wired to the REAL analyzer.

External indicators (L1.12-L1.14) run real stub binaries on a controlled PATH: a
genuine executable at the process boundary, the way the analyzer invokes the tool,
not a mock of the analyzer. Text indicators (L1.15-L1.17) build real files and call
the real scanners. No formula is reimplemented in the test.

Each Given returns the `Codebase` it built, naming the language the scenario is about
instead of leaving the When to assume one. The When dispatches on the indicator number
through a table and returns `result`.
"""

import os
from pathlib import Path
from typing import TypedDict

import pytest
from l1_analyzer import dead_code, indicators, secret_scan
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/l1_external.feature")
scenarios("../features/l1_text.feature")


class Codebase(TypedDict):
    """The codebase a scenario builds, and the language it is written in."""
    repo: Path
    lang: str


def _stub(bindir, name, body):
    bindir.mkdir(parents=True, exist_ok=True)
    f = bindir / name
    f.write_text("#!/bin/sh\n" + body + "\n")
    f.chmod(0o755)


def _on_path(monkeypatch, bindir):
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])


# --- L1.12-L1.14: real stub binaries on PATH --------------------------------

@given("a codebase where every definition is referenced", target_fixture="codebase")
def given_all_referenced(tmp_path) -> Codebase:
    # Native now: no binary is consulted, so the source is the input. `used` is called at
    # module level, which is what makes the reference real rather than asserted.
    (tmp_path / "a.py").write_text("def used():\n    return 1\n\n\nprint(used())\n")
    return {"repo": tmp_path, "lang": "python"}


@given(parsers.parse("a codebase with {dead:d} of {total:d} definitions unreferenced"),
       target_fixture="codebase")
def given_unreferenced(dead, total, tmp_path) -> Codebase:
    bodies = "".join(f"def d{i}():\n    return {i}\n\n\n" for i in range(dead))
    live = "".join(f"def l{i}():\n    return {i}\n\n\n" for i in range(total - dead))
    calls = "".join(f"print(l{i}())\n" for i in range(total - dead))
    (tmp_path / "a.py").write_text(bodies + live + calls)
    return {"repo": tmp_path, "lang": "python"}


@given("a codebase whose one block is copied with every name changed", target_fixture="codebase")
def given_renamed_copy(tmp_path) -> Codebase:
    """A Type-2 clone: same shape, different names and numbers throughout. Normalizing
    identifiers and literals is exactly what makes this match, and comparing raw text is
    what would miss it."""
    first = "\n".join(f"    value_{i} = compute(source_{i}, {i})" for i in range(40))
    second = "\n".join(f"    other_{i} = compute(origin_{i}, {i + 500})" for i in range(40))
    (tmp_path / "a.py").write_text(f"def first():\n{first}\n\n\ndef second():\n{second}\n")
    return {"repo": tmp_path, "lang": "python"}


@given("a codebase where no block repeats", target_fixture="codebase")
def given_no_repeats(tmp_path) -> Codebase:
    """Every line a different SHAPE. Names and literals are what normalization removes, so
    a fixture that varies only its names is duplication and not a clean bill."""
    (tmp_path / "a.py").write_text(
        "def only(seed):\n"
        "    total = 0\n"
        "    for item in seed:\n"
        "        total += 1\n"
        "    while total > 10:\n"
        "        total //= 2\n"
        "    mapping = {'a': [total], 'b': (total,)}\n"
        "    if mapping:\n"
        "        del mapping['a']\n"
        "    try:\n"
        "        return sorted(mapping.items(), key=lambda pair: pair[1])\n"
        "    except TypeError as exc:\n"
        "        raise RuntimeError('no') from exc\n")
    return {"repo": tmp_path, "lang": "python"}


@given(parsers.parse("a codebase carrying {n:d} credential-shaped strings"),
       target_fixture="codebase")
def given_credentials(n, tmp_path) -> Codebase:
    # Assembled from parts, as the rest of this suite does, so no committed literal in this
    # repository matches a provider pattern and trips the scanner on our own tree.
    key = "AKIA" + "IOSFODNN7" + "EXAMPL"
    body = "x = 1\n" if n == 0 else "".join(f'K{i} = "{key}{chr(81 + i)}"\n' for i in range(n))
    (tmp_path / "a.py").write_text(body)
    return {"repo": tmp_path, "lang": "python"}


# --- L1.15-L1.17: real files, real scanners ---------------------------------

@given(
    parsers.parse("a {total:d} LOC TS codebase with {esc:d} `# type: ignore` or `any`"),
    target_fixture="codebase",
)
def given_escapes(total, esc, tmp_path) -> Codebase:
    body = "let x: any = 1;\n" * esc + "const y = 2;\n" * (total - esc)
    (tmp_path / "a.ts").write_text(body)
    return {"repo": tmp_path, "lang": "typescript"}


@given(
    parsers.parse("a codebase where {ws:d} of {total:d} production lines end with spaces"),
    target_fixture="codebase",
)
def given_ws(ws, total, tmp_path) -> Codebase:
    body = "x = 1  \n" * ws + "y = 2\n" * (total - ws)
    (tmp_path / "a.py").write_text(body)
    return {"repo": tmp_path, "lang": "python"}


@given(parsers.parse("{god:d} of {total:d} production files are >1000 LOC"), target_fixture="codebase")
def given_god(god, total, tmp_path) -> Codebase:
    for i in range(god):
        (tmp_path / f"big{i}.py").write_text("x = 1\n" * 1001)
    for i in range(total - god):
        (tmp_path / f"small{i}.py").write_text("x = 1\n" * 10)
    return {"repo": tmp_path, "lang": "python"}


@given(parsers.parse("one {size:d} LOC file in a {tree:d} LOC tree"), target_fixture="codebase")
def given_one_god(size, tree, tmp_path) -> Codebase:
    (tmp_path / "huge.py").write_text("x = 1\n" * size)
    remaining = max(tree - size, 0)
    per_file = 50
    for i in range(remaining // per_file):
        (tmp_path / f"s{i}.py").write_text("x = 1\n" * per_file)
    return {"repo": tmp_path, "lang": "python"}


# --- when / then ------------------------------------------------------------

# Each indicator is produced by its own module, exactly as the panel calls it. L1.13
# joined them on 2026-08-19; nothing here shells out any more, and _compute_external_
# indicators keeps its name only because the panel's shape is what callers depend on.
_COMPUTE = {
    12: lambda repo, lang: dead_code.analyze(repo, lang),
    13: lambda repo, lang: indicators._compute_external_indicators(repo, lang)["L1.13"],
    14: lambda repo, lang: secret_scan.analyze(repo, lang),
    15: lambda repo, lang: indicators._compute_type_escapes(repo, lang),
    16: lambda repo, lang: indicators._trailing_whitespace(repo),
    17: lambda repo, lang: indicators._god_files(repo),
}


@when(parsers.parse("I compute L1.{num:d}"), target_fixture="result")
def when_compute(codebase, num):
    if num not in _COMPUTE:
        raise AssertionError(f"no L1.{num} wiring in this suite")
    return _COMPUTE[num](codebase["repo"], codebase["lang"])


@then(parsers.parse("L1.{num:d} is {val:f} per KLOC"))
def then_val_kloc(result, val):
    assert result["value"] == pytest.approx(val, abs=0.05)


@then(parsers.parse("L1.{num:d} is {val:f}"))
def then_val(result, val):
    assert result["value"] == pytest.approx(val, abs=0.05)


@then(parsers.parse("the band is {band}"))
def then_band(result, band):
    assert result["band"] == band
