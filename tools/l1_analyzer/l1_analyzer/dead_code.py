"""L1.12 unreachable-code ratio, implemented natively on tree-sitter.

Canon (03-layer1-indicators.md, L1.12): "Lines of code flagged as unreachable or
unreferenced by a language-appropriate dead-code analyzer ... divided by total
production lines of code." Bands: <1% Healthy, 1-5% Not Healthy, >5% Slop.

The canon names a tool per language (vulture, ts-prune, staticcheck, error-prone,
rustc's dead_code lint, RuboCop). Requiring six ecosystems' toolchains at a client
site is not realistic, so this computes the same two categories directly:

  1. UNREACHABLE - a statement that follows a `return`, `raise`/`throw`, `break`,
     `continue` or `goto` inside the same block. Decidable from syntax alone, in every
     supported grammar, at full confidence.
  2. UNREFERENCED - a module-level definition whose name occurs nowhere else in the
     repository. Decidable only when nothing can reach the name by a route a syntactic
     scan cannot follow.

What this CANNOT do, stated once rather than hidden in the number: it does not resolve
types, so it cannot tell two same-named symbols apart; it does not follow dynamic
dispatch, reflection, or framework registration. Every definition a language or a
framework can reach by such a route is classified `undecidable`, listed with the reason,
and left OUT of the numerator. The published ratio is therefore a LOWER BOUND, and the
undecidable share is disclosed beside it. A dead-code pass that guesses in this region
reports its own blind spot as a defect in someone's code, which is the failure this
whole instrument exists to name.

Categories the reference tools report and this does not: unused imports and unused
local variables (vulture), unused struct fields (rustc), unused private types. Their
absence pushes the ratio down, never up.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import TypedDict

from tree_sitter import Node

from l1_analyzer.boundary import boundary, text_or_empty
from l1_analyzer.dead_code_corpus import (
    Corpus,
    _read_corpus,
    _repo_facts,
)
from l1_analyzer.dead_code_defs import (
    COLLECTORS,
    EXCLUDED,
    UNDECIDABLE,
    Definition,
)
from l1_analyzer.dead_code_grammars import _EXT_LANG, parser
from l1_analyzer.disclosure import listed_note
from l1_analyzer.scope import (
    PRODUCTION,
    _bucket_reason,
    _in_ignored_dir,
    _read_source_bytes,
    _repo_has_packages,
    _rglob_files,
)
from l1_analyzer.ts_nodes import descendants

_TOKEN_PASTING = b"##"


# One dead or undecidable definition, and the refusal this module returns when it cannot
# measure. Both were written `dict`, the least precise mapping the language has, and the
# key here is always a string.
class Site(TypedDict, total=False):
    """One definition the reader judged, and why it landed where it did.

    Five fields on every entry, and one of `reason` or `category` beside them: an
    undecidable or test-only site carries the sentence that explains it, a dead one carries
    the category that names it. Neither is present on the other, because inventing the
    missing one would be a blank nobody measured.

    It was `dict[str, object]`. Both line numbers were read back and added to, which was an
    assumption on a line that runs on every audit."""

    file: str
    name: str
    kind: str
    line: int
    end_line: int
    reason: str
    category: str


class DeadCodeRow(TypedDict):
    """L1.12's panel row: a band and a value, and the six readings behind it.

    Declared `dict[str, object]` while carrying ten fields, the same shape L1.21's row
    carried before it was written down. The findings are what makes the number readable, and
    the counts are what makes the denominator visible."""

    value: float | int | str
    band: str
    details: str
    findings: list[Site]
    undecidable: list[Site]
    test_only: list[Site]
    counts: dict[str, int]
    production_loc: int
    flagged_lines: int
    unreadable: int

# ---------------------------------------------------------------------------
# Category 1: unreachable statements
# ---------------------------------------------------------------------------

_BLOCK_TYPES: dict[str, frozenset[str]] = {
    "python": frozenset({"block"}),
    "rust": frozenset({"block"}),
    "c": frozenset({"compound_statement"}),
    "java": frozenset({"block"}),
    "typescript": frozenset({"statement_block"}),
    "javascript": frozenset({"statement_block"}),
    "csharp": frozenset({"block"}),
    "ruby": frozenset({"body_statement", "then", "else"}),
    "go": frozenset({"statement_list"}),
}

_TERMINATORS: dict[str, frozenset[str]] = {
    "python": frozenset({"return_statement", "raise_statement", "break_statement", "continue_statement"}),
    "rust": frozenset({"return_expression", "break_expression", "continue_expression"}),
    # `goto` is deliberately NOT a terminator in any of the three languages that have
    # one. Where a goto lands is a label that may sit anywhere below, including nested
    # inside a loop, and a sibling scan cannot see it. libuv's `uv_setup_args` does
    # exactly that - `goto loop;` jumps into the middle of a `for` - and treating the
    # goto as a terminator charged the whole loop as dead code.
    "c": frozenset({"return_statement", "break_statement", "continue_statement"}),
    "java": frozenset({"return_statement", "throw_statement", "break_statement", "continue_statement", "yield_statement"}),
    "typescript": frozenset({"return_statement", "throw_statement", "break_statement", "continue_statement"}),
    "javascript": frozenset({"return_statement", "throw_statement", "break_statement", "continue_statement"}),
    "csharp": frozenset({"return_statement", "throw_statement", "break_statement", "continue_statement"}),
    "ruby": frozenset({"return", "break", "next", "redo", "retry"}),
    "go": frozenset({"return_statement", "break_statement", "continue_statement"}),
}

# Node types that remain reachable after a terminator, so scanning of that block stops
# at the first one rather than charging everything below it.
#
# EVERY TYPE BELOW WAS OBSERVED IN THAT POSITION, and the test that says so is
# tests/test_dead_code_reachable_after.py: for each language it parses a fixture, finds the
# siblings that actually follow a terminator inside one of that language's _BLOCK_TYPES nodes,
# and fails on any row entry that never turns up. A type that cannot occupy the position
# cannot spare anything, and a row of such types reads as protection while doing nothing.
# Fifteen of the sixteen jump-target names here did exactly that until 2026-08-16, under a
# justification (libuv, below) that describes one language.
#
# WHY THE JUMP-TARGET NAMES WENT. A `case` below a `return` is entered from the switch, not
# from the statement above, so it must be spared - but only C spells a switch body with the
# same node it uses for every other block, `compound_statement`. libuv's `uv__close` has a
# `#if`-guarded `return` followed by `break`, and without C's row every remaining `case` in
# that switch, four of them, read as dead code. Every other grammar gives the arms a body node
# of their own: `switch_body` (javascript, typescript, C#), `switch_block` (java), `match_block`
# (rust), the `case` node itself (ruby), the switch statement itself (go), and in python a
# `block` whose only children are `case_clause`s. None of those can hold a terminator as a
# sibling of an arm, so the arm is never reached by the scan and never needs sparing. The rows
# naming `case_clause`, `match_arm`, `switch_label`, `switch_block_statement_group`,
# `switch_rule`, `switch_case`, `switch_default`, `switch_section`, `when`, `in_clause`,
# `expression_case`, `default_case`, `type_case` and `communication_case` are therefore gone.
# C's `case_statement` is the one that had to stay.
#
# WHAT A LABEL IS WORTH depends on whether the language has a `goto` that can jump forward
# into it. C, Go and C# do, so a label below a terminator there is a real entry point. Java,
# JavaScript and TypeScript label only for `break label` and `continue label`, both reached
# from INSIDE the labeled statement, so a label below a terminator in those three is genuinely
# dead and is now charged rather than spared.
#
# The rest are reachable for reasons of their own:
#  - A HOISTED DECLARATION. A JavaScript function declaration below a return is still
#    callable; a Rust item is in scope for the whole block whatever precedes it; a C
#    declaration still allocates and a label below it can reach it.
#  - A TYPE-ONLY DECLARATION. A TypeScript `interface` or `type` is erased before anything
#    runs, so it is never executable code and cannot be unreachable code.
#  - RUBY'S rescue / else / ensure, which are siblings of the return inside the method's own
#    `body_statement`. `ensure` runs precisely BECAUSE the return happened.
#  - A PREPROCESSOR DIRECTIVE, handled by the prefix rule below rather than by name.
#    Newtonsoft.Json writes `return default;` between a `#pragma warning disable` and its
#    matching `restore`, and the restore counted as unreachable code 28 times.
_REACHABLE_AFTER: dict[str, frozenset[str]] = {
    # Empty, and deliberately. Python has no goto, no hoisting and no arm the scan can reach:
    # a `def` or a `class` below a `return` never executes, so its name is never bound, and it
    # is dead by the same rule as any other statement. The row that named `case_clause` here
    # could not fire, so nothing in this table protected any Python code.
    "python": frozenset(),
    # Every item form, because a Rust item is scoped to the whole block and usable from above
    # its own position.
    "rust": frozenset({"function_item", "macro_definition", "struct_item", "enum_item",
                       "union_item", "const_item", "static_item", "type_item",
                       "use_declaration", "mod_item", "trait_item", "impl_item",
                       "foreign_mod_item"}),
    "c": frozenset({"labeled_statement", "declaration", "case_statement"}),
    "java": frozenset({"local_variable_declaration"}),
    "typescript": frozenset({"function_declaration", "class_declaration", "generator_function_declaration",
                             "interface_declaration", "type_alias_declaration"}),
    "javascript": frozenset({"function_declaration", "class_declaration", "generator_function_declaration"}),
    "csharp": frozenset({"labeled_statement", "local_function_statement"}),
    "ruby": frozenset({"method", "class", "module", "else", "rescue", "ensure"}),
    "go": frozenset({"labeled_statement"}),
}

# A preprocessor directive is not executable, so it is never unreachable CODE. Worse, a
# conditional one cuts across the syntax: libuv writes
#
#     if (0 != statfs(req->path, &buf))
#     #endif
#         return -1;
#
# and the `#endif` between the condition and its body detaches them in the parse, so the
# `return` reads as a plain statement of the enclosing block and everything below it reads
# as dead. That is not a fixable off-by-one; a linear sibling scan is simply unsound
# inside a conditionally compiled block. Such a block is therefore NOT SCANNED, which
# costs real findings and never invents one. Matched by prefix because every C-family
# grammar spells a dozen directives (`preproc_if`, `preproc_pragma`, ...).
_DIRECTIVE_PREFIX = "preproc"


def _conditionally_compiled(node: Node) -> bool:
    return any(child.type.startswith(_DIRECTIVE_PREFIX) for child in node.named_children)


def _skip_in_unreachable_scan(node_type: str) -> bool:
    """A comment carries no execution. JUnit writes `return 0L; // 0 = never failed` and
    the trailing comment was charged as an unreachable statement, so this matches every
    grammar's spelling (`comment`, `line_comment`, `block_comment`) rather than one."""
    return "comment" in node_type


