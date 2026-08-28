"""Files the code reads that the test run never opened.

Two projects reported the same failure a day apart, from repositories with no shared code.
In both, the tests passed while the code was broken, because the tests were handed a
stand-in rather than the real thing. One edits a settings file: 244 tests green, 84.6 per
cent of branches reached, four defects through, 47 records damaged in the live file. The
other opens a database through a stand-in that accepted any path, so production never
created the folder the file lives in.

Coverage cannot see this. Both sets of defects sat inside branches already counted as
reached, and repairing them moved that number down.

A text search over the source cannot see it either. It calls a file untested whenever no
test names it, which is wrong for every file a test reaches by calling the code that opens
it. That was tried first and it reported this package's own page template.

So this watches instead. The suite already runs and a plugin already loads into it, so the
run can report every file it opened. What the code names and the run never opened is the
finding.

No band. An empty list does not mean the tests are good, so there is nothing here to grade;
the list is the finding. A suite that could not be run decides nothing, because a clean
result on a run that never happened is the failure this instrument exists to name.
"""

import ast
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

from l1_analyzer.boundary import boundary

OPENS_VARIABLE = "L1_OPENS_OUT"

# Directories whose contents are somebody else's code, or this run's own leavings. Named
# as directory NAMES rather than as pieces of text with slashes around them. Written with
# slashes, the filter was right for an absolute path and wrong for a relative one, and the
# walk here yields relative paths: the first run on this package reported five findings,
# every one of them a binary inside the virtual environment.
_NOT_THIS_REPOSITORY = frozenset({".venv", "venv", "node_modules", ".git", "__pycache__",
                                  ".pytest_cache", "site-packages", "build", "dist",
                                  ".mypy_cache", ".ruff_cache", "target"})


class Unopened(TypedDict):
    """What this check found, or why it could not look.

    `never_opened` is None when the suite could not be run, and a list otherwise. The two
    are different facts and a caller reading an empty list as "nothing to report" would be
    reading a run that never happened."""

    value: int | None
    band: str
    details: str
    never_opened: list[str] | None
    ambiguous: list[str]


def _ours(path: str) -> bool:
    """Whether a path is this repository's own code rather than a dependency's.

    By path component, so the answer is the same whether the caller spelled the path from
    the repository root or from the filesystem root. A directory merely NAMED like one of
    these, `venvtools`, is this repository's own."""
    return not (set(Path(path).parts) & _NOT_THIS_REPOSITORY)


def files_on_disk(repo: Path) -> tuple[set[str], dict[str, set[str]]]:
    """Every file in the repository, by path from the root and by bare name.

    Both, because a project spells the same file two ways. The code that reads it says
    `rules/business_rules.yaml` and the test that opens it says `business_rules.yaml`, so a
    reader that knew only the first would keep reporting a file after somebody fixed it. A
    measurement that does not move when the thing it measures is fixed teaches people to
    ignore it, which is worse than not measuring."""
    by_path: set[str] = set()
    by_name: dict[str, set[str]] = {}
    for found in repo.rglob("*"):
        if not found.is_file() or not _ours(str(found)):
            continue
        relative = str(found.relative_to(repo))
        by_path.add(relative)
        by_name.setdefault(found.name, set()).add(relative)
    return by_path, by_name


def names_a_file(text: str, by_path: set[str], by_name: dict[str, set[str]]) -> tuple[str, str]:
    """The file this string names, or the reason it names none or more than one.

    Every string is offered, whatever call it feeds. The path can be assembled anywhere: one
    adopter builds theirs from a default argument to an environment lookup sixty lines above
    the read, so a reader that followed the read found nothing. Crude collection and a strict
    filter beat precise collection and a loose one, because "is this a file in this
    repository" is answerable and "does this look like a path" is not.

    A bare name several files share is refused rather than guessed at."""
    if text in by_path:
        return text, ""
    sharing = by_name.get(text.rsplit("/", 1)[-1], set())
    if len(sharing) == 1:
        return next(iter(sharing)), ""
    if len(sharing) > 1:
        return "", f"{text} names {len(sharing)} files"
    return "", ""


