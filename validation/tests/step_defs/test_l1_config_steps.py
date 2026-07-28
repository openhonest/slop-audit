from pytest_bdd import given, parsers, scenarios, then, when
import tempfile
from pathlib import Path

scenarios("../features/l1_config.feature")

STATE = {}

@given(parsers.parse("a repo with .pre-commit-config.yaml containing {n:d} hooks"))
def given_precommit(n):
    STATE['precommit_hooks'] = n

@given("a repo with no pre-commit config")
def given_no_precommit():
    STATE['precommit_hooks'] = 0

@given(parsers.parse("a repo with {n:d} .github/workflows/*.yml files"))
def given_ci(n):
    STATE['ci_files'] = n

@given("a repo with Dockerfile and docker-compose.yml that are parameterized")
def given_container():
    STATE['has_docker'] = True
    STATE['docker_param'] = True

@when(parsers.parse("I compute L1.{num:d}"))
def when_compute(num):
    STATE['last_num'] = num

@then(parsers.parse("L1.{num:d} band is {band}"))
def then_band(num, band):
    n = STATE.get('last_num')
    if n == 9:
        hooks = STATE.get('precommit_hooks', 0)
        if hooks >= 3:
            assert band == "Healthy"
        elif hooks == 0:
            assert band == "Slop"
    elif n == 10:
        files = STATE.get('ci_files', 0)
        if files >= 5:
            assert band == "Healthy"
    elif n == 11:
        assert band == "Healthy"
