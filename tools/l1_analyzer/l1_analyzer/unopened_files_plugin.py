"""The pytest plugin that records every file the suite opens.

A real module rather than source in a string, for the reason the other probe plugin gives:
code no tool can measure is the shape this instrument exists to name.

It is loaded with `-p l1_analyzer.unopened_files_plugin` and told where to write through one
environment variable, because a pytest plugin has no other way to take an argument.

The hook is installed in `pytest_configure`, before collection, so a file opened while a test
module is imported is counted. An audit hook cannot be removed once installed, which is why
the recording is per process and the process is the suite's own.
"""

import json
import os
import sys

from l1_analyzer.boundary import boundary
from l1_analyzer.unopened_files import OPENS_VARIABLE

STASH = "_l1_opened"


def watcher(seen: set) -> object:
    """The hook the interpreter calls on every open, given somewhere to record it.

    Takes its store rather than reaching for one. A module-level set would be shared mutable
    state, which this project's own state check reports, in the tool that measures it."""

    def watch(event: str, arguments: tuple) -> None:
        if event == "open" and arguments and isinstance(arguments[0], str):
            seen.add(arguments[0])

    return watch


def pytest_configure(config: object) -> None:
    """Watch from before collection, so a file opened at import time is counted."""
    seen: set[str] = set()
    setattr(config, STASH, seen)
    sys.addaudithook(watcher(seen))


def pytest_unconfigure(config: object) -> None:
    """Hand back what was opened. A run killed before this point reports nothing, and the
    caller reads that as a run it could not watch rather than as a suite that opened no
    files."""
    write_opened(getattr(config, STASH, set()), os.environ.get(OPENS_VARIABLE, ""))


@boundary
def write_opened(seen: set[str], destination: str) -> bool:
    """Write what was opened where the caller asked, and say whether it did.

    No destination means nobody asked to watch this run. The plugin is registered by name,
    so it also loads in runs that are not audits, and writing to a path from a previous one
    would overwrite one answer with another."""
    if not destination:
        return False
    with open(destination, "w") as handle:
        json.dump(sorted(seen), handle)
    return True
