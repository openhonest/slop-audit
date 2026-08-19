"""Every key LANG_CFG declares is read through LANG_CFG somewhere.

`class_types` was declared for all nine languages in LANG_CFG and read zero times through
it. A declared-and-unread config key is a stub in the shape of coverage: it reads as
though each language were configured for something the code never asks about.

WHAT HID IT is the shared name. `class_types` also exists in LANG_SPEC, where it has
several readers, so a plain grep finds it everywhere and says it is used. This test
therefore looks for the LangCfg READ FORMS specifically -- `cfg["key"]`, `cfg.get("key")`
and `LANG_CFG[...]["key"]` -- rather than for the bare name.

WHAT MADE IT LOOK COVERED is that `test_every_language_config_has_required_keys` asserted
its presence in every entry, so a test enforced a declaration nobody consumed. A test can
manufacture the appearance of coverage as easily as it can measure it, and this is the
shape that does: it asserted the key existed, which was true, and never asked whether
anything read it.
"""

import pathlib
import re

from l1_analyzer.indicators import LANG_CFG

_PKG = pathlib.Path(__file__).resolve().parents[1] / "l1_analyzer"

# Keys with no LangCfg reader that are deliberately kept, each with the reason.
_DECLARED_BUT_UNREAD: dict[str, str] = {}


def _read_forms(source: str) -> set[str]:
    """Keys read through a LangCfg, by the three spellings the package uses."""
    found = set()
    for pattern in (r'\bcfg\s*\[\s*"([a-z_]+)"\s*\]',
                    r'\bcfg\.get\(\s*"([a-z_]+)"',
                    r'\bLANG_CFG\s*\[[^\]]+\]\s*\[\s*"([a-z_]+)"\s*\]'):
        found |= set(re.findall(pattern, source))
    return found


def test_no_lang_cfg_key_is_declared_and_never_read():
    source = "\n".join(p.read_text() for p in _PKG.glob("*.py"))
    read = _read_forms(source)
    unread = sorted(k for k in LANG_CFG["python"]
                    if k not in read and k not in _DECLARED_BUT_UNREAD)
    assert not unread, (
        "declared for every language and read through LANG_CFG nowhere: " + ", ".join(unread) +
        "\nDelete the key, or add it to _DECLARED_BUT_UNREAD with the reason it stays.")


def test_the_exclusion_list_carries_a_reason_for_every_entry():
    assert all(reason.strip() for reason in _DECLARED_BUT_UNREAD.values())


def test_the_scan_finds_a_key_that_is_read():
    """The guard. A scan that matched nothing would make the assertion above vacuous."""
    source = "\n".join(p.read_text() for p in _PKG.glob("*.py"))
    assert "extensions" in _read_forms(source)
