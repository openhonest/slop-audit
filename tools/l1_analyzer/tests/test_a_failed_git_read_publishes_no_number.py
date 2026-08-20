"""When git cannot be read, the eight git indicators publish no number.

They published `value: 0` beside `band: "n/a"`. The band said nothing was measured and the
value said zero, and the card renders the value: a directory that is not a git working
copy, or a machine with no git on PATH, produced eight rows reading `0%`.

Zero is not a neutral placeholder on this panel. L1.5 is deleted over added lines, so 0%
is the Slop end of its own scale, and L1.1 through L1.3 are shares of commits where zero
means the same. A reader who takes in the number before the band - which is the order the
card puts them in - reads a repository nobody could measure as a repository that measured
terribly.

This is the half-repair shape the package's own vacuity checker exists to convict: a
measured-looking zero published beside a refusal. It sat inside an exception handler, which
is why nothing found it until the handlers were swept.
"""

import pathlib

import pytest
from l1_analyzer import card, indicators

GIT_INDICATORS = tuple(f"L1.{n}" for n in range(1, 9))


@pytest.fixture(scope="module")
def not_a_repository(tmp_path_factory) -> pathlib.Path:
    """A directory git cannot read as a working copy."""
    return tmp_path_factory.mktemp("bare")


@pytest.mark.parametrize("code", GIT_INDICATORS)
def test_no_number_is_published_when_git_cannot_be_read(code, not_a_repository):
    result = indicators.compute_git_indicators(not_a_repository, None, None)[code]
    assert result["band"] == "n/a"
    assert result["value"] == "n/a", (
        f"{code} publishes {result['value']!r} for a repository nobody could read; the card "
        "renders the value, so a reader sees a number that was never measured"
    )


@pytest.mark.parametrize("code", GIT_INDICATORS)
def test_the_card_shows_it_as_not_measured(code, not_a_repository):
    """The reader's view, which is what the defect was about."""
    result = indicators.compute_git_indicators(not_a_repository, None, None)[code]
    assert card._value_str(result, "%") == "n/a"


def test_the_reason_is_still_named(not_a_repository):
    """Refusing without saying why would be the other half of the same fault."""
    details = indicators.compute_git_indicators(not_a_repository, None, None)["L1.1"]["details"]
    assert "git" in details.lower()
    assert details.strip()


@pytest.mark.parametrize("code", GIT_INDICATORS)
def test_a_range_holding_no_commit_publishes_no_number_either(code):
    """The same refusal on a different path, and an ordinary one to reach: a `--since`
    narrower than the history leaves the walk with nothing to count. It published the same
    bare zero, and a reader would have taken a range they chose too narrow for a repository
    that deletes nothing."""
    repo = pathlib.Path(indicators.__file__).resolve().parents[3]
    result = indicators.compute_git_indicators(repo, since="2001-01-01", until="2001-01-02")[code]
    assert result["band"] == "n/a"
    assert result["value"] == "n/a"
    assert "no commits in range" in result["details"]


def test_no_result_in_the_package_publishes_a_number_beside_an_n_a_band():
    """The rule, made permanent. Both instances of this defect were written the same way
    and lived in different functions, so counting them is what stops a third.

    A published result carries a value and a band, and the card renders the value first. A
    band of n/a says nothing was measured; a value beside it that is not also n/a says
    something was. The two cannot both be true, and the number is the one a reader acts on.

    The results that legitimately carry a value beside an n/a band are the ones whose value
    is a SENTENCE rather than a number: the state and thread meters report their counts as
    prose and leave the band to the reader, which is a different claim from a measurement.
    """
    import ast

    offenders = []
    for path in sorted(pathlib.Path(indicators.__file__).parent.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            literal = node.value if isinstance(node, ast.DictComp) else node
            if not isinstance(literal, ast.Dict):
                continue
            pairs = {ast.unparse(k).strip("'\"") : v
                     for k, v in zip(literal.keys, literal.values) if k is not None}
            band, value = pairs.get("band"), pairs.get("value")
            if not (isinstance(band, ast.Constant) and band.value == "n/a"):
                continue
            if isinstance(value, ast.Constant) and isinstance(value.value, (int, float)):
                offenders.append(f"{path.name}:{node.lineno} value {ast.unparse(value)}")
    assert not offenders, (
        f"a number published beside an n/a band: {offenders}. The band says nothing was "
        "measured and the number says otherwise, and the card renders the number."
    )


def test_a_real_repository_still_publishes_its_numbers():
    """The measure still measures. This repository is a git working copy, so every one of
    the eight comes back with a number rather than the refusal above."""
    repo = pathlib.Path(indicators.__file__).resolve().parents[3]
    results = indicators.compute_git_indicators(repo, None, None)
    for code in GIT_INDICATORS:
        assert results[code]["value"] != "n/a", code
        assert results[code]["band"] != "n/a", code