def strings_in(source: str) -> set[str]:
    """Every string literal in one file, however it is used."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    return {n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and 0 < len(n.value) < 200 and "\n" not in n.value}


@boundary
def files_the_code_names(repo: Path) -> tuple[list[str], list[str]]:
    """Which files in this repository the production source names, and which names it
    refused to decide.

    Both, always. Written with a flag that chose between returning one list and returning
    two, it had a default, and this package's own check on implicit defaults said so: a
    default absorbs the caller's omission, and a flag that changes the SHAPE of the answer
    makes every caller read the signature to know what it got back.

    Test sources are left out: a file only the tests name is a fixture, and reporting it
    would ask an author to test their own fixture."""
    from l1_analyzer.scope import _test_file_by_name

    by_path, by_name = files_on_disk(repo)
    named: set[str] = set()
    ambiguous: set[str] = set()
    for source in repo.rglob("*.py"):
        if not _ours(str(source)) or _test_file_by_name(source):
            continue
        try:
            text = source.read_text(errors="ignore")
        except OSError:
            continue
        for literal in strings_in(text):
            found, why = names_a_file(literal, by_path, by_name)
            if why:
                ambiguous.add(literal)
            elif found:
                named.add(found)
    return sorted(named), sorted(ambiguous)


def opened_during(work: Callable[[], object], record: Path) -> set[str]:
    """Every file opened while `work` runs, watched by the interpreter rather than guessed.

    Used to test the watching itself. The suite runs in its own process, where the same hook
    is installed by the plugin and the answer comes back through a file."""
    seen: set[str] = set()

    def watch(event: str, arguments: tuple) -> None:
        if event == "open" and arguments and isinstance(arguments[0], str):
            seen.add(arguments[0])

    sys.addaudithook(watch)
    work()
    record.write_text(json.dumps(sorted(seen)))
    return seen


@boundary
def _run_the_suite(repo: Path, python_executable: str, record: Path,
                   timeout_seconds: float) -> tuple[bool, str]:
    """Run the suite with the watcher loaded, and say whether it ran.

    A suite that did not run is not a suite with nothing to report, so the reason comes back
    with the answer."""
    environment = {**os.environ, OPENS_VARIABLE: str(record)}
    try:
        finished = subprocess.run(
            [python_executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
             "-p", "l1_analyzer.unopened_files_plugin"],
            cwd=str(repo), env=environment, capture_output=True, text=True,
            timeout=timeout_seconds, check=False)
    except (OSError, subprocess.TimeoutExpired) as failure:
        return False, f"the suite could not be run: {failure}"
    if not record.exists():
        first = (finished.stderr or finished.stdout or "").strip().split("\n")[0]
        return False, f"the suite did not report what it opened (exit {finished.returncode}): {first}"
    return True, ""


def _refusal(why: str) -> Unopened:
    """No number and no list, because nothing was looked at."""
    return {"value": None, "band": "n/a", "details": why, "never_opened": None,
            "ambiguous": []}


def analyze(repo: Path, lang: str, python_executable: str,
            timeout_seconds: float) -> Unopened:
    """Files the production code names that the test run never opened.

    Python only for now. The watcher is an interpreter hook, and every other language needs
    its own; saying so beats reporting an empty list for eight languages nobody watched."""
    if lang != "python":
        return _refusal(f"the file watcher is written for Python and this is a {lang} "
                        "repository, so nothing here was watched")
    named, ambiguous = files_the_code_names(repo)
    if not named:
        return _refusal("the production code names no file that exists in this repository, "
                        "so there was nothing to watch for")
    record = repo / ".l1-opens.json"
    try:
        ran, why = _run_the_suite(repo, python_executable, record, timeout_seconds)
        if not ran:
            return _refusal(why)
        opened = {Path(p).resolve() for p in json.loads(record.read_text())}
    finally:
        record.unlink(missing_ok=True)
    never = sorted(n for n in named if (repo / n).resolve() not in opened)
    detail = (f"{len(never)} of {len(named)} file(s) the code names were never opened while "
              f"the suite ran; {len(ambiguous)} name(s) matched several files and were not "
              "decided")
    return {"value": len(never), "band": "n/a", "details": detail,
            "never_opened": never, "ambiguous": ambiguous}
