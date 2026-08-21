"""The facet readers, each called directly rather than through a whole audit.

Sixteen functions in `facets.py` had no test that called them. `--facets` on the module
itself said so: 82.8% coverage against a 47.8% Silence index, with every helper listed
under `unasserted return contract`. The suite drove them all through `audit()`, which
runs a real pytest subprocess, so a helper could be wrong in a way the end-to-end path
happened to absorb and nothing would say which one.

That reading also found a defect in the reader, and it is the same bug this instrument
exists to name, mirrored. `_annotation` returned the empty string for two different facts:
"no type was declared" and "a type was declared and I could not read it". Every parameter
typed `ast.AST`, `ast.expr` or `int | None` was filed as an UNDECLARED DOMAIN, which
blames the author for a gap in the reader. The two questions are now asked separately:
`is_declared` answers whether there is a type, `_annotation` answers which one.
"""

import ast

import pytest
from l1_analyzer import facets


def _tree(source: str) -> ast.AST:
    return ast.parse(source)


def _fn(source: str) -> ast.FunctionDef:
    return next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef))


# --------------------------------------------------------------------------
# Reading the tree
# --------------------------------------------------------------------------

def test_every_function_in_a_tree_is_found_including_nested_and_method():
    source = ("def top(n: int) -> int:\n    def inner() -> int:\n        return 1\n"
              "    return inner()\n\n\nclass C:\n    def m(self) -> int:\n        return 2\n")
    assert {fn.name for fn in facets._functions(ast.parse(source))} == {"top", "inner", "m"}


def test_a_tree_with_no_function_yields_none():
    assert facets._functions(ast.parse("X = 1\n")) == []


@pytest.mark.parametrize(("target", "names"), [
    ("a", ["a"]), ("a, b", ["a", "b"]), ("[a, b]", ["a", "b"]),
    ("a, (b, c)", ["a", "b", "c"]), ("holder.field", []), ("holder[0]", []),
])
def test_the_names_an_assignment_target_binds_are_read(target, names):
    assigned = ast.parse(f"{target} = f()").body[0]
    assert facets._names(assigned.targets[0]) == names


# --------------------------------------------------------------------------
# Declared, versus readable
# --------------------------------------------------------------------------

@pytest.mark.parametrize("annotation", ["int", "list[int]", "ast.AST", "ast.expr | None",
                                        "dict[str, set[str]]", '"Facet"'])
def test_a_declared_type_is_declared_however_it_is_spelled(annotation):
    """The defect: a dotted name and a union are types, and both read as undeclared."""
    fn = _fn(f"def f(x: {annotation}) -> None:\n    pass\n")
    assert facets.is_declared(fn.args.args[0].annotation) is True, annotation


def test_an_absent_annotation_is_the_only_undeclared_case():
    fn = _fn("def f(x):\n    pass\n")
    assert facets.is_declared(fn.args.args[0].annotation) is False


@pytest.mark.parametrize(("annotation", "expected"), [
    ("int", "int"), ("list[int]", "list"), ("ast.AST", "AST"), ('"Facet"', "Facet"),
    ("dict[str, set[str]]", "dict"), ("None", "None"),
])
def test_the_bare_name_of_a_declared_type_is_read(annotation, expected):
    fn = _fn(f"def f(x: {annotation}) -> None:\n    pass\n")
    assert facets._annotation(fn.args.args[0].annotation) == expected


def test_a_declared_none_return_is_named_rather_than_read_as_absent():
    """`-> None` is a Constant, not a Name, and read as empty. "Declared nothing" and
    "declared None" were the same answer, which is the `_annotation` defect one layer
    down. `_return_facet` happened to be right because it tested for both."""
    fn = _fn("def f(n: int) -> None:\n    pass\n")
    assert facets._annotation(fn.returns) == "None"
    assert facets.is_declared(fn.returns) is True


def test_a_union_has_no_single_bare_name():
    """A union is declared and carries no one region table, so the name is empty and
    `is_declared` is what keeps it out of the undeclared list."""
    fn = _fn("def f(x: int | None) -> None:\n    pass\n")
    assert facets._annotation(fn.args.args[0].annotation) == ""


def test_a_dotted_parameter_type_is_not_reported_undeclared():
    """The whole defect, at the level a reader sees it."""
    fn = _fn("def f(tree: ast.AST) -> list:\n    return []\n")
    _regions, undeclared = facets._region_facets(fn, {})
    assert undeclared == [], undeclared


