"""The model boundary takes its client, so no test reaches in to replace one.

Eight tests written today patch `model_call._import_client` with `monkeypatch.setattr`.
That is the antipattern the 2026-08-17 fixture sweep deleted from this package, stated at
the time as "a test that reaches in to replace what it is testing asserts against its own
fixture", and it is the third appearance of one lesson.

`_prove_one` learned it first and says so at the site: propose, repair and run are required
parameters because a default puts the real model call and a real subprocess one forgotten
argument away from a test. `prove_hazard` learned it second, today. This module reached for
a module-level import instead, so the only way to exercise a missing SDK, a raised request
or a thinking-block reply was to overwrite the module's own name.

The same rule, then: the boundary asks for the thing that makes a client. `anthropic_sdk`
is the production one, named at each of the two callers that mean to spend money, exactly
as the real generator and the real runner are named in cli.py.
"""

import inspect

import pytest
from l1_analyzer import coverage_prove, model_call, prove


class _Block:
    """A content block. Only a text block has `.text`, which is the point of the reader."""

    def __init__(self, text=None):
        if text is not None:
            self.text = text


def _sdk_returning(blocks):
    class _Client:
        def __init__(self, **kwargs):
            self.messages = self

        def create(self, **kwargs):
            return type("Response", (), {"content": blocks})()
    return lambda: _Client


def _sdk_raising(exception: Exception):
    class _Client:
        def __init__(self, **kwargs):
            raise exception
    return lambda: _Client


NO_SDK_INSTALLED = lambda: None


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    """The key is environment and stays environment. It is read at the boundary and there
    is nothing to inject: absence of a key is a fact about the machine."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")


def test_the_client_maker_is_a_required_argument():
    for name in ("call", "model_available", "unavailable_reason"):
        parameters = inspect.signature(getattr(model_call, name)).parameters
        assert "sdk" in parameters, f"{name} reaches for a module global instead of asking"
        assert parameters["sdk"].default is inspect.Parameter.empty, (
            f"{name} defaults its client maker, which is what put a paid call one forgotten "
            "argument away in the two loops that already fixed this"
        )


def test_no_test_in_this_package_patches_the_boundary():
    """The property the change buys, counted rather than promised."""
    import pathlib
    import re

    offenders = []
    for path in sorted(pathlib.Path(__file__).parent.glob("*.py")):
        for number, line in enumerate(path.read_text().split("\n"), start=1):
            if re.search(r"monkeypatch\.setattr\(\s*model_call", line.split("#", 1)[0]):
                offenders.append(f"{path.name}:{number}")
    assert not offenders, f"tests still replace the boundary's own names: {offenders}"


def test_a_missing_sdk_is_named_without_patching_anything():
    reply = model_call.call("system", "user", 16, NO_SDK_INSTALLED)
    assert reply["text"] is None
    assert reply["reason"] == model_call.NO_SDK


def test_a_raised_request_carries_its_cause():
    reply = model_call.call("system", "user", 16, _sdk_raising(RuntimeError("context window exceeded")))
    assert reply["reason"] == model_call.CALL_FAILED
    assert "context window exceeded" in reply["cause"]


def test_a_thinking_block_before_the_text_still_yields_the_text():
    reply = model_call.call("system", "user", 16, _sdk_returning([_Block(), _Block("the answer")]))
    assert reply["text"] == "the answer"
    assert reply["reason"] == model_call.ANSWERED


def test_a_reply_with_no_text_is_a_decline():
    reply = model_call.call("system", "user", 16, _sdk_returning([_Block()]))
    assert reply["text"] is None
    assert reply["reason"] == model_call.DECLINED


def test_no_key_refuses_before_the_client_maker_is_asked(monkeypatch):
    """The order matters: no key means no request, so nothing should be constructed."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def _must_not_be_called():
        pytest.fail("the client maker was asked for even though there is no key")

    assert model_call.call("s", "u", 16, _must_not_be_called)["reason"] == model_call.NO_KEY


@pytest.mark.parametrize(("module", "function"), [
    (prove, "generate"),
    (coverage_prove, "_call_model"),
])
def test_each_caller_names_the_real_sdk(module, function):
    """Where the convenience goes: the two places that mean to reach a paid API say so,
    the way cli.py names the real generator and the real stress runner."""
    assert "anthropic_sdk" in inspect.getsource(getattr(module, function))
