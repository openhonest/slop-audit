"""A whole-repository sweep proves one module at a time on a box with 24 idle cores.

It proves a module by appending a test to that module's own source file, compiling the
crate, running it, and putting the file back. Two workers in one checkout would restore each
other's files mid-compile, and cargo locks the target directory besides, so the loop is
serial by construction rather than by oversight.

The archived turso sweep was 176 modules and about 32 hours, nearly all of it in Rust
compiles. Batching the model requests took the asking off the wall clock and left the
compiles exactly where they were.

One checkout per worker is the way out, and the cost is disk: a turso checkout with a warm
target directory is 34 GB. On a filesystem that copies by reference, which is APFS here and
Btrfs or XFS with reflink on Linux, a copy costs almost nothing until something writes to
it. On any other filesystem it costs 34 GB a worker and the run has to say so rather than
fill somebody's disk quietly.

The pool is bounded by cores rather than by disk. A core-only turso checkout with a warm
target is 6 GB, so a 270 GB volume holds about 45 and about 22 if a sweep doubles the target
compiling test batches. Both are past any core count anyone is running, so disk is a check
somebody makes rather than the number to divide by.

Nothing here runs cargo. What is testable without a toolchain is the part that decides:
which modules go to which worker, how many workers the request and the work allow, and that
every module is dealt exactly once.
"""

from __future__ import annotations

import pytest
from l1_analyzer import coverage_prove, sweep_pool


def _modules(n: int) -> list[tuple[str, list[dict]]]:
    return [(f"src/m{i}.rs", [{"function": f"f{i}", "line": 1}]) for i in range(n)]


@pytest.mark.parametrize("modules,workers,expect", [
    (6, 1, [6]),
    (6, 2, [3, 3]),
    (6, 4, [2, 2, 1, 1]),
    (2, 4, [1, 1]),
    (0, 4, []),
])
def test_the_modules_are_dealt_round_robin(modules, workers, expect):
    """Round robin rather than contiguous blocks. A sweep's modules are in coverage order,
    which is roughly source order, and neighbouring modules in one crate take similar times
    to build; dealing them out keeps one worker from drawing every slow one."""
    shares = sweep_pool.share_out(_modules(modules), workers)
    assert [len(s) for s in shares] == expect


def test_every_module_is_dealt_exactly_once():
    """The property the dealing must not break. A module in two shares is proven twice and
    counted twice; a module in none is a gap nobody attempted while the ceiling counted it
    as spent."""
    work = _modules(17)
    dealt = [m for share in sweep_pool.share_out(work, 5) for m in share]
    assert sorted(m[0] for m in dealt) == sorted(m[0] for m in work)
    assert len(dealt) == len(work)


@pytest.mark.parametrize("asked,modules,expect", [
    (8, 100, 8),
    (8, 3, 3),
    (1, 100, 1),
    (100, 100, 100),
])
def test_no_more_workers_than_there_is_work(asked, modules, expect):
    """A worker with no module still costs a checkout. Asking for eight against three
    modules makes five copies of a repository to do nothing."""
    assert sweep_pool.workers_for(asked, modules) == expect


@pytest.mark.parametrize("asked", [0, -3])
def test_a_pool_of_nothing_is_refused_rather_than_read_as_one(asked):
    """Zero would run nothing and read as a sweep that found nothing. It raises."""
    with pytest.raises(ValueError):
        sweep_pool.workers_for(asked, 10)


def test_one_worker_is_the_default_a_caller_must_override():
    """A default that spends eight copies of somebody's disk without being asked is the
    same defect as a ratchet with a default: an omission absorbed rather than a choice
    made."""
    import inspect

    parameter = inspect.signature(coverage_prove.prove_coverage_repo).parameters["workers"]
    assert parameter.default is inspect.Parameter.empty, (
        "the pool size has a default, so a caller can spend the disk without choosing to")
