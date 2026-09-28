"""The parts of a production file that are somebody's tests.

EIGHT INDICATORS MEASURE PRODUCTION CODE ONLY, and a project's test tree is deliberately
outside them. Every rule that decides this works on PATHS: a directory named test or tests, a
file whose stem ends in _test or .spec. Eight of the nine languages this instrument reads put
their tests where such a rule can see them.

Rust does not. A Rust unit test lives inside the file it tests, so no path names it and it was
measured as production code. Counted under the production scope, 2,532 of uuid-rs/uuid's 9,821
lines are inside a test module, 25.8 per cent, and 4,300 of this port's own 21,633, 19.9 per
cent. The numbers were not wrong about what they measured; they answered a
different question for Rust than for the other eight, and nothing said so.

So a region of a file can be excluded, not only a whole file. The region is replaced by spaces
of the same length, newlines kept, so every line number a reader reports is still the line
number in the file and every reader gets the exclusion without knowing this module exists.

TWO SHAPES ARE READ AND ONE IS NOT, and the third is named here so its absence is a measured
gap rather than a silence. Counted across those same crates:

  227 test modules written in the file they test, `#[cfg(test)] mod tests { ... }`   READ
  851 test functions in 54 files of tests under src, declared `#[cfg(test)] mod tests;`
      from the parent file, the file itself carrying no marker at all                NOT READ
  the rest, a bare `#[test]` on a function with no such module around it             READ

The second needs a module declaration followed from one file to another, which no reader here
does. Rayon, indexmap and winnow all write their tests that way, so a third of the test code
inside src is still measured as production. slop-audit-12x carries that half.

WHAT THE BLANKING CANNOT DO, and L1.12 publishes a zero over it today. A definition whose only
caller is the crate's own unit test should be reported test-only: the tests call it, so it is
not dead, and it is not load-bearing production code either. Deciding that needs the REFERENCES
split the same way the definitions now are, and they are not: the reference corpus reads every
file whole, so a name used only inside a test module still reads as used from production. uuid-
rs/uuid reports 0 definitions referenced only by tests across 2,532 lines of test module, which
is the vacuous affirmative this instrument exists to name, and 497 of its names appear nowhere
but inside a test region. Splitting the corpus per region, not per file, is what would fix it.
slop-audit-12x carries this half as well.

THE TRAP, and it is why this reads a cfg predicate rather than matching on the word test.
`#[cfg(any(test, feature = "std"))]` mentions test and is not test-only: `any` means the item
ships whenever either condition holds, so a normal build with that feature on includes it.
There are 13 of those. `#[cfg(feature = "test_debug")]` and `#[cfg(doctest)]` are the same
mistake wearing different words. Excluding any of them would delete production code from the
measurement, which is the one error worse than the one being fixed.
"""

from __future__ import annotations

import re

from tree_sitter import Node

from l1_analyzer.dead_code_grammars import parser

# Which languages carry tests inside a production file. One row, and the emptiness of the rest
# is the finding: every other language this reads puts its tests in their own file.
TEST_REGION_LANGUAGES = frozenset({".rs"})

# A cfg predicate that REQUIRES test. `cfg(test)` on its own, and `cfg(all(test, ...))` where
# every condition must hold, so test must hold. Anything inside `any(...)` is excluded by the
# `all` requirement: that item ships without test as well.
_TEST_ONLY_CFG = re.compile(r"^#!?\[\s*cfg\s*\(\s*(?:test\s*\)|all\s*\(\s*test\b)")

# What may stand between an attribute and the item it marks, and therefore belongs inside the
# region with them. A comment written there is Rust and is common, and reading it as the marked
# ITEM left the function behind, bare and private and called by nothing, which is the same
# defect the attribute RUN fixed from the other end.
_RUN_TYPES = frozenset({"attribute_item", "line_comment", "block_comment"})

# The attributes that mark one function as a test the harness runs. A bare `#[test]`, and the
# async runtimes' own spellings, which are the same declaration with a runtime attached.
_TEST_ATTRIBUTES = re.compile(
    r"^#\[\s*(?:test|ignore|bench|"
    r"(?:tokio|async_std|actix_rt|actix_web|smol|serial_test|rstest|proptest)::[\w:]*test\w*"
    r")\s*(?:\(|\])")


def marks_a_test(attribute: str) -> bool:
    """Whether this attribute says the item under it exists only for tests.

    Read as a predicate rather than searched for the word, because `any(test, feature = "std")`
    carries the word and ships in a normal build. The two mistakes are not symmetric: missing a
    test region leaves the old answer, and excluding a production item deletes somebody's code
    from the measurement."""
    flat = " ".join(attribute.split())
    return bool(_TEST_ONLY_CFG.match(flat) or _TEST_ATTRIBUTES.match(flat))


