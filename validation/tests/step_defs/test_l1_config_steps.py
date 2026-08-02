"""Behavioural spec for L1.9-L1.11 (config/pipeline discipline), wired to the REAL
analyzer. Each step builds real files under a tmp repo and calls
compute_config_indicators; no hardcoded band logic. State is threaded through a
per-scenario `ctx` fixture, not module globals.
"""

from pytest_bdd import given, parsers, scenarios, then, when

from l1_analyzer.indicators import compute_config_indicators
import pytest

scenarios("../features/l1_config.feature")


@pytest.fixture
def ctx():
    return {}


@given(parsers.parse("a repo with .pre-commit-config.yaml containing {n:d} hooks"))
def given_precommit(ctx, n, tmp_path):
    hooks = "\n".join(f"      - id: hook{i}" for i in range(n))
    (tmp_path / ".pre-commit-config.yaml").write_text("repos:\n  - repo: local\n    hooks:\n" + hooks + "\n")
    ctx["repo"] = tmp_path


@given("a repo with no pre-commit config")
def given_no_precommit(ctx, tmp_path):
    ctx["repo"] = tmp_path


@given(parsers.parse("a repo with {n:d} .github/workflows/*.yml files"))
def given_ci(ctx, n, tmp_path):
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    for i in range(n):
        (wf / f"ci{i}.yml").write_text("name: ci\non: push\n")
    ctx["repo"] = tmp_path


@given("a repo with Dockerfile and docker-compose.yml that are parameterized")
def given_container(ctx, tmp_path):
    (tmp_path / "Dockerfile").write_text("FROM python:3.12\nARG VERSION\n")
    (tmp_path / "docker-compose.yml").write_text("services:\n  app:\n    build: .\n")
    ctx["repo"] = tmp_path


@when(parsers.parse("I compute L1.{num:d}"))
def when_compute(ctx, num):
    ctx["result"] = compute_config_indicators(ctx["repo"])
    ctx["num"] = num


@then(parsers.parse("L1.{num:d} band is {band}"))
def then_band(ctx, num, band):
    assert ctx["result"][f"L1.{num}"]["band"] == band
