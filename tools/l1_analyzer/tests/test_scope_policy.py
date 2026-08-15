"""One scope rule, eight indicators, and nothing that said so.

The scope readers took the directories to scope out as a bare tuple argument, and sixteen
call sites decided their scope from a tuple written beside them: eight spelled
`("tests", "test")` out in full, five reached `("tests", "test", "conformance")` through
three separately defined module constants, and three passed `()`. The tuple carried no
name, so nothing in the package recorded which indicators shared it. Commit 2aff645
changed the corroboration rule that decides whether a test-named directory really holds
tests. It was written for one indicator and it moved the published numbers of eight, and
no test could have said so.

The measured shape of the coupling: a `tests/` directory holding 300 `Any` annotations.
Without a test-framework marker the directory does not corroborate its own name, is
measured as production, and L1.15 reports the escapes inside it. Adding one line,
`import pytest`, corroborates the name, removes the directory from the production scope,
and drops the count. One import line, and no change to any production byte, moves eight
indicators.

The guard below measures that reach instead of trusting a comment about it. It flips one
directory from not-corroborated to corroborated and asserts that the set of indicators
whose panel entry moves is exactly the set `scope.SCOPES` declares. An indicator that
starts reading a scope rule without being declared under it fails this test, which is the
failure 2aff645 did not have.

What it does not see, said plainly. The guard watches ONE rule, the one that decides
whether a directory named like a test directory is believed. A scope edit that touches
nothing else the fixture contains, such as adding a new marker to a scope's `excludes`,
moves nothing here and passes. The runtime half of L1.19, L1.20, and the external-tool
indicators L1.12 to L1.14 read no scope at all and are outside its reach either way.
"""

from __future__ import annotations

import json
from pathlib import Path

from l1_analyzer import indicators, scope

# Enough probe functions that the test tree is over 1k lines, so L1.17 (god files) is in
# the flip as well as the density indicators. Each probe carries one `Any` and one `if`.
_PROBES = 300

_NOT_A_MARKER = "import os"      # an ordinary import: the directory stays uncorroborated
_A_MARKER = "import pytest"      # one of _TEST_FRAMEWORK_MARKERS: the claim is corroborated

# One trailing space, written as a constant so no editor or linter strips it out of the
# fixture. It is here because a guard can only see an indicator that the fixture makes
# move: L1.16 counts trailing whitespace and is declared under the whole-repo scope, and
# without a whitespace defect inside the test tree it reads 0.0 either way, so L1.16
# quietly joining a test-excluding scope would leave no trace for this test to catch.
# Verified by mutation: point L1.16 at the production scope and the guard fails.
_TRAILING_WS = " "


def _make_repo(root: Path, first_line: str) -> Path:
    """A repo with one production package and one directory named `tests/`.

    `first_line` is the ONLY difference between the two builds, and both builds are the
    same number of lines. That matters: an extra line would move the whole-repo
    indicators (L1.16 reads every file, tests included) for a reason that has nothing to
    do with scope, and the guard would then be asserting against noise.

    No file under `tests/` is named like a test file, so the directory's name is
    corroborated by content or not at all."""
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "__init__.py").write_text("")
    (root / "pkg" / "core.py").write_text(
        "from typing import Any\n"
        "\n"
        "REGISTRY = {}\n"
        "\n"
        "def register(key, value: Any) -> None:\n"
        "    REGISTRY[key] = value\n"
        "\n"
        "def pick(flag):\n"
        "    if flag:\n"
        "        return 1\n"
        "    return 0\n"
    )

    lines = [
        first_line,
        "from typing import Any",
        "",
        "CACHE = {}",
        'ROOT = "/Users/fixture/checkout"',
        "",
        "def collect(items=[]):",
        "    return items",
        "",
        "def store(key, value: Any):",
        "    CACHE[key] = value",
        "",
    ]
    for i in range(_PROBES):
        lines += [f"def probe_{i}(flag) -> Any:", "    if flag:", f"        return {i}",
                  "    return 0" + _TRAILING_WS, ""]
    (root / "tests").mkdir()
    (root / "tests" / "suite.py").write_text("\n".join(lines) + "\n")
    return root


