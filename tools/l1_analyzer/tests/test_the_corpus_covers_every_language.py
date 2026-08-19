"""Every language the analyzer claims to read has a repository in the parity corpus.

slop-audit-958. The corpus held java, csharp, c and python. Five of the nine supported
languages had no entry, so no classifier change to javascript, typescript, go, ruby or rust
could have its blast radius measured the way changes to the other four could.

That gap was found the hard way on 2026-08-19. A TypeScript function expression was not
counted as a function, in two separate tables, and the fix had to be measured against two
ad-hoc repositories nobody else can reproduce. A corpus that covers four of nine languages
reads like a corpus, and a run over it reads like a measurement.

This is the poka-yoke: a language added to the analyzer with no repository behind it fails
here rather than looking measured.
"""

import pathlib

import tomllib
from l1_analyzer.lang_cfg import LANG_CFG

_CORPUS = pathlib.Path(__file__).resolve().parents[2] / "slop-audit-rs" / "corpus.toml"


def _entries() -> list[dict]:
    return tomllib.loads(_CORPUS.read_text())["repo"]


def test_every_supported_language_has_a_pinned_repository():
    covered = {entry["lang"] for entry in _entries()}
    missing = sorted(set(LANG_CFG) - covered)
    assert not missing, (
        f"the analyzer reads {missing} and the corpus has no repository for them, so a "
        "change to those grammars cannot have its blast radius measured"
    )


def test_no_entry_names_a_language_the_analyzer_cannot_read():
    """The other direction. An entry for a language nothing reads is a row that will never
    run, and a corpus row that never runs is worse than an absent one: it counts."""
    stray = sorted({e["lang"] for e in _entries()} - set(LANG_CFG))
    assert not stray, f"corpus rows for languages the analyzer does not read: {stray}"


def test_every_entry_is_pinned_and_carries_its_license():
    """A row without a commit is not reproducible, and a row without a license is not
    something anyone can safely clone in CI."""
    for entry in _entries():
        assert len(entry["commit"]) == 40, entry["slug"]
        assert entry["license"].strip(), entry["slug"]
        assert entry["note"].strip(), entry["slug"]
