"""Two sweeps, one selection rule, because the same defect appeared in both.

The Rust sweep and the Python sweep each build coverage, find every function with an
uncovered branch, and hand gaps to a model. What they DO with a gap genuinely differs and
is deliberately not merged: the Rust side batches every proposal into one crate and compiles
once, the Python side runs each proof on its own because pytest has no equivalent. There is
a note in the source saying so, measured statement by statement.

Choosing which gaps to hand over is not that. It is one rule, it was written twice, and on
2026-08-31 the copy showed what a copy does: the per-module cap truncated before the count
of what was found, in both. A sweep with a cap of one over forty modules reported forty gaps
located and forty attempted when it had found six hundred, which is the
unmeasured-read-as-clean shape wearing a budget for a disguise. Fixing it in the Rust module
left it standing in the Python one.

The rule lives beside the allowance arithmetic now, which is the other half of the same
question, and both sweeps ask it.
"""

import ast
import inspect

import pytest
from l1_analyzer import (
    budget,
    coverage_prove,
    python_coverage_prove,
    python_facets,
    rust_facets,
)

_PY = ("def band(n):\n"
       "    if n > 10:\n"
       "        return 'high'\n"
       "    return 'low'\n")
_RS = ("pub fn band(n: i32) -> &'static str {\n"
       "    if n > 10 { \"high\" } else { \"low\" }\n"
       "}\n")


def _python_gaps(source, lines):
    return python_facets.uncovered_gaps(python_facets.module_functions(source), lines)


def _rust_gaps(source, lines):
    return rust_facets.uncovered_gaps(rust_facets.module_functions(source), lines)


def test_the_rule_counts_every_gap_before_either_bound_applies():
    """The defect, from the side that had it fixed. Every gap is located whether or not a
    bound lets the sweep try it, because the report says how many were found as well as how
    many were attempted."""
    sources = {f"m{i}.py": _PY for i in range(4)}
    measured = {name: frozenset([2, 3]) for name in sources}
    _work, located, attempted = budget.gaps_to_attempt(
        measured, sources, _python_gaps, cap_per_module=1, ceiling=100)
    assert located == 4
    assert attempted == 4


def test_the_ceiling_binds_across_the_whole_run():
    sources = {f"m{i}.py": _PY for i in range(4)}
    measured = {name: frozenset([2, 3]) for name in sources}
    work, located, attempted = budget.gaps_to_attempt(
        measured, sources, _python_gaps, cap_per_module=10, ceiling=2)
    assert located == 4
    assert attempted == 2
    assert len(work) == 2


def test_a_file_the_edge_did_not_read_is_passed_over():
    """The suffix filter and the read both happen at the edge, so a file that is not in the
    sources is one the caller decided not to hand over. Guessing at it here would put the
    language rule in the one function that must not know which language it is choosing for."""
    _work, located, _attempted = budget.gaps_to_attempt(
        {"m.py": frozenset([2, 3]), "README.md": frozenset([1])}, {"m.py": _PY},
        _python_gaps, cap_per_module=10, ceiling=100)
    assert located == 1


def test_the_same_rule_serves_the_rust_reader():
    """The point of having one. The gap reader is a parameter, so the rule never learns
    which language it is choosing for."""
    _work, located, attempted = budget.gaps_to_attempt(
        {"src/lib.rs": frozenset([2])}, {"src/lib.rs": _RS},
        _rust_gaps, cap_per_module=10, ceiling=100)
    assert located == 2
    assert attempted == 2


@pytest.mark.parametrize("module", [coverage_prove, python_coverage_prove], ids=["rust", "python"])
def test_neither_sweep_keeps_a_copy_of_the_selection(module):
    """A second copy is how the cap defect came to exist in two places at once. Both sweeps
    ask the one rule and neither has a loop of its own that counts and truncates."""
    calls = [node for node in ast.walk(ast.parse(inspect.getsource(module)))
             if isinstance(node, ast.Call)
             and ast.unparse(node.func).endswith("gaps_to_attempt")]
    assert len(calls) == 1, f"{module.__name__} asks the selection rule {len(calls)} times"
