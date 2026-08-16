"""Behavioural spec for L1.9-L1.11 (config/pipeline discipline), wired to the REAL
analyzer. Each Given builds real files under a tmp repo and returns it as `repo`; the
When calls compute_config_indicators and returns `result`. No hardcoded band logic.
"""

from l1_analyzer.indicators import compute_config_indicators
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/l1_config.feature")


@given(parsers.parse("a repo with .pre-commit-config.yaml containing {n:d} hooks"), target_fixture="repo")
def given_precommit(n, tmp_path):
    hooks = "\n".join(f"      - id: hook{i}" for i in range(n))
    (tmp_path / ".pre-commit-config.yaml").write_text("repos:\n  - repo: local\n    hooks:\n" + hooks + "\n")
    return tmp_path


@given("a repo with no pre-commit config", target_fixture="repo")
def given_no_precommit(tmp_path):
    return tmp_path


@given(parsers.parse("a repo with {n:d} .github/workflows/*.yml files"), target_fixture="repo")
def given_ci(n, tmp_path):
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    for i in range(n):
        (wf / f"ci{i}.yml").write_text("name: ci\non: push\n")
    return tmp_path


@given("a repo with Dockerfile and docker-compose.yml that are parameterized", target_fixture="repo")
def given_container(tmp_path):
    (tmp_path / "Dockerfile").write_text("FROM python:3.12\nARG VERSION\n")
    (tmp_path / "docker-compose.yml").write_text("services:\n  app:\n    build: .\n")
    return tmp_path


@when(parsers.parse("I compute L1.{num:d}"), target_fixture="result")
def when_compute(repo):
    return compute_config_indicators(repo)


@then(parsers.parse("L1.{num:d} band is {band}"))
def then_band(result, num, band):
    assert result[f"L1.{num}"]["band"] == band
