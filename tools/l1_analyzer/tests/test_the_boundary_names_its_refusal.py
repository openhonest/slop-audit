"""When no proof is generated, the record says which of four things happened.

`model_call.call` returned None for all four: no key, no SDK installed, the request
raised, and a model that answered with nothing usable. The sweep folded all four into one
bucket and printed "the model returned nothing usable for 2 of them".

That sentence was false on 2026-08-19. The `anthropic` package is an optional extra and
was not installed, so no request was ever made. The first live sweep reported a model
declining twice when no model had been asked once. A measure publishing a claim it never
earned, in the boundary written the same day to keep the spending legible.

The four are not interchangeable to a reader. No key is a thing you fix in a file. No SDK
is `uv sync --extra prove`. A raised request is the network or the account. Only the
fourth is a fact about the model.
"""

import pytest
from l1_analyzer import coverage_prove, model_call, python_coverage_prove


def _never_asked():
    """A client maker the boundary must not reach for. No key means no request, so nothing
    should be constructed, and handing this in is how that order is asserted rather than
    assumed."""
    raise AssertionError("the client maker was asked for even though there is no key")


def test_no_key_names_the_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    reply = model_call.call("system", "user", 16, _never_asked)
    assert reply["text"] is None
    assert reply["reason"] == model_call.NO_KEY


def test_a_missing_sdk_names_the_sdk_not_the_model(monkeypatch):
    """The case that lied. An optional extra nobody installed is not a model declining."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")
    _sdk = lambda: None
    reply = model_call.call("system", "user",  16, _sdk)
    assert reply["text"] is None
    assert reply["reason"] == model_call.NO_SDK
    assert "extra" in model_call.WHY[model_call.NO_SDK]


def test_a_raised_request_names_the_request(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")

    def _boom():
        raise RuntimeError("connection reset")

    _sdk = lambda: _boom
    reply = model_call.call("system", "user",  16, _sdk)
    assert reply["text"] is None
    assert reply["reason"] == model_call.CALL_FAILED


def test_every_reason_has_a_sentence_a_reader_can_act_on():
    """A code with no sentence is a code that reaches a report as a bare token."""
    for reason in (model_call.NO_KEY, model_call.NO_SDK, model_call.CALL_FAILED, model_call.DECLINED):
        assert model_call.WHY[reason].strip()


@pytest.mark.parametrize("module", [coverage_prove, python_coverage_prove], ids=["rust", "python"])
def test_a_sweep_that_never_reached_a_model_does_not_blame_the_model(module):
    said = module.sweep_detail(retained=0, modules=1, located=154,
                               outcomes={"declined": 2}, provenance="cpython 3.13",
                               reason=model_call.NO_SDK)
    assert "returned nothing usable" not in said
    assert model_call.WHY[model_call.NO_SDK] in said


@pytest.mark.parametrize("module", [coverage_prove, python_coverage_prove], ids=["rust", "python"])
def test_a_sweep_the_model_really_declined_still_says_so(module):
    said = module.sweep_detail(retained=0, modules=1, located=154,
                               outcomes={"declined": 2}, provenance="cpython 3.13",
                               reason=model_call.DECLINED)
    assert "154" in said and "2" in said
