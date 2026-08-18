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

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

import tree_sitter_c
import tree_sitter_c_sharp
import tree_sitter_go
import tree_sitter_java
import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_ruby
import tree_sitter_rust
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

from l1_analyzer.dead_code_defs import (
    COLLECTORS,
    EXCLUDED,
    UNDECIDABLE,
    Definition,
    RepoFacts,
)
from l1_analyzer.scope import (
    PRODUCTION,
    _bucket_reason,
    _in_ignored_dir,
    _read_source_bytes,
    _repo_has_packages,
    _rglob_files,
)

# ---------------------------------------------------------------------------
# Grammars. Local to this module, NOT indicators.LANG_CFG, because .tsx needs the
# JSX grammar: parsing a React component with the plain TypeScript grammar loses every
# `<Component/>` use site and would report live components as dead. LANG_CFG is shared
# with L1.15/L1.17/L1.18/L1.19, so it is not the place to change a grammar choice.
# ---------------------------------------------------------------------------

_GRAMMARS = {
    "python": lambda: tree_sitter_python.language(),
    "rust": lambda: tree_sitter_rust.language(),
    "c": lambda: tree_sitter_c.language(),
    "java": lambda: tree_sitter_java.language(),
    "typescript": lambda: tree_sitter_typescript.language_typescript(),
    "tsx": lambda: tree_sitter_typescript.language_tsx(),
    "csharp": lambda: tree_sitter_c_sharp.language(),
    "javascript": lambda: tree_sitter_javascript.language(),
    "ruby": lambda: tree_sitter_ruby.language(),
    "go": lambda: tree_sitter_go.language(),
}

# Extension -> (grammar key, language key). The language key is the collector to run;
# the grammar key is the parser to run it on, and the two differ only for .tsx.
_EXT_LANG: dict[str, tuple[str, str]] = {
    ".py": ("python", "python"),
    ".rs": ("rust", "rust"),
    ".c": ("c", "c"), ".h": ("c", "c"),
    ".java": ("java", "java"),
    ".ts": ("typescript", "typescript"), ".tsx": ("tsx", "typescript"),
    ".cs": ("csharp", "csharp"),
    ".js": ("javascript", "javascript"), ".jsx": ("javascript", "javascript"),
    ".mjs": ("javascript", "javascript"), ".cjs": ("javascript", "javascript"),
    ".rb": ("ruby", "ruby"),
    ".go": ("go", "go"),
}

@lru_cache(maxsize=len(_GRAMMARS))
def _parser(grammar: str) -> Parser:
    """One parser per grammar, built on first use. Cached through `lru_cache` rather than
    a module-level dict a function writes into: this package's own L1.18 counts a written
    module global as external mutable state, and it caught the dict version of this."""
    return Parser(Language(_GRAMMARS[grammar]()))


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

    def walk(node: Node) -> None:
        if node.type in blocks and not _conditionally_compiled(node):
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
        for child in node.children:
            walk(child)

    walk(root)
    return found


# ---------------------------------------------------------------------------
# Category 2: the reference corpus
# ---------------------------------------------------------------------------

_IDENT_EXTRA = frozenset({"identifier", "constant"})
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_DOC_EXTS = frozenset({".md", ".rst", ".txt", ".adoc", ".org"})
_MAX_BYTES = 1_048_576
_METAPROGRAMMING = ("define_method", "method_missing", "const_get", "instance_variable_get",
                    "class_eval", "instance_eval", "ActiveRecord", "ActiveSupport")
_TOKEN_PASTING = b"##"


class Corpus(TypedDict):
    """Every name occurrence the classifier can consult.

    The three word buckets live in one dict rather than as three fields because every
    reader of them picks a bucket by NAME at runtime: the harvester chooses docs or config
    from a file extension, and _soft_reason walks _SOFT_REASONS in priority order. Three
    TypedDict fields cannot be indexed by a variable, and the version of this that had
    them needed two `# type: ignore[literal-required]` to compile. A bucket chosen at
    runtime is data, so it is keyed like data.
    """
    hard: dict[str, list[tuple[str, int]]]   # name -> [(relpath, byte offset)] of real identifier uses
    words: dict[str, set[str]]               # bucket -> words: strings, config, docs
    unreadable: int


def _is_identifier_leaf(node: Node) -> bool:
    return node.child_count == 0 and (node.type in _IDENT_EXTRA or node.type.endswith("_identifier"))


def _string_reference_names(node: Node) -> set[str]:
    """The names a string literal could be RESOLVING, which is not every word it holds.

    This collected every word of every string and comment, and a hit exempts a definition
    as "a dynamic reference cannot be resolved". So a dead function whose name appeared in
    any docstring anywhere in the repository was excluded from the numerator, and the
    exemption written for `getattr(o, "f")` was satisfied by prose about `f`.

    A string is a candidate reference when the WHOLE string is one identifier, which is
    what `getattr(o, "f")` and `REGISTRY["f"]` look like. A string carrying the name among
    other words is prose and carries no lookup. The quote characters are children of the
    string node in every grammar in the table, so the content is read from the named
    children rather than by trimming quotes this reader would have to know the spelling of.

    Comments no longer reach here at all. A comment carries no execution, which is the
    reason `_is_comment` gives twenty lines up for not charging a trailing comment as an
    unreachable statement, and the same fact makes a comment incapable of being the
    dynamic reference this exemption exists for.

    This narrows an exemption, so it can only ACCUSE code the old rule excused. That is the
    direction that needed the corpus run recorded in the commit, not a quiet landing."""
    parts = [c for c in node.named_children if "content" in c.type or c.type == "string_content"]
    text = "".join(c.text.decode("utf8", errors="ignore") for c in parts if c.text) if parts else (
        node.text.decode("utf8", errors="ignore") if node.text else "")
    stripped = text.strip()
    return {stripped} if _WORD.fullmatch(stripped) else set()


