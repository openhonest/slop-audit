"""The package's one construction of the generation model client.

Two callers carried the same preamble: read the key, import the SDK, construct a client,
swallow every failure so an unusable reply never becomes a false proof. Two copies of a
refusal is two places for it to drift, and they had already drifted on the token limit.
What differs between the callers is the tail alone, so the call is one function and the
parsing belongs to whoever asked.

THE REFUSAL NAMES ITSELF, and the first version did not. It returned None for all four
ways of not answering, so the sweep folded them into one bucket and printed "the model
returned nothing usable". That sentence was false on 2026-08-19: `anthropic` is an
optional extra and was not installed, so no request was ever made, and the first live
sweep reported a model declining twice when no model had been asked once.

The four are not interchangeable to a reader. No key is a thing you fix in a file. No SDK
is one command. A raised request is the network or the account. Only the fourth is a fact
about the model.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import TypedDict

MODEL = "claude-sonnet-5"

NO_KEY = "no-key"
NO_SDK = "no-sdk"
CALL_FAILED = "call-failed"
DECLINED = "declined"
ANSWERED = ""

# One sentence per reason, each naming the next move. A code with no sentence reaches a
# report as a bare token, which is how a reader ends up guessing at a refusal.
WHY = {
    NO_KEY: "no ANTHROPIC_API_KEY was set, so no request was made",
    NO_SDK: "the anthropic SDK is not installed, so no request was made: it is an optional "
            "extra, installed with `uv sync --extra prove`",
    CALL_FAILED: "the request to the model failed, so no reply was received",
    DECLINED: "the model replied with nothing usable",
    ANSWERED: "the model replied",
}


class ModelReply(TypedDict):
    """A reply, or the named reason there is none. Exactly one of the two is meaningful:
    `text` is None whenever `reason` is set, and `reason` is empty when text arrived."""
    text: str | None
    reason: str


def model_available() -> bool:
    """Whether a generation model can be called: a key is present AND the SDK is installed.

    Both halves, because either one missing means no request goes out. The key alone was
    the old test, which is why a sweep with a key and no SDK reported a live run."""
    return unavailable_reason() == ANSWERED


def unavailable_reason() -> str:
    """Why no model can be called, or the empty string when one can.

    NO_KEY and NO_SDK are different repairs and must not share a sentence. A sweep that
    said "needs ANTHROPIC_API_KEY" to a machine that had one and lacked the optional extra
    sent its reader to the wrong file."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return NO_KEY
    if _import_client() is None:
        return NO_SDK
    return ANSWERED


def _import_client() -> Callable[..., object] | None:
    """The Anthropic constructor, or nothing when the optional extra is not installed.

    Split out so the absence is a value this module can name rather than an exception it
    has to catch alongside every other failure."""
    try:
        from anthropic import Anthropic
    except ImportError:
        return None
    return Anthropic


def call(system: str, user: str, max_tokens: int) -> ModelReply:
    """One model call: the reply text, or the named reason there is none."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return {"text": None, "reason": NO_KEY}
    client = _import_client()
    if client is None:
        return {"text": None, "reason": NO_SDK}
    try:
        response = client(api_key=os.environ["ANTHROPIC_API_KEY"]).messages.create(
            model=MODEL, max_tokens=max_tokens,
            system=system, messages=[{"role": "user", "content": user}],
        )
        return {"text": str(response.content[0].text), "reason": ANSWERED}
    except Exception:  # noqa: BLE001 - any failure yields no proof, never a false claim
        return {"text": None, "reason": CALL_FAILED}
