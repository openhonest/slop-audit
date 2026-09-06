"""A request the SDK expects to run long has to be streamed, or it never goes out.

The Anthropic SDK refuses a non-streaming request whose expected duration crosses ten
minutes, and it decides that from `max_tokens` rather than from what actually happens. So a
request that would have returned in seconds is refused before it is sent:

    ValueError: Streaming is required for operations that may take longer than 10 minutes.

Met on 2026-09-06, three hours after the ask was batched. The pack asks for room for one
answer per gap, twenty-odd of them, and that ceiling alone trips the guard. It is the output
allowance rather than the input size: the same refusal fires on a pack of two if the
allowance is high enough.

Every pack in a 176-module sweep failed this way and the run still exited 0, because a sweep
that proves nothing is a real outcome. The reason it was diagnosable at all is the
prove-loops line added that same morning, which prints what each loop said whether or not it
kept anything. Before it, this would have produced a card identical to a run nobody asked to
sweep.

The reply is assembled before anything reads it, so the index-keyed parse and the
truncated-reply refusal downstream see one whole string either way and know nothing about
how it arrived.
"""

from __future__ import annotations

from l1_analyzer import model_call


class _Streamed:
    """A client that answers over a stream and refuses to answer any other way, which is what
    the SDK does once the allowance is large."""

    def __init__(self, **kwargs):
        self.messages = self

    def create(self, **kwargs):
        raise ValueError("Streaming is required for operations that may take longer "
                         "than 10 minutes.")

    def stream(self, **kwargs):
        return _Stream("packed answer")


class _Stream:
    def __init__(self, text: str):
        self._text = text

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def get_final_message(self):
        class _Block:
            type = "text"
            text = self._text
        return type("Message", (), {"content": [_Block()]})()


def test_a_long_allowance_is_asked_for_over_a_stream(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")
    reply = model_call.call("system", "user", 40_960, lambda: _Streamed)
    assert reply["text"] == "packed answer"
    assert reply["reason"] == model_call.ANSWERED


def test_a_short_allowance_is_streamed_too(monkeypatch):
    """One way of asking, not two. A second path taken only above a threshold is a second
    thing to keep working, and the threshold is the SDK's to move rather than ours to
    track."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")
    assert model_call.call("s", "u", 16, lambda: _Streamed)["text"] == "packed answer"


def test_a_stream_that_fails_still_records_what_failed(monkeypatch):
    """The failure record this boundary already keeps. A run must be diagnosable from its
    own report rather than by re-running it under a debugger."""
    class _Broken(_Streamed):
        def stream(self, **kwargs):
            raise RuntimeError("connection reset")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-a-real-key")
    reply = model_call.call("s", "u", 4096, lambda: _Broken)
    assert reply["text"] is None
    assert reply["reason"] == model_call.CALL_FAILED
    assert "connection reset" in reply["cause"]