class Unreachable(TypedDict):
    line: int
    end_line: int


def _is_terminator(node: Node, terminators: frozenset[str]) -> bool:
    """True for a terminator statement, in either grammar shape: the statement node
    itself (`return_statement`), or a wrapper holding one (Rust wraps `return_expression`
    in an `expression_statement`)."""
    if node.type in terminators:
        return True
    return (node.type == "expression_statement"
            and node.named_child_count > 0
            and node.named_children[0].type in terminators)


def _unreachable_statements(root: Node, lang: str) -> list[Unreachable]:
    """Every statement that follows a terminator in the same block. Full confidence:
    no reference, type or framework knowledge is involved."""
    blocks = _BLOCK_TYPES[lang]
    terminators = _TERMINATORS[lang]
    reachable_after = _REACHABLE_AFTER[lang]
    found: list[Unreachable] = []

    for node in descendants(root, "all"):
        if node.type not in blocks or _conditionally_compiled(node):
            continue
        seen_terminator = False
        for child in node.named_children:
            if _skip_in_unreachable_scan(child.type):
                continue
            if seen_terminator:
                if child.type in reachable_after:
                    break
                found.append({"line": child.start_point[0] + 1,
                              "end_line": child.end_point[0] + 1})
            elif _is_terminator(child, terminators):
                seen_terminator = True
    return found


