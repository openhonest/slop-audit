"""The write-once rule reads the language's vocabulary, so it serves all nine.

It named Python's node types and field names directly: `attribute`, `assignment`,
`return_statement`, `argument_list`, `call`, and the fields `left`, `object`, `function`.
So it ran for Python and nobody else, and every shape it clears is a shape where Python
could disagree with the other eight about the same code.

The rule itself is one claim: a value assigned exactly once, never mutated afterwards, never
handed out whole, and never passed to a callee nobody modelled, cannot grow. That claim is
about programs and not about Python, and the vocabulary already carried every node type it
needed.

Two of the four halves needed a spelling the port exposed. Java and Ruby hang a receiver, a
method and its arguments off ONE node, so the in-place-mutation check walked a member access
those two never build. And the compound assignment that writes in place is told from the
plain one by whether the grammar hung an operator on it, which every one of the nine does.
"""

import tempfile
from pathlib import Path

import pytest
from l1_analyzer import state_bounds, state_bounds_filters
from l1_analyzer.indicators import _get_parser
from l1_analyzer.lang_spec import LANG_SPEC

_JAVA_ONCE = ("class A {\n  private java.util.List<String> rows;\n"
              "  A(java.util.List<String> rows) { this.rows = rows; }\n"
              "  int size() { return rows.size(); }\n}\n")
_RUBY_ONCE = ("class A\n  def initialize(rows)\n    @rows = rows\n  end\n"
              "  def size\n    @rows.size\n  end\nend\n")
_PY_ONCE = ("class A:\n    def __init__(self, rows):\n        self._rows = rows\n"
            "    def size(self):\n        return len(self._rows)\n")

_ONCE = {"java": ("M.java", _JAVA_ONCE), "ruby": ("a.rb", _RUBY_ONCE),
         "python": ("m.py", _PY_ONCE)}

_JAVA_MUTATED = ("class A {\n  private java.util.List<String> rows;\n"
                 "  A(java.util.List<String> rows) { this.rows = rows; }\n"
                 "  void add(String s) { rows.add(s); }\n}\n")
_RUBY_MUTATED = ("class A\n  def initialize(rows)\n    @rows = rows\n  end\n"
                 "  def add(s)\n    @rows.push(s)\n  end\nend\n")
_PY_MUTATED = ("class A:\n    def __init__(self, rows):\n        self._rows = rows\n"
               "    def add(self, s):\n        self._rows.append(s)\n")

_MUTATED = {"java": ("M.java", _JAVA_MUTATED), "ruby": ("a.rb", _RUBY_MUTATED),
            "python": ("m.py", _PY_MUTATED)}


def _write_once(lang: str, source: tuple[str, str]) -> bool:
    """Whether the rule itself clears this shape, asked directly.

    Directly, because the classifier can agree with the rule by another route and a test
    reading only the final verdict cannot tell which of them answered."""
    _name, src = source
    spec = LANG_SPEC[lang]
    root = _get_parser(lang).parse(src.encode()).root_node

    def walk(node):
        yield node
        for child in node.children:
            yield from walk(child)

    from l1_analyzer.state_bounds import _state_refs

    cls = next(n for n in walk(root) if n.type in spec["class_types"])
    key = {"python": "self._rows", "ruby": "@rows", "java": "rows"}[lang]
    # The key and the attribute name derived from it exactly as the caller derives them.
    # Ruby's sigil survives on purpose, because the grammar puts it in the node, and a test
    # that strips it asks about an attribute no reference names.
    #
    # The references are the ones the classifier itself collects, not every leaf that spells
    # the name: a leaf inside `self._rows` is the attribute half of a member access, and the
    # rule is handed the whole access.
    return state_bounds_filters._is_write_once(
        cls, state_bounds_filters._attr(key), _state_refs(cls, key, spec), spec)


@pytest.mark.parametrize("lang", sorted(_ONCE))
def test_a_value_assigned_once_and_never_mutated_is_write_once(lang):
    assert _write_once(lang, _ONCE[lang]) is True, lang


@pytest.mark.parametrize("lang", sorted(_MUTATED))
def test_a_value_mutated_after_it_is_assigned_is_not(lang):
    """The half the port had to get right in two spellings. Java and Ruby hang the receiver,
    the method and the arguments off one node, so the check for a mutating method walked a
    member access those two never build and saw nothing."""
    assert _write_once(lang, _MUTATED[lang]) is False, lang


@pytest.mark.parametrize("lang", sorted(_ONCE))
def test_the_verdict_the_whole_reader_publishes_agrees(lang):
    name, src = _ONCE[lang]
    with tempfile.TemporaryDirectory() as t:
        path = Path(t)
        (path / name).write_text(src)
        reading = state_bounds.classify(path, lang)
    verdicts = {f["verdict"] for f in reading["findings"]}
    assert verdicts <= {"neutral"}, (lang, verdicts)


def test_a_compound_assignment_is_told_from_a_plain_one_by_its_operator():
    """Every grammar here spells the compound form as a node carrying its operator and the
    plain form as one carrying none. The first draft of the port asked whether the operator
    was something other than `=`, and an absent operator answered yes, so every write-once
    attribute in the language read as mutated and the rule cleared nothing at all."""
    src = "class A:\n    def __init__(self):\n        self.n = 0\n    def bump(self):\n        self.n += 1\n"
    assert _write_once_named("python", src, "n") is False


def _write_once_named(lang: str, src: str, attr: str) -> bool:
    spec = LANG_SPEC[lang]
    root = _get_parser(lang).parse(src.encode()).root_node

    def walk(node):
        yield node
        for child in node.children:
            yield from walk(child)

    from l1_analyzer.state_bounds import _state_refs

    cls = next(n for n in walk(root) if n.type in spec["class_types"])
    return state_bounds_filters._is_write_once(
        cls, attr, _state_refs(cls, f"self.{attr}", spec), spec)
