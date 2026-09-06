"""What a container has to be for its contents to be data rather than logic.

Two indicators ask this, for two different purposes. A god-file is a pile of logic over a
thousand lines and a data table is not logic, so L1.17 discounts the lines a table spans. A
repeated block is copied logic and a data table is not logic, so L1.13 discounts a table's
contents. One counts lines, the other skips tokens, and both need the same answer to the
same question.

They gave different answers for half a day on 2026-09-01, because the rule was written twice
and I widened one copy. Both had been "a container literal spanning twelve lines or more",
which reads how an author laid a table out rather than whether it holds any logic. That is
the shape this package reports in other people's code: one fact with two owners and nothing
checking they agree.

The rule has two arms and neither covers the other. Long is data, because a container that
big is a table whatever it holds and the size test was the original reason. Every element a
literal is data at any size, because that is the premise the size was standing in for. It
reads down: a literal, a pair of literals, or another container of the same, at any depth,
and a call that wraps one table and nothing else, which is what `frozenset({...})` is.

A container holding anything else is logic, however short. A list of calls is a pile of logic
laid out like a table, and discounting it would let anyone hide a copied block behind
brackets.
"""

from __future__ import annotations

from tree_sitter import Node

# How a grammar spells one entry of a mapping. A pair of literals is data for the same
# reason a literal is, and reading only the container's own children stops one level short.
_PAIRS = frozenset({"pair", "keyword_argument", "key_value_pair", "pair_expression"})
# How a grammar wraps one statement, and how it spells binding a name.
_STATEMENTS = frozenset({"expression_statement", "lexical_declaration",
                         "variable_declaration", "assignment"})
_ASSIGNMENTS = frozenset({"assignment", "variable_declarator", "augmented_assignment"})
_CALLS = frozenset({"call", "call_expression", "method_invocation", "invocation_expression"})

# A container this big is a table whatever it holds. The original rule, kept as one arm.
MIN_TABLE_LINES = 12


def literal_types(lang: str) -> frozenset[str]:
    """The node types this language spells a literal with.

    Subscripted, not defaulted: a supported language whose literals nobody declared would
    read every table as logic, which is the direction that over-accuses on a codebase made
    mostly of tables."""
    from l1_analyzer.lang_spec import LANG_SPEC

    return frozenset(LANG_SPEC[lang]["literal_types"])


def is_table(node: Node, containers: frozenset[str], literals: frozenset[str]) -> bool:
    """Whether this node is a container whose contents carry no logic."""
    if node.type not in containers:
        return False
    if node.end_point[0] - node.start_point[0] + 1 >= MIN_TABLE_LINES:
        return True
    return _all_data(node, containers, literals)


def declares_a_table(node: Node, containers: frozenset[str], literals: frozenset[str]) -> bool:
    """Whether this statement only binds a name to a table.

    Discounting a table's contents leaves the declaration around it: a name, an equals sign,
    an empty pair of brackets. Nine of those in a row is fifty tokens that match nine in a
    row anywhere else, so a file of per-language vocabularies came back as its own largest
    repeated block with every table inside it already discounted.

    Only a declaration OF data. One that runs something to build its value is a statement
    like any other, or a copied block could hide behind an equals sign."""
    if node.type not in _STATEMENTS:
        return False
    inner = node.named_children[0] if node.named_children else None
    if inner is None or inner.type not in _ASSIGNMENTS:
        return False
    value = inner.child_by_field_name("right") or inner.child_by_field_name("value")
    return value is not None and (is_table(value, containers, literals)
                                  or _builds_a_table(value, containers, literals))


def _builds_a_table(node: Node, containers: frozenset[str], literals: frozenset[str]) -> bool:
    """A call that wraps one table and nothing else: `frozenset({...})`, `tuple([...])`.

    One argument, and that argument is data. Two arguments, or an argument that is not a
    table, means a call doing work, so `compute(1, 2)` and `build_the_table(source)` stay
    logic. Without this arm the rule never reached a vocabulary written as a frozenset."""
    if node.type not in _CALLS:
        return False
    arguments = node.child_by_field_name("arguments")
    if arguments is None:
        return False
    given = [child for child in arguments.named_children if "comment" not in child.type]
    return len(given) == 1 and is_table(given[0], containers, literals)


def _all_data(node: Node, containers: frozenset[str], literals: frozenset[str]) -> bool:
    """Whether every element under this container is data, all the way down.

    Over an explicit stack, because it used to call itself once per level of nesting and a
    generated file is nested as deep as its generator felt like. One vocabulary written as
    two thousand nested lists exhausted the interpreter's stack, and what reached the person
    running it was not a repository it could not read: it was a traceback, and the whole
    panel died with it. Five repositories went missing from a corpus of two hundred that
    way.

    The flag on each work item is which nodes that item may hold. A container may hold a
    pair; a pair may not hold another pair, only literals and containers. That was the one
    difference between the two functions this replaces, and it is now the one bit of state
    the loop carries."""
    stack = [(node, True)]
    while stack:
        current, pairs_allowed = stack.pop()
        elements = [child for child in current.named_children if "comment" not in child.type]
        if not elements:
            return False
        for child in elements:
            if child.type in literals:
                continue
            if child.type in containers:
                stack.append((child, True))
            elif pairs_allowed and child.type in _PAIRS:
                stack.append((child, False))
            else:
                return False
    return True
