"""Source of another language, held whole inside a string, that no clause examined.

A Python file holding a JavaScript widget scored 100 per cent with fourteen clauses decided
and no findings, and the JavaScript in it had a dispatch chain and a swallowed error. Every
clause examined the Python correctly and nothing examined the substance.

Its own module since 2026-08-31. It reads a file for something entirely different from what
the clauses read it for: they ask what the code does, this asks whether there is other code
inside it that nobody looked at. The clause table and this share only the parsed source.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from typing import TYPE_CHECKING, TypedDict

from tree_sitter import Parser

from l1_analyzer.honest_code_grammars import _MARKUP, _STYLESHEET, GRAMMARS
from l1_analyzer.honest_code_read import Finding, Source, read_tree, walk
from l1_analyzer.lang_spec import LANG_SPEC

if TYPE_CHECKING:
    from tree_sitter import Node


_PARSED = frozenset({"python"})
_VOCABULARY = frozenset(LANG_SPEC)
# Grammars this reader uses that no clause reads. They are deliberately NOT in LANG_SPEC:
# that table is the clause vocabulary, and an entry there would tell nineteen clauses they
# can read markup.
#
# Page content is why they are here. The same JavaScript reported bare went silent once
# wrapped in a script tag, because the tags are not JavaScript and the whole-grammar test
# rejected the block. That is the commonest way embedded source arrives.
# How much of a string constant has to parse as another language before it is worth
# naming. Five lines, because one line of something that parses is a fragment rather than
# content nobody examined, and a reader told about fragments stops reading the notices.
_BLOCK_LINES = 5
# A cheap gate before nine grammars are tried on a string. Trying them all on every long
# docstring cost 203ms on this package's most fixture-heavy file, over the budget that keeps
# this usable behind a write hook.
#
# Its only failure mode is SILENCE. A block that carries none of these is not reported, which
# is exactly what happened before any of this existed; it can never invent a block that is not
# there. That direction is the reason it is acceptable and the reason it is written down.
_CODE_MARKS = (";", "{", "}", "=>", "<", "func ", "def ", "class ", "fn ", "public ", "var ")
# The element types whose text is another language. Read by node type, so nothing is
# stripped and nothing is matched by pattern: a wrapper removed by hand is the guess this
# whole test exists to avoid.
_EMBEDDING_ELEMENTS = ("script_element", "style_element")


class Block(TypedDict):
    """One block of another language, as it is found, before anything reads it.

    Every field the published record below carries, plus the block's own source. The text
    travels only as far as the reader and never into the record: carrying every embedded
    block's source into a report about the file would put the file back into the report.

    Its own record rather than the published one, because the published one does not hold
    text and said so, while the code built it holding text and popped it out again. Nothing
    said the two disagreed until a type checker ran over this package.

    It then said four fields while the builder wrote six, and the two it left out are the
    two the published record keeps. So the record that exists to hold what the builder makes
    described neither what was built nor what was published.
    """

    language: str
    line: int
    lines: int
    text: str
    findings: list[Finding]
    also_accepted_by: list[str]

class Unexamined(TypedDict):
    """A block inside a readable file that no clause looked at.

    Not a clause and not graded. The Python in a file holding a JavaScript widget really
    does hold every clause that read it, and saying otherwise would invent a violation.
    This says the other true thing: the file's substance was never examined.

    THE FINDINGS ARE THE POINT, NOT THE LANGUAGE. A twelve-line SQL query inside a database
    driver is accepted whole by the ruby grammar, there is no SQL grammar, so that name can
    never be right and a driver holds dozens of such queries. Reporting a guessed name and
    nothing else teaches a reader to skip the field, which costs the embedded-widget case it
    was built for.

    So the clauses are run on the block and travel with it. A misnamed block reports nothing,
    because it is not that language and has none of that language's shapes. A real one
    reports what a reader can act on, and the name it was given stops mattering."""

    language: str
    line: int
    lines: int
    findings: list[Finding]
    # The other grammars that also took this block whole. A name is a pick among these, and
    # a reader discounting a finding needs to see how much of a pick it was.
    also_accepted_by: list[str]

def unexamined_blocks(source: Source,
                      findings_in: Callable[[Block, str], list[Finding]]
                      ) -> list[Unexamined]:
    """Substantial string constants that parse cleanly as another language this tool knows.

    A Python file holding a JavaScript widget scored 100 per cent with fourteen clauses
    decided and no findings, and the JavaScript in it had a dispatch chain and a swallowed
    error. Every clause examined the Python correctly; nothing examined the substance.

    Nothing is guessed from resemblance. A block is named only when a real grammar accepts
    the WHOLE of it with no error node, which is what keeps prose out: run over this
    package's own source, 355 long string literals produced eleven hits and every one was
    genuine embedded source held as a test fixture."""
    if not source["readable"] or source["language"] not in _PARSED:
        return []
    documentation = _docstrings(source["tree"])
    found: list[Block] = []
    for node in ast.walk(source["tree"]):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if id(node) in documentation:
            continue
        lines = node.value.count("\n") + 1
        if lines < _BLOCK_LINES or not any(mark in node.value for mark in _CODE_MARKS):
            continue
        found += _blocks_in(node.value, source["language"], node.lineno)
    examined: list[Unexamined] = []
    for block in found:
        # The block's own text travels only this far. A reader wants the findings, and
        # carrying every embedded block's source into the published record would put the
        # file back into the report that is about the file.
        #
        # Built by naming each field rather than by popping one out of the block and
        # spreading the rest. The pop mutated the block a line before it was read, and the
        # spread carried whatever else happened to be there into the published record.
        examined.append({"language": block["language"], "line": block["line"],
                         "lines": block["lines"],
                         "also_accepted_by": block["also_accepted_by"],
                         "findings": findings_in(block, block["text"])})
    return examined


def _blocks_in(text: str, own: str, line: int) -> list[Block]:
    """Every block of another language inside this text, one entry per element.

    One entry per BLOCK was wrong and it was wrong quietly. Page content usually carries a
    style element and a script element together, and returning a single language reported
    whichever was found first while dropping the other, so a record read as though the
    block had been accounted for. Which one survived depended on the order they came out of
    the tree.

    Each entry carries its own line and its own size. Reporting the whole block's size
    against one language says the entire string was that language, and giving both elements
    line 1 makes a reader search for the one that starts on line 6."""
    wrapper = _accepts_whole(text, _MARKUP)
    if wrapper is not None:
        parts = _markup_parts(wrapper, text)
        found = [block for part, offset in parts
                 for block in _blocks_in(part, own, line + offset)]
        if found:
            return found
        # Markup carrying no embedded source this reader knows is still content nothing
        # examined, and naming it as markup is truer than naming it as a language it does
        # not contain.
        #
        # It is named BEFORE the other grammars are tried, and that order settles an
        # ambiguity between grammars rather than expressing a preference. The JavaScript and
        # TypeScript grammars both accept JSX, so any tag-shaped text parses cleanly as
        # JavaScript: a plain block of divs was reported as JavaScript and an unterminated
        # script tag as TypeScript, and which one won came down to the alphabetical order of
        # the language names.
        #
        # What it costs, stated because it is a real cost: genuine JSX held in a Python
        # string is named markup. The block is unexamined content either way and only the
        # name is wrong, which is the direction to be wrong in.
        if any(n.type == "element" for n in walk(wrapper)):
            return [{"language": _MARKUP, "line": line, "lines": text.count("\n") + 1,
                     "findings": [], "text": text, "also_accepted_by": []}]

    accepted = _accepted_by(text, own)
    if not accepted:
        return []
    # The name is a pick among candidates, and the candidates travel with it. Counting them
    # was tried first, on the theory that many acceptors means the name is a coin flip: two
    # one-line functions are taken whole by five grammars, and naming that block `c` gave a
    # finding whose symbols read "function, function". But a REAL embedded widget is taken
    # by three, csharp among them, so any cut that refused the five refused the widget too,
    # and the widget is the case this field exists for.
    #
    # So the pick stands and the ambiguity is disclosed beside it rather than acted on. A
    # missed widget is the silence this was built to stop; a finding under a doubtful name
    # is noise a reader can discount, once they are told.
    language = accepted[0]
    return [{"language": language, "line": line,
             "lines": text.count("\n") + 1, "findings": [], "text": text,
             "also_accepted_by": accepted[1:]}]


def _docstrings(tree: ast.AST) -> set[int]:
    """The string constants this file declares as documentation.

    Skipped, because a docstring IS declared documentation and source inside one is an
    example rather than shipped content. It is also where nearly all the cost was: 342 of
    this package's 355 long string literals are docstrings and not one of its eleven real
    embedded blocks is, so trying nine grammars on each of them bought nothing and cost
    25 milliseconds a file.

    The limit, stated because its failure mode is silence: a template genuinely held in a
    docstring is missed."""
    declared: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)) or not body:
            continue
        first = body[0]
        if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            declared.add(id(first.value))
    return declared


def _accepted_by(text: str, own: str) -> list[str]:
    """Every grammar OTHER than the file's own that takes this text whole, in name order.

    A parse with no error node and some named structure in it. tree-sitter accepts almost
    anything and reports the trouble as error nodes rather than as a failure, so the absence
    of them is the test.

    The LIST rather than a winner, because the count is the evidence. Returning one name
    made "nothing accepted this" and "everything accepted this" the same answer, and they
    are opposite facts: the first is not a block at all, the second is a block whose name
    nobody can know.

    Markup is not tried here. Its caller tries it first and goes one grammar deeper when it
    finds an element, because it is the most permissive grammar in this set and would
    otherwise claim blocks a stricter one should have."""
    return [language for language in sorted({*_VOCABULARY, _STYLESHEET} - {own})
            if (root := _accepts_whole(text, language)) is not None
            and root.named_child_count]


def _markup_parts(root: Node, text: str) -> list[tuple[str, int]]:
    """The text inside each script and style element, with the line each starts on.

    Found by NODE TYPE. Nothing is stripped and nothing is matched by pattern: a wrapper
    removed by hand is the guess this whole test exists to avoid, so the markup grammar has
    to accept the block whole first and the element is then located the way the grammar
    names it.

    The line travels with the text because a reader given the block's own line has to search
    for the element inside it, and two elements would carry the same one."""
    raw = text.encode()
    parts: list[tuple[str, int]] = []
    for node in walk(root):
        if node.type not in _EMBEDDING_ELEMENTS:
            continue
        for child in node.children:
            if child.type == "raw_text":
                inner = raw[child.start_byte:child.end_byte].decode(errors="replace")
                parts.append((inner, child.start_point[0]))
    return sorted(parts, key=lambda part: part[1])


def _accepts_whole(text: str, language: str) -> Node | None:
    """The root a grammar produced, when it accepted the WHOLE text with no error node.

    None means one thing only: that grammar read the text and rejected it. A language with
    no grammar here raises, because a caller cannot tell a rejection from an absence and the
    absence is the expensive one. It makes every block in that language vanish, so the file
    reports nothing unexamined and the share claims to cover what it never read."""
    root = _grammar_root(text, language)
    if any(n.type == "ERROR" or n.is_missing for n in walk(root)):
        return None
    return root


def _grammar_root(text: str, language: str) -> Node:
    """One parse, by whichever grammar owns this language.

    The clause vocabulary is asked first. Markup and stylesheets are not in it, because
    that table is what tells a clause it can read a language and no clause reads these."""
    if language in _VOCABULARY:
        return read_tree(text, language, "")["root"]

    return Parser(GRAMMARS[language]).parse(text.encode()).root_node
