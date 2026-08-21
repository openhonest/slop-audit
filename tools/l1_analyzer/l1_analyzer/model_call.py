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


# How much of a failure's own words to keep. Enough to name a context-window overflow or a
# rate limit; short enough that a sweep's record stays readable.
CAUSE_LIMIT = 300


class ModelReply(TypedDict):
    """A reply, or the named reason there is none.

    `text` is None whenever `reason` is set, and `reason` is empty when text arrived.
    `cause` carries the exception's type and message, and ONLY for a failed request: no key
    and no SDK are decisions about this machine rather than failures of a request, and a
    cause on either would invent an interaction that never happened.

    Swallowing the exception is right, because an unusable reply must never become a false
    proof. Not recording it was not. The first real live run reported a failed request five
    times with no way to tell whether it was the key, a rate limit, a payload over the
    context window, a dropped connection or a wrong model name."""
    text: str | None
    reason: str
    cause: str


# What makes a client. Asked for rather than reached for: `_prove_one` learned this first
# and says so at its own site, `prove_hazard` learned it second, and this module reaching
# for a module-level import was the third appearance. Eight tests had to overwrite that
# name to exercise a missing SDK, a raised request or a thinking-block reply, which is a
# test asserting against its own fixture.
SdkMaker = Callable[[], Callable[..., object] | None]


def anthropic_sdk() -> Callable[..., object] | None:
    """The Anthropic constructor, or nothing when the optional extra is not installed.

    The production maker, named at each of the two callers that mean to spend money, the
    way cli.py names the real generator and the real stress runner. The absence is a value
    this module can report rather than an exception it has to catch beside every other
    failure."""
    try:
        from anthropic import Anthropic
    # honest-code-allow: L1.21.8 - the absence is the point: unavailable_reason turns this None into NO_SDK, which WHY renders as its own sentence, so the caller can tell a missing extra from a missing key
    except ImportError:
        return None
    return Anthropic


def model_available(sdk: SdkMaker) -> bool:
    """Whether a generation model can be called: a key is present AND the SDK is installed.

    Both halves, because either one missing means no request goes out. The key alone was
    the old test, which is why a sweep with a key and no SDK reported a live run."""
    return unavailable_reason(sdk) == ANSWERED


def unavailable_reason(sdk: SdkMaker) -> str:
    """Why no model can be called, or the empty string when one can.

    NO_KEY and NO_SDK are different repairs and must not share a sentence. A sweep that
    said "needs ANTHROPIC_API_KEY" to a machine that had one and lacked the optional extra
    sent its reader to the wrong file."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return NO_KEY
    if sdk() is None:
        return NO_SDK
    return ANSWERED




def _first_text(blocks: object) -> str | None:
    """The first content block that carries text, or nothing.

    `content[0].text` assumed the first block IS text. It is not: a thinking-capable model
    puts a ThinkingBlock first, so every call raised AttributeError and was swallowed as a
    failed request. A short probe against the same key and model succeeded, because it
    asked a question that produced no thinking block, which is why the failure read as a
    configuration problem and was not."""
    for block in blocks or ():
        text = getattr(block, "text", None)
        if text is not None:
            return str(text)
    return None


def call(system: str, user: str, max_tokens: int, sdk: SdkMaker) -> ModelReply:
    """One model call: the reply text, or the named reason there is none.

    The key stays environment and is read here, because its absence is a fact about the
    machine and there is nothing to inject. It is read FIRST, so no key means the maker is
    never even asked."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return {"text": None, "reason": NO_KEY, "cause": ""}
    client = sdk()
    if client is None:
        return {"text": None, "reason": NO_SDK, "cause": ""}
    try:
        response = client(api_key=os.environ["ANTHROPIC_API_KEY"]).messages.create(
            model=MODEL, max_tokens=max_tokens,
            system=system, messages=[{"role": "user", "content": user}],
        )
        text = _first_text(response.content)
        if text is None:
            # It arrived and held nothing sayable. That is the model declining, not a
            # failed request: calling it a failure sends a reader to the network for a
            # thing the model did.
            return {"text": None, "reason": DECLINED, "cause": ""}
        return {"text": text, "reason": ANSWERED, "cause": ""}
    except Exception as failure:  # noqa: BLE001 - any failure yields no proof, never a false claim
        return {"text": None, "reason": CALL_FAILED,
                "cause": f"{type(failure).__name__}: {failure}"[:CAUSE_LIMIT]}