# ---------------------------------------------------------------------------
# Pure classification
# ---------------------------------------------------------------------------

_SOFT_REASONS = (
    ("config", "named in a configuration file (an entry point can be wired by name)"),
    ("strings", "named in a string literal or comment (a dynamic reference cannot be resolved)"),
    ("docs", "named only in documentation (a documented symbol is a published surface)"),
)


def _has_module_level_call(body: str) -> bool:
    """Whether the module does work at import time, as opposed to declaring values.

    A bare call at module level (`main()`, `print(f())`) is a script running. An
    assignment whose value happens to be a call (`_WORD = re.compile(...)`) is a
    declaration, and so is a dispatch table naming forty functions. The difference is the
    statement kind, not whether a call appears.

    Read with the standard library parser rather than tree-sitter because this clause is
    Python-only, as the island rule above it is, and asking a second parser the same
    question is how two readers come to disagree about one file. A file this cannot parse
    is reported runnable, which under-accuses."""
    try:
        tree = ast.parse(body)
    except (SyntaxError, ValueError):
        return True
    return any(isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) for node in tree.body)


@boundary
def _runnable_islands(repo: Path, islands: frozenset[str], production_files: frozenset[str]) -> frozenset[str]:
    """The island modules that can actually be RUN, so their module level executes.

    A walk. Both decisions it used to make inline are functions below that touch nothing:
    which console scripts a manifest declares, and whether a module's own text says somebody
    can run it.

    This is the clause that decides whether seeding roots from module-level code is
    honest. An island is never imported, so its top level runs only if somebody runs the
    file. Three pieces of evidence say they can, and nothing else counts:

      a `if __name__ == "__main__"` guard, which is what a runnable module carries;
      a declared console script naming the module, read from pyproject;
      a module-level CALL statement, which is a script doing its work at import time;
      being the repository's only production module, which is a one-file program.

    The call-statement clause is the one that separates a script from a subsystem, and it
    is not the same as having module-level code. `TABLE = {"a": handler}` and
    `_WORD = re.compile(...)` are declarations: they build a value and bind it. `main()`
    and `print(f())` are work. Measured across this package, vacuity.py, cli.py and
    indicators.py each hold zero module-level call statements, while a nine-line script
    holds one.

    Without this, module-level code seeded roots in every island, and a module written in
    the dispatch-table style certified itself: name forty functions in a table at module
    level and all forty are roots. That is exactly the shape of this repository's own
    vacuity.py, 892 lines and 60 definitions, of which the island rule alone reached 58.
    It has no guard, no declared script and forty siblings, so nothing in it runs.

    cli.py is the control in the same tree: a guard AND a declared script, so it keeps its
    roots and stays alive."""
    if len(production_files) == 1:
        return islands
    declared = declared_scripts_in(text_or_empty(repo / "pyproject.toml"))
    runnable: set[str] = set()
    for relpath in islands:
        if relpath.rsplit("/", 1)[-1][:-3] in declared:
            runnable.add(relpath)
            continue
        try:
            body = (repo / relpath).read_text(encoding="utf8", errors="ignore")
        except OSError:
            runnable.add(relpath)      # unreadable: do not accuse on a file we could not open
            continue
        if can_be_run(body):
            runnable.add(relpath)
    return frozenset(runnable)


