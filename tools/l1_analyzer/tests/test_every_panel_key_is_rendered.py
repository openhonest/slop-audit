"""Every key the panel publishes reaches the rendered card, or is excluded on purpose.

The architectural cause `slop-audit-4j2` names: two renderers existed for one panel, a
section was added to the orphaned one, and it was invisible while passing every gate. The
orphaned renderers are gone. What was missing, and is the reason the next section can go
the same way, is any test asserting that a published key appears in the output a reader
actually sees.

`interleaving_robustness` is computed in cli.py, published into the JSON panel, and
mentioned nowhere in card.py. A Rust repository with unmodeled concurrency surface shows
the finding only to a reader who parses `--format json`.

The exclusion list is the point of the design. A key that does not belong on the card
must be named here with a reason, so leaving one out is a decision somebody wrote down
rather than an omission nobody noticed.
"""

import pathlib

from l1_analyzer import card

# Keys the card deliberately does not render, each with the reason it does not.
_NOT_ON_THE_CARD = {
    "lang": "the detected language is the card's subtitle, not a finding",
    "grade": "rendered as the grade block rather than as a named key",
    "census": "feeds the grade's basis; the card prints what it concluded, not the tally",
    "state_bounds": "the L1.18b findings are rendered through their own section",
}


def _panel_keys(results: dict) -> set[str]:
    return {k for k in results if not k.startswith("_")}


def test_every_published_key_is_rendered_or_excluded_with_a_reason():
    """Built from a panel shape rather than a live run, so it costs nothing and still
    fails when a key is added to the panel and not to the card."""
    from l1_analyzer import cli

    source = pathlib.Path(cli.__file__).read_text()
    published = {line.split('results["', 1)[1].split('"]', 1)[0]
                 for line in source.splitlines() if 'results["' in line}
    rendered = pathlib.Path(card.__file__).read_text()
    missing = sorted(k for k in published
                     if k not in _NOT_ON_THE_CARD and k not in rendered)
    assert not missing, (
        "published in the panel and absent from the card: " + ", ".join(missing) +
        "\nAdd the section to card.py, or add the key to _NOT_ON_THE_CARD with its reason.")


def test_the_exclusion_list_carries_a_reason_for_every_entry():
    """An exclusion without a reason is the omission it was meant to replace."""
    assert all(reason.strip() for reason in _NOT_ON_THE_CARD.values())
