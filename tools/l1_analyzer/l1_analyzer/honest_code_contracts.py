"""Three clauses about what a signature promises and what a caller may assume.

A mock stands in for a dependency the signature does not name. A runtime type test distrusts
a type the signature already fixed. A resource on instance state hides a lifetime the
signature never states. All three are read at the contract rather than at the boundary or
inside the control flow, which is what separates them from the clauses in
`honest_code_edges` and `honest_code_rules`.

Split out of `honest_code_rules` when that file crossed a thousand lines and this tool's own
god-file rule said so on the commit that pushed it over.

Every checker is a pure function of a source and returns the sites it found. `None` is the
third answer: the clause was not decided for this file, which is different from an empty
list meaning the clause ran and found nothing.
"""

from pathlib import Path

from l1_analyzer.honest_code_read import (
    Finding,
    _finding,
    class_nodes,
    first_name,
    function_nodes,
    method_nodes,
    node_text,
    walk,
)
from l1_analyzer.honest_code_rules import RESOURCE_CALLS


def _declared_type_of(parameter, spec: dict, raw: bytes) -> str:
    """The type a parameter declares, stripped of the punctuation a grammar hangs on it.

    TypeScript's annotation node carries the colon (`: number`), Python's does not. Reading
    the text as it comes would compare `: number` against `number` and never match."""
    declared = parameter.child_by_field_name(spec["typed_param_type"])
    return (node_text(declared, raw) or "").lstrip(":").strip()


def _parameter_name(parameter, spec: dict, raw: bytes) -> str:
    """The name a typed parameter binds. Named by a field in most grammars; Python's
    typed_parameter hangs it as the first child with no field at all."""
    field = spec["typed_param_name"]
    named = parameter.child_by_field_name(field) if field else parameter.child(0)
    return node_text(named, raw) or ""


def _type_tests_in(fn, spec: dict, raw: bytes) -> list[tuple[str, str, int]]:
    """Every runtime type test inside `fn`, as (value tested, type tested for, line).

    Two shapes, because languages spell it two ways. An operator form is a node with the
    value in one field and the type in another: Java's `instanceof_expression`, C#'s
    `is_expression`, Go's `type_assertion_expression`, and TypeScript's binary expression
    where the operator happens to be `instanceof`. A call form names the value in its first
    argument and the type in its second, which is Python's `isinstance`."""
    tests: list[tuple[str, str, int]] = []
    for node in walk(fn):
        if node.type in spec["type_test_types"]:
            wanted = spec["type_test_operators"]
            if wanted:
                operator = node.child_by_field_name("operator")
                if node_text(operator, raw) not in wanted:
                    continue
            subject = node.child_by_field_name(spec["type_test_subject"])
            tested = node.child_by_field_name(spec["type_test_type"])
            if subject is not None and tested is not None:
                tests.append((node_text(subject, raw) or "", node_text(tested, raw) or "",
                              node.start_point[0] + 1))
        if node.type in spec["call_types"] and spec["type_test_calls"]:
            if first_name(node, raw) not in spec["type_test_calls"]:
                continue
            arguments = [a for a in _call_arguments(node) if a.is_named]
            if len(arguments) >= 2:
                tests.append((node_text(arguments[0], raw) or "",
                              node_text(arguments[1], raw) or "", node.start_point[0] + 1))
    return tests


def _call_arguments(call) -> list:
    """The argument nodes of a call, whatever the grammar calls the list holding them."""
    holder = call.child_by_field_name("arguments")
    return list(holder.children) if holder is not None else []


