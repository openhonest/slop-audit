"""The per-module Rust prover reaches its own proof loop.

`prove_coverage` called `_prove_one` with five arguments where nine are required, so the
whole path raised TypeError before it proved anything. It is the entry point behind
`--prove-coverage <module>`, and the four missing arguments are the four collaborators the
loop declares rather than defaults, for the stated reason that a default puts a real cargo
invocation one forgotten argument away from a test. Requiring them was right; this call site
was never updated to supply them.

Nothing caught it because every test of the loop passes its own collaborators, which is what
made the loop testable and what made this call site the only one nobody exercised.
"""

import inspect

from l1_analyzer import coverage_prove


def _call_arguments(caller: str) -> int:
    """How many arguments this function hands the proof loop."""
    import ast
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(getattr(coverage_prove, caller))))
    call = next(n for n in ast.walk(tree)
                if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_prove_one")
    return len(call.args) + len(call.keywords)


def test_every_caller_hands_the_loop_every_argument_it_requires():
    """Counted at the call rather than matched by name, because both callers pass
    positionally and a name search would pass on a function that merely mentions one."""
    required = [n for n, p in inspect.signature(coverage_prove._prove_one).parameters.items()
                if p.default is inspect.Parameter.empty]
    for caller in ("prove_coverage", "_prove_module"):
        assert _call_arguments(caller) == len(required), caller


def test_the_module_prover_refuses_before_it_reaches_the_loop_without_cargo(tmp_path):
    """The refusal paths run, which is what the type checker could see and a caller could
    not: every one of them returns before the broken call, so the crash needed a repository
    with cargo, a key and a real uncovered branch to show itself."""
    result = coverage_prove.prove_coverage(tmp_path, "src/m.rs", 3, 1.0, 1)
    assert result["retained"] == []
    assert result["detail"]
