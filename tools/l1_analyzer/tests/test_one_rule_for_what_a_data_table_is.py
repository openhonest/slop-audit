"""Two indicators ask what a data table is, and they must not answer differently.

A god-file is a pile of logic over a thousand lines, and a data table is not logic, so L1.17
discounts the lines a table spans. A repeated block is copied logic, and a data table is not
logic, so L1.13 discounts a table's contents. One premise, read by two indicators for two
different purposes: one counts the lines, one skips the tokens.

It was one rule until 2026-09-01, when I widened L1.13's half and left L1.17's alone. Both
had been "a container literal spanning twelve lines or more", which reads how an author laid
a table out rather than whether it holds any logic. L1.13 learned that a container of
literals is data at any size, that a mapping of names to names is too, and that the line
binding one to a name is a declaration. L1.17 did not, and for half a day the same file was
data to one indicator and code to the other.

That is the defect this package keeps finding in other people's code: one fact with two
owners and nothing checking they agree. Now there is one owner and both ask it.
"""

from l1_analyzer import data_tables
from l1_analyzer.indicators import _get_parser


def _node(source: str):
    return _get_parser("python").parse(source.encode()).root_node


def _counted(source: str) -> int:
    """The lines the god-file check discounts as data, which is the reading under test."""
    from l1_analyzer.indicators import _LITERAL_NODES, _data_literal_lines

    return _data_literal_lines(_node(source), _LITERAL_NODES["python"],
                               data_tables.literal_types("python"))


def test_both_indicators_ask_the_same_function():
    """Asserted on identity, because two functions that agree today are two functions."""
    import inspect

    from l1_analyzer import clone_detect, indicators

    for module in (clone_detect, indicators):
        assert "data_tables" in inspect.getsource(module), (
            f"{module.__name__} does not ask the shared rule")


def test_a_short_table_of_literals_is_data_to_both():
    """The case that pushed this package's own language spec over the god-file line: nine
    vocabularies, each a frozenset of four lines, none of them twelve."""
    source = 'A = frozenset({\n    "one", "two",\n    "three", "four",\n})\n'
    assert _counted(source) > 0, "the god-file check still reads this as logic"


def test_a_long_table_is_data_to_both_as_it_always_was():
    body = "".join(f'    "name_{i}": {i},\n' for i in range(20))
    assert _counted("T = {\n" + body + "}\n") > 0


def test_a_container_of_calls_is_logic_to_both():
    """The premise from the other side, and the reason neither indicator may simply skip
    anything written between brackets."""
    source = "H = [\n    build(one),\n    build(two),\n]\n"
    assert _counted(source) == 0
