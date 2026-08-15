"""Diff the portable Rust panel against the Python reference on one repo.

The crate's standing discipline: no indicator lands until it is validated equal to
l1_analyzer on real repos. This runs both tools on the same repo and prints every
indicator they both produce, marking each EQUAL or DIFF. Exit code 1 on any DIFF, so
it can gate a commit.

The Python side runs with --no-exec, because the Rust side has no runtime harness yet;
that is the same static half on both. Usage:

    uv run validate.py <repo> [lang]
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent / "l1_analyzer"
BINARY = HERE / "target" / "release" / "slop-audit-rs"


def python_panel(repo: Path, lang: str) -> dict[str, dict]:
    """The reference panel, keyed L1.x. Run from the reference package so `uv run`
    resolves that project's environment, not this directory's."""
    out = subprocess.run(
        ["uv", "run", "slop-audit-l1", str(repo), "--no-exec", "--format", "json", "--lang", lang],
        cwd=REFERENCE, capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)["results"]


def rust_panel(repo: Path, lang: str) -> dict[str, dict]:
    """The portable panel, parsed from --tsv."""
    args = [str(BINARY), str(repo), "--tsv"]
    if lang != "auto":
        args += ["--lang", lang]
    out = subprocess.run(args, capture_output=True, text=True, check=True).stdout
    panel: dict[str, dict] = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if parts[0] == "lang":
            panel["lang"] = {"value": parts[1]}
            continue
        code, value, band, details = (parts + ["", "", ""])[:4]
        panel[code] = {"value": value, "band": band, "details": details}
    return panel


def render(value) -> str:
    """The reference's JSON value as the Rust side prints it: a string verbatim, any
    number through json.dumps (so 0.0 stays "0.0" and 47 stays "47")."""
    return value if isinstance(value, str) else json.dumps(value)


def diff_panels(repo: Path, lang: str = "auto", *, quiet: bool = False) -> tuple[int, int]:
    """Run both tools on `repo` and report each shared indicator EQUAL or DIFF.
    Returns (diffs, compared). `quiet` prints only the disagreements, which is what a
    corpus run wants when it is walking several repositories."""
    def say(line: str) -> None:
        if not quiet:
            print(line)

    reference = python_panel(repo, lang)
    ported = rust_panel(repo, lang)

    if "lang" in reference:
        detected_py = reference.pop("lang")
        detected_rs = ported.pop("lang", {}).get("value", "")
        mark = "EQUAL" if detected_py == detected_rs else "DIFF "
        (print if mark.startswith("DIFF") else say)(
            f"{mark} lang: reference={detected_py} ported={detected_rs}")

    # The additive absolute-paths check is keyed differently on the two sides.
    if "absolute_paths" in reference and "abs-paths" in ported:
        reference["abs-paths"] = reference.pop("absolute_paths")

    def order(code: str) -> float:
        # L1.18b sorts between 18 and 19; the additive checks sort last.
        if not code.startswith("L1."):
            return 99.0
        return float(code[3:].replace("b", ".5"))

    # The binary now emits a row for every canonical indicator, and says "not measured"
    # for the ones it does not compute. Those carry no value to compare, so they are
    # counted and named rather than diffed. Comparing them would report six false
    # disagreements; intersecting them away silently is what this differ used to do.
    unmeasured = sorted(
        (c for c, row in ported.items() if row.get("band") == "not measured"), key=order)
    for code in unmeasured:
        say(f"GAP   {code}: not measured by the binary ({ported[code]['details']})")

    # The direction that was never checked, and the reason parity read 16/16 for weeks
    # across a key set that excluded L1.18. An indicator the reference produces and the
    # binary does not mention at all is a coverage defect, not something to skip.
    missing = sorted((c for c in reference if c not in ported), key=order)
    for code in missing:
        print(f"DIFF  {code}: in the reference panel, absent from the binary entirely")

    codes = [c for c in ported if c in reference and c not in set(unmeasured)]
    for code in [c for c in ported if c not in reference]:
        say(f"SKIP  {code}: not in the reference panel")
    diffs = len(missing)
    for code in sorted(codes, key=order):
        want = reference[code]
        got = ported[code]
        fields = [
            ("value", render(want.get("value", "")), got["value"]),
            ("band", str(want.get("band", "")), got["band"]),
            ("details", str(want.get("details", "")), got["details"]),
        ]
        bad = [(name, a, b) for name, a, b in fields if a != b]
        if not bad:
            say(f"EQUAL {code}")
            continue
        diffs += 1
        print(f"DIFF  {code}")
        for name, a, b in bad:
            print(f"        {name}: reference={a!r}")
            print(f"        {name}: ported   ={b!r}")

    if unmeasured:
        say(f"\n{len(unmeasured)} indicator(s) the binary does not measure: "
            f"{', '.join(unmeasured)}")
    return diffs, len(codes)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    repo = Path(sys.argv[1]).resolve()
    lang = sys.argv[2] if len(sys.argv) > 2 else "auto"
    diffs, compared = diff_panels(repo, lang)
    # "16/16" on its own reads as a complete audit. It is a statement about the indicators
    # that were compared, and saying so is the whole lesson of this differ's own blind spot.
    print(f"\n{compared - diffs}/{compared} COMPARED indicators equal on {repo}")
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
