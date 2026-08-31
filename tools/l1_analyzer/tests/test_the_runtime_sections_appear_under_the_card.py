"""Two sections come from running the code, and they only appear when something ran.

The card is a static reading. Two stages watch the code run instead: a thread checker
looking for a race, and the proof loop, which writes a test for a gap and keeps it only if
it fails against the code as written. Neither runs by default, so both are appended under
the card rather than being part of it.

Nothing could read this until 2026-08-31, because it was eleven lines of printing inside
the argument reader and asking what a confirmed race renders as meant running a whole audit
with a thread checker installed. Four of the reader's unexercised branches were these
lines. That is the reader being unreadable, not the sections being untested.

The empty case is the one that matters most. A heading over no findings reads as a checker
that ran and found nothing, which is the opposite of a checker that never ran.
"""

from l1_analyzer import cli

_RACE = {
    "tool": "tsan", "verdict": "RACE", "details": "two threads wrote `count`.",
    "findings": [{"file": "src/a.rs", "line": 12, "symbol": "bump"},
                 {"file": "src/b.rs", "line": 40, "symbol": "flush"}],
    "confirmed_surface": [{"file": "src/a.rs", "line": 12, "symbol": "bump"}],
}
_PROOFS = {
    "verdict": "DEMONSTRATED", "demonstrated": 1, "attempted": 2,
    "outcomes": [{"file": "m.py", "line": 3, "symbol": "band", "verdict": "retained",
                  "detail": "band(-1) returned 'low'"},
                 {"file": "m.py", "line": 9, "symbol": "clip", "verdict": "discarded",
                  "detail": "the written test passed"}],
}


def test_a_run_with_neither_stage_appends_nothing():
    """Both stages are opt-in and most runs skip them, so this is the ordinary case."""
    assert cli.runtime_sections({}) == ""


def test_a_race_names_the_tool_that_watched():
    """Which checker ran is part of the finding. A reader deciding whether to believe it
    needs to know whether a thread sanitiser or a stress loop said so."""
    assert "runtime/tsan" in cli.runtime_sections({"race": _RACE})


def test_every_race_it_found_is_listed_with_a_place():
    section = cli.runtime_sections({"race": _RACE})
    assert "`src/a.rs:12`" in section
    assert "`src/b.rs:40`" in section


def test_a_race_the_static_reader_also_flagged_is_marked_as_confirmed():
    """Where the two readers agree, the static one has a second witness. Where the runtime
    one found it alone, the static one has a gap, and telling them apart is the point."""
    section = cli.runtime_sections({"race": _RACE})
    bump = next(line for line in section.splitlines() if "bump" in line)
    flush = next(line for line in section.splitlines() if "flush" in line)
    assert "confirms flagged surface" in bump
    assert "confirms flagged surface" not in flush


def test_a_race_stage_that_found_nothing_still_reports_that_it_ran():
    """The whole reason this is worth printing. A checker that ran and found no race is a
    result, and it must not look the same as a checker that never ran."""
    ran = cli.runtime_sections({"race": {**_RACE, "verdict": "CLEAN", "findings": [],
                                         "details": "no race in 40 runs.", "confirmed_surface": []}})
    assert "CLEAN" in ran
    assert ran != ""


def test_the_proof_stage_gives_the_two_counts_rather_than_a_rate():
    """One in two and fifty in a hundred are not the same evidence, and a percentage hides
    which one you have."""
    assert "1/2 demonstrated" in cli.runtime_sections({"proofs": _PROOFS})


def test_a_test_that_was_kept_and_one_that_was_thrown_away_are_both_listed():
    """A proposal that passed against the code as written proved nothing and is discarded.
    Listing only the kept ones would report the hit rate as perfect."""
    section = cli.runtime_sections({"proofs": _PROOFS})
    assert "retained" in section
    assert "discarded" in section


def test_both_stages_in_one_run_print_both_sections():
    section = cli.runtime_sections({"race": _RACE, "proofs": _PROOFS})
    assert "Thread-safety race" in section
    assert "Prove (locate" in section


def test_a_proof_result_that_is_not_a_record_is_passed_over():
    """The panel carries whatever the stage returned, and a refusal is a sentence rather
    than a record. Rendering it under a heading of counts it does not have would put a
    stack trace where a report goes."""
    assert cli.runtime_sections({"proofs": "no key, so nothing ran"}) == ""


def test_what_comes_back_is_ready_to_write_without_being_checked():
    """The caller writes this verbatim. Making it check for emptiness first put a branch in
    the argument reader whose only job was to avoid a blank line, and that branch was one
    of the reader's unexercised ones."""
    assert cli.runtime_sections({}) == ""
    assert cli.runtime_sections({"race": _RACE}).endswith("\n")