def imperative_validation(source: dict) -> list[Finding] | None:
    """A runtime type test on a parameter whose declaration already fixes the type.

    Re-checking a value the signature promised is distrust of your own contract. In a correct
    program the caller has already been excluded by the declaration; in an incorrect one the
    branch fires where the type checker should have. A check on a value that arrived untyped
    from outside is where validation belongs, so only the declared ones are counted.

    The declaration fixes the type in two cases this reader can tell apart from a guess: the
    test asks for exactly the type the parameter declares, or the parameter declares one of
    the language's own scalars. `Object`, `any` and `interface{}` promise nothing, so a test
    against one of those is the check the declaration deliberately left to run.

    This measures Trust the Contract in the Interior, not Type Declarations Over Imperative
    Validation, and it was named after the second until the two were separated upstream. The
    other is a hand-written check copying a constraint declared elsewhere, a schema column or
    a form field, and drifting from it. Nothing here measures that one.

    Not decided: whether the function is a boundary receiving external input, where a typed
    parameter may still deserve a runtime check. Nor a test for a type the parameter cannot
    hold, such as asking `isinstance(x, str)` of an `x: int`. That branch is unreachable
    rather than redundant, which is a different defect, and this reader does not count it.

    Not decided for a language with no parameter type or no runtime type test: JavaScript and
    Ruby declare no parameter types, C and Rust have no runtime downcast in this vocabulary.
    That is a fact about the language, not a gap here, and an empty list would instead claim
    the file was read and found clean."""
    spec, raw = source["spec"], source["raw"]
    if not spec["typed_param_types"]:
        return None
    if not (spec["type_test_types"] or spec["type_test_calls"]):
        return None
    found: list[Finding] = []
    for fn in function_nodes(source["root"], spec):
        declared: dict[str, str] = {}
        for parameter in walk(fn):
            if parameter.type in spec["typed_param_types"]:
                declared[_parameter_name(parameter, spec, raw)] = _declared_type_of(
                    parameter, spec, raw)
        for value, tested, line in _type_tests_in(fn, spec, raw):
            promised = declared.get(value)
            if promised is None:
                continue
            if tested != promised and promised not in spec["scalar_types"]:
                continue
            owner = node_text(fn.child_by_field_name("name"), raw) or first_name(fn, raw)
            found.append(_finding(
                "L1.21.11", f"{owner}({value})", line,
                f"re-checks `{value}`, which the signature already types as `{promised}`",
                "trust the contract in the interior and tighten the boundary or the "
                "type instead", ""))
    return found


def _resource_calls(spec: dict) -> frozenset[str]:
    """Every name that counts as acquiring a resource in this language.

    The shared list joined to the language's own spellings. C# names the same operation
    `Connect` where the shared list says `connect`, and Java says `getConnection`, so a
    single lowercase list spelled every language's convention in Python's."""
    return RESOURCE_CALLS | spec["resource_calls"]


def _instance_member_written(assignment, spec: dict, raw: bytes) -> str:
    """The name of the instance state this assignment writes, or the empty string.

    Two shapes. Most languages write a member on a receiver, `self.conn` or `this.conn`, so
    the target is a member access whose object is one of the language's receiver words. Ruby
    writes `@conn`, which is instance state on its own and reaches for no receiver at all, so
    a reader looking only for the first shape finds nothing in idiomatic Ruby."""
    left = assignment.child_by_field_name(spec["assign_left"])
    if left is None:
        return ""
    if left.type in spec["instance_state_types"]:
        return node_text(left, raw) or ""
    if left.type not in spec["member_types"]:
        return ""
    obj = left.child_by_field_name(spec["mem_object"]) or left.child(0)
    if obj is None or node_text(obj, raw) not in spec["this_idents"]:
        return ""
    member = left.child_by_field_name(spec["mem_attr"])
    return node_text(member, raw) if member is not None else ""


def _scopes_its_own_resource(class_node, spec: dict, raw: bytes) -> bool:
    """Whether the class declares the language's own release hook.

    Python declares `__enter__`, Java implements `close`, C# implements `Dispose`, Ruby
    offers a `close` for the block form to call. Declaring one is doing what the rule asks,
    so reporting such a class would punish the remedy."""
    for method in method_nodes(class_node, spec):
        named = method.child_by_field_name("name")
        if node_text(named, raw) in spec["release_methods"]:
            return True
    return False


def unscoped_resources(source: dict) -> list[Finding] | None:
    """A resource held on instance state by a class that never releases it.

    A connection with a manual lifecycle is a leak waiting for an exception: the path that
    returns closes it and the path that raises does not. A class declaring the language's own
    release hook has scoped it, which is the whole point of the rule.

    Read through the language's own node vocabulary, so the rule means the same thing in
    every language the spec covers rather than being reimplemented per language.

    Not decided: a language with no class to hold the resource. C has none and Go's struct
    has no release hook in this vocabulary, since `defer` scopes at the call site rather than
    in the type. That is a fact about the language, and an empty list would instead claim the
    file was read against this clause and found clean.

    Not decided either: whether a receiver named something other than the language's own word
    for it is a receiver. Python allows any name for the first parameter, and this reader
    believes only `self`."""
    spec, raw = source["spec"], source["raw"]
    if not spec["class_types"] or not spec["release_methods"]:
        return None
    wanted = _resource_calls(spec)
    found: list[Finding] = []
    seen: set[tuple[str, int]] = set()
    for class_node in class_nodes(source["root"], spec):
        if _scopes_its_own_resource(class_node, spec, raw):
            continue
        owner = node_text(class_node.child_by_field_name("name"), raw) or first_name(class_node, raw)
        for node in walk(class_node):
            if node.type not in spec["assign_types"]:
                continue
            member = _instance_member_written(node, spec, raw)
            if not member:
                continue
            value = node.child_by_field_name("right")
            if value is None or value.type not in spec["call_types"]:
                continue
            if (node_text(value, raw) or "").split("(")[0].split(".")[-1] not in wanted:
                continue
            line = node.start_point[0] + 1
            # A grammar that nests one class node inside another, as Ruby's does, walks the
            # same assignment twice. The site is the finding, so it is reported once.
            if (member, line) in seen:
                continue
            seen.add((member, line))
            found.append(_finding(
                "L1.21.12", f"{owner}.{member}", line,
                "a resource with a manual lifecycle, waiting for an exception",
                "give the class the language's own release hook and take it in a scoped "
                "block, so it is released on the path that raises as well as the one that "
                "returns", ""))
    return found


