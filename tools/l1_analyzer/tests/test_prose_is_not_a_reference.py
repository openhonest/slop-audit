"""A name mentioned in prose is not a dynamic reference (L1.12).

`_harvest_source` put every WORD of every string and comment into the soft-reference
bucket, and `_SOFT_REASONS` reads a hit there as "a dynamic reference cannot be
resolved", which excludes the definition from the numerator. So a dead function whose
name appeared anywhere in any docstring or comment in the repository cost nothing, and
L1.12 reported 0.0 Healthy over it.

The rule exists for a real case: a name resolved at run time through `getattr`, a
registry keyed by string, an entry point wired by name. A prose mention satisfies it by
accident. Two narrowings, both with a precedent already in this module:

  A comment carries no execution. `_is_comment` says exactly that, twenty lines up, as
  the reason a trailing comment is not an unreachable statement. The same fact means a
  comment can never be the dynamic reference the exemption is for.

  A string is a candidate reference when the WHOLE string is the identifier, which is
  what `getattr(o, "f")` and `REGISTRY["f"]` look like. A string holding the name among
  other words is prose.

The verdict this file asserts on is whether the definition is FLAGGED or excluded as
undecidable, not the L1.12 percentage, so it does not move when the fixture's line count
does.
"""

import pathlib

from l1_analyzer import dead_code


def _report(tmp_path: pathlib.Path, files: dict[str, str]) -> dict:
    for name, body in files.items():
        (tmp_path / name).write_text(body)
    return dead_code.analyze(tmp_path, "python")


def _flagged(r: dict) -> set[str]:
    """The names the report ACCUSES. They live in `findings`, each carrying its category.
    An earlier draft of this file read `r["unreferenced"]`, which is not a key the report
    has, so `.get` returned None and two of the four assertions below passed vacuously."""
    return {f["name"] for f in (r.get("findings") or [])}


def _undecidable(r: dict) -> set[str]:
    return {f["name"] for f in (r.get("undecidable") or [])}


_DEAD = "def build_report(x):\n    return x + 1\n"


def test_a_name_mentioned_in_a_docstring_is_still_dead(tmp_path):
    r = _report(tmp_path, {"m.py": '"""This module used to call build_report before the rewrite."""\n' + _DEAD})
    assert "build_report" in _flagged(r)
    assert "build_report" not in _undecidable(r)


def test_a_name_mentioned_in_a_comment_is_still_dead(tmp_path):
    """A comment carries no execution, which this module already says elsewhere."""
    r = _report(tmp_path, {"m.py": "# build_report is the old entry point\n" + _DEAD})
    assert "build_report" in _flagged(r)
    assert "build_report" not in _undecidable(r)


def test_a_whole_string_naming_the_symbol_still_exempts_it(tmp_path):
    """The case the exemption exists for. `getattr(mod, "build_report")` cannot be
    resolved, so the definition must not be accused."""
    src = _DEAD + '\n\ndef run(mod):\n    return getattr(mod, "build_report")\n'
    r = _report(tmp_path, {"m.py": src})
    assert "build_report" not in _flagged(r)


def test_a_registry_keyed_by_the_name_still_exempts_it(tmp_path):
    src = _DEAD + '\n\ndef run(reg):\n    return reg["build_report"]\n'
    r = _report(tmp_path, {"m.py": src})
    assert "build_report" not in _flagged(r)


def test_the_name_in_neither_prose_nor_a_string_is_flagged(tmp_path):
    """The control. Without this, every assertion above could be satisfied by a reader
    that flags nothing and by one that flags everything, respectively."""
    r = _report(tmp_path, {"m.py": _DEAD})
    assert "build_report" in _flagged(r)
