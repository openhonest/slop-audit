""""No scanner for this language" and "the meter returned nothing" are different facts.

`thread_surface.NO_SCANNER` is the string "n/a", and `gate._verdict_of` returns "n/a" when
a panel entry carries no verdict at all. Two distinct facts arrive at the gate as one
string, and the gate prints "no scanner for this language" for both: right for the first,
a guess for the second.

Found on 2026-08-17 while making `_UNMEASURED_THREAD_SURFACE` read by subscript. The
`.get` default it used to carry, "the meter returned no verdict", was UNREACHABLE
precisely because of this collision, so the dead default was hiding the collision rather
than handling it.

A gate that tells an adopter their language has no scanner, when what happened is that
the meter returned nothing, sends them to look for a scanner that exists.
"""


from l1_analyzer import gate, thread_surface


def test_the_two_facts_do_not_share_a_string():
    assert gate.ABSENT_VERDICT != thread_surface.NO_SCANNER, \
        "an absent verdict and a missing scanner are still one string"


def test_an_entry_with_no_verdict_reads_as_absent_not_as_no_scanner():
    assert gate._verdict_of({"value": 1, "band": "Healthy"}) == gate.ABSENT_VERDICT
    assert gate._verdict_of("not a dict at all") == gate.ABSENT_VERDICT


def test_a_scanner_less_language_still_reads_as_no_scanner():
    """The other side. A real NO_SCANNER verdict must keep its own sentence."""
    assert gate._verdict_of({"verdict": thread_surface.NO_SCANNER}) == thread_surface.NO_SCANNER


def test_both_facts_have_their_own_sentence_in_the_table():
    table = gate._UNMEASURED_THREAD_SURFACE
    assert thread_surface.NO_SCANNER in table
    assert gate.ABSENT_VERDICT in table
    assert table[gate.ABSENT_VERDICT] != table[thread_surface.NO_SCANNER], \
        "two facts, one sentence, which is the collision this file is about"
