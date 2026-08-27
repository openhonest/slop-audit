"""A Slop band a reader cannot act on.

The canon puts this dimension's judgment at Layer 2 and says what clears it: a count at or
above three is disqualifying "unless every hit is demonstrably a false positive on a test
fixture" (spec/dimensions/07-configuration-secrets.md, Layer 2 step 1). Layer 1 cannot
demonstrate that. It can say where each hit sits, and it does, so counting all of them is
the right answer and the band must not move.

What it did not do is tell the reader the route exists. A repository whose only hits are the
fixtures of its own secret scanner reads "Slop" with no next step, which invites the one
repair this project refuses: excluding a path until the number looks better.

Found by running the audit on this repository. Every hit here is a documentation example or
a fixture belonging to the scanner itself, and the band is Slop, correctly.
"""

from pathlib import Path

from l1_analyzer import secret_scan


def _text(tmp_path: Path) -> str:
    return secret_scan.analyze(tmp_path, "python")["details"]


def _repo_with(tmp_path: Path, where: str) -> Path:
    (tmp_path / where).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / where).write_text(
        'DATABASE_URL = "postgres://app:8Kd2Lm9Qp1Xz@db:5432/app"\n'
        'API_KEY = "9Xq4Lm2Vn8Zc1Bd7Rt5Yw3Hs6Jf0Kg"\n'
        'TOKEN = "sk_live_9Zx8Wq7Vt6Ru5"\n')
    return tmp_path


def test_a_count_that_can_still_be_cleared_says_how(tmp_path):
    _repo_with(tmp_path, "tests/test_scanner.py")
    text = _text(tmp_path)
    assert "Layer 2" in text
    assert "fixture" in text


def test_it_names_the_condition_rather_than_promising_the_outcome(tmp_path):
    """The canon clears the count only if EVERY hit is demonstrably a false positive. A
    message implying the fixtures are already excused would be the suppression in prose."""
    _repo_with(tmp_path, "tests/test_scanner.py")
    clause = _text(tmp_path).split("; none of these sits in production code")[1]
    assert "only where every hit" in clause
    assert "may still clear" in clause          # may, not will
    for promise in ("does not count", "will be cleared", "safe to ignore", "already"):
        assert promise not in clause.lower(), promise


def test_a_hit_in_production_code_is_offered_no_route(tmp_path):
    """The route is for fixtures. A credential in shipped code has no Layer 2 escape, and
    printing one there would read as a way out of a finding that has none."""
    _repo_with(tmp_path, "app/config.py")
    text = _text(tmp_path)
    assert "Layer 2" not in text, text


def test_the_band_does_not_move(tmp_path):
    """The point of the whole change: the message gains a sentence and the measurement
    gains nothing. Layer 1 counts what it found, wherever it found it."""
    _repo_with(tmp_path, "tests/test_scanner.py")
    result = secret_scan.analyze(tmp_path, "python")
    assert result["value"] == 3
    assert result["counts"]["in_tests"] == 3
    assert result["band"] == "Slop"
