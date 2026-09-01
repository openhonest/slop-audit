"""What the Rust sweep reads and says, once the choosing moved out from under it.

The sweep builds coverage over a crate, finds every function with an uncovered branch, and
hands each gap to a model that writes a test for it. Every step costs a cargo build or a
paid call, so nothing had ever asked it anything: fifty-four per cent of the module was
unmeasured.

The choosing went to `budget.gaps_to_attempt`, shared with the Python sweep, and
tests/test_both_sweeps_choose_by_one_rule.py holds it. What is left here is what only this
sweep does: reading the crate's files, filtering the gaps its host cannot run, and saying
what a truncated sweep owes its reader.
"""

from l1_analyzer import coverage_prove

_UNCOVERED = ("pub fn band(n: i32) -> &'static str {\n"
              "    if n > 10 { \"high\" } else { \"low\" }\n"
              "}\n")


# --------------------------------------------------------------------------
# Reading the crate, at the edge
# --------------------------------------------------------------------------

def test_only_rust_files_are_read(tmp_path):
    """Coverage reports every file it built. Only Rust has a grammar here, and handing a
    model a file nobody parsed spends a call on a gap nobody located."""
    (tmp_path / "lib.rs").write_text(_UNCOVERED)
    (tmp_path / "README.md").write_text("# notes\n")
    read = coverage_prove._rust_sources(tmp_path, {"lib.rs": frozenset([2]),
                                                   "README.md": frozenset([1])})
    assert set(read) == {"lib.rs"}


def test_a_file_that_will_not_open_is_left_out_rather_than_given_back_empty(tmp_path):
    """An empty module has no functions and no gaps, which reads as a file with nothing to
    prove instead of a file nobody could read."""
    assert coverage_prove._rust_sources(tmp_path, {"gone.rs": frozenset([2])}) == {}


# --------------------------------------------------------------------------
# What a truncated sweep owes its reader
# --------------------------------------------------------------------------

def test_a_sweep_stopped_by_its_ceiling_names_both_numbers():
    """A result reading "attempted 5, retained 1" with no further word reads as a codebase
    with five uncovered branches, when it may have had five hundred."""
    said = coverage_prove.ceiling_detail(attempted=5, located=500, ceiling=5)
    assert "5 of 500" in said
    assert "ceiling 5" in said
    assert "not counted clean" in said


def test_a_sweep_stopped_by_the_per_module_cap_is_not_told_the_ceiling_did_it():
    """Two bounds can truncate a sweep and this named only one of them, so a reader stopped
    by the cap went and raised the wrong number."""
    said = coverage_prove.ceiling_detail(attempted=4, located=16, ceiling=100)
    assert "4 of 16" in said
    assert "ceiling 100" not in said
    assert "cap" in said


def test_a_sweep_nothing_truncated_says_nothing():
    """Saying it on every sweep would train a reader to skip the sentence on the one sweep
    where it matters."""
    assert coverage_prove.ceiling_detail(attempted=16, located=16, ceiling=100) == ""


def test_a_run_the_operator_gave_no_budget_says_nothing_here_either():
    """A ceiling of nothing is a request for a count and no spending. The sweep's own
    refusal says that; repeating it as a truncation would name a bound the operator set
    deliberately as though the run had run into it."""
    assert coverage_prove.ceiling_detail(attempted=0, located=40, ceiling=0) == ""
