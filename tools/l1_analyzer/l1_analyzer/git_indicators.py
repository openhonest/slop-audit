"""L1.1 through L1.8, read from git log alone.

Eight indicators about how a repository is worked on rather than what it holds: the share of
commits touching documentation, the ratio of deleted to added lines, how much of the tree is
tests. None of them opens a source file or builds a parse tree, which is why they run on any
language and why they belong apart from the readers that do.

Split out of indicators.py on 2026-08-30, when that module crossed a thousand lines of code
and the audit reported it as a god-file. The seam is real: these read a history and the rest
read a tree, and the two have no vocabulary in common.

A repository nobody could read gets eight rows saying "n/a" and the reason, never eight rows
saying zero. Zero is not neutral on this panel: L1.5 is deleted over added lines, so zero is
the Slop end of its own scale, and a directory that is not a git working copy would have
read as a repository that measured terribly.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from l1_analyzer.incomplete import ratio
from l1_analyzer.indicators import (
    _measure,
    _read_text_files,
    _with_skipped,
    band,
)
from l1_analyzer.pytest_trace import L1Result
from l1_analyzer.scope import _TEST_STEM_SUFFIXES, WHOLE_REPO

if TYPE_CHECKING:
    from l1_analyzer.panel import Panel


def _classify_file(path: str) -> str:
    p = path.lower()
    if any(p.endswith(ext) for ext in (".md", ".rst", ".adoc", ".txt", ".feature")):
        return "doc"
    if any(p.endswith(ext) for ext in (".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".java", ".rb", ".rs", ".c", ".h", ".cpp", ".cs", ".kt", ".swift", ".php", "dockerfile", ".yml", ".yaml", ".json", ".toml")):
        return "code"
    return "other"

# The two ratio indicators, as rows. They were two functions that became identical once the
# labels, the thresholds and the two numbers were erased, which is the shape clause 1 names.
# Each row is the label a refusal quotes, the sentence that says why an absent denominator is
# absent rather than zero, the two band thresholds, and how the counts read back.
_RATIOS = {
    "L1.4": ("L1.4 documentation line share",
             ("no line was added in the measured range, so the share of them that is "
              "documentation is absent and not zero"),
             25, 5, "{numerator} doc / {denominator} total lines added"),
    "L1.5": ("L1.5 delete-to-add ratio",
             ("no CODE line was added in the measured range, so a ratio against them is "
              "absent and not zero"),
             60, 30, "{numerator} deleted / {denominator} added code lines"),
}


def _ratio_indicator(code: str, numerator: int, denominator: int) -> L1Result:
    """One of the ratio indicators, by its row.

    Both raise rather than substituting 0.0, which is what stood here for L1.4. A share of
    no added lines is absent, and 0.0 with higher_is_better lands below the Slop threshold,
    so the substitution did not merely publish a wrong number, it published a BAD one over a
    range that had added nothing. Found by vacuity.check.

    L1.5 is load-bearing: it is one of the four indicators that separated the controls in
    the 2026-08-17 validation run."""
    label, absent, high, low, details = _RATIOS[code]
    pct = ratio(numerator, denominator, label, absent)
    return {"value": round(pct, 1), "band": band(pct, high, low, higher_is_better=True),
            "details": details.format(numerator=numerator, denominator=denominator)}


def _git_refused(reason: str) -> Panel:
    """The eight git rows for a repository nobody could read, each carrying the reason.

    Written out rather than built by a comprehension over a range. The keys are the panel's
    own and a comprehension makes them at run time, so the one place these eight rows are
    born was the one place nothing could check that they are the eight rows the panel
    names."""
    row: L1Result = {"value": "n/a", "band": "n/a", "details": reason}
    return {"L1.1": row, "L1.2": row, "L1.3": row, "L1.4": row,
            "L1.5": row, "L1.6": row, "L1.7": row, "L1.8": row}


def compute_git_indicators(repo: Path, since: str | None, until: str | None) -> Panel:
    """L1.1-L1.8 from `git log --numstat`. `since`/`until` are the explicit
    Optional date bounds (None = unbounded); resolved here at the boundary.

    `--numstat` alone carries added/deleted counts AND the path (enough to both
    classify each commit's files and sum line changes). Combining it with
    `--name-status` makes git drop the numeric counts, so we use numstat only.
    """
    cmd = ["git", "-C", str(repo), "log", "--numstat", "--pretty=format:COMMIT %H"]
    if since:
        cmd += ["--since", since]
    if until:
        cmd += ["--until", until]

    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        # "n/a", not 0. The band said nothing was measured and the value said zero, and the
        # card renders the value, so a directory that is not a git working copy produced
        # eight rows reading 0%. Zero is not neutral on this panel: L1.5 is deleted over
        # added lines, so 0% is the Slop end of its own scale, and the shares of commits
        # read the same way. A reader taking in the number before the band - the order the
        # card puts them in - read a repository nobody could measure as one that measured
        # terribly. The half-repair this package's own vacuity checker exists to convict,
        # sitting inside an exception handler where nothing looked until the handlers were
        # swept on 2026-08-19.
        return _git_refused(f"git log failed: {error}")

    total_commits = 0
    doc_only = code_only = mixed = 0
    total_added = total_deleted = 0
    doc_added = code_added = code_deleted = 0
    net_negative_commits = high_delete_commits = 0

    current_commit_files: set[str] = set()
    current_add = current_del = 0

    def close_commit() -> None:
        nonlocal total_commits, doc_only, code_only, mixed
        nonlocal total_added, total_deleted, net_negative_commits, high_delete_commits
        if not current_commit_files:
            return
        total_commits += 1
        kinds = {_classify_file(f) for f in current_commit_files}
        if "doc" in kinds and "code" not in kinds:
            doc_only += 1
        elif "code" in kinds and "doc" not in kinds:
            code_only += 1
        elif "doc" in kinds and "code" in kinds:
            mixed += 1
        if current_add or current_del:
            total_added += current_add
            total_deleted += current_del
            if current_del > current_add:
                net_negative_commits += 1
            if current_add > 0 and (current_del / current_add) > 0.4:
                high_delete_commits += 1

    for line in out.splitlines():
        if line.startswith("COMMIT "):
            close_commit()
            current_commit_files = set()
            current_add = current_del = 0
            continue
        if "\t" not in line:
            continue
        # numstat line: "added<TAB>deleted<TAB>path" (added/deleted are "-" for binary)
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added_s, deleted_s, path = parts[0], parts[1], parts[-1]
        current_commit_files.add(path)  # every touched file counts toward commit classification
        if added_s.isdigit() and deleted_s.isdigit():
            a, d = int(added_s), int(deleted_s)
            current_add += a
            current_del += d
            kind = _classify_file(path)
            if kind == "doc":
                doc_added += a
            elif kind == "code":
                code_added += a
                # Deletions of CODE, which L1.5 divides by and which nobody tracked. The
                # additions were tracked all along and never read: L1.5 used the whole-tree
                # totals while the canon says "across code files".
                code_deleted += d
    close_commit()

    if total_commits == 0:
        # The same refusal as the unreadable-git one above, and for the same reason: a range
        # that holds no commit measured nothing, and 0% is the Slop end of L1.5's scale.
        # `--since` narrower than the history is an ordinary way to reach here.
        return _git_refused("no commits in range")

    results: Panel = {}

    l1 = doc_only / total_commits * 100
    # Every one of these carries the counts behind it. Six published a bare percentage
    # until 2026-08-18, and answering "why is this repository Slop on L1.5" meant
    # re-deriving from git log what the analyzer had already counted and discarded.
    results["L1.1"] = {"value": round(l1, 1), "band": band(l1, 10, 1, higher_is_better=True),
                       "details": f"{doc_only} doc-only / {total_commits} commits"}

    l2 = code_only / total_commits * 100
    results["L1.2"] = {"value": round(l2, 1), "band": band(l2, 70, 85, higher_is_better=False),
                       "details": f"{code_only} code-only / {total_commits} commits"}

    l3 = mixed / total_commits * 100
    results["L1.3"] = {"value": round(l3, 1), "band": band(l3, 12, 3, higher_is_better=True),
                       "details": f"{mixed} mixed doc-and-code / {total_commits} commits"}

    # Through the one boundary, like every other measure. Both divide by added lines, so both
    # can meet a range that added none, and _measure is what turns the refusal into an n/a
    # carrying its reason instead of a fabricated Slop.
    results["L1.4"] = _measure(_ratio_indicator, "L1.4", doc_added, total_added)
    results["L1.5"] = _measure(_ratio_indicator, "L1.5", code_deleted, code_added)

    l6 = net_negative_commits / total_commits * 100
    results["L1.6"] = {"value": round(l6, 1), "band": band(l6, 15, 5, higher_is_better=True),
                       "details": f"{net_negative_commits} net-negative / {total_commits} commits"}

    l7 = high_delete_commits / total_commits * 100
    results["L1.7"] = {"value": round(l7, 1), "band": band(l7, 20, 5, higher_is_better=True),
                       "details": f"{high_delete_commits} delete-heavy / {total_commits} commits"}

    results["L1.8"] = _test_to_prod_ratio(repo)

    return results

# Files whose path marks them as test code (used by L1.8).
_TEST_PATH_MARKERS = frozenset({"test", "tests", "spec", "specs", "__tests__"})
# A .NET test project is a sibling directory named <Project>.Tests, never a plain
# `tests/` parent. The production scope learned this in the same pass; L1.8 needs it too.
_TEST_DOTTED_MARKERS = ("test", "tests", "spec", "specs")
# The .NET and JVM file convention, in its original casing. Capitalised on purpose: see
# _is_test_file.
_SRC_EXTS = frozenset({".py", ".rs", ".c", ".h", ".cpp", ".js", ".jsx", ".mjs", ".cjs",
                       ".ts", ".tsx", ".java", ".cs", ".go", ".rb", ".kt", ".swift", ".php"})

def _is_test_file(path: Path) -> bool:
    """True when a path is test code, for the L1.8 test-to-production split.

    Two arms beyond the original ones carry the .NET and JVM conventions, which the
    Python, Go and JavaScript arms could not see. Without them L1.8 reported
    Newtonsoft.Json as "0 test / 193720 production LOC", band Slop, for a repository
    with 704 test files: the exact inverse of the truth, on a scored indicator.

    A dotted project directory (Newtonsoft.Json.Tests) is a test directory, matching the
    same rule the production scope uses. A stem ending in a CAPITALISED Test, Tests, Spec
    or Specs (JsonSerializerTests.cs) is a test file. The capital is what makes that arm
    safe: `Latest.java` ends with "test" when lowercased and would otherwise be counted
    as test code, while `SmokeTests.cs` reads as one only in its original casing.
    """
    lowered = {p.lower() for p in path.parts}
    if lowered & _TEST_PATH_MARKERS:
        return True
    if any(p.endswith("." + m) for p in lowered for m in _TEST_DOTTED_MARKERS):
        return True
    name = path.name.lower()
    suffix = path.suffix.lower()
    if name.startswith("test_") or name.endswith(("_test" + suffix, ".test" + suffix, ".spec" + suffix)):
        return True
    return path.stem.endswith(_TEST_STEM_SUFFIXES)

def _test_to_prod_ratio(repo: Path) -> L1Result:
    """L1.8: lines of test code / lines of production code."""
    files, skipped = _read_text_files(repo, _SRC_EXTS, scope=WHOLE_REPO)
    test_loc = prod_loc = 0
    for path, text in files:
        n = len(text.splitlines())
        if _is_test_file(path):
            test_loc += n
        else:
            prod_loc += n
    if prod_loc == 0:
        return {"value": "n/a", "band": "n/a", "details": _with_skipped("no production source files found", skipped)}
    ratio = test_loc / prod_loc
    return {"value": round(ratio, 2), "band": band(ratio, 0.4, 0.1, higher_is_better=True), "details": _with_skipped(f"{test_loc} test / {prod_loc} production LOC", skipped)}

# ---------------------------------------------------------------------------
# Config (L1.9-11)
# ---------------------------------------------------------------------------
