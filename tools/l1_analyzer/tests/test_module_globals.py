"""Regression tests for L1.18 module-global detection (_find_module_mutable_names).

These lock the four defects fixed on 2026-08-01 (see
docs/amendment-2026-08-01-l1-18-module-global.md). Per the bug report, they
assert on the NAMES the extractor registers, not only on the ratio, because every
defect was visible in the name set and invisible in an aggregate count.
"""

from l1_analyzer.indicators import LANG_CFG, _find_module_mutable_names, _get_parser, analyze_mutable_state


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
