"""What the whole-crate sweep decides before it spends anything, asked without spending.

The sweep builds coverage over a Rust crate, finds every function with an uncovered branch,
and hands each gap to a model that writes a test for it. Every one of those steps costs a
cargo build or a paid call, so nothing had ever asked the sweep what it picks: fifty-four
per cent of the module was unmeasured and the whole selection loop was inside that.

The choosing is not the spending, and it is the half that would be wrong quietly. Three
things it decides:

A gap is located whether or not the run has budget left to try it, because the report says
how many were found as well as how many were attempted. Truncating before counting would
hide the size of what was skipped, and a sweep that reports three of three attempted looks
complete when it found forty.

Two bounds, not one. The per-module cap stops a single large module consuming the run; the
run ceiling is what the operator authorised. Five per module across forty modules is two
hundred calls, and only the ceiling stops that.

A module with nothing left to try is not a module the sweep visited. Counting it would
report work on a file the sweep walked past.
"""


from l1_analyzer import coverage_prove

_UNCOVERED = ("pub fn band(n: i32) -> &'static str {\n"
              "    if n > 10 { \"high\" } else { \"low\" }\n"
              "}\n"
              "\n"
              "pub fn clip(n: i32) -> i32 {\n"
              "    if n < 0 { 0 } else { n }\n"
              "}\n")


def _sources(**files):
    """The text the edge already read. This was a reader the chooser called, and the clause
    check refused it on the commit that introduced it: I/O inside the function that decides
    is the shape this whole package is built to keep out."""
    return files


def _cov(**files):
    return {"measured": True, "reason": "", "files": {k: frozenset(v) for k, v in files.items()}}


def test_a_file_that_is_not_rust_is_passed_over():
    """Coverage reports every file it built. Only Rust has a grammar here, and handing a
    model a file nobody parsed spends a call on a gap nobody located."""
    work, located, _attempted = coverage_prove.gaps_to_attempt(
        _cov(**{"src/lib.rs": [2, 6], "README.md": [1]}),
        _sources(**{"src/lib.rs": _UNCOVERED}), frozenset(), cap_per_module=10, ceiling=100)
    assert [relpath for relpath, _gaps in work] == ["src/lib.rs"]
    assert located == 4, "two functions, each with an if, is four branches"


def test_a_file_the_edge_could_not_read_is_passed_over_rather_than_guessed_at():
    work, located, _attempted = coverage_prove.gaps_to_attempt(
        _cov(**{"src/gone.rs": [2]}), _sources(), frozenset(), cap_per_module=10, ceiling=100)
    assert work == []
    assert located == 0


def test_every_gap_is_counted_as_located_even_when_the_ceiling_stops_it():
    """The report says how many were found as well as how many were tried. A sweep that
    counted only what it attempted would report one of one and look complete."""
    work, located, attempted = coverage_prove.gaps_to_attempt(
        _cov(**{"src/lib.rs": [2, 6]}), _sources(**{"src/lib.rs": _UNCOVERED}),
        frozenset(), cap_per_module=10, ceiling=1)
    assert located == 4
    assert attempted == 1
    assert len(work[0][1]) == 1


def test_the_per_module_cap_and_the_run_ceiling_are_two_different_bounds():
    """Five per module over forty modules is two hundred calls, and only the ceiling stops
    that. A single bound cannot say both things."""
    files = {f"src/m{i}.rs": _UNCOVERED for i in range(4)}
    _work, located, attempted = coverage_prove.gaps_to_attempt(
        _cov(**{name: [2, 6] for name in files}), _sources(**files),
        frozenset(), cap_per_module=1, ceiling=100)
    assert located == 16, "every branch is found, whichever bound stops the sweep trying it"
    assert attempted == 4, "the cap allows one from each of the four"

    _work, located, attempted = coverage_prove.gaps_to_attempt(
        _cov(**{name: [2, 6] for name in files}), _sources(**files),
        frozenset(), cap_per_module=10, ceiling=3)
    assert located == 16, "four modules of four branches, all of them found"
    assert attempted == 3, "the ceiling allows three across the whole run"


def test_a_module_the_ceiling_left_nothing_for_is_not_reported_as_visited():
    """Counting it would report work on a file the sweep walked past."""
    files = {"src/a.rs": _UNCOVERED, "src/b.rs": _UNCOVERED}
    work, _located, _attempted = coverage_prove.gaps_to_attempt(
        _cov(**{name: [2, 6] for name in files}), _sources(**files),
        frozenset(), cap_per_module=10, ceiling=2)
    assert [relpath for relpath, _gaps in work] == ["src/a.rs"]


def test_a_ceiling_of_nothing_locates_the_gaps_and_attempts_none():
    """The operator asked for a count and no spending, which is a real request and not the
    same as finding nothing."""
    work, located, attempted = coverage_prove.gaps_to_attempt(
        _cov(**{"src/lib.rs": [2, 6]}), _sources(**{"src/lib.rs": _UNCOVERED}),
        frozenset(), cap_per_module=10, ceiling=0)
    assert located == 4
    assert attempted == 0
    assert work == []


def test_the_modules_come_back_in_a_settled_order():
    """Two runs over one crate must hand the same gaps to the model in the same order, or a
    ceiling that stops halfway stops somewhere different each time and the report cannot be
    compared against the run before it."""
    files = {f"src/{name}.rs": _UNCOVERED for name in ("zeta", "alpha", "mid")}
    args = (_cov(**{name: [2, 6] for name in files}), _sources(**files), frozenset())
    first, _l, _a = coverage_prove.gaps_to_attempt(*args, cap_per_module=10, ceiling=100)
    assert [relpath for relpath, _gaps in first] == sorted(files)


# --------------------------------------------------------------------------
# What the sweep found, against what it tried (slop-audit, 2026-08-31)
# --------------------------------------------------------------------------

def test_the_count_of_what_was_found_is_not_shortened_by_the_cap():
    """A sweep reporting four found and four tried reads as a crate with four uncovered
    branches, when the cap of one per module means it found sixteen and looked at four.

    That is the unmeasured-read-as-clean shape wearing a budget for a disguise, which is the
    exact thing `ceiling_detail` was written to refuse one level up. The cap truncated
    before the count, so the number that message needs was already wrong when it got it."""
    files = {f"src/m{i}.rs": _UNCOVERED for i in range(4)}
    _work, located, attempted = coverage_prove.gaps_to_attempt(
        _cov(**{name: [2, 6] for name in files}), _sources(**files),
        frozenset(), cap_per_module=1, ceiling=100)
    assert located == 16
    assert attempted == 4


def test_a_sweep_the_cap_truncated_says_so_and_names_the_cap():
    """Two bounds truncate and the sentence named only one of them. A reader told the
    ceiling stopped a run that the cap stopped goes and raises the wrong number."""
    said = coverage_prove.ceiling_detail(attempted=4, located=16, ceiling=100)
    assert "4 of 16" in said
    assert "not counted clean" in said


def test_a_sweep_nothing_truncated_says_nothing():
    """Saying it on every sweep would train a reader to skip the sentence on the one sweep
    where it matters."""
    assert coverage_prove.ceiling_detail(attempted=16, located=16, ceiling=100) == ""
