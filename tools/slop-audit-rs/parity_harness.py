"""What every parity script here needs, in one place.

Five scripts diff the Rust port against the Python reference: the whole panel, the state
census, the classifier's enumerator, the position predicates and the false-positive filters.
Each carried its own copy of the staleness refusal and its own copy of the boundary marker,
which is four copies of one rule, and the fifth never had it at all.

That cost a real measurement. `validate.py` reads the RELEASE binary while the other four
read the debug one, and nothing checked its age, so on 2026-09-21 it reported three
indicators as needing tools the binary stopped needing weeks earlier, and reported a newly
ported indicator as not ported. Every line of it was about a build from another day, and the
run said EQUAL.
"""

from __future__ import annotations

from pathlib import Path


def boundary(fn):
    """Mark a function as one of these scripts' edges, and change nothing about it.

    The analyzer package declares its edges with a decorator of this name. These scripts sit
    beside that package rather than inside it, so they say the same thing in their own words
    rather than importing across the boundary between a Rust crate's helper and the Python
    tool it validates."""
    return fn


@boundary
def binary_is_stale(binary: Path, src: Path) -> str:
    """Why a run of `binary` would report on code nobody is looking at, or the empty string.

    Refused rather than rebuilt. A harness that quietly rebuilds hides which build produced
    a number, and the answer a reader wants is the build command, not a number from a binary
    they did not ask for. The message names the command for the binary in front of it, so a
    reader of the release harness is not sent to rebuild the debug one.
    """
    build = "cargo build --release" if binary.parent.name == "release" else "cargo build"
    if not binary.exists():
        return f"no binary at {binary}; run `{build}` first"
    built = binary.stat().st_mtime
    newer = [path for path in src.rglob("*.rs") if path.stat().st_mtime > built]
    if newer:
        names = ", ".join(sorted(p.name for p in newer)[:3])
        return (f"{binary.name} in {binary.parent.name}/ is older than {len(newer)} source "
                f"file(s) ({names}); run `{build}` first, or this run reports on the "
                "previous build")
    return ""