def declared_scripts_in(text: str) -> set[str]:
    """The module names a pyproject declares as console scripts.

    The last segment only: a script points at `package.module:function` and what matters
    here is which MODULE somebody can run."""
    return {match.group(1).rsplit(".", 1)[-1]
            for match in re.finditer(r'=\s*"([\w.]+):', text)}


def can_be_run(body: str) -> bool:
    """Whether this module's own text says somebody can run it.

    A `__main__` guard, which is what a runnable module carries, or a module-level CALL
    statement, which is a script doing its work at import time. A declaration is neither:
    `TABLE = {"a": handler}` builds a value and binds it. Without that distinction a module
    written in the dispatch-table style certified itself, because naming forty functions in
    a table at module level made all forty roots."""
    guarded = "__main__" in body and re.search(r'__name__\s*==\s*["\']__main__["\']', body)
    return bool(guarded) or _has_module_level_call(body)


def _owner_at(spans: list[tuple[int, int, str]], offset: int) -> str | None:
    """The innermost definition whose span holds `offset`, or None for module level.

    None is the answer that matters: a reference at module level runs when the file runs,
    so it is a root. A reference inside a definition only runs if that definition does."""
    owner, width = None, None
    for start, end, name in spans:
        if start <= offset < end and (width is None or end - start < width):
            owner, width = name, end - start
    return owner


