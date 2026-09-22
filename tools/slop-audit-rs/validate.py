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

from parity_harness import binary_is_stale, boundary

HERE = Path(__file__).resolve().parent
# One indicator's reading from either tool. The panels were typed `dict[str, dict]`, which
# pins the outer key and leaves the inner mapping completely open: our own escape counter
# reads that inner `dict` as the bare generic it is.
Reading = dict[str, object]



REFERENCE = HERE.parent / "l1_analyzer"
BINARY = HERE / "target" / "release" / "slop-audit-rs"


@boundary
def python_panel(repo: Path, lang: str, exec_tests: bool) -> dict[str, Reading]:
    """The reference panel, keyed L1.x. Run from the reference package so `uv run`
    resolves that project's environment, not this directory's.

    BOTH SIDES ARE ASKED THE SAME QUESTION. This passed `--no-exec` while the binary was
    invoked without it, so from the day the binary started running the audited suite the
    harness compared a run that executed tests against one that did not, and reported the
    difference as a disagreement about L1.19 and L1.20."""
    args = ["uv", "run", "slop-audit-l1", str(repo), "--format", "json", "--lang", lang]
    if not exec_tests:
        args.insert(4, "--no-exec")
    out = subprocess.run(args, cwd=REFERENCE, capture_output=True, text=True,
                         check=True).stdout
    return json.loads(out)["results"]


@boundary
def rust_panel(repo: Path, lang: str, exec_tests: bool) -> dict[str, Reading]:
    """The portable panel, parsed from --tsv. Run the same way the reference was."""
    args = [str(BINARY), str(repo), "--tsv"]
    if not exec_tests:
        args.append("--no-exec")
    if lang != "auto":
        args += ["--lang", lang]
    return panel_from_tsv(subprocess.run(args, capture_output=True, text=True, check=True).stdout)


def panel_from_tsv(out: str) -> dict[str, Reading]:
    """The portable tool's tab-separated output, as a panel keyed by indicator code.

    Lifted out of the run above, which ran the binary and read what it printed in one
    function, so the reading could be exercised only by building the binary first.

    A short row is padded rather than refused: the tool prints a value with no band and no
    details for some indicators, and treating that as malformed would refuse a panel it
    prints on purpose."""
    panel: dict[str, Reading] = {}
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


@boundary
def diff_panels(repo: Path, lang: str, *, quiet: bool,
                exec_tests: bool) -> tuple[int, int, str]:
    """Run both tools on `repo` and report each shared indicator EQUAL or DIFF.
    Returns (diffs, compared, detected language). The language is handed back rather than
    left for a caller to ask for: the corpus walk ran the binary a SECOND time to read that
    one field, with its own flags, and those flags did not carry --no-exec, so every
    repository in the corpus had its test suite executed by a line that wanted a string.

    `quiet` prints only the disagreements, which is what a corpus run wants when it is
    walking several repositories.

    `exec_tests` has no default, and the missing default is the point: whether both tools
    run the audited project's own suite changes two indicators, and a caller that forgot to
    say must not read as one that chose not to."""
    @boundary
    def say(line: str) -> None:
        """The output half of `quiet`, which is the only reason this closure exists: a
        corpus run walking several repositories wants the disagreements and nothing else."""
        if not quiet:
            print(line)

    reference = python_panel(repo, lang, exec_tests)
    ported = rust_panel(repo, lang, exec_tests)

    detected_rs = ""
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
    return diffs, len(codes), detected_rs


@boundary
def _reference_version() -> str:
    """The Python reference's build, asked of the tool rather than read from a file.

    Run from the reference package, the same way its panel is, so `uv run` resolves that
    project's environment rather than this directory's."""
    run = subprocess.run(["uv", "run", "slop-audit-l1", "--version"], cwd=REFERENCE,
                         capture_output=True, text=True, check=False)
    return version_or_unnamed(run.stdout, "slop-audit-l1")


@boundary
def _ported_version() -> str:
    """The portable bundle's build, asked of the binary the same way."""
    run = subprocess.run([str(BINARY), "--version"], capture_output=True, text=True, check=False)
    return version_or_unnamed(run.stdout, "slop-audit-rs")


def version_or_unnamed(printed: str, tool: str) -> str:
    """What a tool said its version is, or a sentence saying it did not say.

    The two askers above were one function with the tool's name in it, which is what put
    the same fallback sentence in two places. A version that came back empty must not read
    as a version: this comparison is published, and a blank beside a real build number
    would look like agreement."""
    return printed.strip() or f"{tool} (version not reported)"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    argv = [a for a in sys.argv[1:] if a != "--exec"]
    # Both tools run the audited project's suite, or neither does. Off by default, because
    # a parity run over a corpus must not execute thirteen strangers' test suites without
    # being asked.
    exec_tests = "--exec" in sys.argv
    repo = Path(argv[0]).resolve()
    lang = argv[1] if len(argv) > 1 else "auto"
    # WHICH two builds. This job's verdict is that two implementations agree, and it used to
    # name neither, so a green run could not be cited afterwards and a disagreement could not
    # be attributed to a change in either side.
    print(f"reference: {_reference_version()}")
    print(f"ported:    {_ported_version()}\n")
    # THE AGE OF THE BUILD, checked before a word of the comparison is printed. This script
    # reads the RELEASE binary while the four beside it read the debug one, and it had no
    # age check at all, so on 2026-09-21 it reported three indicators as needing tools the
    # binary had stopped needing and one newly ported indicator as not ported. Every line
    # was about a build from another day, and the run said EQUAL.
    stale = binary_is_stale(BINARY, HERE / "src")
    if stale:
        print(stale)
        return 2
    # Stated: one repository, and a reader wants every line of the comparison. The
    # corpus walker asks for quiet because it is walking several.
    diffs, compared, _detected = diff_panels(repo, lang, quiet=False,
                                             exec_tests=exec_tests)
    # "16/16" on its own reads as a complete audit. It is a statement about the indicators
    # that were compared, and saying so is the whole lesson of this differ's own blind spot.
    print(f"\n{compared - diffs}/{compared} COMPARED indicators equal on {repo}")
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