# --------------------------------------------------------------------------
# What a test file supplies
# --------------------------------------------------------------------------

def test_a_declared_parameter_type_with_no_region_table_yields_no_region_facet():
    """`Path` has no canonical boundary regions, so there is nothing to enumerate. That is
    not the same as an undeclared parameter and must not be reported as one."""
    fn = _fn("def f(target: Path) -> None:\n    pass\n")
    regions, undeclared = facets._region_facets(fn, {})
    assert regions == [] and undeclared == []


def test_an_undeclared_parameter_yields_one_undeclared_domain_and_no_region():
    fn = _fn("def f(x) -> None:\n    pass\n")
    regions, undeclared = facets._region_facets(fn, {})
    assert regions == []
    assert [u["detail"] for u in undeclared] == ["parameter `x` has no declared type"]


def test_a_method_is_not_charged_for_its_own_receiver():
    """`self` is bound by the call, not supplied by the caller, so it has no input region
    and it is not an undeclared domain either."""
    fn = _fn("class C:\n    def m(self, n: int) -> int:\n        return n\n")
    regions, undeclared = facets._region_facets(fn, {})
    assert {f["detail"].split("`")[1].split(":")[0] for f in regions} == {"n"}
    assert undeclared == []


def test_a_keyword_only_parameter_carries_regions_too():
    fn = _fn("def f(*, limit: int) -> int:\n    return limit\n")
    regions, _undeclared = facets._region_facets(fn, {"f/limit": {"zero"}})
    assert {f["detail"].rsplit(" ", 1)[-1]: f["silent"] for f in regions} == {
        "zero": False, "positive": True, "negative": True}


def test_asserted_calls_reads_a_call_inside_an_assert():
    assert facets.asserted_calls(_tree("def t():\n    assert band(1) == 'x'\n")) == {"band"}


def test_asserted_calls_reads_a_call_bound_to_a_name_the_test_asserts_about():
    source = "def t():\n    result = band(1)\n    assert result == 'x'\n"
    assert facets.asserted_calls(_tree(source)) == {"band"}


def test_a_bare_call_statement_is_not_asserted_evidence():
    """It proves the function runs and nothing about what it returns, which is the gap
    `unasserted_return_contract` names."""
    assert facets.asserted_calls(_tree("def t():\n    band(1)\n")) == set()


def test_a_name_bound_and_never_asserted_about_is_not_evidence():
    """`band`'s result is dropped. `other`'s is asserted, so it is evidence and belongs."""
    source = "def t():\n    result = band(1)\n    assert other() == 1\n"
    assert facets.asserted_calls(_tree(source)) == {"other"}


def test_a_result_the_test_unpacks_and_asserts_on_is_evidence():
    """`a, b = f()` then `assert a == 1`. Reading only the plain-name form meant a function
    whose result the test unpacks read as having no evidence at all."""
    source = "def t():\n    kept, dropped = split(1)\n    assert kept == 1\n"
    assert facets.asserted_calls(_tree(source)) == {"split"}


def test_a_target_that_binds_no_name_binds_nothing():
    source = "def t():\n    holder.field = split(1)\n    assert holder.field == 1\n"
    assert facets.asserted_calls(_tree(source)) == set()


@pytest.mark.parametrize(("call", "region"), [
    ("set()", "empty"), ("dict()", "empty"), ("list()", "empty"), ("tuple()", "empty"),
    ("frozenset()", "empty"), ("str()", "empty"), ("bytes()", "empty"),
    ("list([1])", "non-empty"), ("dict(a=1)", "non-empty"),
    ("int()", "zero"), ("float()", "zero"), ("int('7')", ""), ("other()", ""),
])
def test_an_empty_collection_written_as_a_constructor_lands_in_a_region(call, region):
    """`set()` is how an empty set is usually written. Reading it as unreadable reported a
    region silent that the test right in front of it supplies."""
    assert facets._region_of(ast.parse(call, mode="eval").body) == region


def test_regions_of_reads_nothing_from_an_empty_binding_table():
    assert facets.regions_of(ast.parse("value", mode="eval").body, {}, {}) == set()


def test_expected_exceptions_names_the_function_whose_raise_is_asserted():
    """The set holds FUNCTIONS, not exception types, because the facet it closes belongs to
    the function that raises. The type is already in the facet's own detail."""
    source = ("def t():\n    with pytest.raises(ValueError):\n        divide(1, 0)\n")
    assert facets.expected_exceptions(_tree(source)) == {"divide"}


