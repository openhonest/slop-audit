"""Regression tests for L1.18 module-global detection (_find_module_mutable_names).

These lock the four defects fixed on 2026-08-01 (see
research/amendments/amendment-2026-08-01-l1-18-module-global.md). Per the bug report, they
assert on the NAMES the extractor registers, not only on the ratio, because every
defect was visible in the name set and invisible in an aggregate count.
"""

from l1_analyzer.indicators import (
    LANG_CFG,
    _find_module_mutable_names,
    _get_parser,
    analyze_mutable_state,
)


def _names(src: str) -> set[str]:
    root = _get_parser("python").parse(src.encode()).root_node
    return _find_module_mutable_names(root, LANG_CFG["python"])


def test_defect1_binds_the_name_not_the_annotation_tail():
    # Previously returned {'str', 'FunctionNode'}: the annotation tail, not the name.
    assert _names('SITE_LABELS: dict[str, str] = {"a": "b"}\n') == set()      # uppercase populated -> constant table
    assert _names('site_map: dict[str, str] = {"a": "b"}\n') == {"site_map"}  # lowercase value binding still counts


def test_defect4_type_aliases_are_not_mutable_state():
    assert _names("FunctionNode = int | str\n") == set()
    assert _names("NodeStream = Iterable[int]\n") == set()
    assert _names("Requester = Callable[[int], object]\n") == set()
    assert _names("Dotted = ast.FunctionDef | ast.AsyncFunctionDef\n") == set()


def test_defect3_string_literals_are_not_scanned_for_identifiers():
    assert _names("WORKER = r'''let counter = 0; process.stdout.write(x)'''\n") == set()
    assert _names('DOC = "Silence index = 100 * sites / facets"\n') == set()


def test_defect2_uppercase_empty_container_is_a_mutable_accumulator():
    assert _names("RETAINED_PROOFS_BY_AUDIT = {}\n") == {"RETAINED_PROOFS_BY_AUDIT"}
    assert _names("CACHE: dict[str, int] = {}\n") == {"CACHE"}
    assert _names("BUF = []\n") == {"BUF"}
    assert _names("MAX = 100\n") == set()                 # uppercase scalar constant
    assert _names('LABELS = {"a": "b"}\n') == set()       # uppercase populated -> constant table


def test_empty_immutable_container_is_not_an_accumulator():
    # frozenset()/tuple are immutable and cannot accumulate, so an empty one is a
    # constant, not mutable state (regression for the honest-framework FIXABLE_RULES
    # false positive). Contrast the mutable empties above, which do count.
    assert _names("FIXABLE_RULES: frozenset = frozenset()\n") == set()
    assert _names("SEEN = frozenset()\n") == set()
    assert _names("EMPTY = ()\n") == set()


def test_lowercase_binding_still_counts():
    # The frozen convention: a lowercase module binding is mutable state.
    assert _names("counter = 0\n") == {"counter"}


def test_dunder_metadata_is_not_mutable_state():
    assert _names('__all__ = ["Foo", "Bar"]\n') == set()
    assert _names('__version__ = "1.0"\n') == set()


def test_annotated_table_plus_local_str_annotation_flags_nothing(tmp_path):
    (tmp_path / "m.py").write_text(
        'X: dict[str, str] = {"a": "b"}\n'
        "def f(v):\n    y: str = v\n    return y\n"
    )
    assert analyze_mutable_state(tmp_path, "python")["details"].startswith("0/1")


def test_type_alias_used_in_annotation_flags_nothing(tmp_path):
    (tmp_path / "m.py").write_text(
        "Alias = int | str\n"
        "def f(v: Alias):\n    return v\n"
    )
    assert analyze_mutable_state(tmp_path, "python")["details"].startswith("0/1")


def test_embedded_program_string_flags_nothing(tmp_path):
    (tmp_path / "m.py").write_text(
        "WORKER = r'''let counter = 0;'''\n"
        "def f():\n    counter = 1\n    return counter\n"   # local counter, unrelated to the string
    )
    assert analyze_mutable_state(tmp_path, "python")["details"].startswith("0/1")


def test_empty_cache_accumulator_flags_its_readers(tmp_path):
    # The case the indicator exists for: uppercase accumulator, both users counted.
    (tmp_path / "m.py").write_text(
        "CACHE: dict[str, int] = {}\n"
        "def put(k, v):\n    CACHE[k] = v\n"
        "def get(k):\n    return CACHE[k]\n"
    )
    assert analyze_mutable_state(tmp_path, "python")["details"].startswith("2/2")


# --- C file-scope declarations, read structurally rather than from line text ----
#
# C used the text heuristic, which needs an `=` on the line, so `static int cache[256];`
# declared no state at all and L1.18 read 0.0 Healthy over a file whose only state was that
# array. The classifier read the same file and called `cache` promiscuous. Two measures of
# one file disagreeing about what is even a candidate is the defect these pin.

_C_FILE_SCOPE = (
    "static int cache[256];\n"
    "int counter = 0;\n"
    "const int MAX = 10;\n"
    "static const char *NAME = \"x\";\n"
    "char *buf;\n"
    "void proto(int k);\n"
)


def _c_module_names(src: str) -> set[str]:
    from l1_analyzer.indicators import LANG_CFG
    from l1_analyzer.mutable_state import _find_module_mutable_names
    from l1_analyzer.state_bounds import _get_parser
    root = _get_parser("c").parse(src.encode()).root_node
    return _find_module_mutable_names(root, LANG_CFG["c"])


def test_a_c_array_with_no_initialiser_is_still_a_declaration():
    # The regression. No `=` on the line, so the text heuristic saw nothing.
    assert "cache" in _c_module_names(_C_FILE_SCOPE)


def test_every_non_const_c_file_scope_declarator_form_is_read():
    # array, initialiser and pointer forms all bind a name.
    assert _c_module_names(_C_FILE_SCOPE) == {"cache", "counter", "buf"}


def test_a_c_prototype_declares_no_state():
    assert _c_module_names("void proto(int k);\n") == set()


def test_a_c_function_pointer_is_state_because_it_is_rebindable():
    assert _c_module_names("void (*handler)(int);\n") == {"handler"}


def test_the_two_measures_agree_that_the_c_array_is_state():
    """The point of the fix: L1.18 and the classifier stop contradicting each other.

    Before, L1.18 read 0.0 Healthy over this file while the classifier called `cache`
    promiscuous. The write alone is not what makes it promiscuous: with only `put`, the
    classifier says neutral, because state nothing branches on is compositional. `get` reads
    it into a return, and that is the read that decides. I asserted promiscuous against the
    write-only fixture when writing this test and had to be corrected by the classifier.
    """
    import tempfile
    from pathlib import Path

    from l1_analyzer import mutable_state, state_bounds
    src = ("static int cache[256];\n\n"
           "void put(int k, int v) { cache[k] = v; }\n\n"
           "int get(int k) { return cache[k]; }\n")
    with tempfile.TemporaryDirectory() as d:
        Path(d, "a.c").write_text(src)
        counted = mutable_state.analyze_mutable_state(Path(d), "c")
        classified = state_bounds.classify(Path(d), "c")
    assert counted["value"] == 100.0, "both functions reach the array, so both count"
    assert any(f["state"] == "cache" and f["verdict"] == "promiscuous"
               for f in classified["findings"])
