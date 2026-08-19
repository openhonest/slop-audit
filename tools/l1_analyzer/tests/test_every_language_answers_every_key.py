"""Every language answers every question in the vocabulary tables.

A language that simply lacks a key is not a language that has no such construct: it is a
language nobody wrote a row for. The two read the same downstream, because the readers
spelled `sp.get("extra_bounded", frozenset())`. An empty answer that was never written is
a rule finding nothing and a measure publishing a clean result it never earned, which is
the bug category this whole package exists to name.

Ten such reads existed across the package, over eight keys. mutable_state carries a
comment about one of them: "`if cfg.get(flag)` tests whose fall-through was the text
heuristic, which is how a" defect got in.

Making the key sets identical is what turns the omission into a build failure: adding a
key for one language now forces the other eight to answer it, even if the answer is
"nothing". These tests are the enforcement.
"""

import pathlib
import re

from l1_analyzer import indicators, mutable_state, state_bounds, state_refs
from l1_analyzer.lang_cfg import LANG_CFG
from l1_analyzer.lang_spec import LANG_SPEC


def test_every_langspec_entry_holds_the_same_keys():
    keys = {lang: frozenset(spec) for lang, spec in LANG_SPEC.items()}
    every = frozenset().union(*keys.values())
    gaps = {lang: sorted(every - k) for lang, k in keys.items() if k != every}
    assert not gaps, f"languages with unanswered LangSpec keys: {gaps}"


def test_every_langcfg_entry_holds_the_same_keys():
    keys = {lang: frozenset(cfg) for lang, cfg in LANG_CFG.items()}
    every = frozenset().union(*keys.values())
    gaps = {lang: sorted(every - k) for lang, k in keys.items() if k != every}
    assert not gaps, f"languages with unanswered LangCfg keys: {gaps}"


def test_no_reader_supplies_its_own_default_for_a_vocabulary_key():
    """With every key answered, a reader that still defaults is asking for an answer it
    has already been given, and hiding the KeyError that would otherwise name a language
    nobody wrote a row for."""
    offenders = []
    for module in (indicators, mutable_state, state_bounds, state_refs):
        path = pathlib.Path(module.__file__)
        for number, line in enumerate(path.read_text().split("\n"), start=1):
            # Comments are skipped on purpose. mutable_state carries a note naming this
            # exact pattern as the cause of a fixed defect, and a check that cannot tell
            # a description of a bug from the bug is a check nobody can keep green.
            code = line.split("#", 1)[0]
            if re.search(r"\b(?:cfg|sp|spec)\.get\(", code):
                offenders.append(f"{path.name}:{number}")
    assert not offenders, f"vocabulary reads with a fall-through default: {offenders}"
