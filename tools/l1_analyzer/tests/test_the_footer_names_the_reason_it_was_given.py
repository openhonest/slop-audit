"""We told a Python repository that our harness is Python-only.

Reported by a peer on 2026-08-28. When the CLI runs a suite and gets no coverage number, the
footer said one thing: the runtime harness is Python-only so far, so it did not run this
repo's suite. That is true for Rust and Go. It was false for the repository that reported it,
which is Python, and where the real cause was our own coverage session colliding with theirs.

One sentence asserting one cause for every failure. A reader could not tell a language we
cannot run from a bug in how we ran theirs, and the sentence they were shown blamed them.

The harness already says why it declined, in the row itself. The footer carries that reason
now instead of inventing one.
"""

from l1_analyzer import card


def _card(reason: str, lang: str = "python") -> dict:
    return {"ran_tests": True, "tests_measured": False, "lang": lang,
            "coverage_na_reason": reason}


def test_the_footer_carries_the_reason_the_harness_gave():
    reason = "the repository starts its own coverage session and it collided with ours"
    assert reason in card.footer_for(_card(reason))


def test_it_does_not_claim_a_python_only_harness_on_a_python_repository():
    """The sentence the peer was shown. It named a limit that was not the one they hit."""
    footer = card.footer_for(_card("something else entirely"))
    assert "Python-only" not in footer


def test_a_language_we_cannot_run_still_says_so():
    """The direction that must not move. That reason is real, and it is the harness's to
    give, so it arrives the same way every other reason does."""
    reason = "the runtime harness does not run a rust suite yet"
    assert reason in card.footer_for(_card(reason, lang="rust"))


def test_a_measured_run_says_the_suite_ran():
    footer = card.footer_for({"ran_tests": True, "tests_measured": True, "lang": "python",
                              "coverage_na_reason": ""})
    assert "measured, not estimated" in footer


def test_a_run_that_executed_nothing_says_that_instead():
    """The website. It never runs anyone's code, which is a third case and not a failure."""
    footer = card.footer_for({"ran_tests": False, "tests_measured": False, "lang": "python",
                              "coverage_na_reason": ""})
    assert "never executes" in footer


def test_a_missing_reason_does_not_become_a_confident_one():
    """If the harness said nothing, we say we do not know, rather than picking a cause."""
    footer = card.footer_for(_card(""))
    assert "did not say" in footer or "no reason" in footer
    assert "Python-only" not in footer
