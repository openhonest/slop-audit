"""The four-column call-stack map, and the `.hd` file it renders as.

`.hd` is the Honest Framework's own plain-text architecture spec, and the grammar here is
that one rather than a private dialect: roles are function prefixes, I/O lives on the
outside in columns one and four, pure logic sits in the middle.

  boundary_in fn    inbound I/O, reads a source
  orchestrator fn   composes other functions
  fn                pure core, no side effects
  boundary_out fn   outbound I/O, writes a target

The honesty violation the map exists to show is a write sitting in the pure lane: a bare
`fn` carrying `side_effect writes`. Nothing should write in column three.

This map has one thing a reader of the source alone does not. The audit already watched the
suite run, so a function whose purity BREAKS was seen writing. The violation is
demonstrated rather than inferred, and an unwatched function is not accused at all.

A layer is not in that list. `layer foundation|data|domain|ui|tooling` is an architectural
intent, and no reading of the source decides it. The caller states it or the file says
nobody did.
"""

import ast
import textwrap

import pytest
from l1_analyzer import callmap


def _fn(source: str) -> ast.FunctionDef:
    return next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef))


def test_the_four_roles_are_named_in_column_order():
    assert callmap.ROLES == ("boundary_in", "orchestrator", "pure", "boundary_out")


# --------------------------------------------------------------------------
# Reading the effects out of a function
# --------------------------------------------------------------------------

@pytest.mark.parametrize(("body", "source"), [
    ("return open(path).read()", "file"),
    ("return path.read_text()", "filesystem"),
    ("return os.environ['HOME']", "environment"),
    ("return input()", "stdin"),
    ("return subprocess.run(['ls'])", "subprocess"),
    ("return importlib.import_module(name)", "import"),
])
def test_a_call_that_reads_a_source_names_it(body, source):
    reads, writes = callmap.effects(
        _fn(f"def f(path, name, os, subprocess, importlib):\n    {body}\n"))
    assert reads == [source], (reads, writes)
    assert writes == []


@pytest.mark.parametrize(("body", "target"), [
    ("open(path, 'w').write(x)", "file"),
    ("path.write_text(x)", "filesystem"),
    ("print(x)", "stdout"),
    ("path.mkdir()", "filesystem"),
    ("setattr(module, 'x', 1)", "namespace"),
])
def test_a_call_that_writes_a_target_names_it(body, target):
    reads, writes = callmap.effects(_fn(f"def f(path, x, module):\n    {body}\n"))
    assert writes == [target], (reads, writes)


def test_a_function_that_touches_nothing_has_no_effects():
    assert callmap.effects(_fn("def f(n: int) -> int:\n    return n * 2\n")) == ([], [])


def test_a_write_and_a_read_are_both_named():
    reads, writes = callmap.effects(_fn(
        "def f(source, target):\n    target.write_text(source.read_text())\n"))
    assert reads == ["filesystem"] and writes == ["filesystem"]


def test_the_same_source_is_named_once():
    reads, _writes = callmap.effects(_fn(
        "def f(a, b):\n    return a.read_text() + b.read_text()\n"))
    assert reads == ["filesystem"]


def test_a_global_statement_is_a_write_to_the_module():
    """`global CACHE` followed by an assignment is a write nothing in the signature
    mentions, which is the shape column four exists to make visible."""
    _reads, writes = callmap.effects(_fn("def f():\n    global CACHE\n    CACHE = 1\n"))
    assert writes == ["namespace"]


# --------------------------------------------------------------------------
# What a function calls
# --------------------------------------------------------------------------

def test_the_functions_it_calls_in_its_own_module_are_named():
    source = "def top(n):\n    return inner(helper(n))\n"
    assert callmap.invocations(_fn(source), {"inner", "helper", "other"}) == ["helper", "inner"]


def test_a_call_to_something_outside_the_module_is_not_an_invocation():
    """The map is of THIS module. A call to json.dumps is a fact about the library."""
    assert callmap.invocations(_fn("def top(n):\n    return json.dumps(n)\n"), {"top"}) == []


def test_a_function_does_not_list_itself():
    """Recursion is a fact about the function, not about what it composes."""
    assert callmap.invocations(_fn("def top(n):\n    return top(n - 1)\n"), {"top"}) == []


# --------------------------------------------------------------------------
# Which column a function belongs in
# --------------------------------------------------------------------------

@pytest.mark.parametrize(("reads", "writes", "invokes", "role"), [
    (["file"], [], [], "boundary_in"),
    ([], ["file"], [], "boundary_out"),
    ([], [], ["helper"], "orchestrator"),
    ([], [], [], "pure"),
    (["file"], ["file"], [], "boundary_out"),
    (["file"], [], ["helper"], "boundary_in"),
])
def test_a_function_lands_in_one_column(reads, writes, invokes, role):
    """A write outranks a read: the map's whole point is where the writes are, so a
    function that does both belongs in the column a reader is looking for."""
    assert callmap.role_of(reads, writes, invokes) == role


# --------------------------------------------------------------------------
# The violation the map exists to show
# --------------------------------------------------------------------------

MODULE = textwrap.dedent('''
    SEEN = []


    def double(n: int) -> int:
        return n * 2


    def remember(n: int) -> int:
        SEEN.append(n)
        return n


    def load(path) -> str:
        return path.read_text()


    def run(n: int) -> int:
        return double(n)
''').lstrip("\n")


def test_a_pure_function_observed_writing_is_marked_a_violation():
    """`remember` appends to a module global. Nothing in its signature says so, and the map
    puts the write in column three where nothing should write."""
    roles = callmap.classify(ast.parse(MODULE), {"remember": {"purity": "breaks"}})
    remember = next(r for r in roles if r["function"] == "remember")
    assert remember["role"] == "pure"
    assert remember["violation"]
    assert "observed" in remember["violation"]