def _sees(site: str, home: str, corpus: Corpus) -> bool:
    """Whether the file at `site` can see the module defined in `home`.

    The corpus maps a bare NAME to its reference sites and knows nothing about which
    module a reference resolves to, so any identifier anywhere in production kept a
    definition alive. `vacuity.py` is the case: correctly detected as an island, and zero
    of its sixty definitions reported, because `check` is also the name of a function in
    three unrelated modules and `render` in two more. Only names unique in the whole
    repository survived to be reported.

    A file sees a module when it names that module's stem as a real identifier, which is
    what `import m`, `from p import m` and `m.f()` all leave behind, or when it is that
    module. Read off the same hard-reference map as everything else here rather than by
    parsing imports a second way, so the two readings cannot drift apart.

    Asked ONLY about islands, where the question is already being put and where a wrong
    answer decides between reporting a subsystem and reporting nothing. Everywhere else
    the name-pooled behaviour stands, which under-accuses."""
    if site == home:
        return True
    stem = home.rsplit("/", 1)[-1][:-3] if home.endswith(".py") else home
    return any(where == site for where, _offset in corpus["hard"].get(stem, ()))


def _island_live_names(definitions: list[tuple[str, Definition]], corpus: Corpus,
                       production_files: frozenset[str], islands: frozenset[str],
                       runnable: frozenset[str]) -> set[str]:
    """Which definitions in the island modules are actually reachable.

    Reference is not reachability, and the difference is the whole defect. Two functions
    in a module nothing imports prove each other alive under a reference test, and a
    subsystem of forty prove each other alive forty times over. The roots are what runs:
    module-level code in an island file, which executes when the file does, and any
    reference from a production file that is NOT an island. From those roots this closes
    over references sitting inside a live definition's span, so a helper called by a live
    function stays live and a helper called only by a dead one does not.

    Names are global rather than per-file because the corpus's reference map is keyed by
    name, as every other rule here reads it. Two island modules holding a same-named
    function therefore rescue each other, which over-EXCUSES and is the direction this
    module takes when it cannot tell."""
    spans: dict[str, list[tuple[int, int, str]]] = {}
    for relpath, d in definitions:
        if relpath in islands:
            spans.setdefault(relpath, []).append((d["start_byte"], d["end_byte"], d["name"]))

    def sites(d: Definition, relpath: str):
        for site, offset in corpus["hard"].get(d["name"], ()):
            if site not in production_files:
                continue
            if site == relpath and d["start_byte"] <= offset < d["end_byte"]:
                continue          # the definition's own name token, or its recursion
            if not _sees(site, relpath, corpus):
                continue          # a same-named symbol in a module that cannot see this one
            yield site, offset

    live: set[str] = set()
    for relpath, d in definitions:
        if relpath not in islands:
            continue
        for site, offset in sites(d, relpath):
            if site not in islands or (site in runnable and _owner_at(spans.get(site, []), offset) is None):
                live.add(d["name"])
                break

    changed = True
    while changed:
        changed = False
        for relpath, d in definitions:
            if relpath not in islands or d["name"] in live:
                continue
            for site, offset in sites(d, relpath):
                if site in islands and _owner_at(spans.get(site, []), offset) in live:
                    live.add(d["name"])
                    changed = True
                    break
    return live


def _island_files(corpus: Corpus, production_files: frozenset[str]) -> frozenset[str]:
    """The production modules no OTHER production file names.

    A definition was proven alive by a reference from any production file, and the file it
    is defined in is a production file. So a module whose functions call each other
    certified its own contents, and the bigger the island the more thoroughly it did so.
    This repository is the case that found it: vacuity.py is 892 lines holding 40
    functions, its only importer is its own test, and L1.12 named two of the forty. The
    rest were alive because vacuity called vacuity.

    A module is named when its stem appears as a real identifier somewhere else in
    production, which is what `import m`, `from p import m` and `m.f()` all leave behind.
    Test references deliberately do NOT rescue it: a subsystem certified by its own tests
    plus itself is the same island one importer wider, and `test_only` already exists to
    report that shape honestly.

    Package initialisers and entry-point modules are never islands. `__init__` re-exports
    on behalf of a package and `__main__` is invoked rather than imported, so neither is
    named by a sibling even when the package is live.

    Language scope is Python, because the stem-equals-module-name rule is Python's. Every
    other language returns the empty set and keeps the old behaviour, which under-accuses
    rather than over-accuses and says so here rather than by omission."""
    loaded = _modules_named_by_a_dotted_string(corpus, production_files)
    islands = set()
    for relpath in production_files:
        if not relpath.endswith(".py"):
            continue
        stem = relpath.rsplit("/", 1)[-1][:-3]
        if stem in ("__init__", "__main__") or relpath in loaded:
            continue
        sites = corpus["hard"].get(stem, ())
        if not any(site in production_files and site != relpath for site, _offset in sites):
            islands.add(relpath)
    return frozenset(islands)


