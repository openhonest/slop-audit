"""Every operator-facing CLI path runs, rather than only the default one.

`cli.py` carried 72 uncovered lines, the largest block reachable without a paid model call
or ThreadSanitizer. They are the flag branches: `--report` writing cards, `--race` and
`--prove` refusing when their toolchain or key is absent, the type-escape ratchet, and the
hazard-context reader.

I smoke-tested these by hand earlier in the day and found a real regression that way - a
ceiling with no flag to set it. Then I did not write the smoke test down, which is the
difference between having checked something once and knowing it still works.

Each path here is exercised through `main`, the way an operator reaches it, and asserted on
what the operator sees: a file written, a refusal naming its reason, an exit code. Nothing
here needs a key or a network; the prove paths are driven to their refusals, which is what
they do on any machine without one, including CI.
"""

import json
import pathlib

import pytest
from l1_analyzer import cli

REPO = pathlib.Path(cli.__file__).resolve().parents[2]


def _run(argv: list[str], capsys) -> tuple[int, str]:
    code = cli.main(argv)
    return code, capsys.readouterr().out


@pytest.fixture(scope="module")
def small_repo(tmp_path_factory) -> pathlib.Path:
    """A real git working copy, small enough that a full panel takes no time.

    The first version of these tests ran every panel over THIS repository and added two and
    a half minutes to a seventy-five second suite. A suite that takes minutes is a suite
    people stop waiting for, and four pre-commit gates are worth exactly as often as
    somebody runs them. What is under test here is the CLI's paths, not the analyzer's
    numbers, so the tree only has to be real, not large.

    The two gate tests still use the whole repository, because what they assert is that the
    gate passes on THIS code."""
    import subprocess

    repo = tmp_path_factory.mktemp("small")
    (repo / "band.py").write_text(
        "def band(n: int) -> str:\n"
        "    if n > 10:\n"
        "        return 'high'\n"
        "    return 'low'\n"
    )
    (repo / "test_band.py").write_text(
        "from band import band\n\n\ndef test_high():\n    assert band(20) == 'high'\n"
    )
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "one"], check=True, capture_output=True)
    return repo


def test_the_default_run_prints_a_panel(small_repo, capsys):
    code, out = _run([str(small_repo), "--no-exec"], capsys)
    assert code == 0
    assert "L1.1" in out and "L1.17" in out


def test_json_output_parses_and_names_the_language(small_repo, capsys):
    code, out = _run([str(small_repo), "--no-exec", "--format", "json"], capsys)
    assert code == 0
    payload = json.loads(out)
    assert payload["results"]["lang"] == "python"
    assert payload["results"]["L1.17"]["band"]


def test_report_writes_both_cards(small_repo, tmp_path, capsys):
    """The `--report` path, which writes files rather than printing, so nothing but running
    it proves the writer works."""
    code, _ = _run([str(small_repo), "--no-exec", "--report", str(tmp_path)], capsys)
    assert code == 0
    written = {p.suffix for p in tmp_path.iterdir()}
    assert written == {".md", ".html"}, sorted(p.name for p in tmp_path.iterdir())
    card = next(tmp_path.glob("*.md")).read_text()
    assert "Slop Audit" in card


def test_prove_refuses_for_the_language_before_it_asks_for_a_key(small_repo, capsys, monkeypatch):
    """The order the operator meets, and it is the right one: the concurrency prove loop is
    Rust-only, and this repository is Python. Telling a Python user to set an API key for a
    stage that would refuse anyway sends them to buy something they cannot use.

    I wrote this expecting the key refusal, which is the second gate, not the first."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    code, out = _run([str(small_repo), "--no-exec", "--prove", "--format", "json"], capsys)
    assert code == 0
    proofs = json.loads(out)["results"]["proofs"]
    assert proofs["verdict"] == "n/a"
    assert proofs["demonstrated"] == 0
    assert "Rust-only" in proofs["detail"]


def test_prove_coverage_repo_refuses_without_a_key(small_repo, capsys, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    code, out = _run([str(small_repo), "--no-exec", "--prove-coverage-repo", "--format", "json"], capsys)
    assert code == 0
    payload = json.loads(out)
    proofs = payload["results"].get("coverage_proofs") or payload.get("coverage_proofs")
    assert proofs["attempted"] == 0
    assert proofs["detail"].strip()


def test_race_refuses_on_a_language_it_does_not_support(small_repo, capsys):
    """The runtime race harness is Rust-only, and this repository is Python."""
    code, out = _run([str(small_repo), "--no-exec", "--race", "--format", "json"], capsys)
    assert code == 0
    payload = json.loads(out)
    race = payload["results"].get("race") or payload.get("race")
    assert race["verdict"] == "n/a"
    assert race["tool"], "a refusal must name the instrument that produced no reading"


def test_the_gate_passes_on_this_repository(capsys):
    """The pre-commit gate's own entry point. It runs on every commit here, and until now
    nothing ran it under test."""
    code, out = _run([str(REPO), "--gate", "--max-type-escapes", "0"], capsys)
    assert code == 0
    assert "gate passed" in out.lower()


def test_the_gate_fails_when_the_ratchet_is_looser_than_reality(capsys):
    """Slack is a defect: a baseline above the real count is a regression nobody is told
    about. The gate refuses in both directions and this is the downward one."""
    code, out = _run([str(REPO), "--gate", "--max-type-escapes", "9"], capsys)
    assert code != 0
    assert "ratchet" in out.lower() or "lower it" in out.lower()


@pytest.mark.parametrize("indicators", ["1,2,3", "17", "12,14"])
def test_a_subset_of_indicators_can_be_asked_for(indicators, small_repo, capsys):
    """Asserted through the JSON, because the text output is a report card written for a
    reader and names indicators by their titles rather than their codes."""
    code, out = _run([str(small_repo), "--no-exec", "--indicators", indicators, "--format", "json"], capsys)
    assert code == 0
    results = json.loads(out)["results"]
    for number in indicators.split(","):
        assert f"L1.{number}" in results, sorted(results)


def test_an_unreadable_repository_is_reported_rather_than_crashing(tmp_path, capsys):
    """A directory that is not a git working copy: every git indicator refuses and the run
    still completes, which is the property the fabricated-zero fix was about."""
    code, out = _run([str(tmp_path), "--no-exec", "--format", "json"], capsys)
    assert code == 0
    results = json.loads(out)["results"]
    assert results["L1.5"]["value"] == "n/a"
    assert results["L1.5"]["band"] == "n/a"
