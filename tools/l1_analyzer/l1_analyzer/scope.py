"""Audit scope: which files are in the measurement, and which are set aside and why.

Extracted from indicators.py, which crossed the 1000-line god-file threshold that this
package's own L1.17 enforces on itself. The split is not arbitrary: every function here
answers one question, "is this file part of the code under audit", and every indicator
that measures source consults them.

The scope rule decides what the instrument can see, which makes it the one place where a
subject can change the score without changing the artifact. See _test_dir_corroborated.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

from l1_analyzer.boundary import boundary

# The .NET and JVM file convention, in its original casing. Also used by L1.8.
_TEST_STEM_SUFFIXES = ("Test", "Tests", "Spec", "Specs")

_IGNORE_DIRS = frozenset({
    ".git", "node_modules", "venv", ".venv", "env", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".eggs",
    "site-packages", "target", "build", "dist", "vendor",
})

# The two markers that name a test directory. Everything else in an `extra` scope-out
# tuple is matched on the nose; these two are also matched case-insensitively and as a
# dotted suffix, because C# names a test project `<Project>.Tests` and an exact match
# never catches `Src/Newtonsoft.Json.Tests/`. Until this existed, every C# repository's
# whole test tree was measured as production code by L1.15, L1.17, L1.19 and the
# absolute-path check (Newtonsoft.Json reported 31 absolute paths, all of them stack-
# trace fixture data). Deliberately this narrow: "spec", "fixtures" and the rest are
# not test-directory conventions in the languages this scope covers.
_TEST_DIR_MARKERS = frozenset({"test", "tests"})


# ---------------------------------------------------------------------------
# Named measurement scopes
# ---------------------------------------------------------------------------
#
# A scope is the set of directory names an indicator removes from its measurement. It
# used to travel as a bare tuple argument, and sixteen call sites decided their scope from
# a tuple written beside them: eight spelled ("tests", "test") out in full, five reached
# ("tests", "test", "conformance") through three separately defined module constants, and
# three passed (). The tuple had no name, so nothing in the package recorded which
# indicators shared it, and a change to a rule underneath it could not be reviewed
# against a list of what it would move.
#
# That is not hypothetical. Commit 2aff645 added the corroboration rule below to close
# one hole; it moved the published numbers of eight indicators, and the eight were
# knowable only by reading every call site. The scope is now named, each indicator
# declares one, and `indicators` is the list the change had no way to produce.
#
# The list is a claim, so it is measured rather than trusted: tests/test_scope_policy.py
# flips one directory from not-corroborated to corroborated and asserts that the set of
# panel entries that move is exactly the set declared here. An indicator that starts
# reading a scope without being declared under it fails the suite.
PRODUCTION = "production"
PRODUCTION_WITHOUT_CONFORMANCE = "production-without-conformance"
WHOLE_REPO = "whole-repo"


class Scope(TypedDict):
    """One named measurement scope: the directory names it removes, and every indicator
    measured under it. `indicators` names panel keys, plus any consumer that publishes a
    number without being a panel entry (the CLI gate's type-escape ratchet).

    `buckets` names which of the three judgment-call exclusions this scope makes: docs,
    tooling, root-script. They were unconditional, so a scope could not decline them, and
    the reader that had to decline them implemented the whole rule a second time instead.
    Vendored trees and machine output are not listed because no scope may decline those:
    neither is anybody's code here, whatever the question being asked."""
    excludes: tuple[str, ...]
    buckets: tuple[str, ...]
    indicators: tuple[str, ...]


SCOPES: dict[str, Scope] = {
    # The code under audit. A test tree is not the artifact being graded, and a check
    # that fires on its own fixtures measures the fixtures: this repo's own tests carried
    # 24 of 57 absolute-path findings on the run that prompted the scope fix.
    PRODUCTION: {
        "excludes": ("tests", "test"),
        "buckets": ("docs", "tooling", "root-script"),
        # L1.12 measures dead code in production source and divides by production LOC, and
        # it splits its reference sites into production and test so a symbol only the
        # tests call is disclosed rather than called dead. L1.14 counts the whole tree,
        # the way `gitleaks --no-git` does, but splits the count the same way: a fixture
        # credential and a production credential are not the same finding to an auditor.
        # Both read this rule, so both are declared here. L1.13 joined them on 2026-08-19
        # when it stopped shelling out to jscpd: it now reads production source and divides
        # by production LOC, and a duplication figure that counted the test tree would
        # measure the fixtures, which repeat by design.
        "indicators": ("L1.12", "L1.13", "L1.14", "L1.15", "L1.18", "L1.19", "path_cover",
                       "absolute_paths", "gate:type-escapes"),
    },
    # The same, and conformance/ as well. A conformance directory holds law and spec
    # scaffolding and test doubles (fault-injection markers, failing connections), so it
    # is production neither for the state meters nor for the god-file count: nobody
    # hand-piles logic into an append-only conformance table.
    PRODUCTION_WITHOUT_CONFORMANCE: {
        "excludes": ("tests", "test", "conformance"),
        "buckets": ("docs", "tooling", "root-script"),
        "indicators": ("L1.17", "L1.18b", "thread_surface"),
    },
    # Everything, tests included, because for these three the test tree IS the subject:
    # L1.8 is the ratio of test lines to production lines, L1.16 asks whether the
    # repository's whitespace is disciplined anywhere, and interleaving robustness asks
    # which files carry a model-checker harness.
    WHOLE_REPO: {
        "excludes": (),
        # None of the three, because under this name they are the subject. L1.8 is the
        # ratio of test lines to production lines and L1.16 asks whether the whitespace is
        # disciplined anywhere, so a reading that skipped the docs, the tooling files and
        # the loose scripts would answer a narrower question under the wider question's
        # name. This is what the second reader was working around by rewriting the rule.
        "buckets": (),
        "indicators": ("L1.8", "L1.16", "interleaving_robustness"),
    },
}


def scope_rule(name: str) -> Scope:
    """The whole rule for one named scope: the directory names it removes, the judgment-call
    exclusions it makes, and the indicators measured under it.

    KeyError on a name that is not in SCOPES, which is the point of routing every reader
    through here: an indicator cannot quietly measure under a scope that nobody wrote down
    and no test knows to check.

    One function rather than one accessor per field. Two of those were two names over a
    single lookup, which this package's own conformity check reads as one shape, and it is
    right: naming the field at the call site says which part of the rule is being read."""
    return SCOPES[name]


# A directory NAMED like a test directory is believed only if its contents corroborate
# the claim. Without this, renaming a production package to `Core.Tests` removes it from
# every indicator declared under PRODUCTION and PRODUCTION_WITHOUT_CONFORMANCE above,
# and flips `--gate` from fail to pass, with zero bytes of code changed. The
# instrument's primary consumer is an AI, which optimises exactly what it is told to
# optimise, so a scope rule that reads a free-to-forge name is an instruction to rename.
#
# Corroboration is one-directional on purpose: a directory that fails to corroborate is
# MEASURED, never dropped. A false negative can only add code to the audit, so the rule
# itself cannot be turned into a cheaper score.
_TEST_FRAMEWORK_MARKERS = (
    "import pytest", "import unittest", "from unittest", "@pytest",
    "org.junit", "org.testng", "using Xunit", "using NUnit",
    "Microsoft.VisualStudio.TestTools", "[TestMethod]", "[Fact]", "@Test",
    '"testing"', "#[test]", "#[cfg(test)]",
    "require 'rspec'", 'require "rspec"', "minitest", "describe(",
    "from vitest", "require('mocha')",
)

_TEST_MARKER_WINDOW = 4096       # a framework import sits at the top of a file
_GENERATED_WINDOW = 2048         # so does a toolchain's banner


# honest-code-allow: L1.21.9 - measured, not argued. One walk of this project's test tree costs 1.8ms over 464 entries and it is called once per file scoped underneath it, so uncached that one directory costs 464 walks and the cost grows as the square of the tree. test_a_cache_earns_its_place_or_goes.py measures the margin and fails if it stops holding. The sibling cache on the tree-sitter parser was measured the same way, found to save milliseconds across a whole audit, and deleted.
@boundary
@lru_cache(maxsize=4096)
def _test_dir_corroborated(directory: Path) -> bool:
    """True when a directory named like a test directory actually holds test code.

    Corroborated by a test-file name (the L1.8 conventions) or a test-framework marker in
    a file's first 4 KiB. Cached per directory: the answer is a pure function of the tree,
    and the cache stops one rglob per file underneath it."""
    try:
        entries = list(directory.rglob("*"))
    # honest-code-allow: L1.21.8 - an unreadable directory falls through to being audited as production rather than scoped out, which is the conservative direction: it can only add files to a measurement, never silently remove them
    except OSError:
        return False
    for f in entries:
        if not f.is_file():
            continue
        # By FILE NAME only. _is_test_file also believes a path component, so using it
        # here would let a renamed directory corroborate itself, which is the exact
        # circularity this function exists to break.
        if _test_file_by_name(f):
            return True
        if head_carries_any(boundary_in_file_head(f, _TEST_MARKER_WINDOW), _TEST_FRAMEWORK_MARKERS):
            return True
    return False


def head_carries_any(head: str, markers: tuple[str, ...]) -> bool:
    """Whether any of `markers` appears in the opening text of a file.

    This module asks that of a header twice: does it name a test framework, and did a tool
    claim to have written the file. Those were two functions with one body. Naming them
    apart did not make them two questions, so there is one function and the caller brings
    the table. Lifted out of the walk above, which is a boundary; this is the question it
    asks of each file, and it could not be asked there without a directory to walk."""
    return any(marker in head for marker in markers)


def _test_file_by_name(path: Path) -> bool:
    """The file-name half of _is_test_file: test_x, x_test.ext, x.spec.ext, XTests.cs.
    Deliberately excludes the path-component arm, so this cannot be satisfied by the
    directory name under examination."""
    name = path.name.lower()
    suffix = path.suffix.lower()
    stem = path.stem.lower()
    # Hyphen as well as underscore: libuv writes test/test-tcp-open.c and carries no
    # framework import at all, so a rule that knew only test_ and _test would fail to
    # corroborate a genuine test tree and start measuring it as production.
    return (name.startswith(("test_", "test-", "test."))
            or stem.endswith(("_test", "-test", ".test", ".spec", "_spec", "-spec"))
            or name.endswith((".test" + suffix, ".spec" + suffix))
            or path.stem.endswith(_TEST_STEM_SUFFIXES))


def _claiming_dir(path: Path, component: str) -> Path | None:
    """The ancestor directory of `path` whose own name is `component`."""
    for parent in path.parents:
        if parent.name == component:
            return parent
    return None


def _component_scoped_out(component: str, marker: str) -> bool:
    """True when one path component is scoped out by `marker`. Exact for a general
    marker; for a test marker, `Tests`, `tests`, `Foo.Tests` and `Foo.Test` all count."""
    if component == marker:
        return True
    if marker not in _TEST_DIR_MARKERS:
        return False
    lowered = component.lower()
    return lowered == marker or lowered.endswith("." + marker)


def _extra_reason(parts: Iterable[str], extra: tuple[str, ...], path: Path | None) -> str | None:
    """The first `extra` marker any path component is scoped out by, or None.

    Given `path`, a TEST marker must also be corroborated by the claiming directory's
    contents. Other markers, `conformance` and the rest, still match on the name alone."""
    parts = tuple(parts)
    for marker in extra:
        for component in parts:
            if not _component_scoped_out(component, marker):
                continue
            if marker in _TEST_DIR_MARKERS and path is not None:
                claiming = _claiming_dir(path, component)
                if claiming is not None and not _test_dir_corroborated(claiming):
                    continue
            return marker
    return None


def _in_ignored_dir(path: Path, extra: tuple[str, ...]) -> bool:
    """True if any path component is a vendored/tooling dir (or one of `extra`)."""
    parts = set(path.parts)
    return bool(parts & _IGNORE_DIRS) or _extra_reason(parts, extra, path) is not None


def under_symlinked_dir(path: Path, root: Path) -> bool:
    """True when `path` is, or sits under, a symlinked directory below `root`.

    BY DECISION, NOT BY VERSION. The two tools agreed on symlinked trees by coincidence:
    pathlib's `**` stopped following symlinked directories in Python 3.13, and walkdir,
    which the Rust port uses, has never followed them. A run under 3.12 would descend into
    a tree the port skips and the panels would diverge on any repository that has one.

    The decision is the one already written for nested checkouts a few lines down:
    measuring a tree that is not in this commit reports code the commit does not carry. A
    symlinked directory points at exactly that, and it can point at itself.

    A symlinked FILE is unaffected. `is_file()` follows symlinks deliberately, and one file
    is not a tree."""
    current = path
    while True:
        if current == root or root not in current.parents:
            return current != root and current.is_symlink() and current.is_dir()
        if current.is_symlink() and current.is_dir():
            return True
        current = current.parent


def _rglob_files(repo: Path, pattern: str) -> Iterator[Path]:
    """Every FILE under `repo` matching `pattern`. The single entry point for every
    scan in this module, so no reader has to remember what `rglob` yields.

    `Path.rglob` yields directories as well as files, so a directory whose name ends in
    a source extension (node_modules/decimal.js is a real one) used to reach a reader,
    raise IsADirectoryError, and be disclosed as "1 file(s) unreadable and excluded".
    It is not a file and it is not unreadable, so that disclosure was false. A directory
    is now neither measured nor counted. `is_file()` follows symlinks, so a symlinked
    source file is still read, and a file the process may not read still reaches the
    reader and is still disclosed as unreadable.

    A nested checkout is also skipped. A directory below the root that carries its own
    `.git` is a different repository with its own history and its own audit: a submodule
    working copy, a vendored clone, or a git worktree. Measuring it reports code that is
    not in this commit. The tool caught this on itself: an agent's worktree under
    `.claude/worktrees/` held an older checkout of this repository, and the gate charged
    eleven type escapes that existed only in that second copy.

    `.git` is a directory in a clone and a FILE in a worktree, so the test is existence,
    not is_dir. The root's own `.git` is not consulted, or every scan would be empty."""
    root_resolved = repo.resolve()
    inside_nested: dict[Path, bool] = {}

    def under_nested_checkout(directory: Path) -> bool:
        """True when `directory` is, or sits under, a nested checkout. Memoised per call
        so each directory is stat-ed once however many files it holds."""
        cached = inside_nested.get(directory)
        if cached is not None:
            return cached
        if directory == root_resolved or root_resolved not in directory.parents:
            result = False
        elif (directory / ".git").exists():
            result = True
        else:
            result = under_nested_checkout(directory.parent)
        inside_nested[directory] = result
        return result

    return (
        p for p in repo.rglob(pattern)
        if p.is_file()
        and not under_symlinked_dir(p.parent, repo)
        and not under_nested_checkout(p.parent.resolve())
    )


# Conventional build/test/dev tooling recognised by filename, not by directory.
#
# `hatch_build.py` joins them for the same reason the rest are here: a build tool reads it
# and calls what it finds, and the program never does. Hatchling discovers the hook class by
# scanning the module for a subclass of its interface, so nothing in the source references
# it and the dead-code reader was right to say so and wrong to count it.
_TOOLING_FILES = frozenset({"setup.py", "noxfile.py", "conftest.py", "tasks.py", "manage.py",
                            "hatch_build.py"})

# Strong, low-false-positive sentinels that machine-generated source carries in its
# header: the machine-readable @generated convention (tree-sitter and many others),
# the Go convention ("// Code generated by ... DO NOT EDIT."), and the protobuf
# banner. Such a file is nobody's authored code: it is regenerated from a grammar or
# a schema, so every number an audit puts on it describes the generator instead of
# the repository. Read by _bucket_reason, which is the one scope every indicator uses.
_GENERATED_MARKERS = ("@generated", "Code generated by", "Generated by the protocol buffer compiler")


def boundary_in_file_head(path: Path, window: int) -> str:
    """Read the first `window` bytes of a file as text, and decide nothing. An unreadable
    file yields the empty string, which every caller reads as a header carrying no marker:
    the file falls through to normal scope and is audited rather than skipped.

    The window is named by the caller rather than defaulted, because the two questions this
    module asks of a header look at different amounts of it, and a default would hide which
    one a reader is getting."""
    try:
        return path.read_bytes()[:window].decode("utf8", errors="ignore")
    # honest-code-allow: L1.21.8 - an unreadable file is reported as an empty head, which is the conservative direction and is stated in the docstring above
    except OSError:
        return ""


def _is_generated(path: Path) -> bool:
    """Whether a tool declared itself the author of this file, read from its header. Only
    the header is offered to the question, so a hand-written file mentioning the convention
    deep in its prose is unaffected."""
    return head_carries_any(boundary_in_file_head(path, _GENERATED_WINDOW), _GENERATED_MARKERS)


def _is_machine_output(path: Path) -> bool:
    """True if a tool wrote this file rather than a person: it declares itself generated
    in its header, or it is a minified bundle. One function so the two call sites below
    cannot drift into disagreeing about what machine output is."""
    return path.name.endswith((".min.js", ".min.css")) or _is_generated(path)


def _repo_has_packages(repo: Path) -> bool:
    """True if the repo is organised into importable packages (any __init__.py).
    Used to tell a loose dev/entry-point script from a flat script-only repo.

    Vendored directories are skipped and nothing else is: this is a question about the
    repository's layout, not a measurement, so it takes no scope. Scoping out a test tree
    here would answer "is this repo packaged" with "is its production code packaged",
    which is a different question and would misclassify a packaged test-only repo."""
    return any(not _in_ignored_dir(f, ()) for f in _rglob_files(repo, "__init__.py"))


def _bucket_reason(path: Path, repo: Path, has_packages: bool, scope: str) -> str | None:
    """Why this source file is scoped out of the audit, or None to keep it. General
    and structural: it references no specific project. Disclosed, never silent."""
    parts = set(path.parts)
    if parts & _IGNORE_DIRS:
        return "vendored"
    rule = scope_rule(scope)
    reason = _extra_reason(parts, rule["excludes"], path)
    if reason is not None:
        return reason
    calls = rule["buckets"]
    if "docs" in calls and "docs" in parts:
        return "docs"
    if "tooling" in calls and path.name in _TOOLING_FILES:
        return "tooling"
    # Machine output is not the author's code. Measuring its mutable state, its type
    # escapes or its conformity reports on a code generator nobody in this repository
    # wrote. The marker is the toolchain's own declaration, read from the header only.
    if _is_machine_output(path):
        return "generated"
    # A loose top-level .py sitting beside packages (its own dir is not a package,
    # and the repo does have packages) is a dev/entry-point script, not the library.
    # A flat, script-only repo (no packages anywhere) keeps its root scripts: they
    # are the code.
    if ("root-script" in calls and has_packages and path.parent == repo
            and not (repo / "__init__.py").exists()):
        return "root-script"
    return None


def _read_source_bytes(repo: Path, extensions: tuple[str, ...], scope: str) -> tuple[list[tuple[Path, bytes]], int]:
    """Read every source file with one of `extensions` as bytes, excluding files scoped
    out under `scope` (see _bucket_reason). Returns the files read and the number
    unreadable. `scope` is a name from SCOPES, never a tuple: the caller declares which
    measurement it belongs to and the table records that it does."""
    files: list[tuple[Path, bytes]] = []
    skipped = 0
    has_packages = _repo_has_packages(repo)
    for ext in extensions:
        for f in _rglob_files(repo, f"*{ext}"):
            if _bucket_reason(f, repo, has_packages, scope) is not None:
                continue
            try:
                files.append((f, f.read_bytes()))
            except OSError:
                skipped += 1
    return files, skipped


class BucketedPath(TypedDict):
    """One scoped-out file and the reason it was scoped out."""
    path: str
    reason: str


class BucketedPaths(TypedDict):
    """The scope disclosure: a count per reason, and the judgment-call exclusions listed
    file by file. Typed, not dict[str, Any]: the shape is fixed, so a key typo is a type
    error rather than a KeyError in the report writer."""
    counts: dict[str, int]
    paths: list[BucketedPath]


def bucketed_paths(repo: Path, extensions: tuple[str, ...], scope: str) -> BucketedPaths:
    """The source files scoped out of the audit, with the reason for each, so a
    reader sees exactly what was not looked at and can challenge it (the cone of
    light on the meter's own choice of scope). `counts` covers every reason; `paths`
    lists the judgment-call exclusions (docs / tooling / loose root scripts) that a
    reader most needs to see, since over-bucketing a real entry point would hide
    behind a silent skip otherwise. Vendored dependencies are counted, not listed."""
    has_packages = _repo_has_packages(repo)
    counts: dict[str, int] = {}
    paths: list[BucketedPath] = []
    for ext in extensions:
        for f in _rglob_files(repo, f"*{ext}"):
            reason = _bucket_reason(f, repo, has_packages, scope)
            if reason is None:
                continue
            counts[reason] = counts.get(reason, 0) + 1
            if reason in ("docs", "tooling", "root-script"):
                rel = str(f.relative_to(repo)) if repo in f.parents else str(f)
                paths.append({"path": rel, "reason": reason})
    return {"counts": counts, "paths": sorted(paths, key=lambda d: d["path"])}

def _read_text_files(repo: Path, extensions: frozenset[str], scope: str) -> tuple[list[tuple[Path, str]], int]:
    """Read every file whose suffix is in `extensions` as text, under the named `scope`.
    Returns the files read and the number that could not be read.

    Machine output is dropped here as it is in _bucket_reason, reading the same marker
    through the same function. The two are separate call sites because this reader
    honours only the scope's ignored directories, where _bucket_reason also buckets
    docs, tooling and loose root scripts; folding them together would change what the
    whole-repository indicators measure, which is a different question from this one."""
    files: list[tuple[Path, str]] = []
    skipped = 0
    has_packages = _repo_has_packages(repo)
    for f in _rglob_files(repo, "*"):
        if f.suffix.lower() not in extensions:
            continue
        if _bucket_reason(f, repo, has_packages, scope) is not None:
            continue
        try:
            files.append((f, f.read_text(errors="ignore")))
        except OSError:
            skipped += 1
    return files, skipped

# ---------------------------------------------------------------------------
# Git-based (L1.1-L1.8) - language agnostic
# ---------------------------------------------------------------------------
