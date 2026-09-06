"""Module state written with `export` in front of it was invisible.

The reader walked the file's own top-level children looking for a lexical or variable
declaration. `export const CACHE = {}` is an export statement with the declaration inside
it, so the reader never met the declaration and the binding was not state as far as this
instrument could tell.

Almost all module-level state in TypeScript and JavaScript is exported. A module that keeps
something and never exports it keeps it for itself, which is the rarer case and the only one
this reader could see.

Found on 2026-09-06 while chasing why TypeScript repositories read nearly empty. The
200-repository run of 2026-09-05 gives medians of 3,073 pieces of state for Java, 3,042 for
C#, 1,436 for Python and 372 for TypeScript.

The census's own vector for this site was `let cache: Record<string, number> = {}`, with no
export in front of it, so the gap was never exercised. A fixture that supplies the property
under test proves nothing, and this is the second time that shape has been found here in a
week.
"""

from __future__ import annotations

import subprocess

import pytest

# No type annotations, so the same text is valid in both languages and the two readings can
# be compared. A first draft annotated them and the JavaScript grammar read the annotations
# as extra declarators, which made the fixture disagree with itself rather than with the
# reader.
_EXPORTED = """export const CACHE = {};
export let hits = 0;

export function put(k, v) { CACHE[k] = v; hits += 1; }
"""

_UNEXPORTED = """const CACHE = {};
let hits = 0;

export function put(k, v) { CACHE[k] = v; hits += 1; }
"""

_DEFAULT = """const CACHE = {};
export default CACHE;
"""


def boundary(fn):
    """Mark this file's one edge, and change nothing about it."""
    return fn


@boundary
def _write(tmp_path, name: str, source: str):
    (tmp_path / name).write_text(source)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def _declared(tmp_path, name: str, source: str, lang: str) -> int:
    from l1_analyzer import state_bounds

    return int(state_bounds.classify(_write(tmp_path, name, source), lang)["census"]["declared"])


@pytest.mark.parametrize("lang,name", [("typescript", "m.ts"), ("javascript", "m.js")])
def test_an_exported_module_binding_is_declared_state(tmp_path, lang, name):
    """Two bindings, both exported, both state. This read zero."""
    assert _declared(tmp_path, name, _EXPORTED, lang) == 2


@pytest.mark.parametrize("lang,name", [("typescript", "m.ts"), ("javascript", "m.js")])
def test_the_same_two_bindings_unexported_read_the_same(tmp_path, lang, name):
    """The control. Whether a module hands a binding out does not change whether the module
    keeps it, so the two files must read alike, and only one of them ever did."""
    assert _declared(tmp_path, name, _UNEXPORTED, lang) == 2


@pytest.mark.parametrize("lang,name", [("typescript", "m.ts"), ("javascript", "m.js")])
def test_a_default_export_of_an_existing_binding_is_not_a_second_declaration(tmp_path, lang, name):
    """The other direction, so looking through the export wrapper does not start counting
    twice. `export default CACHE` hands out a binding declared on the line above; it
    declares nothing itself."""
    assert _declared(tmp_path, name, _DEFAULT, lang) == 1


@pytest.mark.parametrize("lang,name", [("typescript", "m.ts"), ("javascript", "m.js")])
def test_the_classifier_reads_what_the_census_counted(tmp_path, lang, name):
    """The two meters over one file, which is the pair this instrument keeps getting wrong.

    Fixing the census alone made the exported case honest and still wrong: it reported two
    declarations and zero visited, so the tool said the state was there and unread rather
    than saying it was absent. That is the better failure and it is still a failure. Both
    readers now go through one function, so neither can meet a shape the other cannot."""
    from l1_analyzer import state_bounds

    reading = state_bounds.classify(_write(tmp_path, name, _EXPORTED), lang)
    assert reading["census"]["declared"] == reading["census"]["visited"] == 2, reading["census"]
