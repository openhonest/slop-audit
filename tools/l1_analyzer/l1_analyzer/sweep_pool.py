"""How a whole-repository sweep runs on more than one core.

A module is proven by appending a test to that module's own source file, compiling the
crate, running it, and putting the file back. Two workers in one checkout would restore each
other's files mid-compile, and cargo locks the target directory besides, so parallelism here
is a question about directories rather than about threads.

Nothing here knows what a proof is or how one is judged. It decides how many workers there
will be, which modules each takes, where each one works, and what the run says it cost.

The pool is bounded by cores rather than by disk. A core-only turso checkout with a warm
target is 6 GB, so a 270 GB volume holds about 45 of them and about 22 if a sweep doubles
the target compiling test batches. Both are past any core count anyone is running, so disk
is a check somebody makes rather than the number to divide by. That correction came from the
session auditing turso on 2026-09-07, who had quoted 34 GB from a different box and went and
measured the one the sweep would run on.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import TypedDict

from l1_analyzer.boundary import boundary
from l1_analyzer.rust_facets import CoverageGap


def workers_for(asked: int, modules: int) -> int:
    """How many workers this sweep will actually run.

    Never more than there is work for: a worker with no module still costs a checkout, so
    asking for eight against three modules would make five copies of a repository to do
    nothing.

    A pool of nothing raises. Zero would run nothing and report it as a sweep that found
    nothing, which is the reading this instrument exists to refuse."""
    if asked <= 0:
        raise ValueError(f"a pool of {asked} workers would prove nothing and report it as "
                         "a sweep that found nothing")
    return min(asked, modules) if modules else asked


def share_out(work: list[tuple[str, list[CoverageGap]]],
              workers: int) -> list[list[tuple[str, list[CoverageGap]]]]:
    """The modules each worker will prove, dealt round robin.

    Round robin rather than contiguous blocks. The work arrives in coverage order, which is
    roughly source order, and neighbouring modules in one crate take similar times to build;
    dealing them out keeps one worker from drawing every slow one.

    Every module is dealt exactly once. A module in two shares is proven twice and counted
    twice, and one in no share is a gap nobody attempted while the ceiling counted it as
    spent."""
    shares: list[list[tuple[str, list[CoverageGap]]]] = [[] for _ in range(workers)]
    for at, module in enumerate(work):
        shares[at % workers].append(module)
    return [share for share in shares if share] if work else []


class Checkouts(TypedDict):
    """The directories a sweep's workers will prove in, and what making them cost."""
    paths: list[Path]
    copies: int
    how: str
    # How many were asked for. A sweep that wanted eight and got two must not read like one
    # that asked for two.
    asked: int


@boundary
def checkouts_for(repo: Path, workers: int, root: Path) -> Checkouts:
    """One directory per worker, the first being the repository itself.

    The sweep proves a module by appending a test to that module's own source file,
    compiling, and putting the file back. Two workers in one checkout would restore each
    other's files mid-compile, and cargo locks the target directory besides, so parallelism
    needs isolation rather than a thread pool.

    No copy for a single worker: copying a checkout to hand it back to itself would cost the
    disk for nothing, and the restore-in-place path is the one that has always run.

    Every worker gets a copy once there is more than one, the first included, so a parallel
    sweep never edits the repository under audit. A module is proven by appending a test to
    its own source file and putting the file back, and a hard kill skips the putting back.
    One killed serial sweep left one modified file somebody found by hand; eight workers
    would leave up to eight, in eight directories, and nobody would know which. A copy is
    disposable by construction, so an interrupt leaves nothing to clean up.

    The cost is disk and it depends on the filesystem. A turso checkout with a warm target
    directory is 34 GB; APFS here and Btrfs or XFS with reflink on Linux copy by reference,
    so the copy is nearly free until something writes to it, and any other filesystem pays
    34 GB a worker. Which one happened is recorded, because eight workers is a good trade on
    the first and a quarter of a terabyte on the second, and a reader told only the number
    cannot tell them apart."""
    if workers <= 1:
        return {"paths": [repo], "copies": 0, "how": "no copy needed", "asked": workers}
    paths: list[Path] = []
    root.mkdir(parents=True, exist_ok=True)
    how = ""
    for n in range(workers):
        made = copy_checkout(repo, root / f"worker-{n}")
        if not made:
            # A copy that will not be made costs a worker, not the run. On a filesystem
            # without reflink, eight copies of a 6 GB checkout is 48 GB of real bytes, and
            # that fails in ways the free copy does not: disk pressure, no space left half
            # way through the sixth worker. This used to raise, and by the time the pool is
            # made the sweep has already asked a model for every proposal, so the traceback
            # threw away the expensive half.
            break
        how = made
        paths.append(root / f"worker-{n}")
    if not paths:
        # No workers would be a sweep that proved nothing and reported it as one that found
        # nothing. The floor is the repository itself, proven in place as a serial sweep
        # always was.
        return {"paths": [repo], "copies": 0, "how": "no copy could be made", "asked": workers}
    return {"paths": paths, "copies": len(paths), "how": how, "asked": workers}


