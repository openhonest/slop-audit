"""A failed request records what failed, not just that something did.

The first real live run reported "the request to the model failed, so no reply was
received" five times and there was no way to tell why. The same sentence covers a bad key,
a rate limit, a payload over the context window, a network drop and a wrong model name,
and those are five different repairs.

Swallowing the exception is right: an unusable reply must never become a false proof. Not
recording it is not. The exception's type and message go on the reply so a run can be
diagnosed from its record instead of by re-running it under a debugger.
"""

from l1_analyzer import model_call


def test_a_reply_that_arrives_carries_no_cause():
    assert model_call.ModelReply.__required_keys__ >= {"text", "reason", "cause"}


def test_a_failed_request_records_the_exception_type_and_message(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")

    class _Boom:
        def __init__(self, **kwargs):
            raise RuntimeError("context window exceeded: 250000 > 200000")

    _sdk = lambda: _Boom
    reply = model_call.call("system", "user",  16, _sdk)
    assert reply["text"] is None
    assert reply["reason"] == model_call.CALL_FAILED
    assert "RuntimeError" in reply["cause"]
    assert "context window exceeded" in reply["cause"]


def test_the_cause_is_bounded_so_a_report_stays_readable(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")

    class _Boom:
        def __init__(self, **kwargs):
            raise RuntimeError("x" * 5000)

    _sdk = lambda: _Boom
    assert len(model_call.call("s", "u",  16, _sdk)["cause"]) <= model_call.CAUSE_LIMIT


def test_the_refusals_that_never_made_a_request_carry_no_cause(monkeypatch):
    """No key and no SDK are decisions about this machine, not failures of a request.
    A cause on either would invent an interaction that never happened."""
    def _never_asked():
        raise AssertionError("no key, so the client maker must not be reached for")

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert model_call.call("s", "u", 16, _never_asked)["cause"] == ""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")
    assert model_call.call("s", "u", 16, lambda: None)["cause"] == ""
