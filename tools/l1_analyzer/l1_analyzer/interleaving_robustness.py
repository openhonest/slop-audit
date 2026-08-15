"""Interleaving-robustness meter (concurrency anti-coverage).

Cross-references the static thread-surface (WHERE shared concurrency state is) against
which of that surface a model checker actually exercises (loom / shuttle in Rust).
Surface that no model touches is unmodeled: the interleavings its invariants depend on
are never forced in testing, so a green suite says nothing about them.

This check was called `schedule_silence` until 2026-08-15, and the rename is not
cosmetic. "Silence" is the instrument's word for what the analyzer could not read,
reported beside the grade and never inside it (see `state_partition.silence_summary`).
This meter measures something else entirely: it reads its input fine and reports what
the target's own model checkers do not exercise. One word naming two measurements is
how a reader comes to believe a coverage-disclosure number is a concurrency result, so
the concurrency check took a name that says what it measures.

Honesty, stated plainly because Rust reviewers will check:
  - Measures model PRESENCE, not model ADEQUACY. "unmodeled" (no model touches this
    file) is the confident direction; "modeled" is necessary, not sufficient - a model
    may exist and still not exercise the specific interleaving.
  - Static heuristic. A loom test in another file can drive a surface file without
    living in it, so a surface file is called "modeled-elsewhere" (a weaker signal)
    when a file that carries a model also names its module, and "unmodeled" only when
    nothing does. The distinction is disclosed, never collapsed.
  - Rust / loom / shuttle only; other languages return n/a rather than guess.

The verdict is a prioritized audit list, never a bug claim: an unmodeled site is
"force these schedules with a model", not "this races".
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TypedDict

from l1_analyzer import thread_surface
from l1_analyzer.indicators import LANG_CFG, _read_source_bytes
from l1_analyzer.scope import WHOLE_REPO

# What marks a file as carrying a concurrency model in Rust.
_MODEL_MARKERS = re.compile(r"cfg\((?:loom|shuttle)\)|\b(?:loom|shuttle)::")

# The verdict vocabulary. UNMODELED replaced "schedule-silent" in the same rename that
# moved the check off the word "silence": a verdict string is panel output a reader sees,
# so leaving the old word inside a renamed check would have kept the collision alive in
# the one place the reader actually looks.
UNMODELED = "unmodeled"
MODELED = "modeled"
CLEAN = "clean"
NA = "n/a"


class InterleavingRobustnessResult(TypedDict):
    verdict: str
    value: str
    band: str
    unmodeled: list[str]        # flagged surface with no model that touches it (the finding)
    modeled_elsewhere: list[str]  # surface a model names but does not clearly exercise (weak)
    modeled_in_file: list[str]  # surface whose own file carries a model
    details: str


def _module_stem(rel_path: str) -> str:
    """The Rust module name a file defines: storage/shared_wal_coordination.rs ->
    shared_wal_coordination. This is what a `mod` / `use` in a model test would name."""
    return Path(rel_path).stem


def classify(surface_files: set[str], modeled_in_file: set[str], modeled_text: str) -> dict[str, list[str]]:
    """Pure: split flagged-surface files by whether a model touches them.

    A surface file is modeled-in-file when its own file carries a model marker;
    modeled-elsewhere when some modelled file names its module (a weak signal, not
    proof the interleaving is exercised); unmodeled otherwise (the confident gap).
    """
    unmodeled: list[str] = []
    elsewhere: list[str] = []
    in_file: list[str] = []
    for path in sorted(surface_files):
        if path in modeled_in_file:
            in_file.append(path)
        elif re.search(rf"\b{re.escape(_module_stem(path))}\b", modeled_text):
            elsewhere.append(path)
        else:
            unmodeled.append(path)
    return {"unmodeled": unmodeled, "modeled_elsewhere": elsewhere, "modeled_in_file": in_file}


def _na(reason: str) -> InterleavingRobustnessResult:
    return {"verdict": NA, "value": "n/a", "band": "n/a", "unmodeled": [], "modeled_elsewhere": [],
            "modeled_in_file": [], "details": reason}


def analyze(repo: Path, lang: str) -> InterleavingRobustnessResult:
    """The interleaving-robustness verdict: of the flagged concurrency surface, which
    files no model checker touches. Depends on the static thread-surface meter."""
    if lang != "rust":
        return _na(f"interleaving-robustness meter is Rust/loom/shuttle only; {lang} not supported yet")

    surface = thread_surface.scan(repo, "rust")
    surface_files = {f["file"] for f in surface["findings"] if f["severity"] == thread_surface.EXPOSED}
    if not surface_files:
        return {"verdict": CLEAN, "value": "no exposed surface", "band": "n/a", "unmodeled": [],
                "modeled_elsewhere": [], "modeled_in_file": [],
                "details": "no hand-overridden concurrency surface to model"}

    cfg = LANG_CFG["rust"]
    files, _skipped = _read_source_bytes(repo, cfg["extensions"], scope=WHOLE_REPO)
    modeled_in_file: set[str] = set()
    modeled_chunks: list[str] = []
    for path, src in files:
        rel = str(path.relative_to(repo)) if (repo in path.parents or path == repo) else str(path)
        text = src.decode("utf8", errors="ignore")
        if _MODEL_MARKERS.search(text):
            modeled_in_file.add(rel)
            modeled_chunks.append(text)

    split = classify(surface_files, modeled_in_file, "\n".join(modeled_chunks))
    unmodeled = split["unmodeled"]
    verdict = UNMODELED if unmodeled else MODELED
    return {
        "verdict": verdict,
        "value": f"{len(unmodeled)} of {len(surface_files)} exposed-surface files unmodeled",
        "band": "n/a",
        "unmodeled": unmodeled,
        "modeled_elsewhere": split["modeled_elsewhere"],
        "modeled_in_file": split["modeled_in_file"],
        "details": (
            f"{len(unmodeled)} flagged-surface file(s) no loom/shuttle model touches, "
            f"{len(split['modeled_elsewhere'])} named by a model (unproven), "
            f"{len(split['modeled_in_file'])} modelled in-file, across {len(surface_files)} exposed-surface files"
        ),
    }