# Three mocks in one test. One or two is ordinary isolation, and the third is where the
# count stops being about the test and starts being about the code under it.
_MOCK_LIMIT = 3


def called_spelling(call, spec: dict, raw: bytes) -> str:
    """What a call is called, reduced to the one word a vocabulary can hold.

    Four grammars spell the same idea four ways: Python writes `Mock()`, JavaScript
    `jest.fn()`, Java `Mockito.mock()` and C# `Substitute.For<IStore>()`. Taking the tail
    after the last dot and dropping any type arguments leaves `Mock`, `fn`, `mock` and
    `For`, so one list per language can name them without a branch per grammar."""
    named = call.child_by_field_name(spec["call_fn"])
    text = node_text(named, raw) if named is not None else (node_text(call, raw) or "")
    return text.split("(")[0].split("<")[0].split("::")[-1].split(".")[-1].strip()


def _test_bodies(source: dict) -> list[tuple[str, object, int]]:
    """Every test in this file, as (what to call it, the node holding its body, its line).

    Two shapes, because a test is not the same kind of thing everywhere. Python, Java and C#
    name a function whose name says it is a test. JavaScript and Ruby pass the body to `it`,
    so the test has no name of its own and a reader looking for named functions finds none.

    The block form yields the CALL, not the anonymous function inside it, so the mocks in the
    body are reached without the same body being counted twice under two names."""
    spec, raw = source["spec"], source["raw"]
    bodies: list[tuple[str, object, int]] = []
    for fn in function_nodes(source["root"], spec):
        name = node_text(fn.child_by_field_name("name"), raw) or ""
        if spec["test_name_prefixes"] and name.startswith(spec["test_name_prefixes"]):
            bodies.append((name, fn, fn.start_point[0] + 1))
    if spec["test_block_calls"]:
        for node in walk(source["root"]):
            if node.type not in spec["call_types"]:
                continue
            spelling = called_spelling(node, spec, raw)
            if spelling in spec["test_block_calls"]:
                bodies.append((spelling, node, node.start_point[0] + 1))
    return bodies


def mock_heavy_tests(source: dict) -> list[Finding] | None:
    """Three or more mocks in one test.

    The count is a readout on the CODE, not on the test: three mocks means the function under
    test has three hidden dependencies. One or two is ordinary isolation, and a rule firing
    there would report the practice it is asking for.

    Read through the language's own node vocabulary, so the rule means the same thing in
    every language the spec covers rather than being reimplemented per language.

    Not decided for a file that is not a test, where the count means nothing, and the answer
    is that nobody asked rather than that the file is clean. The file-name question is put to
    the scope module, which is the one place in this package that decides what a test file is
    called; a second copy here would be free to drift from it.

    Not decided for a language this table gives no mock vocabulary. Go, Rust and C are the
    three, and an empty list would instead claim the file was read and found clean.

    Not decided: a test named by an annotation rather than by a prefix. Java's @Test and C#'s
    [Fact] sit on functions with any name at all, and this reader believes the prefix."""
    from l1_analyzer.scope import _test_file_by_name

    spec, raw = source["spec"], source["raw"]
    if not spec["mock_calls"]:
        return None
    if not _test_file_by_name(Path(source["path"])):
        return None
    found: list[Finding] = []
    for name, body, line in _test_bodies(source):
        mocks = [n for n in walk(body) if n.type in spec["call_types"]
                 and called_spelling(n, spec, raw) in spec["mock_calls"]]
        if len(mocks) >= _MOCK_LIMIT:
            found.append(_finding(
                "L1.21.10", name, line,
                f"{len(mocks)} mocks, so the function under test has {len(mocks)} hidden "
                "dependencies",
                "extract the pure logic and assert f(input) == expected on it directly", ""))
    return found