def blanked(source: bytes, ext: str) -> tuple[bytes, frozenset[int]]:
    """The same bytes with every test region replaced by spaces, and which line numbers those
    were, counting from 1.

    A language with no row in the table above comes back untouched, which is eight of the nine.

    Spaces rather than deletion, so a line number a reader reports is the line number in the
    file. A reader that says line 391 must mean line 391 of what the author wrote.

    THE LINE NUMBERS TRAVEL WITH THE BYTES because nothing can recover them afterwards: an
    emptied line and a line the author left blank are the same bytes. Two readers want them for
    different reasons and one structure answers both. Three indicators divide by a line count,
    and without the numbers their numerator excluded a crate's tests while their denominator
    kept them. The secret scanner wants membership rather than a count: it reports a credential
    wherever it sits and labels the ones in a test, so a fixture key in a Rust test module was
    labelled production until it could ask this.

    A SET, because the first version added up each span's line count. Regions nest inside one
    another and sit on consecutive lines, so the shared lines were counted twice over: uuid-rs/
    uuid's lib.rs came out at 1,302 lines of 1,715 where 710 are test. Comparing the two byte
    strings line by line fixed the double count and gave 598, which is wrong the other way: a
    line the author left blank inside a test module does not change, so it stayed under every
    ratio that divides by a line count. The line numbers are read off the parse tree instead.

    One line can still be part test and part production, where an author puts code after the
    closing brace of a test item. The whole line is called test, and nothing in the 68 crates
    measured is written that way."""
    if ext not in TEST_REGION_LANGUAGES:
        return source, frozenset()
    tree = parser("rust").parse(source)
    keep = bytearray(source)
    lines: set[int] = set()
    for start, end, first_row, last_row in _regions(tree.root_node, source):
        for at in range(start, end):
            if keep[at] != 0x0A:
                keep[at] = 0x20
        lines.update(range(first_row + 1, last_row + 2))
    return bytes(keep), frozenset(lines)


def _regions(root: Node, source: bytes) -> list[tuple[int, int, int, int]]:
    """Every test region: its first and last byte, then its first and last row, counting rows
    from 0 the way tree-sitter does. The region is the whole run of attributes and the item
    they mark.

    The rows come from the parse tree rather than from counting newlines in the bytes, because
    tree-sitter already knows them and a second count is a second answer.

    THE RUN, NOT THE ONE ATTRIBUTE. An item may carry several, and the one that marks it a test
    need not be next to it:

        #[test]
        #[cfg(windows)]
        fn guid_to_uuid() { ... }

    Taking the marking attribute and its next sibling took the two attributes and left the
    function, bare and private and called by nothing, so the dead-code reader said somebody's
    example was dead. uuid-rs/uuid has three written that way and the 68 crates on one machine
    have 391. Starting at the run's first attribute matters for the same reason from the other
    end: begin at the marking one and a `#[cfg(windows)]` is left in front of nothing, which is
    not Rust.

    AND A COMMENT MAY STAND BETWEEN THEM, which is the same defect from a third direction:

        #[test]
        #[cfg(windows)]
        // why this one is windows-only
        fn guid_to_uuid() { ... }

    tree-sitter gives the comment its own named node, so the run ended at the attributes and the
    comment was read as the item they marked. The function was left bare again. Three of these
    are written across the 68 crates on one machine. The run absorbs comments and the marked
    item is the first node after it that is not one.

    An explicit stack, and it does not read below a region. A test module holds functions
    carrying their own attributes, and walking in would find them all again for no gain."""
    spans: list[tuple[int, int, int, int]] = []
    stack: list[Node] = [root]
    while stack:
        node = stack.pop()
        children = node.named_children
        at = 0
        while at < len(children):
            if children[at].type != "attribute_item":
                at += 1
                continue
            run = at
            while at < len(children) and children[at].type in _RUN_TYPES:
                at += 1
            marked = children[at] if at < len(children) else None
            attributes = [c for c in children[run:at] if c.type == "attribute_item"]
            if marked is not None and any(
                    marks_a_test(source[a.start_byte:a.end_byte].decode("utf8", "ignore"))
                    for a in attributes):
                # From the first ATTRIBUTE, not from the first node of the run: a comment
                # written above the attributes may belong to whatever stands above them, and
                # the run only ever starts at an attribute because of the test above.
                spans.append((attributes[0].start_byte, marked.end_byte,
                              attributes[0].start_point[0], marked.end_point[0]))
                at += 1          # the item is inside the region, so nothing below it is read
            else:
                stack.extend(reversed(children[run:at]))
        stack.extend(c for c in children if c.type != "attribute_item")
    return spans
