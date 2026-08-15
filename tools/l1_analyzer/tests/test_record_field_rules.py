"""Record-field state: the slots a language declares inside a record type.

Three declaration kinds reached the census with no rule behind them, and the census said
so on every report it touched: a Python name bound in a class body, a C struct field, and
a C# auto-property. Each is a place a program keeps data for the life of a process, and
for each the classifier's enumerator had nothing that could match it. A repository whose
state is spelled that way was not passing the finite-testability meter, it was unexamined
by it, and the card printed "none of the data this code keeps can grow without limit" over
a reading of nothing.

The proof each gap is closed is `state_census.CAPABILITY` flipping from `admitted: False`
to `admitted: True` for that pair, because that value is MEASURED against the real
classifier by `tests/test_state_census.py` rather than asserted. The tests here are the
other half: they pin the verdict the rule must reach, so a rule that enumerates a slot and
then says nothing useful about it cannot pass by flipping a boolean.
"""

from __future__ import annotations

from l1_analyzer import state_bounds, state_census

# The same unbounded cache in three languages, each spelled the way its own grammar hides
# it from a reference-driven enumerator. `cache[k]` with a variable key is an unbounded
# lookup in all three; only the declaration site differs.
#
# The Python one reads the cache in a branch where the other two return it, and the extra
# `if` is not decoration. `state_bounds_filters` runs on Python alone and clears a
# promiscuous verdict whose value reaches no decision, so a Python fixture that only stored
# and returned would come back NEUTRAL through a filter that has nothing to do with the rule
# under test. The branch is what makes this test measure the enumerator.
PY_CLASS_BODY = (
    "class Store:\n"
    "    cache = {}\n"
    "\n"
    "    def put(self, k, v):\n"
    "        Store.cache[k] = v\n"
    "\n"
    "    def route(self, k):\n"
    "        if Store.cache[k]:\n"
    "            return 1\n"
    "        return 0\n"
)
C_STRUCT_FIELD = (
    "struct Store { int cache[256]; };\n"
    "void put(struct Store *s, int k, int v) { s->cache[k] = v; }\n"
    "int get(struct Store *s, int k) { return s->cache[k]; }\n"
)
CS_PROPERTY = (
    "class Store {\n"
    "    public System.Collections.Generic.Dictionary<string, int> Cache { get; set; }\n"
    "    void Put(string k, int v) { Cache[k] = v; }\n"
    "    int Get(string k) { return Cache[k]; }\n"
    "}\n"
)


def _findings(tmp_path, name: str, src: str, lang: str) -> list[dict]:
    (tmp_path / name).write_text(src)
    return state_bounds.classify(tmp_path, lang)["findings"]


def _verdict_of(findings: list[dict], ending: str) -> str:
    matched = [f for f in findings if f["state"].endswith(ending)]
    assert matched, f"no finding for a state named ...{ending}; got {[f['state'] for f in findings]}"
    return matched[0]["verdict"]


# --------------------------------------------------------------------------
# Python: a name bound in a class body.
# --------------------------------------------------------------------------

def test_a_python_class_body_binding_is_read_as_state(tmp_path):
    """`class Store: cache = {}` is one dict shared by every instance for the life of the
    process. The receiver rule enumerates `self.x = ...` and the module scan reaches root
    children, so this binding sat between the two and was read by neither."""
    assert _verdict_of(_findings(tmp_path, "m.py", PY_CLASS_BODY, "python"), ".cache") == state_bounds.PROMISCUOUS


def test_the_census_records_python_class_body_bindings_as_readable():
    assert state_census.CAPABILITY[("python", state_census.CLASS_BODY_BINDING)]["admitted"] is True


def test_a_class_body_slot_the_receiver_rule_already_enumerates_is_not_counted_twice(tmp_path):
    """A default declared in the class body and then rebound per instance is one slot. The
    receiver rule already reports it, so the record rule must stand down rather than publish
    a second finding about the same state and inflate every count computed over findings."""
    src = (
        "class Store:\n"
        "    cache = {}\n"
        "\n"
        "    def __init__(self):\n"
        "        self.cache = {}\n"
        "\n"
        "    def put(self, k, v):\n"
        "        self.cache[k] = v\n"
    )
    findings = _findings(tmp_path, "m.py", src, "python")
    assert len([f for f in findings if f["state"].endswith("cache")]) == 1


def test_a_bare_annotation_nothing_references_declares_no_state(tmp_path):
    """`class Row(TypedDict): name: str` binds nothing at run time. The rule enumerates the
    slot and finds no reference to it, which is how a type declaration stays out of the
    findings without a special case that would also silence a dataclass field."""
    src = "from typing import TypedDict\n\n\nclass Row(TypedDict):\n    name: str\n    count: int\n"
    assert _findings(tmp_path, "m.py", src, "python") == []


# --------------------------------------------------------------------------
# C: a field declared inside a struct.
# --------------------------------------------------------------------------

def test_a_c_struct_field_is_read_as_state(tmp_path):
    """The case the census was built to expose: the identical unbounded cache graded F at
    file scope and A one syntactic level down, because the C enumerator read file-scope
    declarations and nothing else."""
    assert _verdict_of(_findings(tmp_path, "m.c", C_STRUCT_FIELD, "c"), ".cache") == state_bounds.PROMISCUOUS


def test_the_census_records_c_struct_fields_as_readable():
    assert state_census.CAPABILITY[("c", state_census.FIELD_DECLARATION)]["admitted"] is True


def test_a_c_struct_field_nothing_in_the_file_touches_yields_no_finding(tmp_path):
    """A field declared in a header and used in another translation unit is out of reach:
    references are collected per file, as they are for every other language here. The rule
    reports nothing rather than inventing a verdict over zero references."""
    (tmp_path / "m.h").write_text("struct Store { int cache[256]; };\n")
    assert state_bounds.classify(tmp_path, "c")["findings"] == []


# --------------------------------------------------------------------------
# C#: an auto-property.
# --------------------------------------------------------------------------

def test_a_csharp_auto_property_is_read_as_state(tmp_path):
    """A property holds state as surely as a field does, and `field_decl_types` named
    `field_declaration` alone, so the same dictionary was read when it was written as a
    field and invisible when it was written with accessors."""
    assert _verdict_of(_findings(tmp_path, "M.cs", CS_PROPERTY, "csharp"), "Cache") == state_bounds.PROMISCUOUS


def test_the_census_records_csharp_properties_as_readable():
    assert state_census.CAPABILITY[("csharp", state_census.PROPERTY_DECLARATION)]["admitted"] is True
