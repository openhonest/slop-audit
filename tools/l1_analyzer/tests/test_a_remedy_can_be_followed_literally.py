"""Every remedy line is one imperative sentence, and people follow it exactly.

That is the point of writing it, and it is why a wrong one is worse than none. A peer
measuring adoption reported that clause 4's line, `take the data as a parameter and let the
caller at the edge do the I/O`, was followed verbatim and worked. It says what to do and
where the work goes.

Three did not meet that bar and were rewritten on 2026-08-23.

CLAUSE 5 OFFERED AN API THAT DOES NOT EXIST. It read `compose the steps at the point of
assembly: pipe(validate, authenticate, create)`. There is no `pipe` in this package, in the
Honest Framework's Python implementation, or in the standard library. A reader following it
exactly gets a NameError, which is worse than being told nothing.

CLAUSE 3 OFFERED A SHAPE RATHER THAN AN INSTRUCTION. `a free function: save_store(data)`
names a call and leaves the reader to work out what `data` is, whether the method's class
survives, and what happens to the call sites.

CLAUSE 16 SAID `call it where it happens`, which is four words that assume the reader
already knows what to do.
"""

import ast
import pathlib

import pytest
from l1_analyzer.honest_code import CLAUSES


def _remedies() -> list[tuple[str, str]]:
    """Every remedy line in the two rule modules, with the clause it belongs to."""
    # Every module in the package, not two named by hand. It listed two and the edge
    # clauses moved to a third, so a clause carrying no remedy at all would have passed. A
    # check narrower than its subject reports on what nobody changed, which is the third
    # time that shape has cost something here.
    out: list[tuple[str, str]] = []
    for path in sorted((pathlib.Path(__file__).parent.parent / "l1_analyzer").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_finding"
                    and len(node.args) >= 5):
                continue
            code = ast.unparse(node.args[0]).strip("'\"")
            # L1.21 only. Widening the scan to the package picked up a `_finding` of the
            # same name in the state reader, whose arguments mean something else entirely,
            # and the test then judged its wording against a rule it is not under.
            if not code.startswith("L1.21."):
                continue
            out.append((code, ast.unparse(node.args[4])))
    return out


def test_every_clause_carries_a_remedy():
    codes = {code for code, _ in _remedies()}
    assert codes >= {c["code"] for c in CLAUSES if c["code"] != "L1.21.17"}


@pytest.mark.parametrize("banned", ["pipe(", "pipe (", "compose(", "flow("])
def test_no_remedy_names_a_function_this_ecosystem_does_not_have(banned):
    """The failure that prompted this file. A remedy that names an API nobody ships sends a
    reader to write a call that raises."""
    for code, remedy in _remedies():
        assert banned not in remedy, (code, remedy)


# The words that tell a reader what to DO. A remedy naming only what to end up with leaves
# them to work out the move, and `a free function: save_store(data)` left three things
# unsaid: what `data` holds, whether the class survives, and what happens at the call sites.
_INSTRUCTIONS = ("take", "make", "let", "read", "call", "move", "profile", "extract",
                 "scope", "declare", "trust", "put", "return", "use", "replace", "map",
                 "assert", "add", "fix", "give", "hand", "keep", "raise", "render", "send")


def test_every_remedy_contains_something_the_reader_does():
    """A shape is not an instruction. The first draft of this test allowed a line to begin
    with "a", which let `a free function: save_store(data)` pass and measured nothing."""
    for code, remedy in _remedies():
        words = set(remedy.strip("f'\"").lower().replace("`", " ").split())
        assert words & set(_INSTRUCTIONS), (code, remedy)


def test_the_shortest_remedy_is_long_enough_to_act_on():
    """`call it where it happens` was four words and assumed the reader already knew."""
    for code, remedy in _remedies():
        assert len(remedy.strip("f'\"").split()) >= 8, (code, remedy)