def _loaded_reason(relpath: str, loaded: frozenset[str]) -> str:
    """Why a definition in a module loaded by name cannot be called dead.

    The reader knows the module runs, because something in the tree names its path in a
    string and hands that to a framework. What it cannot know is which of its functions the
    framework calls: pytest calls every `pytest_` hook it finds, celery calls the task, a
    server calls the factory, and none of those calls is written down anywhere the parser
    can read.

    Undecidable, which is the same answer this module gives everywhere it can see that
    something is happening without seeing what. Excluding these outright would claim they
    all run, and flagging them claims none of them does."""
    if relpath not in loaded:
        return ""
    return ("in a module loaded by name from a string (a framework calls into it without "
            "an import)")


def _modules_named_by_a_dotted_string(corpus: Corpus,
                                      production_files: frozenset[str]) -> frozenset[str]:
    """The files a dotted string in this repository loads, which nothing imports.

    A framework hook is registered by a name in a string: `-p pkg.plugin`, a task called
    `pkg.tasks.run`, a server started from `app.main:create_app`. The module is real and it
    really runs, and no import statement anywhere leads to it, so the island rule above
    reads it and every function in it as unreachable.

    The string is RESOLVED against the repository's own files rather than pattern-matched,
    which is what stops the rule from becoming "any string with a dot in it". A version
    number, a filename and a sentence ending in a full stop are all dotted strings, and none
    of them names a file in the tree.

    Found on 2026-08-31 by this reader flagging the file-open watcher this package loads
    exactly that way. The finding was false and one line from its own caller."""
    loaded: set[str] = set()
    for dotted in corpus["words"]["dotted"]:
        # A suffix match, because an import path is relative to a package root and a package
        # root is not the repository root. This package lives at tools/l1_analyzer, so
        # `l1_analyzer.unopened_files_plugin` names a file three directories down, and an
        # anchored match found it when the audit ran from inside the package and lost it
        # when the same audit ran from the repository above.
        tail = dotted.replace(".", "/") + ".py"
        loaded.update(f for f in production_files
                      if f == tail or f.endswith("/" + tail))
    return frozenset(loaded)


def _referenced_from(definition: Definition, relpath: str, corpus: Corpus,
                     files: frozenset[str]) -> bool:
    """True when the name has a real identifier use in one of `files`, outside the
    definition's own span. Excluding its own span is what stops a self-recursive call,
    or the name token itself, from proving the definition alive.

"""
    for site_path, offset in corpus["hard"].get(definition["name"], ()):
        if site_path not in files:
            continue
        if site_path == relpath and definition["start_byte"] <= offset < definition["end_byte"]:
            continue
        return True
    return False


def _soft_reason(name: str, corpus: Corpus) -> str:
    for bucket, reason in _SOFT_REASONS:
        if name in corpus["words"][bucket]:
            return reason
    return ""


def _band_for(percent: float) -> str:
    """The canon's three bands: <1% Healthy, 1-5% Not Healthy, >5% Slop."""
    from l1_analyzer.indicators import band
    return band(percent, 1, 5, higher_is_better=False)


# ---------------------------------------------------------------------------
# Boundary
# ---------------------------------------------------------------------------

_CAP = 100

# The share of a language's production files the grammar must parse before a ratio is
# publishable. Measured, not chosen from taste: python, java, rust, go and javascript parse
# at 100% on the validation corpus, typescript at 98% and C# at 84-93%, while C parses at
# 34% (json-c) and 59% (libuv) because tree-sitter runs no preprocessor and real C hides
# its declarations behind export macros. A dead-code ratio over a third of a codebase is
# not a ratio for that codebase, so C reports n/a with the count instead of a number.
_MIN_PARSED_SHARE = 0.8


def _na(reason: str) -> DeadCodeRow:
    """The row for a repository this reader will not measure, with the reason.

    Every field the measured path writes, so a reader indexing the row cannot be handed a
    KeyError by a refusal. `unreadable` was missing here and present there, which is exactly
    that: nine fields on the refusal and ten on the measurement, and nothing said so."""
    return {"value": "n/a", "band": "n/a", "details": reason, "findings": [],
            "undecidable": [], "test_only": [], "counts": {}, "production_loc": 0,
            "flagged_lines": 0, "unreadable": 0}


