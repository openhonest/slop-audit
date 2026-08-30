"""The state finding says what it holds, so a reader can be told it read the wrong field.

It was `dict[str, object]`, the least precise mapping the language has. Nine fields are
written by two builders and read by four modules, and every one of those reads was an
assumption: nothing could say whether `partition` was a partition or `line` a number. The
type checker reported twenty-one of those reads as indexing an `object`, which is the same
sentence in its own words.

Written out, so a renamed field fails at the read rather than at whatever the reader did
with the KeyError.
"""

import typing

from l1_analyzer.state_partition import Finding

_FIELDS = typing.get_type_hints(Finding)

_BUILT_BY_STATE_BOUNDS = {
    "state", "verdict", "drives_decision", "file", "line", "silence", "construct",
    "silence_line", "partition",
}


def test_the_finding_names_every_field_its_builders_write():
    assert set(_FIELDS) == _BUILT_BY_STATE_BOUNDS


def test_the_partition_is_a_partition_rather_than_anything():
    """The field eight reads go through. `f["partition"]["counted"]` was two unchecked
    indexings in a row."""
    from l1_analyzer.state_partition import Partition

    assert _FIELDS["partition"] is Partition


def test_the_line_numbers_are_numbers():
    """Both are added to and compared, and neither was declared as anything."""
    assert _FIELDS["line"] is int
    assert _FIELDS["silence_line"] is int


def test_both_builders_write_exactly_these_fields():
    """The check that keeps the declaration honest as the builders change. Reading them from
    the source rather than restating them here: a list written twice is the defect this file
    exists about."""
    import ast
    import pathlib

    source = (pathlib.Path(__file__).resolve().parents[1]
              / "l1_analyzer" / "state_bounds.py").read_text()
    builder = next(n for n in ast.walk(ast.parse(source))
                   if isinstance(n, ast.FunctionDef) and n.name == "_finding")
    written = [{k.value for k in d.keys if isinstance(k, ast.Constant)}
               for d in ast.walk(builder) if isinstance(d, ast.Dict) and d.keys]
    returned = [w for w in written if "state" in w]
    assert returned, "no dict in _finding carries a state key any more"
    for fields in returned:
        assert fields == _BUILT_BY_STATE_BOUNDS
