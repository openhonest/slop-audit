"""Additive check: hardcoded machine-specific absolute paths in source.

An absolute path baked into source couples the code to one machine's filesystem. It breaks
on every other checkout, and it leaks the author's home directory, user name, or a
throwaway scratch location into a committed artifact. Both are hidden state, which is the
thing the slop audit exists to surface.

This flags the machine-specific roots, not every string that starts with `/`. An HTTP route
(`/api/users`), an XPath, or a JSON pointer starts with `/` and is not a filesystem path, so
none of those match. The flagged roots are home and user directories, temp and scratch
locations, and Windows drive-letter paths, which have no honest place hardcoded in committed
source.

Additive and gated with the other refinements, so a frozen or pre-registered run
(classify_state_bounds=False) never sees it. It is not an L1 indicator and it changes no L1
number.
"""

from __future__ import annotations

import re
from pathlib import Path

from l1_analyzer import incomplete
from l1_analyzer.scope import PRODUCTION

# Roots that identify one machine: a home or user directory, a temp or scratch location, a
# mount point. A URL path or an API route never begins with one of these.
_UNIX_ROOTS = (
    r"/home/", r"/Users/", r"/root/", r"/tmp/", r"/private/(?:tmp|var)/",
    r"/var/folders/", r"/mnt/", r"/media/", r"/opt/",
)
# The lookbehind stops a root that continues a hostname (inside an http URL) from matching,
# while a quoted or bare home-directory path still does. The Windows arm matches a
# drive-letter path. A path ends at whitespace or a closing quote/paren.
#
# Both arms require the root to be followed by something. A bare root identifies no machine;
# it names a convention, and the only source that carries bare roots is a tool that lists
# them, this module included. One trailing character is enough on the unix arm, because a
# home root plus a single character already names one machine's path.
#
# The Windows arm requires TWO characters after the drive backslash, which is what separates
# a drive path from an escape sequence. A single letter, a colon and a one-character escape
# is a string escape in every language, not a drive. That false positive fired 21 times on
# this repo's own tests before the rule was tightened, and two characters still keeps every
# real drive path, down to a four-character directory at the drive root.
#
# The worked examples live in tests/test_absolute_paths.py, not here. A comment in production
# code that exhibits a machine path is itself a finding, which is how this module came to
# report on its own documentation.
_ABSOLUTE = re.compile(
    r"(?<![A-Za-z0-9._/-])(?:" + "|".join(_UNIX_ROOTS) + r")[^\s\"'`)\]]+"
    r"|(?<![A-Za-z0-9])[A-Za-z]:\\[^\s\"'`)\]]{2,}"
)

_CODE_EXTS = frozenset({".py", ".rs", ".c", ".h", ".cpp", ".hpp", ".js", ".jsx", ".mjs",
                        ".cjs", ".ts", ".tsx", ".java", ".cs", ".rb", ".go", ".sh"})
_CAP = 50


def _matches(text: str) -> list[tuple[int, str]]:
    """(1-based line, matched path) for every machine-specific absolute path in a file."""
    out: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        out.extend((lineno, m.group(0)) for m in _ABSOLUTE.finditer(line))
    return out


def scan(repo: Path, lang: str) -> dict:
    """Flag hardcoded machine-specific absolute paths across the repo's source. Returns
    {verdict, value, band, details, findings}. `lang` is accepted for a uniform additive
    signature; the check is language-agnostic (a leaked home path is the same smell in any
    language). Healthy at zero, Slop otherwise: a hardcoded machine path is never correct."""
    from l1_analyzer.indicators import _read_text_files

    # The production scope, declared once in scope.SCOPES beside the other indicators that
    # measure under it. A test that proves a path detector fires has to contain the path it
    # detects, so scanning the test tree measures the fixtures, not the code. This repo's
    # own tests carried 24 of the 57 findings on the run that prompted the scope fix.
    files, _skipped = _read_text_files(repo, _CODE_EXTS, scope=PRODUCTION)
    # A count of zero over zero files read is not a clean bill, it is no reading at all, and
    # this module returned "no hardcoded machine-specific absolute paths" for both. vacuity.py
    # had already named this module as an instance; secret_scan and thread_surface were
    # repaired at the time and this one was missed.
    if not files:
        raise incomplete.refuse(
            "absolute-path scan",
            f"no production file carried a scanned extension, so nothing was searched ({sorted(_CODE_EXTS)})")
    findings = [
        {"file": str(path.relative_to(repo)) if repo in path.parents else str(path),
         "line": lineno, "path": matched}
        for path, text in files
        for lineno, matched in _matches(text)
    ]
    count = len(findings)
    files_hit = len({f["file"] for f in findings})
    band = "Healthy" if count == 0 else "Slop"
    details = ("no hardcoded machine-specific absolute paths"
               if count == 0
               else f"{count} hardcoded machine-specific absolute path(s) across {files_hit} file(s)")
    return {
        "verdict": "clean" if count == 0 else "flagged",
        "value": count,
        "band": band,
        "details": details,
        "findings": findings[:_CAP],
    }
