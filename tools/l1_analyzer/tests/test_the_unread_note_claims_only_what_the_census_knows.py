"""The note about places the reader never reached says the count, not the reason.

It said: "Our tool has not learned to read those, so it never looked at them... Closing that
gap is our job rather than yours: send us the repository and we will teach the tool to read
them." That is three claims, and the census supports one of them.

Measured on crates/buzz-acp in the public github.com/block/buzz on 2026-08-31. The note
reported 347 places unread. Of those, 204 are fields on a record that no code in the crate
attaches behaviour to, and whose names are never used through a receiver anywhere. The
reader did read those files. It found no state held through a receiver, which is what it
looks for, so it recorded none. That is a scoping decision working, not a form nobody
taught it.

For those 204 the note was wrong three times over. They are not a form the tool cannot
read. It did look. And nobody would teach it to "read" them, because they are not what this
measure is about, so the promise is one we would not keep.

The count is what the census holds and the count is what the note now gives. A reader is
still told the number, still told the grade does not cover it, and no longer told a story
about why that the measurement cannot support.

The direction matters. Overstating our own ignorance is the safer way to be wrong, and it
is still being wrong, and a promise nobody will keep costs more than a number.
"""

from l1_analyzer import card

_FORBIDDEN = ("has not learned", "we will teach", "never looked")


def test_the_note_states_the_count():
    note = card._census_note({"declared": 470, "visited": 123, "by_kind": {"field_declaration": 469},
                              "files": 16, "admitted": 163, "judged": 122, "unread_kinds": [],
                              "visited_fraction": 0.262, "judged_fraction": 0.992})
    assert "347" in note and "470" in note


def test_the_note_still_says_the_grade_does_not_cover_them():
    note = card._census_note({"declared": 470, "visited": 123, "by_kind": {"field_declaration": 469},
                              "files": 16, "admitted": 163, "judged": 122, "unread_kinds": [],
                              "visited_fraction": 0.262, "judged_fraction": 0.992})
    assert "grade" in note.lower()


def test_the_note_claims_no_cause_the_census_cannot_know():
    note = card._census_note({"declared": 470, "visited": 123, "by_kind": {"field_declaration": 469},
                              "files": 16, "admitted": 163, "judged": 122, "unread_kinds": [],
                              "visited_fraction": 0.262, "judged_fraction": 0.992})
    said = [phrase for phrase in _FORBIDDEN if phrase in note.lower()]
    assert said == [], said


def test_the_note_promises_nothing_it_would_not_do():
    note = card._census_note({"declared": 470, "visited": 123, "by_kind": {"field_declaration": 469},
                              "files": 16, "admitted": 163, "judged": 122, "unread_kinds": [],
                              "visited_fraction": 0.262, "judged_fraction": 0.992})
    assert "send us the repository" not in note.lower()


def test_a_repository_the_reader_read_whole_gets_no_note():
    assert card._census_note({"declared": 12, "visited": 12, "by_kind": {}, "files": 1,
                              "admitted": 12, "judged": 12, "unread_kinds": [],
                              "visited_fraction": 1.0, "judged_fraction": 1.0}) == ""