def test_the_raises_call_itself_is_not_collected_as_evidence():
    """It was, and `raises` went into the set. Any module holding a function of that name
    had its exception path read as asserted by any raises block anywhere in the suite."""
    source = "def t():\n    with pytest.raises(ValueError):\n        divide(1, 0)\n"
    assert "raises" not in facets.expected_exceptions(_tree(source))


def test_expected_exceptions_ignores_an_unrelated_context_manager():
    source = "def t():\n    with open('f') as handle:\n        f(handle)\n"
    assert facets.expected_exceptions(_tree(source)) == set()


# --------------------------------------------------------------------------
# Regions, names and bindings
# --------------------------------------------------------------------------

@pytest.mark.parametrize(("literal", "region"), [
    ("0", "zero"), ("7", "positive"), ("-7", "negative"), ("-0", "negative"),
    ("0.0", "zero"), ("''", "empty"), ("'x'", "non-empty"), ("b''", "empty"),
    ("[]", "empty"), ("[1]", "non-empty"), ("{}", "empty"), ("{'a': 1}", "non-empty"),
    ("()", "empty"), ("(1,)", "non-empty"), ("True", "true"),
    ("False", "false"), ("None", ""), ("some_name", ""),
])
def test_a_literal_lands_in_one_region_or_in_none(literal, region):
    """`-0` reads negative because the source says negative: the reader is looking at what
    the author wrote, and reading it as zero would silently merge two written intents."""
    node = ast.parse(literal, mode="eval").body
    assert facets._region_of(node) == region


@pytest.mark.parametrize(("call", "name"), [
    ("band(1)", "band"), ("m.band(1)", "band"), ("get()(1)", "")])
def test_the_called_name_is_read_from_a_plain_call_and_an_attribute(call, name):
    node = ast.parse(call, mode="eval").body
    assert facets.called_name(node) == name


def test_bound_regions_reads_a_parametrize_decorator():
    source = ("@pytest.mark.parametrize(('n', 'expected'), [(20, 'high'), (0, 'low')])\n"
              "def t(n, expected):\n    assert band(n) == expected\n")
    assert facets.bound_regions(_tree(source)) == {
        "n": {"positive", "zero"}, "expected": {"non-empty"}}


def test_bound_regions_reads_a_single_name_spelled_as_a_string():
    source = ("@pytest.mark.parametrize('n', [1, 0])\n"
              "def t(n):\n    assert band(n)\n")
    assert facets.bound_regions(_tree(source)) == {"n": {"positive", "zero"}}


def test_bound_regions_reads_several_names_from_one_comma_separated_string():
    source = ("@pytest.mark.parametrize('n, flag', [(1, True)])\n"
              "def t(n, flag):\n    assert band(n, flag)\n")
    assert facets.bound_regions(_tree(source)) == {"n": {"positive"}, "flag": {"true"}}


def test_a_parametrize_case_that_is_not_a_literal_contributes_nothing():
    """A guess about where a computed value lands is not evidence."""
    source = ("@pytest.mark.parametrize('n', [random.randint(1, 9)])\n"
              "def t(n):\n    assert band(n)\n")
    assert facets.bound_regions(_tree(source)) == {}


def test_a_decorator_that_is_not_parametrize_yields_nothing():
    node = ast.parse("pytest.mark.skipif(True, reason='x')", mode="eval").body
    assert facets._parametrized(node) == []


def test_a_parametrize_missing_its_case_list_yields_nothing():
    node = ast.parse("pytest.mark.parametrize('n')", mode="eval").body
    assert facets._parametrized(node) == []


def test_bound_regions_reads_a_plain_assignment():
    assert facets.bound_regions(_tree("def t():\n    value = 0\n    assert band(value)\n")) == {
        "value": {"zero"}}


def test_an_assignment_to_something_other_than_a_name_binds_nothing():
    source = "def t():\n    holder.value = 0\n    assert band(holder.value)\n"
    assert facets.bound_regions(_tree(source)) == {}


def test_a_parametrize_whose_cases_are_a_name_yields_nothing():
    """The case list has to be readable. A name pointing at a list built elsewhere could
    hold anything, and assuming it holds the regions would be counting absent evidence."""
    node = ast.parse("pytest.mark.parametrize('n', CASES)", mode="eval").body
    assert facets._parametrized(node) == []


