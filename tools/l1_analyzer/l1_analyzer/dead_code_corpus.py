"""What the repository says about a name, gathered once from every file in it.

The other half of the dead-code reading. This one walks the whole tree and records where
every name appears; `dead_code` decides which definitions that leaves unreachable. The seam
is real rather than a size cut: this touches the disk and answers "where is this name
written", and nothing here knows what a definition is or what dead means.

A name is recorded as a hard reference when a grammar this package has parsed it as an
identifier, and as a word otherwise, split by what the file is: prose, configuration, a
specification, or a dotted path naming a module. Those four carry different weight, because
a YAML that names a function can be calling it and a paragraph that names it cannot.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TypedDict

from tree_sitter import Node

from l1_analyzer.boundary import boundary
from l1_analyzer.dead_code_defs import RepoFacts
from l1_analyzer.dead_code_grammars import _EXT_LANG, parser
from l1_analyzer.scope import _in_ignored_dir, _rglob_files
from l1_analyzer.ts_nodes import descendants

_IDENT_EXTRA = frozenset({"identifier", "constant"})
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_DOC_EXTS = frozenset({".md", ".rst", ".txt", ".adoc", ".org"})
# A file that DESCRIBES the code rather than wiring it. Read for the same reason as the
# documentation above and not for the config reason beside it: gherkin binds a step to a
# function by matching the STEP TEXT against a decorator's pattern, never by the function's
# name, so a scenario titled after a function calls nothing.
#
# This module already made the same distinction once, for string literals: a string is a
# candidate reference when the whole string is one identifier, because "a string carrying
# the name among other words is prose and carries no lookup". A scenario is a sentence.
#
# Found on 2026-08-31 in this package, which writes one scenario per function as a commit
# gate. That put every function name it has into a .feature file, so every function nobody
# called came back "an entry point can be wired by name", and four dead ones sat in one
# module behind that excuse.
_SPEC_EXTS = frozenset({".feature", ".story"})
_MAX_BYTES = 1_048_576
_METAPROGRAMMING = ("define_method", "method_missing", "const_get", "instance_variable_get",
                    "class_eval", "instance_eval", "ActiveRecord", "ActiveSupport")


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
    words: dict[str, set[str]]               # bucket -> words: strings, config, docs, specs, dotted
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


def dotted_path_in(text: str) -> str:
    """The dotted module path a string holds, or the empty string.

    Every framework that loads code the parser cannot follow spells it this way: `-p
    pkg.plugin`, `app.main:create_app`, a task named `pkg.tasks.run`. The file is imported
    by a name in a string, so nothing imports it in the source and the island rule reads it
    and everything in it as dead.

    Two segments at least, each one an identifier, and the colon form is cut at the colon
    because what follows it is a symbol inside the module rather than part of the path.
    Whether it means anything is settled by resolving it against the repository's own files,
    which is what keeps this from becoming "any string with a dot in it": a version number,
    a filename and a sentence ending in a full stop are all dotted strings."""
    head = text.strip().split(":")[0]
    parts = head.split(".")
    if len(parts) < 2 or not all(_WORD.fullmatch(part) for part in parts):
        return ""
    return head


def _harvest_source(root: Node, relpath: str, corpus: Corpus) -> None:
    for node in descendants(root, "all"):
        if _is_identifier_leaf(node):
            name = node.text.decode("utf8", errors="ignore") if node.text else ""
            corpus["hard"].setdefault(name, []).append((relpath, node.start_byte))
        elif "string" in node.type:
            corpus["words"]["strings"].update(_string_reference_names(node))
            text = node.text.decode("utf8", errors="ignore") if node.text else ""
            dotted = dotted_path_in(text.strip("\"'"))
            if dotted:
                corpus["words"]["dotted"].add(dotted)


Manifest = dict[str, object]
"""One package manifest as it was parsed: keys to whatever JSON put under them."""


def entry_paths_in(data: Manifest, base: Path, repo: Path) -> set[str]:
    """The entry points one package manifest declares, relative to the repository.

    Five keys name a single path and `bin` names a map of them. A `bin` that is a bare
    string is legal npm and is NOT a map: reading it as one iterates the characters of the
    string, which is why the type is checked rather than assumed.

    The parameter was declared `Site`, which is the record describing one definition the
    reader judged and has nothing to do with a package manifest. One name was doing two
    jobs, and the split on 2026-08-31 made that visible by trying to carry it across."""
    found: set[str] = set()
    for key in ("main", "module", "browser", "types", "typings"):
        value = data.get(key)
        if isinstance(value, str):
            found.add(str((base / value).relative_to(repo)))
    binaries = data.get("bin")
    for value in (binaries.values() if isinstance(binaries, dict) else ()):
        if isinstance(value, str):
            found.add(str((base / value).relative_to(repo)))
    return found


def metaprogramming_in(text: str) -> str:
    """The first metaprogramming marker this Ruby source uses, or nothing.

    One marker is enough for the repository-level gate above, which decides whether any
    dead-code reading of Ruby is publishable at all."""
    return next((marker for marker in _METAPROGRAMMING if marker in text), "")


@boundary
def _read_corpus(repo: Path) -> Corpus:
    """Boundary reader. Every file in the repository is a possible reference site: a
    sibling module, a test, a CI workflow that names an entry point, a README. Vendored
    and ignored directories are skipped; unreadable and oversized files are counted and
    disclosed, never silently dropped."""
    corpus: Corpus = {"hard": {},
                      "words": {"strings": set(), "config": set(), "docs": set(),
                                "specs": set(), "dotted": set()},
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
        classify_into(corpus, relpath, path.suffix.lower(), raw)
    return corpus


def classify_into(corpus: Corpus, relpath: str, suffix: str, raw: bytes) -> None:
    """What one file contributes to the corpus, decided from its bytes and its suffix.

    Lifted out of the walk above, which read and decided in one loop, so a question as
    ordinary as "does a binary file contribute words" needed a temporary directory to ask.
    This touches nothing, which is what makes the walk's declaration honest rather than a
    stamp.

    A file this package has a grammar for is parsed, so a name is a name rather than a run
    of letters that happens to match one. Everything else contributes words, split into
    documentation and configuration because the two carry different weight downstream.

    Binary contributes nothing. A null byte in the first 8 KiB is the test, which is what
    `git` uses and is wrong only for text that legitimately holds one."""
    if b"\0" in raw[:8192]:
        return
    entry = _EXT_LANG.get(suffix)
    if entry is not None:
        _harvest_source(parser(entry[0]).parse(raw).root_node, relpath, corpus)
        return
    words = _WORD.findall(raw.decode("utf8", errors="ignore"))
    if suffix in _SPEC_EXTS:
        corpus["words"]["specs"].update(words)
        return
    bucket = "docs" if suffix in _DOC_EXTS else "config"
    corpus["words"][bucket].update(words)


@boundary
def _repo_facts(repo: Path, lang: str) -> RepoFacts:
    """The three repository-level questions a single file cannot answer.

    A walk, and the two decisions it used to make inline are below. What is left obtains
    manifests and Ruby sources and hands their contents to functions that touch nothing."""
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
        entries |= entry_paths_in(data, manifest.parent, repo)
    marker = ""
    if lang == "ruby":
        for path in _rglob_files(repo, "*.rb"):
            if _in_ignored_dir(path, ()):
                continue
            try:
                text = path.read_text(errors="ignore")
            except OSError:
                continue
            marker = metaprogramming_in(text)
            if marker:
                break
    return {"rust_is_library": rust_is_library,
            "js_entry_files": frozenset(entries),
            "ruby_metaprogramming": marker}
