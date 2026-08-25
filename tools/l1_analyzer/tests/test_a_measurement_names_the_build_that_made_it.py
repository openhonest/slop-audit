"""Every published number says which build produced it.

None of them did. The version lived in `pyproject.toml`, nothing read it, there was no
`--version` flag, and neither the JSON panel nor the card carried it. A card is a published
measurement, and a reader could not tell whether it came from the build that fixed L1.13's
denominator or the one before it.

The parity job is the sharper case. It compares two implementations that are supposed to
agree, they carry different version numbers, and its verdict of sixteen equal indicators was
about two builds nobody could name afterwards.

This is the fourth instance tonight of one shape, three of them found by an adopter in their
own tooling: a value with two owners and nothing checking they agree. Here it was worse and
simpler, one owner and no reader at all.

The single source is the installed package metadata. A constant in the source would be the
second owner this exists to remove.
"""

import json
import subprocess
import sys
from importlib import metadata
from pathlib import Path

import pytest
import tomllib
from l1_analyzer import cli

REPO = Path(__file__).resolve().parents[1]


def _run(argv: list[str], capsys) -> tuple[int, str]:
    code = cli.main(argv)
    return code, capsys.readouterr().out


# --------------------------------------------------------------------------
# The tool can say which build it is
# --------------------------------------------------------------------------

def test_the_tool_reports_a_version(capsys):
    code, out = _run(["--version"], capsys)
    assert code == 0
    assert cli.version() in out


def test_the_reported_version_is_the_one_the_package_declares():
    """One source for the RELEASE number. A constant in the source would be the second
    owner this exists to remove, and nothing would check the two agreed.

    The release is now followed by the commit the build came from, which is a different
    fact with its own single owner: the checkout. It is not a second spelling of the
    release, so the invariant is that the string starts with what the metadata says, not
    that it equals it."""
    assert cli.version().startswith(metadata.version("slop-audit-l1"))


def test_the_declared_version_matches_the_packaging_metadata():
    """The two places a version can live in a Python project, asserted equal. This is the
    check whose absence let an adopter ship a release that the marketplace never served
    while `plugin update` reported the plugin current."""
    declared = tomllib.loads((REPO / "pyproject.toml").read_text())["project"]["version"]
    assert cli.version().startswith(declared), (
        "the installed package and pyproject.toml disagree; reinstall or reconcile them")


def test_asking_for_the_version_needs_no_repository(capsys):
    """It answers a question about the tool, not about a tree, so requiring a path would be
    asking for something the answer does not depend on."""
    assert _run(["--version"], capsys)[0] == 0


# --------------------------------------------------------------------------
# Every published measurement carries it
# --------------------------------------------------------------------------

def test_the_json_panel_names_the_build_that_produced_it(tmp_path, capsys):
    (tmp_path / "m.py").write_text("def f(n: int) -> int:\n    return n\n")
    _code, out = _run([str(tmp_path), "--format", "json", "--no-exec"], capsys)
    assert json.loads(out)["analyzer_version"] == cli.version()


def test_the_card_names_the_build_that_produced_it(tmp_path, capsys):
    """A card is a published measurement. A reader has to be able to tell which build made
    it, because the bands and the denominators have both changed under them."""
    (tmp_path / "m.py").write_text("def f(n: int) -> int:\n    return n\n")
    _code, out = _run([str(tmp_path), "--no-exec"], capsys)
    assert cli.version() in out


def test_the_facet_report_names_the_build(tmp_path, capsys):
    (tmp_path / "m.py").write_text("def band(n: int) -> str:\n    return 'x'\n")
    (tmp_path / "test_m.py").write_text(
        "from m import band\n\n\ndef test_b():\n    assert band(1) == 'x'\n")
    _code, out = _run(["--facets", str(tmp_path / "m.py"), str(tmp_path / "test_m.py")], capsys)
    assert cli.version() in out


# --------------------------------------------------------------------------
# The portable bundle, and the parity claim about the two of them
# --------------------------------------------------------------------------

BUNDLE = REPO.parent / "slop-audit-rs" / "target" / "release" / "slop-audit-rs"


@pytest.mark.skipif(not BUNDLE.exists(), reason="the portable bundle is not built")
def test_the_portable_bundle_reports_its_own_version():
    run = subprocess.run([str(BUNDLE), "--version"], capture_output=True, text=True, check=False)
    assert run.returncode == 0
    declared = tomllib.loads(
        (REPO.parent / "slop-audit-rs" / "Cargo.toml").read_text())["package"]["version"]
    assert declared in run.stdout


@pytest.mark.skipif(not BUNDLE.exists(), reason="the portable bundle is not built")
def test_the_parity_check_records_both_builds_it_compared(tmp_path):
    """Its verdict is that two implementations agree. Which two was not recorded anywhere,
    so a green parity run named neither build and could not be cited later."""
    run = subprocess.run(
        [sys.executable, "validate.py", str(REPO)],
        cwd=REPO.parent / "slop-audit-rs", capture_output=True, text=True, check=False)
    assert cli.version() in run.stdout, "the reference build is not named in the parity output"
    declared = tomllib.loads(
        (REPO.parent / "slop-audit-rs" / "Cargo.toml").read_text())["package"]["version"]
    assert declared in run.stdout, "the ported build is not named in the parity output"