def _panel(repo: Path) -> dict:
    """The source panel a real run publishes. `exec_tests=False` keeps the runtime
    indicators out (they run the target's suite); every scope-reading indicator is
    static and is present either way."""
    return indicators.compute_source_indicators(
        repo, lang="python", exec_tests=False, timeout_seconds=5.0, classify_state_bounds=True
    )


def _moved(before: dict, after: dict) -> set[str]:
    """Panel keys whose published entry is not identical. The whole entry, not just
    `value`: a scope change that moves only the count inside `details` has still moved a
    published number, and a guard that read `value` alone would miss it."""
    keys = set(before) | set(after)
    return {
        k for k in keys
        if json.dumps(before.get(k), sort_keys=True, default=str)
        != json.dumps(after.get(k), sort_keys=True, default=str)
    }


def _declared_test_scope_indicators() -> set[str]:
    """Every indicator declared under a scope that removes test directories.

    The caller intersects this with the panel's own keys, because one declared consumer is
    not a panel entry: the CLI's `--gate` recomputes L1.15's raw count under the production
    scope, and is declared as `gate:type-escapes`. The intersection still catches a
    misspelled id, because the misspelling drops out while the indicator it meant to name
    goes on moving, and the equality fails on the extra."""
    return {
        indicator
        for policy in scope.SCOPES.values()
        if set(policy["excludes"]) & scope._TEST_DIR_MARKERS
        for indicator in policy["indicators"]
    }


def test_one_import_line_moves_the_type_escape_count(tmp_path):
    """The defect, reproduced. The production code is byte-identical in both builds; the
    only edit is one import inside a directory named `tests/`. L1.15 is a density, so
    read the raw escape count out of `details`, which is the number the CLI gate ratchets
    on."""
    measured = _panel(_make_repo(tmp_path / "measured", _NOT_A_MARKER))
    excluded = _panel(_make_repo(tmp_path / "excluded", _A_MARKER))

    escapes_measured = int(measured["L1.15"]["details"].split()[0])
    escapes_excluded = int(excluded["L1.15"]["details"].split()[0])

    # 300 probe annotations, plus the test tree's own `Any` import and its one annotated
    # parameter: all of them invisible once the directory corroborates its name.
    assert escapes_measured - escapes_excluded == _PROBES + 2
    assert escapes_excluded == 2      # the import and the annotation in the production package


def test_the_scope_table_names_every_indicator_the_test_directory_rule_moves(tmp_path):
    """The guard. Flip one directory from not-corroborated to corroborated and compare
    the indicators that actually move against the indicators the table says measure under
    a test-excluding scope.

    Equality in both directions is deliberate. A moved indicator missing from the table is
    the 2aff645 failure: a scope change silently republishing a number nobody reviewed. A
    declared indicator that does not move is a stale claim, which would let the first
    failure back in the next time someone trusts the list."""
    measured = _panel(_make_repo(tmp_path / "measured", _NOT_A_MARKER))
    excluded = _panel(_make_repo(tmp_path / "excluded", _A_MARKER))

    moved = _moved(measured, excluded)
    declared = _declared_test_scope_indicators()

    assert moved == declared & set(measured)


def test_a_whole_repo_indicator_does_not_move_when_a_test_directory_is_scoped_out(tmp_path):
    """The other half of the claim: an indicator declared under the whole-repo scope reads
    the test tree in both builds, so the corroboration rule cannot touch it. Asserted
    separately from the guard because a fixture bug that silently changed the test tree's
    line count would satisfy the guard's equality and quietly break this one."""
    measured = _panel(_make_repo(tmp_path / "measured", _NOT_A_MARKER))
    excluded = _panel(_make_repo(tmp_path / "excluded", _A_MARKER))

    assert measured["L1.16"] == excluded["L1.16"]
