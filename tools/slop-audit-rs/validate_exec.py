"""Validate the port equal to the reference on projects whose tests actually RUN.

    uv run validate_exec.py                # every project in exec-corpus.toml
    uv run validate_exec.py rust go        # only these languages
    uv run validate_exec.py --verbose      # print every EQUAL line, not just diffs

`validate_corpus.py` sweeps thirteen real repositories and runs neither tool's execution
path, on purpose: executing thirteen strangers' test suites is slow, it is not reproducible,
and it is not a thing to do to somebody's code without asking. That left L1.19's runtime half
and the whole of L1.20 compared by nothing, in nine languages.

MEASURED 2026-09-23, which is why this exists. A twelve-line Rust crate with two tests,
audited once with execution on, produced three disagreements in the first run: the binary had
no Rust coverage runner at all, L1.18b wrote "1" where the reference wrote "1.0", and L1.20
printed two brackets and the version of the wrong tool. All three are fixed. None of them was
reachable by any check this repository had.

The projects here are ours and about ten lines each, so none of the objection to the pinned
corpus applies. Each is copied into a temp directory and given one git commit before either
tool reads it: a fixture cannot carry its own .git inside this repository, and every indicator
from L1.1 to L1.8 reads a history.

TWO REFUSALS, and they are the reason this is a harness rather than a second manifest. A
language whose toolchain is not installed is skipped BY NAME and never counted equal, because
a sweep that silently compares two of nine reads exactly like one that compared all nine. And
a run that compared no project at all exits 2 rather than printing a clean sweep over nothing.

Exit 1 on any disagreement, 2 when nothing was compared.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from parity_harness import binary_is_stale, boundary
from validate import BINARY, compare_panels, python_panel, rust_panel

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "exec-corpus.toml"


@boundary
def missing_tools(needs: list[str]) -> list[str]:
    """The executables this project needs that are not on PATH."""
    return [tool for tool in needs if shutil.which(tool) is None]


@boundary
def planted(source: Path, into: Path) -> Path:
    """The project copied into a fresh directory with one commit behind it.

    A commit, not a bare `git init`. The first eight indicators read a history, and an empty
    repository makes both tools refuse rather than agree about a number; a refusal both sides
    print is a comparison of two sentences, not of two readings.

    The author is fixed rather than taken from the machine's git config, so two people running
    this compare the same repository rather than two that differ by a name."""
    if into.exists():
        shutil.rmtree(into)
    shutil.copytree(source, into)
    author = ["-c", "user.email=corpus@example.invalid", "-c", "user.name=Exec Corpus"]
    subprocess.run(["git", "init", "--quiet", "."], cwd=into, check=True)
    subprocess.run(["git", "add", "-A"], cwd=into, check=True)
    subprocess.run(["git", *author, "commit", "--quiet", "-m", "the project under audit"],
                   cwd=into, check=True)
    return into


@boundary
def prepare(steps: list[list[str]], root: Path) -> str:
    """Install the project's own test dependencies, or say which step refused.

    The empty string means every step ran. A step that fails is a fact about this machine,
    never about the two tools, so it reads as a skip rather than as a disagreement."""
    for step in steps:
        run = subprocess.run(step, cwd=root, capture_output=True, text=True, check=False)
        if run.returncode != 0:
            first = next((line for line in (run.stderr or run.stdout).splitlines() if line), "")
            return f"`{' '.join(step)}` exited {run.returncode}: {first[:160]}"
    return ""


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    projects = tomllib.loads(MANIFEST.read_text())["project"]
    if args:
        projects = [p for p in projects if p["lang"] in args]
        if not projects:
            print(f"nothing in exec-corpus.toml matches {args}")
            return 2

    stale = binary_is_stale(BINARY, HERE / "src")
    if stale:
        print(stale)
        return 2

    scratch = Path(os.environ.get("TMPDIR", "/tmp")) / f"slop-exec-corpus-{os.getpid()}"
    failures: list[str] = []
    skipped: list[str] = []
    compared_languages: list[str] = []
    try:
        for project in projects:
            lang, source = project["lang"], HERE / project["dir"]
            print(f"\n=== {lang} ({project['dir']})")
            absent = missing_tools(project["needs"])
            if absent:
                print(f"  SKIP: not on PATH: {', '.join(absent)}")
                skipped.append(f"{lang}: needs {', '.join(absent)}")
                continue
            # ONE path, planted TWICE, and each tool reads a pristine tree at the same
            # place. Both halves of that matter. A suite writes into the tree it ran in, so
            # the second tool would otherwise audit the first tool's leftovers: a Ruby
            # project that starts SimpleCov left a coverage report behind and the two
            # disagreed about how many production files the project has. And the path has to
            # be the SAME, because a details line names the interpreter that ran the suite by
            # its absolute path, so two copies in two directories differ for a reason that is
            # not a disagreement.
            root = scratch / lang
            refused = ""
            panels = []
            for read in (python_panel, rust_panel):
                planted(source, root)
                refused = prepare(project["prepare"], root)
                if refused:
                    break
                panels.append(read(root, lang, True))
            if refused:
                print(f"  SKIP: could not prepare the project: {refused}")
                skipped.append(f"{lang}: {refused}")
                continue
            diffs, compared, _detected = compare_panels(panels[0], panels[1],
                                                        quiet=not verbose)
            print(f"  {compared - diffs}/{compared} compared indicators equal"
                  f"  [{'OK' if diffs == 0 else 'DIFF'}]")
            compared_languages.append(lang)
            if diffs:
                failures.append(f"{lang}: {diffs} indicator(s) disagree")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if skipped:
        print(f"\n{len(skipped)} project(s) skipped, and a skip is not a pass:")
        for line in skipped:
            print(f"  {line}")
    # The refusal that makes the rest of this worth reading. A sweep that compared nothing
    # prints the same "no failures" as one that compared every language.
    if not compared_languages:
        print("\nNOTHING WAS COMPARED: every project was skipped, so this run proves nothing")
        return 2
    if failures:
        print(f"\n{len(failures)} language(s) disagree:")
        for line in failures:
            print(f"  {line}")
        return 1
    print(f"\nevery compared indicator equal, with tests EXECUTED, in "
          f"{', '.join(compared_languages)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
