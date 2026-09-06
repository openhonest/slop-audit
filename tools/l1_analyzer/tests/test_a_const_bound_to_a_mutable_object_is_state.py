"""`const` says the name cannot be rebound. It says nothing about the object.

Two files that behave identically at run time got opposite readings, decided by a keyword
that describes the binding rather than the thing bound:

    export let   CACHE = {};   export function put(k, v) { CACHE[k] = v; }   promiscuous
    export const CACHE = {};   export function put(k, v) { CACHE[k] = v; }   nothing at all

The second is the one people write. `const` is the default in these two languages and `let`
is the exception, so declining every const declined nearly all the real module state in
every JavaScript and TypeScript repository this instrument has ever read, and declined it as
a clean pass rather than as silence.

Found on 2026-09-06 while measuring what the TSX grammar fix recovered. chakra-ui went from
almost nothing to 5,328 declaration sites, every one of them visited, and ten verdicts. The
classifier reached all 5,328 and ruled out 5,318 on a keyword.

The census had it right all along and says so in its own words: a const binding to a mutable
object is state, and the census counts it. The two meters disagreed and only one of them was
looked at.
"""

from __future__ import annotations

import subprocess

import pytest

_MUTATED = """export {keyword} CACHE = {{}};

export function put(k, v) {{ CACHE[k] = v; }}
export function get(k) {{ if (CACHE[k]) {{ return 1; }} return 0; }}
"""

_SCALAR = """export const LIMIT = 5;

export function ok(n) {{ if (n > LIMIT) {{ return 1; }} return 0; }}
"""


def boundary(fn):
    """Mark this file's one edge, and change nothing about it."""
    return fn


@boundary
def _classify(tmp_path, name: str, source: str, lang: str) -> dict:
    from l1_analyzer import state_bounds

    (tmp_path / name).write_text(source)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return state_bounds.classify(tmp_path, lang)


@pytest.mark.parametrize("lang,name", [("typescript", "m.ts"), ("javascript", "m.js")])
def test_a_const_container_written_in_place_reads_as_state(tmp_path, lang, name):
    """The case people write, which read as nothing."""
    counts = _classify(tmp_path, name, _MUTATED.format(keyword="const"), lang)["counts"]
    assert sum(counts.values()) == 1, counts


@pytest.mark.parametrize("lang,name", [("typescript", "m.ts"), ("javascript", "m.js")])
def test_the_keyword_does_not_change_the_reading(tmp_path, lang, name):
    """The whole argument in one assertion. Two files that behave identically at run time
    must read identically, and the keyword describes the binding rather than the object."""
    with_let = _classify(tmp_path, name, _MUTATED.format(keyword="let"), lang)["counts"]
    other = tmp_path / "second"
    other.mkdir()
    with_const = _classify(other, name, _MUTATED.format(keyword="const"), lang)["counts"]
    assert with_let == with_const, (with_let, with_const)


@pytest.mark.parametrize("lang,name", [("typescript", "m.ts"), ("javascript", "m.js")])
def test_a_const_bound_to_a_scalar_is_still_declined(tmp_path, lang, name):
    """The other direction, and the reason this is not simply counting every const. A name
    bound once to a number cannot be rebound and holds nothing that can be written, so it is
    a constant and declining it is a reading rather than a gap."""
    counts = _classify(tmp_path, name, _SCALAR, lang)["counts"]
    assert sum(counts.values()) == 0, counts
