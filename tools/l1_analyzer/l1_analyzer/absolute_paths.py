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

# Roots that identify one machine: a home or user directory, a temp or scratch location, a
# mount point. A URL path or an API route never begins with one of these.
_UNIX_ROOTS = (
    r"/home/", r"/Users/", r"/root/", r"/tmp/", r"/private/(?:tmp|var)/",
    r"/var/folders/", r"/mnt/", r"/media/", r"/opt/",
)
# The lookbehind stops `http://host/home/x` (the root continues a hostname) from matching,
# while a quoted or bare path such as "/home/adam/x" still does. The Windows arm matches a
# drive-letter path. A path ends at whitespace or a closing quote/paren.
_ABSOLUTE = re.compile(
    r"(?<![A-Za-z0-9._/-])(?:" + "|".join(_UNIX_ROOTS) + r")[^\s\"'`)\]]*"
    r"|(?<![A-Za-z0-9])[A-Za-z]:\\[^\s\"'`)\]]+"
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

    files, _skipped = _read_text_files(repo, _CODE_EXTS, extra_ignore=())
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
