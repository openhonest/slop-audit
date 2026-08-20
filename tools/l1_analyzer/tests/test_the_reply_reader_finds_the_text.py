"""The reply is read from the first TEXT block, not from the first block.

`response.content[0].text` assumed the model's first content block carries text. It does
not. A thinking-capable model puts a ThinkingBlock first, so every call raised
`AttributeError: 'ThinkingBlock' object has no attribute 'text'` and was swallowed as a
failed request.

That is what the first real live run hit, five times, and what recording the exception's
own words turned from "the request failed" into a one-line diagnosis. A direct probe
against the same key and model succeeded, because it asked a question short enough that
the model returned no thinking block at all, which is why the failure looked like a
configuration problem and was not.

Reading the first block WITH text rather than the first block is the fix, and it is
correct for both shapes: a reply with thinking and a reply without.
"""

import pytest
from l1_analyzer import model_call


class _Block:
    """Stands in for an SDK content block. Only a text block has `.text`, which is the
    whole point: the reader must not assume."""

    def __init__(self, text=None):
        if text is not None:
            self.text = text


def _client_returning(blocks):
    class _Client:
        def __init__(self, **kwargs):
            self.messages = self

        def create(self, **kwargs):
            return type("Response", (), {"content": blocks})()
    return _Client


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")


def test_a_reply_whose_first_block_is_thinking_still_yields_its_text(monkeypatch):
    _sdk = lambda: _client_returning([_Block(), _Block("the answer")])
    reply = model_call.call("system", "user",  16, _sdk)
    assert reply["text"] == "the answer"
    assert reply["reason"] == model_call.ANSWERED


def test_a_reply_with_no_thinking_block_is_unchanged(monkeypatch):
    _sdk = lambda: _client_returning([_Block("the answer")])
    assert model_call.call("system", "user",  16, _sdk)["text"] == "the answer"


def test_a_reply_carrying_no_text_at_all_is_a_decline_not_a_failure(monkeypatch):
    """A reply that arrived and held nothing sayable is the model declining. Calling it a
    failed request would send a reader to the network for a thing the model did."""
    _sdk = lambda: _client_returning([_Block()])
    reply = model_call.call("system", "user",  16, _sdk)
    assert reply["text"] is None
    assert reply["reason"] == model_call.DECLINED