def test_a_parametrize_whose_names_are_neither_a_string_nor_a_tuple_yields_nothing():
    node = ast.parse("pytest.mark.parametrize(NAMES, [(1,)])", mode="eval").body
    assert facets._parametrized(node) == []


def test_regions_of_reads_a_literal_a_bound_name_and_a_factory_call():
    """Two tables, because a name and a call of the same spelling are different facts."""
    names, factories = {"value": {"zero"}}, {"make": {"empty"}}
    read = lambda text: facets.regions_of(ast.parse(text, mode="eval").body, names, factories)
    assert read("7") == {"positive"}
    assert read("value") == {"zero"}
    assert read("make()") == {"empty"}
    assert read("value()") == set(), "a call is not the name it shares a spelling with"
    assert read("make") == set(), "a name is not the factory it shares a spelling with"
    assert read("other") == set()


def test_a_call_with_no_readable_name_supplies_nothing():
    supplied = facets.supplied_regions(_tree("def t():\n    assert get()(0) == 'x'\n"))
    assert not any(key.startswith("/") for key in supplied), supplied


def test_supplied_regions_keys_a_positional_argument_by_its_position():
    supplied = facets.supplied_regions(_tree("def t():\n    assert band(0) == 'x'\n"))
    assert supplied["band/0"] == {"zero"}


def test_supplied_regions_keys_a_keyword_argument_by_its_name():
    supplied = facets.supplied_regions(_tree("def t():\n    assert band(n=0) == 'x'\n"))
    assert supplied["band/n"] == {"zero"}


# --------------------------------------------------------------------------
# The facet builders
# --------------------------------------------------------------------------

def test_a_branch_facet_is_silent_when_its_line_is_uncovered():
    fn = _fn("def band(n: int) -> str:\n    if n > 10:\n        return 'high'\n    return 'low'\n")
    # Line 3, the first line of the BODY. The `if` on line 2 runs whenever the function is
    # reached, so its own coverage says nothing about whether the arm was entered.
    silent = facets._branch_facets(fn, frozenset({3}))
    assert [f["silent"] for f in silent] == [True]
    assert facets._branch_facets(fn, frozenset())[0]["silent"] is False


def test_a_function_with_no_branch_yields_no_branch_facet():
    assert facets._branch_facets(_fn("def f(n: int) -> int:\n    return n\n"), frozenset()) == []


def test_a_return_facet_is_closed_by_an_assertion_on_the_result():
    fn = _fn("def band(n: int) -> str:\n    return 'x'\n")
    assert facets._return_facet(fn, {"band"})[0]["silent"] is False
    assert facets._return_facet(fn, set())[0]["silent"] is True


@pytest.mark.parametrize("returns", ["", " -> None"])
def test_a_function_declaring_no_value_has_no_return_contract(returns):
    assert facets._return_facet(_fn(f"def f(n: int){returns}:\n    pass\n"), set()) == []


def test_an_exception_facet_is_closed_by_a_test_expecting_it_from_that_function():
    fn = _fn("def f(n: int) -> int:\n    raise ValueError('x')\n")
    assert facets._exception_facets(fn, {"f"})[0]["silent"] is False
    assert facets._exception_facets(fn, {"other"})[0]["silent"] is True
    assert facets._exception_facets(fn, {"f"})[0]["detail"] == "raises ValueError"


def test_a_function_that_raises_nothing_explicitly_has_no_exception_facet():
    assert facets._exception_facets(_fn("def f(n: int) -> int:\n    return n\n"), set()) == []


def test_a_bare_reraise_is_not_an_exception_path_of_its_own():
    """`raise` inside an except block re-raises what is already being handled, so counting
    it would ask a test to expect an exception this function does not introduce."""
    source = "def f(n: int) -> int:\n    try:\n        return n\n    except KeyError:\n        raise\n"
    assert facets._exception_facets(_fn(source), set()) == []


# --------------------------------------------------------------------------
# Where the suite has to run from
# --------------------------------------------------------------------------

def test_the_import_root_of_a_loose_module_is_its_own_directory(tmp_path):
    (tmp_path / "m.py").write_text("X = 1\n")
    assert facets.import_root(tmp_path / "m.py") == tmp_path


def test_the_import_root_of_a_package_is_above_the_package(tmp_path):
    """The coverage-null defect. Running pytest inside the package makes the test's own
    `from package.module import ...` unresolvable, so every real package reported a NULL
    coverage reading and the branch facets came back unmeasured."""
    package = tmp_path / "pkg"
    (package / "inner").mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "inner" / "__init__.py").write_text("")
    (package / "inner" / "m.py").write_text("X = 1\n")
    assert facets.import_root(package / "inner" / "m.py") == tmp_path