def test_a_function_the_run_showed_pure_carries_no_violation():
    roles = callmap.classify(ast.parse(MODULE), {"double": {"purity": "holds"}})
    double = next(r for r in roles if r["function"] == "double")
    assert double["role"] == "pure"
    assert double["violation"] == ""


def test_a_boundary_function_that_writes_is_not_a_violation():
    """A write is only dishonest where the signature denies it. In column four it is
    declared, which is the whole point of having a column four."""
    roles = callmap.classify(
        ast.parse("def save(path, text):\n    path.write_text(text)\n"),
        {"save": {"purity": "breaks"}})
    assert roles[0]["role"] == "boundary_out"
    assert roles[0]["violation"] == ""


def test_an_unwatched_function_is_not_accused():
    """Silence about a property is not evidence of a violation. A function nobody watched
    gets no verdict rather than a clean one or a charge."""
    roles = callmap.classify(ast.parse(MODULE), {})
    assert all(r["violation"] == "" for r in roles), roles


# --------------------------------------------------------------------------
# Rendering the .hd
# --------------------------------------------------------------------------

def test_the_rendered_file_declares_the_module():
    rendered = callmap.render(callmap.classify(ast.parse(MODULE), {}), "m", layer="domain")
    assert rendered.startswith("module m\n")
    assert "  layer domain\n" in rendered


def test_a_layer_nobody_declared_is_named_as_undeclared():
    """A layer is an architectural intent and no reading of the source decides it. Emitting
    a guess would put an invented fact in a file whose whole job is to state facts."""
    rendered = callmap.render(callmap.classify(ast.parse(MODULE), {}), "m", layer="")
    assert "layer domain" not in rendered
    assert "not declared" in rendered


def test_each_role_carries_its_prefix_from_the_grammar():
    rendered = callmap.render(callmap.classify(ast.parse(MODULE), {}), "m", layer="")
    assert "boundary_in fn load :" in rendered
    assert "orchestrator fn run :" in rendered
    assert "\n  fn double :" in rendered


def test_a_boundary_names_the_source_it_reads():
    rendered = callmap.render(callmap.classify(ast.parse(MODULE), {}), "m", layer="")
    assert 'boundary_in fn load : (path) -> str side_effect reads "filesystem"' in rendered


def test_an_orchestrator_lists_what_it_invokes():
    rendered = callmap.render(callmap.classify(ast.parse(MODULE), {}), "m", layer="")
    assert "orchestrator fn run : (n: int) -> int invokes double" in rendered


def test_a_violation_keeps_the_side_effect_in_the_pure_lane_and_is_marked():
    """Emitted as a bare `fn` with the write still attached, so the map SHOWS the write
    sitting in column three rather than quietly moving it to column four."""
    rendered = callmap.render(
        callmap.classify(ast.parse(MODULE), {"remember": {"purity": "breaks"}}), "m", layer="")
    line = next(line for line in rendered.split("\n") if "remember" in line)
    assert line.strip().startswith("fn remember :")
    assert "side_effect writes" in line
    assert "VIOLATION" in line


def test_the_rendered_file_parses_back_into_the_same_roles():
    """A format nobody can read back is a report, not a spec."""
    roles = callmap.classify(ast.parse(MODULE), {"remember": {"purity": "breaks"}})
    rendered = callmap.render(roles, "m", layer="tooling")
    assert callmap.read_roles(rendered) == {r["function"]: r["role"] for r in roles}


# --------------------------------------------------------------------------
# What counts as a boundary, and what does not
# --------------------------------------------------------------------------

def test_setting_an_attribute_on_something_the_function_made_is_not_a_boundary():
    """`observe` was filed in column four for setting an attribute on the wrapper it had
    just built. Writing to an object you created is not outbound I/O, and calling it one
    puts a pure function in the boundary column where a reader looks for the real writes."""
    source = ("def observe(fn):\n"
              "    def watched():\n        return fn()\n"
              "    setattr(watched, '__wrapped__', fn)\n"
              "    return watched\n")
    _reads, writes = callmap.effects(_fn(source))
    assert writes == []


def test_setting_an_attribute_on_something_handed_in_is_a_boundary():
    """The caller's object outlives the call, so the write is visible outside it."""
    _reads, writes = callmap.effects(_fn("def stash(config):\n    setattr(config, 'x', 1)\n"))
    assert writes == ["namespace"]


def test_a_function_observed_mutating_its_argument_carries_that_write():
    """The `.hd` doc's own example: a pure-position `fn` that writes its argument is the
    crime the format was written to show. The charge rests on the watched run, so the
    argument is named from the signature and the write from the observation."""
    roles = callmap.classify(
        ast.parse("def add_item(order: dict, item: dict) -> dict:\n    return order\n"),
        {"add_item": {"mutation": "breaks"}})
    assert roles[0]["role"] == "pure"
    assert roles[0]["writes"] == ["order"]
    assert roles[0]["violation"]


def test_a_function_observed_leaving_its_argument_alone_carries_no_write():
    roles = callmap.classify(
        ast.parse("def with_item(order: dict, item: dict) -> dict:\n    return order\n"),
        {"with_item": {"mutation": "holds"}})
    assert roles[0]["writes"] == []
    assert roles[0]["violation"] == ""


def test_the_rendered_violation_names_the_argument_it_writes():
    roles = callmap.classify(
        ast.parse("def add_item(order: dict, item: dict) -> dict:\n    return order\n"),
        {"add_item": {"mutation": "breaks"}})
    rendered = callmap.render(roles, "cart", layer="domain")
    assert 'fn add_item : (order: dict, item: dict) -> dict side_effect writes "order"' in rendered
    assert "VIOLATION" in rendered