# Every way this package knows to copy a tree, each with the sentence its success earns.
# Ordered: the ones that share blocks and refuse when they cannot, then the plain copy that
# always works and never shares. A command that may silently fall back cannot be in this
# list, because its success proves nothing about which of the two happened.
COPY_COMMANDS: tuple[tuple[list[str], str], ...] = (
    (["cp", "-Rc", "{from}", "{to}"], "by reference"),
    (["cp", "-R", "--reflink=always", "{from}", "{to}"], "by reference"),
    (["cp", "-R", "{from}", "{to}"], "byte for byte"),
)


def copy_commands(source: str, destination: str) -> list[tuple[list[str], str]]:
    """The copy commands to try, in order, each with what its success would prove."""
    return [([part.format(**{"from": source, "to": destination}) for part in command], how)
            for command, how in COPY_COMMANDS]


@boundary
def copy_checkout(repo: Path, destination: Path) -> str:
    """One copy of the repository, and how it was made, or nothing when it could not be.

    Each command carries the sentence its success earns, and only a command that REFUSES
    when it cannot share blocks earns "by reference". `cp --reflink=auto` does not: it falls
    back to a full copy and exits 0 either way, so reading its exit status as proof of
    sharing made the report say "copied by reference" over 48 GB of real bytes on ext4.
    Measured on 2026-09-07: a 100 MB directory, exit 0, 102,404K of disk gone. The run
    before that spelling was added said "byte for byte" and was right.

    `--reflink=always` is the spelling that refuses, and `-c` is its macOS equivalent. A
    filesystem that says no falls through to the plain copy and is reported as the plain
    copy.

    The destination is cleared first, every time. A copy that died part way leaves a
    directory behind, and the next thing tried against it fails because the directory
    exists, which reports that instead of the real cause and sends the reader to the wrong
    problem."""
    shutil.rmtree(destination, ignore_errors=True)
    for command, name in copy_commands(str(repo), str(destination)):
        # check=False: a refused flag is the answer this loop is asking for, and the next
        # command is the fallback.
        if subprocess.run(command, capture_output=True, check=False).returncode == 0:
            return name
        shutil.rmtree(destination, ignore_errors=True)
    return _copy_tree(repo, destination)


@boundary
def _copy_tree(repo: Path, destination: Path) -> str:
    """The last resort, where no cp on this machine would do it.

    Nothing rather than a raise, for the reason the caller gives: a sweep that has already
    bought every proposal must not be thrown away because one directory would not copy."""
    try:
        shutil.copytree(repo, destination)
    except OSError:
        shutil.rmtree(destination, ignore_errors=True)
        return ""
    return "byte for byte"


@boundary
def discard_checkouts(made: Checkouts) -> None:
    """Remove every checkout this sweep copied, and never the repository.

    A single-worker sweep copied nothing and its one path is the repository, which is why
    the count is what this reads rather than the list. A worker's copy left behind after a
    32-hour sweep is 34 GB somebody has to find."""
    if not made["copies"]:
        return
    for path in made["paths"]:
        shutil.rmtree(path, ignore_errors=True)


def pool_detail(workers: int, copies: int, how: str, asked: int) -> str:
    """What the run says about the pool it used.

    Said whether or not it is one, because a sweep that wanted eight workers and got one
    must not read like a sweep that asked for one."""
    hands = "1 worker" if workers == 1 else f"{workers} workers"
    short = (f" {asked} were asked for and the rest could not be made." if asked > workers
             else "")
    if not copies:
        return f" Proven by {hands}, in the repository itself.{short}"
    made = "1 checkout" if copies == 1 else f"{copies} checkouts"
    return (f" Proven by {hands}, each in its own checkout: {made} copied {how}, and the "
            f"repository itself was never edited.{short}")
