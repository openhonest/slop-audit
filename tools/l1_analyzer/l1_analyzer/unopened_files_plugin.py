"""The pytest plugin that records every file the suite opens.

A real module rather than source in a string, for the reason the other probe plugin gives:
code no tool can measure is the shape this instrument exists to name.

It is loaded with `-p l1_analyzer.unopened_files_plugin` and told where to write through one
environment variable, because a pytest plugin has no other way to take an argument.

The hook is installed in `pytest_configure`, before collection, so a file opened while a test
module is imported is counted. An audit hook cannot be removed once installed, which is why
the recording is per process and the process is the suite's own.
"""

import os
import sys
from collections.abc import Callable

from l1_analyzer import probe_record
from l1_analyzer.unopened_files import OPENS_VARIABLE

STASH = "_l1_opened"


def watcher(seen: set[str]) -> Callable[[str, tuple[object, ...]], None]:
    """The hook the interpreter calls on every open, given somewhere to record it.

    Takes its store rather than reaching for one. A module-level set would be shared mutable
    state, which this project's own state check reports, in the tool that measures it."""

    def watch(event: str, arguments: tuple[object, ...]) -> None:
        if event == "open" and arguments and isinstance(arguments[0], str):
            seen.add(arguments[0])

    return watch


def pytest_configure(config: object) -> None:
    """Watch from before collection, so a file opened at import time is counted."""
    seen: set[str] = set()
    setattr(config, STASH, seen)
    sys.addaudithook(watcher(seen))


def pytest_unconfigure(config: object) -> None:
    """Hand back what was opened, and write nothing at all when nothing was watched.

    A run killed before this point writes no file, and the caller reads a missing file as a
    run it could not watch rather than as a suite that opened nothing. That distinction is
    the whole reading, and it lives in `probe_record` now: this function and its twin in
    `runtime_probe_plugin` broke it the same way, defaulting an absent record to empty, and
    were fixed the same day. One copy since 2026-09-01.

    Sorted, because the caller compares this against a listing of the tree and against the
    run before it. An unsettled order would report changes nobody made."""
    probe_record.hand_back(config, STASH, os.environ.get(OPENS_VARIABLE, ""), sorted)
