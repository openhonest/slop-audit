"""What these functions declare is what they hand over and what they are handed.

A bulk rename on 2026-08-17 put the name of a model's answer on a proof summary, a sweep and
a gap, because it matched a spelling rather than a meaning. `Sweep` was written that day and
its docstring says so. Two sites were missed and nothing could see it: `prove_coverage` said
it returned a model's answer while returning a sweep, and `missing_by_file` said it received
one function's coverage gap while receiving the whole run's coverage report.

Neither is a runtime failure. Both are a reader being told the wrong thing by the line
written to tell them, which is the defect this instrument reports in other people's code.
"""

import typing

from l1_analyzer import coverage_prove, python_coverage_prove


def test_proving_one_rust_module_hands_back_a_sweep():
    hints = typing.get_type_hints(coverage_prove.prove_coverage)
    assert hints["return"] is coverage_prove.Sweep


def test_proving_a_python_package_hands_back_a_sweep():
    """It was declared as a mapping of anything to anything, so no reader could be told the
    field they asked for is not one the sweep carries."""
    hints = typing.get_type_hints(python_coverage_prove.prove_coverage_repo)
    assert hints["return"] is python_coverage_prove.Sweep


def test_the_sweep_carries_every_field_the_rust_prover_writes():
    """The two provers write the same shape and only one declared it. `repair_rounds` was
    written by the module prover and missing from the declaration."""
    fields = set(typing.get_type_hints(coverage_prove.Sweep))
    assert {"retained", "attempted", "outcomes", "detail", "repair_rounds"} <= fields


def test_reading_a_coverage_report_says_it_receives_a_coverage_report():
    """A report covers the whole run and a gap covers one branch of one function. The
    parameter said gap, the body read `report["files"]`, and a gap has no files."""
    hints = typing.get_type_hints(python_coverage_prove.missing_by_file)
    assert hints["report"] is not python_coverage_prove.CoverageGap
    assert "files" in typing.get_type_hints(hints["report"])
