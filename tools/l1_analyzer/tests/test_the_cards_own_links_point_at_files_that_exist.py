"""The card's "How each number is measured" button was a 404 for anyone who clicked it.

The link read `blob/main/03-layer1-indicators.md`. That file lives under `spec/`, so GitHub
answered 404. The card invites a reader to go and check the measurement, and the one link that
takes them there was broken.

Nothing checked it, which is why it survived. The template is rendered by two things, this
engine and the public site, and neither resolves its own links. So this test reads every link
in the template that points into this repository and asserts the file is there. It does not
reach the network: a test that needs GitHub to answer fails when the network is down and tells
you nothing about the link.

A link to somewhere else is skipped and counted, and the count is asserted, so a new outbound
link cannot quietly arrive unexamined.
"""

from __future__ import annotations

import re
from pathlib import Path

from l1_analyzer.boundary import boundary

# The repository this card belongs to. A link to any other GitHub repository is somebody
# else's file and this test cannot say whether it exists.
_OWN_REPO = "https://github.com/openhonest/slop-audit/blob/main/"

_HREF = re.compile(r'href="([^"]*)"')

# Links that deliberately leave this repository. Counted rather than ignored, so adding one
# fails this test until somebody writes it down here.
_EXPECTED_OUTBOUND = 1


@boundary
def card_links() -> list[str]:
    """Every href written in the card templates, in the order the files are read."""
    templates = Path(__file__).resolve().parent.parent / "l1_analyzer" / "card_templates"
    return [href
            for path in sorted(templates.glob("*.html"))
            for href in _HREF.findall(path.read_text())]


@boundary
def repo_root() -> Path:
    """The checkout this test is running inside."""
    return Path(__file__).resolve().parent.parent.parent.parent


def test_every_link_into_this_repository_names_a_file_that_is_there():
    root = repo_root()
    missing = [href[len(_OWN_REPO):]
               for href in card_links()
               if href.startswith(_OWN_REPO)
               and not (root / href[len(_OWN_REPO):]).exists()]
    assert not missing, f"the card links to files this repository does not have: {missing}"


def test_the_card_links_into_this_repository_at_all():
    """A template with no inbound links would pass the test above by having nothing to check,
    which is the empty denominator this instrument exists to name."""
    inbound = [href for href in card_links() if href.startswith(_OWN_REPO)]
    assert inbound, "the card no longer points a reader at how the numbers are measured"


def test_a_link_that_leaves_this_repository_is_counted_rather_than_ignored():
    outbound = [href for href in card_links()
                if href.startswith("http") and not href.startswith(_OWN_REPO)]
    assert len(outbound) == _EXPECTED_OUTBOUND, (
        f"the card's outbound links changed: {outbound}. Nothing here can check where they "
        "lead, so the count is written down instead")