def test_an_audit_whose_coverage_produced_no_data_says_so(tmp_path):
    """The branch facets are unmeasured, not clean, and the reason has to reach the reader
    rather than sitting in a null the report renders as a dash."""
    (tmp_path / "m.py").write_text("def f(n: int) -> int:\n    if n:\n        return n\n    return 0\n")
    (tmp_path / "test_m.py").write_text("def test_x():\n    assert True\n")
    result = facets.audit(tmp_path / "m.py", tmp_path / "test_m.py")
    assert result["coverage_measured"] is False
    assert "coverage" in result["unusable_reason"]


def test_the_coverage_reader_returns_no_percentage_for_a_module_the_suite_never_imports(tmp_path):
    """A module no test touches is not a module at 0%: the run produced no entry for it at
    all, and inventing a zero would put a number where there is no reading."""
    (tmp_path / "m.py").write_text("def f(n: int) -> int:\n    return n\n")
    (tmp_path / "test_m.py").write_text("def test_x():\n    assert True\n")
    _uncovered, percent, succeeded = facets._coverage(tmp_path / "m.py", (tmp_path / "test_m.py",))
    assert succeeded is True
    assert percent is None


def test_the_coverage_reader_returns_no_percentage_when_the_module_never_loads(tmp_path):
    """An import error is not zero coverage. Reporting 0% would read as a suite that ran
    and touched nothing, rather than one that never started."""
    (tmp_path / "m.py").write_text("import a_module_nobody_has\n")
    (tmp_path / "test_m.py").write_text("import m\n\n\ndef test_x():\n    assert m\n")
    _uncovered, percent, succeeded = facets._coverage(tmp_path / "m.py", (tmp_path / "test_m.py",))
    assert succeeded is False
    assert percent is None, (
        "a module that raised on import reported a coverage percentage, which is this "
        "instrument's own bug category turned on itself")


# --------------------------------------------------------------------------
# Values that arrive through a fixture or a factory
# --------------------------------------------------------------------------

def test_a_function_returning_a_literal_lends_its_region_to_its_callers():
    """`_fresh()` returning `[]` is how a test suite supplies an empty list, and the reader
    saw a call it could not read. The region was reported silent on a function every test
    in the file calls with an empty list."""
    source = ("def _fresh():\n    return []\n\n\n"
              "def test_x():\n    assert collect(_fresh()) == ['added']\n")
    assert facets.returned_regions(_tree(source)) == {"_fresh": {"empty"}}


def test_a_function_with_several_literal_returns_lends_every_region():
    source = "def make(flag):\n    if flag:\n        return []\n    return [1]\n"
    assert facets.returned_regions(_tree(source)) == {"make": {"empty", "non-empty"}}


def test_a_function_returning_something_unreadable_lends_nothing():
    source = "def make():\n    return build_it()\n"
    assert facets.returned_regions(_tree(source)) == {}


def test_a_factory_call_supplies_the_region_it_returns():
    source = ("def _fresh():\n    return []\n\n\n"
              "def test_x():\n    assert collect(_fresh()) == ['added']\n")
    assert facets.supplied_regions(_tree(source))["collect/0"] == {"empty"}


def test_a_fixture_lends_its_region_to_the_test_parameter_named_after_it():
    """pytest's own mechanism, and the commonest way a value reaches a test at all."""
    source = ("import pytest\n\n\n"
              "@pytest.fixture\ndef items():\n    return []\n\n\n"
              "def test_x(items):\n    assert collect(items) == ['added']\n")
    assert facets.supplied_regions(_tree(source))["collect/0"] == {"empty"}


def test_a_fixture_that_yields_a_literal_is_read_too():
    source = ("import pytest\n\n\n"
              "@pytest.fixture\ndef items():\n    yield []\n\n\n"
              "def test_x(items):\n    assert collect(items) == ['added']\n")
    assert facets.supplied_regions(_tree(source))["collect/0"] == {"empty"}


def test_a_plain_function_is_not_treated_as_a_fixture():
    """A helper's name colliding with a test parameter is not evidence that the helper
    produced it. Only the decorator says so."""
    source = ("def items():\n    return []\n\n\n"
              "def test_x(items):\n    assert collect(items) == ['added']\n")
    assert facets.supplied_regions(_tree(source)).get("collect/0", set()) == set()
