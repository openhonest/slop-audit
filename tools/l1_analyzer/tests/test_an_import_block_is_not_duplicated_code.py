"""Two modules importing the same names is not one module written twice.

After the record fix, the two largest remaining contributors to this repository's duplication
number are import blocks. Ten `from x import y as _y` lines in one module and ten in another
normalise to the same token stream, because that is what an import statement is: a list of
names, and this check erases names.

There is no logic in an import, so there is nothing here for the check to be about. And the
duplication cannot be removed: a module that uses a name has to import it. A measurement an
author cannot act on teaches them to ignore the measurement, which is worse than not taking
it. An adopter made exactly that argument to us about a different rule this week, and it is
the argument that decided this one.

Same family as the two discounts already here. A data table is not a pile of logic. A record
declaration is a list of field names. An import block is a list of imported names.
"""

from l1_analyzer import clone_detect
from l1_analyzer.indicators import _get_parser

_TWO_MODULES_IMPORTING_THE_SAME = (
    "from pkg.a import one as _one\nfrom pkg.a import two as _two\n"
    "from pkg.b import three as _three\nfrom pkg.b import four as _four\n"
    "from pkg.c import five as _five\nfrom pkg.c import six as _six\n"
    "from pkg.d import seven as _seven\nfrom pkg.d import eight as _eight\n")

_TWO_FUNCTIONS = '''def widen(values, limit):
    out = []
    for value in values:
        if value > limit:
            out.append(value * 2)
        else:
            out.append(value)
    return out


def narrow(items, ceiling):
    kept = []
    for item in items:
        if item > ceiling:
            kept.append(item * 2)
        else:
            kept.append(item)
    return kept
'''


def _duplicated(sources: dict[str, str], min_tokens: int = 20) -> int:
    parser = _get_parser("python")
    streams = {name: clone_detect.normalized_tokens(parser.parse(text.encode()).root_node,
                                                    "python")
               for name, text in sources.items()}
    return sum(len(v) for v in clone_detect.duplicated_lines(streams, min_tokens).values())


def test_two_modules_importing_the_same_names_are_not_duplicated_code():
    assert _duplicated({"a.py": _TWO_MODULES_IMPORTING_THE_SAME,
                        "b.py": _TWO_MODULES_IMPORTING_THE_SAME}) == 0


def test_two_functions_doing_the_same_thing_still_are():
    """The direction that must not move."""
    assert _duplicated({"a.py": _TWO_FUNCTIONS}) > 0


def test_code_beside_an_import_block_is_still_read():
    """Skipping the import must not skip the file. A module is not exempt because it starts
    with imports, which every module does."""
    both = _TWO_MODULES_IMPORTING_THE_SAME + "\n\n" + _TWO_FUNCTIONS
    assert _duplicated({"a.py": both}) > 0


def test_a_call_that_imports_at_runtime_is_still_code():
    """`importlib.import_module(name)` is a call and does work. Only the statement is a
    declaration, and treating the call as one would hide a real repeated block."""
    runtime = "".join(
        f"def load_{n}(name):\n    module = importlib.import_module(name)\n"
        f"    return getattr(module, 'go_{n}')\n\n\n" for n in range(6))
    assert _duplicated({"a.py": runtime}) > 0


def test_the_reading_names_every_discount_it_makes(tmp_path):
    """It named one of three. A reader told about the data table and not about records or
    imports is told this check read more code than it did, which is the disclosure failure
    this instrument exists to report in other people's tools."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "a.py").write_text(_TWO_FUNCTIONS)
    details = clone_detect.analyze(tmp_path, "python")["details"]
    for discount in ("data table", "record declaration", "import statement"):
        assert discount in details, discount
