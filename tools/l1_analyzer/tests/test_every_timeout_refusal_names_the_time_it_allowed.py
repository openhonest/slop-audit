"""A timeout refusal that does not say how long it waited blames the repository.

"The test suite timed out" reads as a fact about the code. The fact is usually that nobody
asked for long enough: the default is three hundred seconds for one execution of a whole
suite, which no real repository's suite fits in. Those are two different findings and only
one of them is the adopter's to fix.

`disclosure.timeout_note` was written for this and fifteen refusals were given it. Two were
missed, and one of the two is the path a Rust workspace actually takes: the coverage build's
own timeout inside `decision_space_coverage`, which is what the session auditing turso met
on 2026-09-06 and read as a fact about turso.

This reads the source rather than the output, because the refusals that matter are the ones
no test reaches: each needs a real toolchain, a real suite and a real stopwatch to produce.
"""

from __future__ import annotations

import pathlib
import re

_PACKAGE = pathlib.Path(__file__).resolve().parents[1] / "l1_analyzer"

# A refusal that names a timeout. The note may be appended on the same line or the next, so
# the window is the statement rather than the line.
_REFUSAL = re.compile(r"_na\(\s*(?:f?\"[^\"]*\"\s*)+", re.MULTILINE)


def boundary(fn):
    """Mark this file's one edge, and change nothing about it."""
    return fn


@boundary
def _sources() -> list[tuple[str, str]]:
    return [(p.name, p.read_text()) for p in sorted(_PACKAGE.glob("*_trace.py"))]


def test_every_timeout_refusal_names_the_time_and_the_flag():
    silent = []
    for name, text in _sources():
        for match in _REFUSAL.finditer(text):
            said = match.group(0)
            if "timed out" not in said:
                continue
            after = text[match.end():match.end() + 120]
            if "timeout_note" not in said and "timeout_note" not in after:
                line = text[:match.start()].count("\n") + 1
                silent.append(f"{name}:{line}")
    assert silent == [], (
        "these refusals say a run timed out and not how long it was given, so a reader "
        f"cannot tell a slow suite from a stopwatch nobody set: {silent}")