def _classify_files(repo: Path) -> tuple[frozenset[str], frozenset[str]]:
    """Split every file in the repository into production reference sites and test
    reference sites. A definition reached only from the test tree is not dead - the
    tests call it - but it is not load-bearing production code either, so it is
    reported separately rather than folded into either verdict."""
    has_packages = _repo_has_packages(repo)
    production: set[str] = set()
    tests: set[str] = set()
    for path in _rglob_files(repo, "*"):
        if _in_ignored_dir(path, ()):
            continue
        relpath = str(path.relative_to(repo)) if repo in path.parents else path.name
        reason = _bucket_reason(path, repo, has_packages, PRODUCTION)
        (tests if reason in ("tests", "test") else production).add(relpath)
    return frozenset(production), frozenset(tests)


def analyze(repo: Path, lang: str) -> DeadCodeRow:
    """L1.12 for one repository. Returns the ratio, the band, the two finding lists,
    and the undecidable disclosure that makes the ratio readable as a lower bound."""
    if lang not in COLLECTORS:
        return _na(f"no native dead-code analysis for {lang}; the canon's tool for it is not wired")

    extensions = tuple(ext for ext, (_g, key) in _EXT_LANG.items() if key == lang)
    sources, unreadable = _read_source_bytes(repo, extensions, scope=PRODUCTION)
    if not sources:
        return _na(f"no production {lang} source in scope")

    facts = _repo_facts(repo, lang)
    if facts["ruby_metaprogramming"]:
        return _na("not measured for ruby: the repository uses runtime metaprogramming "
                   f"({facts['ruby_metaprogramming']}), so an unreferenced name is not "
                   "evidence of dead code")

    production_files, test_files = _classify_files(repo)
    corpus = _read_corpus(repo)

    production_loc = analyzed_loc = 0
    definitions: list[tuple[str, Definition]] = []
    unreachable: list[Site] = []
    unparsed = pasted = 0
    for path, src in sources:
        relpath = str(path.relative_to(repo)) if repo in path.parents else path.name
        production_loc += len(src.splitlines())
        analyzed_loc += len(src.splitlines())
        grammar, _key = _EXT_LANG[path.suffix.lower()]
        root = parser(grammar).parse(src).root_node
        # A tree the grammar could not parse cannot support a claim about what it
        # contains. Newtonsoft.Json's JValue.cs parses with ERROR nodes and the statements
        # around them read as unreachable, sixteen of them. The file's identifiers are
        # still harvested as references by _read_corpus, which can only spare a symbol,
        # never condemn one.
        if root.has_error:
            unparsed += 1
            analyzed_loc -= len(src.splitlines())
            continue
        # C builds function names with the preprocessor. libuv writes
        # `#define XX(uc, lc) case UV_FS_##uc: fs__##lc(req); break;`, so `fs__rmdir` is
        # called at a site where that name never appears. Twenty-eight of libuv's
        # findings were this. No syntactic scan can follow a pasted name, so a file that
        # pastes has its definitions disclosed as undecidable instead.
        if _TOKEN_PASTING in src and lang == "c":
            pasted += 1
            definitions.extend(
                (relpath, {**d, "status": UNDECIDABLE,
                           "reason": "the file builds identifiers with preprocessor token "
                                     "pasting (##), so a call site need not spell this name"})
                for d in COLLECTORS[lang](root, src, relpath, facts))
            continue
        definitions.extend((relpath, d) for d in COLLECTORS[lang](root, src, relpath, facts))
        unreachable.extend(
            {"file": relpath, "name": "", "kind": "statement", "category": "unreachable", **u}
            for u in _unreachable_statements(root, lang))

    parsed_share = (len(sources) - unparsed) / len(sources)
    if parsed_share < _MIN_PARSED_SHARE:
        return _na(
            f"not measured for {lang}: the grammar parsed only {parsed_share:.0%} of the "
            f"{len(sources)} production file(s) ({unparsed} failed), which is below the "
            f"{_MIN_PARSED_SHARE:.0%} floor this indicator needs. tree-sitter does not run "
            "a preprocessor, so macro-decorated declarations and #if regions do not parse; "
            "a ratio computed over the remainder would describe a different codebase")

    loaded = _modules_named_by_a_dotted_string(corpus, production_files)
    islands = _island_files(corpus, production_files) if lang == "python" else frozenset()
    runnable = _runnable_islands(repo, islands, production_files)
    island_live = _island_live_names(definitions, corpus, production_files, islands, runnable)
    dead: list[Site] = []
    undecidable: list[Site] = []
    test_only: list[Site] = []
    excluded = 0
    for relpath, definition in definitions:
        entry: Site = {"file": relpath, "name": definition["name"],
                       "kind": definition["kind"], "line": definition["line"],
                       "end_line": definition["end_line"]}
        if definition["status"] == EXCLUDED:
            excluded += 1
        elif definition["status"] == UNDECIDABLE:
            undecidable.append({**entry, "reason": definition["reason"]})
        # An island definition that nothing reaches has no production reference worth
        # consulting: the references it has are its neighbours', and its neighbours are
        # unreachable too. It falls through to the same tail as any other unreferenced
        # definition, so a test consumer still reports test_only and a config entry point
        # still reports undecidable. An earlier draft appended it straight to `dead` and
        # stole both of those cases.
        elif ((relpath not in islands or definition["name"] in island_live)
              and _referenced_from(definition, relpath, corpus, production_files)):
            continue
        elif _referenced_from(definition, relpath, corpus, test_files):
            test_only.append({**entry, "reason": "referenced only from the test tree"})
        else:
            reason = _loaded_reason(relpath, loaded) or _soft_reason(definition["name"], corpus)
            if reason:
                undecidable.append({**entry, "reason": reason})
            else:
                dead.append({**entry, "category": "unreferenced"})

    # Read as numbers because that is what they are. The entries carry line numbers under a
    # declaration that said nothing about their type, so adding one to the end line was an
    # assumption at a line that runs on every audit.
    flagged = {(f["file"], line)
               for f in dead + unreachable
               for line in range(int(f["line"]), int(f["end_line"]) + 1)}
    if not production_loc:
        # 0.0 here bands Healthy, so a tree with no lines to measure published "no dead
        # code" over a measurement that never happened. Same shape as the L1.4 and L1.5
        # empty denominators fixed on 2026-08-18, and found by vacuity.check.
        return _na(f"no production {lang} lines to measure: {len(definitions)} definition(s) "
                   "were read but the files carry no countable code")
    percent = round(len(flagged) / production_loc * 100, 2)
    counts = {"unreferenced": len(dead), "unreachable": len(unreachable),
              "undecidable": len(undecidable), "test_only": len(test_only),
              "entry_points": excluded, "definitions": len(definitions),
              "files_unparsed": unparsed, "files_token_pasting": pasted}
    details = (
        f"{len(flagged)} flagged line(s) of {production_loc} production {lang} LOC "
        f"({analyzed_loc} of them analyzed) "
        f"({len(dead)} unreferenced definition(s), {len(unreachable)} unreachable statement(s)); "
        f"{len(undecidable)} definition(s) undecidable and excluded from the numerator, "
        f"{len(test_only)} referenced only by tests, {excluded} runtime entry point(s); "
        "lower bound - dynamic dispatch, reflection and framework registration are not resolved"
    )
    if unparsed:
        details += f"; {unparsed} file(s) the grammar could not parse, not analyzed"
    if pasted:
        details += f"; {pasted} file(s) use preprocessor token pasting, definitions undecidable"
    if corpus["unreadable"]:
        details += f"; {corpus['unreadable']} file(s) unreadable or oversized and excluded"
    # Three lists share one cap, so the note names the largest of them: a reader told the
    # findings were cut knows to check the others rather than trust their lengths.
    details += listed_note(_CAP, max(len(dead) + len(unreachable),
                                                    len(undecidable), len(test_only)))
    return {
        "value": percent,
        "band": _band_for(percent),
        "details": details,
        "findings": sorted(dead + unreachable, key=lambda f: (f["file"], f["line"]))[:_CAP],
        "undecidable": sorted(undecidable, key=lambda f: (f["file"], f["line"]))[:_CAP],
        "test_only": sorted(test_only, key=lambda f: (f["file"], f["line"]))[:_CAP],
        "counts": counts,
        "production_loc": production_loc,
        "flagged_lines": len(flagged),
        "unreadable": unreadable,
    }
