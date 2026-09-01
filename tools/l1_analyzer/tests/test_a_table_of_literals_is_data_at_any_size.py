"""A list of literals carries no logic, and how many lines it takes is not the question.

The duplication check normalises identifiers and literals, so two blocks doing one thing
with different names read alike. That is what makes it useful and it is exactly what makes
it wrong about a data table: nine per-language vocabularies become nine identical token
streams, and the whole table measures as copied code.

The check already knows this and says so three times: it discounts a large container
literal, a record declaration, and an import block, each time with the same argument. There
is no logic in any of them to be duplicated.

The container discount was gated on size, twelve lines, and that turned the argument into a
rule about layout. This package's own language vocabularies are the case: one file writes
nine tables as nine short frozensets, and 54 of its 69 lines came back as duplicated code.
Written as one long dictionary instead, the identical content would have been discounted.

So the size test is gone and the premise stands on its own. Every element a literal means no
logic at any size, and a container holding anything else is still code however short.
"""

from l1_analyzer import clone_detect
from l1_analyzer.indicators import _get_parser


def _tokens(source: str) -> list[str]:
    """What the check would compare. A discounted container contributes nothing here, so a
    table of literals leaves no `L` behind and a list of calls leaves its `(` and its `I`."""
    return [symbol for symbol, _line in clone_detect.normalized_tokens(
        _get_parser("python").parse(source.encode()).root_node, "python")]


def test_a_short_table_of_literals_is_not_read_as_code():
    """The case this repository hit. Four lines of names, and nothing in it to copy."""
    source = ('MUTATING = frozenset({\n'
              '    "append", "add", "update", "extend",\n'
              '    "insert", "pop", "remove",\n'
              '})\n')
    assert "L" not in _tokens(source), "the table's contents should not reach the stream"


def test_nine_short_tables_do_not_read_as_nine_copies_of_one():
    """Nine languages need nine vocabularies. The content differs and only the shape
    repeats, so there is nothing an author could factor out."""
    tables = "".join(
        f'_{name}_LITERALS = frozenset({{\n    "{name.lower()}_a", "{name.lower()}_b",\n}})\n'
        for name in ("PY", "JS", "JAVA", "CS", "RUST", "RUBY", "C", "GO", "TS"))
    streams = {"vocab.py": clone_detect.normalized_tokens(
        _get_parser("python").parse(tables.encode()).root_node, "python")}
    duplicated = clone_detect.duplicated_lines(streams, clone_detect.MIN_TOKENS)
    assert duplicated.get("vocab.py", set()) == set()


def test_a_long_table_of_literals_is_still_not_code():
    """Unchanged. This was already discounted and the reason has not moved."""
    body = "".join(f'    "name_{i}",\n' for i in range(30))
    assert "L" not in _tokens("TABLE = [\n" + body + "]\n")


def test_a_container_holding_anything_but_literals_is_still_code():
    """The premise, said from the other side. A list of calls is a pile of logic laid out
    like a table, and discounting it would let anyone hide a copied block behind brackets."""
    source = ('HANDLERS = [\n'
              '    build(one, two),\n'
              '    build(three, four),\n'
              ']\n')
    assert "(" in _tokens(source), "a list of calls is logic laid out like a table"


def test_a_short_container_holding_a_call_is_code_too():
    """Size never enters it, in either direction."""
    assert "(" in _tokens("PAIR = [compute(1), 2]\n")


def test_a_short_mapping_of_names_to_names_is_data_too():
    """The half I missed when I wrote the rule this morning.

    A mapping's elements are pairs, not literals, so a dictionary of eleven lines satisfied
    neither arm: too short for the size test, and its pairs are not literals. The pair is
    where the premise lives, one level down. `"read_text": "filesystem"` has no logic in it
    any more than `"read_text"` does.

    Found by reading the inventory the check produces about this package. Two tables in one
    file, eleven lines and eight, and what survived the discount was the skeleton around
    them, which matched the skeleton around every other file's tables."""
    source = ('READS = {\n'
              '    "read_text": "filesystem",\n'
              '    "connect": "network",\n'
              '}\n')
    assert "L" not in _tokens(source)


def test_a_mapping_whose_values_are_computed_is_still_code():
    """The premise from the other side, and the reason this reads the pair rather than
    assuming a mapping is always data."""
    source = ('HANDLERS = {\n'
              '    "resize": build(one),\n'
              '    "crop": build(two),\n'
              '}\n')
    assert "(" in _tokens(source)


def test_a_mapping_of_names_to_tables_is_data_at_any_size():
    """Nine languages, each with a list of node types. This is the shape the size arm was
    already catching, held here so the two arms cannot drift apart."""
    source = ("SPEC = {\n"
              + "".join(f'    "lang{i}": ["a", "b"],\n' for i in range(3))
              + "}\n")
    assert "L" not in _tokens(source)
