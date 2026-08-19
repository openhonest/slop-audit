"""The two coverage-prove modules validate a model proposal with one function.

`_valid` was written identically in coverage_prove and python_coverage_prove: reject a
proposal with no body or a blank one, and otherwise return the body stripped beside its
explanation. That is the rule deciding whether a model's answer is usable at all, and two
copies of it is two places for one language to start accepting a proposal the other
rejects.

Everything else in the pair genuinely differs, which is why only this one moved: the
Python side passes a module path and an is_method flag the Rust side has no use for. An
AST comparison over the whole package found this as the last rule written twice.
"""

import ast
import pathlib

from l1_analyzer import coverage_prove, python_coverage_prove


def test_both_modules_ask_the_same_validator():
    assert python_coverage_prove._valid is coverage_prove._valid


def test_no_rule_in_the_package_is_written_twice():
    """The sweep that found it, kept as the guard. Compared by rule rather than by name:
    the function is renamed to a constant and its docstring dropped, so two functions with
    different names and the same body still collide."""
    bodies: dict[str, list[str]] = {}
    for path in sorted(pathlib.Path(coverage_prove.__file__).parent.glob("*.py")):
        for node in ast.parse(path.read_text()).body:
            if not isinstance(node, ast.FunctionDef):
                continue
            stripped = ast.parse(ast.unparse(node)).body[0]
            stripped.name = "f"
            if ast.get_docstring(stripped):
                stripped.body = stripped.body[1:]
            if len(stripped.body) < 2:      # one-liners are not worth chasing
                continue
            bodies.setdefault(ast.dump(stripped), []).append(f"{path.name}:{node.name}")
    twice = [v for v in bodies.values() if len({s.split(":")[0] for s in v}) > 1]
    assert not twice, f"rules written identically in more than one module: {twice}"


def test_the_validator_refuses_a_proposal_with_no_body():
    assert coverage_prove._valid(None) is None
    assert coverage_prove._valid({}) is None
    assert coverage_prove._valid({"body": "   "}) is None
    assert coverage_prove._valid({"body": 42}) is None


def test_the_validator_keeps_a_real_proposal():
    assert coverage_prove._valid({"body": "  fn t() {}  ", "explanation": "why"}) == {
        "body": "fn t() {}", "explanation": "why"}
