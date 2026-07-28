"""Basic tests for the any-language L1 analyzer."""

from pathlib import Path

import pytest

from l1_analyzer import compute_git_indicators, detect_primary_language, analyze_mutable_state

REPO = Path("/tmp/oss-analysis/requests")

def test_detect_lang():
    assert detect_primary_language(REPO) == "python"

def test_l1_18_python_runs():
    res = analyze_mutable_state(REPO, "python")
    assert "value" in res
    assert res["band"] in ("Healthy", "Not Healthy", "Slop")
    assert res["value"] < 10  # requests is quite clean

def test_git_indicators_run():
    res = compute_git_indicators(REPO)
    assert "L1.1" in res
    # shallow clone may give odd numbers, but it shouldn't crash
    assert "value" in res["L1.1"]
