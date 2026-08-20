"""L1.13 near-duplicate code, measured here rather than shelled out to a tool nobody has.

The canon: the percentage of production LOC participating in a Type-2 or Type-3 clone
class of at least 50 tokens, with identifiers and literals normalized. It names
`pmd cpd --ignore-identifiers --ignore-literals --minimum-tokens 50` as the reference tool
and jscpd in weak mode as an alternative, and this package shelled out to jscpd.

jscpd was not installed on any machine that ever ran the panel, so L1.13 reported n/a on
every repository this instrument has measured, both validation controls included. An
indicator that has never produced a number is not a lenient indicator: it is a column in a
published panel nobody has read, and since n/a is excluded from both halves of the slop
fraction, the panel measured nineteen things while saying twenty.

HOW IT WORKS. Every leaf token of the parse tree becomes one symbol. An identifier becomes
`I` and a literal becomes `L`, whatever they were called, which is what makes a renamed
copy match and makes this Type-2 rather than exact. Keywords, operators and punctuation
keep their text, so the SHAPE of the code is what is compared. A window of `min_tokens`
consecutive symbols is hashed; a window whose hash appears at two or more distinct places
is a clone, and every line those windows touch is a duplicated line.

WHAT IT DOES NOT DO. Type-3 clones with insertions inside them are caught only where a
window of the required length still matches on one side of the gap. Chasing gapped clones
needs suffix trees or a similarity threshold, and neither is what the canon's reference
tool does either: `--ignore-identifiers --ignore-literals` over a minimum token run is
this algorithm.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path

from tree_sitter import Node

from l1_analyzer.incomplete import (
    IncompleteCode,  # noqa: F401 - the refusal type, re-exported
)

IDENTIFIER = "I"
LITERAL = "L"
MIN_TOKENS = 50            # the canon's threshold, named rather than spelled at the callsite


def literal_types(lang: str) -> frozenset[str]:
    """The node types this language spells a literal with.

    Subscripted, not defaulted: a supported language whose literals nobody declared would
    compare unnormalized text and report near-zero duplication on a codebase full of it."""
    from l1_analyzer.lang_spec import LANG_SPEC

    return frozenset(LANG_SPEC[lang]["literal_types"])


def normalized_tokens(root: Node, lang: str) -> list[tuple[str, int]]:
    """Every leaf of the tree as (symbol, line), with identifiers and literals normalized.

    A comment is dropped rather than normalized. Two blocks that differ only in their
    comments are the same code, and counting comment text would let a copied block escape
    by having its comment reworded."""
    from l1_analyzer.indicators import _LITERAL_NODES, _MIN_TABLE_LINES

    literals = literal_types(lang)
    # The same discount L1.17 applies, for the same stated reason: a god-file is a pile of
    # logic and a data table is not. A per-language vocabulary table is nine rows of the
    # same keys, so normalizing the identifiers and literals makes every row read
    # identically and the whole table measures as duplicated code. On the first real run of
    # this indicator lang_spec.py contributed 390 such lines and lang_cfg.py 142, and
    # neither is duplicated code: both are one table with a row per language, which is the
    # shape this project tells other people to separate data into.
    tables = frozenset(_LITERAL_NODES.get(lang, ()))
    out: list[tuple[str, int]] = []

    def walk(node: Node) -> None:
        if "comment" in node.type:
            return
        if (node.type in tables
                and node.end_point[0] - node.start_point[0] + 1 >= _MIN_TABLE_LINES):
            return
        # The literal test comes BEFORE the descent, because a literal is not always a
        # leaf. Python spells a string as a node with string_start, string_content and
        # string_end beneath it, so a leaf-only test emitted three tokens carrying the
        # text itself and `a = "text"` failed to match `a = 1`.
        if node.type in literals:
            out.append((LITERAL, node.start_point[0] + 1))
            return
        if not node.children:
            line = node.start_point[0] + 1
            if node.type == "identifier" or node.type.endswith("_identifier"):
                out.append((IDENTIFIER, line))
            else:
                text = node.text.decode("utf8", errors="ignore") if node.text else ""
                if text.strip():
                    out.append((text, line))
            return
        for child in node.children:
            walk(child)

    walk(root)
    return out


def _window_hash(symbols: list[str]) -> str:
    """A window's identity. A hash rather than the tuple itself, so a large repository
    holds one short digest per window instead of fifty strings."""
    return hashlib.blake2b("\x00".join(symbols).encode(), digest_size=16).hexdigest()


def duplicated_lines(streams: dict[str, list[tuple[str, int]]],
                     min_tokens: int) -> dict[str, set[int]]:
    """The lines of each file that sit inside a window repeated somewhere in the tree.

    Two passes, because a window is only a clone once a SECOND occurrence is known, and
    the first occurrence's lines count as duplicated too. Counting on one pass would
    charge the copy and acquit the original."""
    seen: dict[str, list[tuple[str, int, int]]] = defaultdict(list)
    for relpath, stream in streams.items():
        symbols = [symbol for symbol, _line in stream]
        lines = [line for _symbol, line in stream]
        for start in range(len(stream) - min_tokens + 1):
            digest = _window_hash(symbols[start:start + min_tokens])
            seen[digest].append((relpath, tuple(lines[start:start + min_tokens])))

    duplicated: dict[str, set[int]] = defaultdict(set)
    for occurrences in seen.values():
        if len(occurrences) < 2:
            continue
        # Distinct PLACES, not distinct hashes. A window that overlaps itself inside one
        # long run of identical tokens is one clone, not a hundred, and the start line is
        # what separates them.
        places = {(relpath, window[0]) for relpath, window in occurrences}
        if len(places) < 2:
            continue
        # The lines the clone's TOKENS sit on, not the range from its first line to its
        # last. A docstring is one token spanning many lines, so a window could reach across
        # a signature, a docstring and the next signature and call every line between
        # duplicated: one here held fifty tokens on six lines and was credited with
        # twenty-six. A line no token of the clone sits on is not participating in it.
        for relpath, window in occurrences:
            duplicated[relpath].update(window)
    return duplicated


def analyze(repo: Path, lang: str, min_tokens: int = MIN_TOKENS) -> dict:
    """L1.13 for one repository: the share of production lines inside a repeated window."""
    from l1_analyzer.indicators import LANG_CFG, _get_parser, _read_source_bytes, band
    from l1_analyzer.scope import PRODUCTION

    if lang not in LANG_CFG:
        return {"value": "n/a", "band": "n/a", "details": f"no tree-sitter config for {lang}"}
    files, skipped = _read_source_bytes(repo, LANG_CFG[lang]["extensions"], scope=PRODUCTION)
    if not files:
        # A share of no lines is absent, not zero. Reporting 0.0 here would band Healthy
        # for a repository nobody read, which is the zero-denominator lie this package
        # exists to refuse.
        return {"value": "n/a", "band": "n/a",
                "details": f"no production {lang} source in scope, so duplication was not measured"}

    parser = _get_parser(lang)
    streams: dict[str, list[tuple[str, int]]] = {}
    total_lines = 0
    for path, src in files:
        relpath = str(path.relative_to(repo)) if repo in path.parents else path.name
        streams[relpath] = normalized_tokens(parser.parse(src).root_node, lang)
        # Lines that carry a code token, which is what "production LOC" means and what the
        # numerator now counts. It was every line in the file, blanks and docstrings
        # included, while the numerator marked whole line ranges: both halves generous, and
        # generosity in a divisor lowers a percentage, so the mismatch flattered the result.
        # On this package it was worth a band, 7.69% Not Healthy against 10.51% Slop.
        total_lines += len({line for _symbol, line in streams[relpath]})

    duplicated = duplicated_lines(streams, min_tokens)
    duplicated_count = sum(len(lines) for lines in duplicated.values())
    if total_lines == 0:
        # A share over no code lines is absent, not zero, and zero is the HEALTHY end of
        # this scale: a tree the parser found no token in must not read as clean.
        return {"value": "n/a", "band": "n/a",
                "details": f"no {lang} code line carried a token, so duplication was not measured"}
    pct = round(duplicated_count / total_lines * 100, 2)
    detail = (f"{duplicated_count} of {total_lines} production code lines inside a repeated "
              f"{min_tokens}-token window, identifiers and literals normalized, "
              f"large data tables discounted as L1.17 discounts them, "
              f"across {len(files)} file(s)")
    if skipped:
        detail += f"; {skipped} file(s) unreadable or oversized and excluded"
    return {"value": pct, "band": band(pct, 3, 10, higher_is_better=False), "details": detail}