def _harvest_source(root: Node, relpath: str, corpus: Corpus) -> None:
    def walk(node: Node) -> None:
        if _is_identifier_leaf(node):
            name = node.text.decode("utf8", errors="ignore") if node.text else ""
            corpus["hard"].setdefault(name, []).append((relpath, node.start_byte))
        elif "string" in node.type:
            corpus["words"]["strings"].update(_string_reference_names(node))
        for child in node.children:
            walk(child)

    walk(root)


def _read_corpus(repo: Path) -> Corpus:
    """Boundary reader. Every file in the repository is a possible reference site: a
    sibling module, a test, a CI workflow that names an entry point, a README. Vendored
    and ignored directories are skipped; unreadable and oversized files are counted and
    disclosed, never silently dropped."""
    corpus: Corpus = {"hard": {}, "words": {"strings": set(), "config": set(), "docs": set()},
                      "unreadable": 0}
    for path in _rglob_files(repo, "*"):
        if _in_ignored_dir(path, ()):
            continue
        relpath = str(path.relative_to(repo)) if repo in path.parents else path.name
        try:
            if path.stat().st_size > _MAX_BYTES:
                corpus["unreadable"] += 1
                continue
            raw = path.read_bytes()
        except OSError:
            corpus["unreadable"] += 1
            continue
        if b"\0" in raw[:8192]:
            continue
        entry = _EXT_LANG.get(path.suffix.lower())
        if entry is not None:
            _harvest_source(_parser(entry[0]).parse(raw).root_node, relpath, corpus)
        else:
            words = _WORD.findall(raw.decode("utf8", errors="ignore"))
            bucket = "docs" if path.suffix.lower() in _DOC_EXTS else "config"
            corpus["words"][bucket].update(words)
    return corpus


def _repo_facts(repo: Path, lang: str) -> RepoFacts:
    """The three repository-level questions a single file cannot answer."""
    rust_is_library = (repo / "src" / "lib.rs").exists() or any(
        True for _ in _rglob_files(repo, "lib.rs"))
    entries: set[str] = set()
    for manifest in _rglob_files(repo, "package.json"):
        if _in_ignored_dir(manifest, ()):
            continue
        try:
            data = json.loads(manifest.read_text(errors="ignore"))
        except (OSError, ValueError):
            continue
        base = manifest.parent
        for key in ("main", "module", "browser", "types", "typings"):
            value = data.get(key)
            if isinstance(value, str):
                entries.add(str((base / value).relative_to(repo)))
        for value in (data.get("bin") or {}).values() if isinstance(data.get("bin"), dict) else ():
            if isinstance(value, str):
                entries.add(str((base / value).relative_to(repo)))
    marker = ""
    if lang == "ruby":
        for path in _rglob_files(repo, "*.rb"):
            if _in_ignored_dir(path, ()):
                continue
            try:
                text = path.read_text(errors="ignore")
            except OSError:
                continue
            hit = next((m for m in _METAPROGRAMMING if m in text), "")
            if hit:
                marker = hit
                break
    return {"rust_is_library": rust_is_library,
            "js_entry_files": frozenset(entries),
            "ruby_metaprogramming": marker}


# ---------------------------------------------------------------------------
# Pure classification
# ---------------------------------------------------------------------------

_SOFT_REASONS = (
    ("config", "named in a configuration file (an entry point can be wired by name)"),
    ("strings", "named in a string literal or comment (a dynamic reference cannot be resolved)"),
    ("docs", "named only in documentation (a documented symbol is a published surface)"),
)


def _referenced_from(definition: Definition, relpath: str, corpus: Corpus,
                     files: frozenset[str]) -> bool:
    """True when the name has a real identifier use in one of `files`, outside the
    definition's own span. Excluding its own span is what stops a self-recursive call,
    or the name token itself, from proving the definition alive."""
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


def _na(reason: str) -> dict:
    return {"value": "n/a", "band": "n/a", "details": reason, "findings": [],
            "undecidable": [], "test_only": [], "counts": {}, "production_loc": 0,
            "flagged_lines": 0}


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


def analyze(repo: Path, lang: str) -> dict[str, object]:
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
    unreachable: list[dict] = []
    unparsed = pasted = 0
    for path, src in sources:
        relpath = str(path.relative_to(repo)) if repo in path.parents else path.name
        production_loc += len(src.splitlines())
        analyzed_loc += len(src.splitlines())
        grammar, _key = _EXT_LANG[path.suffix.lower()]
        root = _parser(grammar).parse(src).root_node
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

    dead: list[dict] = []
    undecidable: list[dict] = []
    test_only: list[dict] = []
    excluded = 0
    for relpath, definition in definitions:
        entry = {"file": relpath, "name": definition["name"], "kind": definition["kind"],
                 "line": definition["line"], "end_line": definition["end_line"]}
        if definition["status"] == EXCLUDED:
            excluded += 1
        elif definition["status"] == UNDECIDABLE:
            undecidable.append({**entry, "reason": definition["reason"]})
        elif _referenced_from(definition, relpath, corpus, production_files):
            continue
        elif _referenced_from(definition, relpath, corpus, test_files):
            test_only.append({**entry, "reason": "referenced only from the test tree"})
        else:
            reason = _soft_reason(definition["name"], corpus)
            if reason:
                undecidable.append({**entry, "reason": reason})
            else:
                dead.append({**entry, "category": "unreferenced"})

    flagged = {(f["file"], line)
               for f in dead + unreachable
               for line in range(f["line"], f["end_line"] + 1)}
    percent = round(len(flagged) / production_loc * 100, 2) if production_loc else 0.0
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
