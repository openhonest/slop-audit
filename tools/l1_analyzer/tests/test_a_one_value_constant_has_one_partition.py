"""A state settled at one value carries the same partition however it was settled.

Two branches decide a constant. A language declaring `private static final int X = 11` is a
declared constant; Python constructing an immutable value is an immutable constant. Both
have a one-value domain and neither has anything to order, and the two wrote different
partitions: the second used the module's own EMPTY, one class and ordered, and the first
built a per-reference REACH with ordered false.

The reach is the wrong shape entirely. It is what ONE reference does to the domain, and the
field it was assigned to holds the rolled-up partition of all of them. It carries four
fields the partition does not have, so at run time it fitted and told the summary a
one-value constant was unordered.

The published effect: every declared constant landed in the unordered-classes list, which is
the distribution the coarseness bound is meant to be set from.
"""

import pathlib

import pytest
from l1_analyzer import state_bounds
from l1_analyzer.state_partition import EMPTY

_JAVA = ("class A {\n    private static final int X = 11;\n"
         "    int f(int v) { return v == X ? 1 : 0; }\n}\n")
_CSHARP = ("class A {\n    private const int X = 11;\n"
           "    int F(int v) { return v == X ? 1 : 0; }\n}\n")

_CONSTANTS = {"java": ("A.java", _JAVA), "csharp": ("A.cs", _CSHARP)}


def _partitions(tmp_path, lang, name, source):
    (tmp_path / name).write_text(source)
    return [f["partition"] for f in state_bounds.classify(tmp_path, lang)["findings"]]


@pytest.mark.parametrize("lang", sorted(_CONSTANTS))
def test_a_declared_constant_carries_one_ordered_class(tmp_path, lang):
    name, source = _CONSTANTS[lang]
    for partition in _partitions(tmp_path, lang, name, source):
        assert partition == EMPTY, partition


@pytest.mark.parametrize("lang", sorted(_CONSTANTS))
def test_a_declared_constant_carries_no_field_a_partition_lacks(tmp_path, lang):
    """The reach's four extra fields. They fitted at run time, which is why nothing noticed
    for as long as the field said nothing about its type."""
    name, source = _CONSTANTS[lang]
    for partition in _partitions(tmp_path, lang, name, source):
        assert set(partition) == {"classes", "ordered", "counted"}, partition


def test_the_two_constant_branches_write_the_same_partition():
    """Read from the source, so the two branches cannot drift apart again. A one-value
    domain is one fact whichever branch established it."""
    import ast

    source = (pathlib.Path(__file__).resolve().parents[1]
              / "l1_analyzer" / "state_bounds.py").read_text()
    fn = next(n for n in ast.walk(ast.parse(source))
              if isinstance(n, ast.FunctionDef) and n.name == "_finding")
    written = {ast.unparse(n) for n in ast.walk(fn)
               if isinstance(n, ast.Attribute) and ast.unparse(n).startswith("state_partition.")}
    assert "state_partition.finite" not in written, (
        "a per-reference reach is being written where the rolled-up partition belongs")
