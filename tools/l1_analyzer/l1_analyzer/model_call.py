"""The one place this package talks to a model.

`prove.generate` and `coverage_prove._call_model` each carried the same preamble: check
the key, import the SDK, construct a client, and swallow every exception so an unusable
reply never becomes a false proof. Two copies of a fallible boundary are two places for
that refusal to drift, and they had already drifted on the token limit, 4096 against
2048, with nothing recording whether that was a decision or an accident.

What differed between them was the TAIL and only the tail: one wanted the text with its
fences stripped, the other wanted that text parsed as JSON. So the call is one function
and the parsing belongs to the caller.

EVERY FAILURE RETURNS NONE, and that is the contract rather than a convenience. No key,
no SDK, a refused request, a malformed reply: each is a reason to generate nothing, and
none of them is a reason to claim anything. The callers turn None into "not generated",
which is a stated outcome; a partial or invented reply would become a proof.
"""

from __future__ import annotations

import os

MODEL = "claude-sonnet-5"


def model_available() -> bool:
    """Whether a key is present. The one reader of the environment variable's NAME, so a
    rename cannot leave a second copy checking the old one."""
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def call(system: str, user: str, max_tokens: int) -> str | None:
    """One model call, returning the reply text or None on any failure.

    `max_tokens` is a required argument and not a default. The two callers want different
    budgets, 4096 for a generated test and 2048 for a structured proposal, and a default
    here would have made one of those silent and the other look like an override."""
    if not model_available():
        return None
    try:
        from anthropic import Anthropic
    except ImportError:
        return None
    try:
        response = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"]).messages.create(
            model=MODEL, max_tokens=max_tokens,
            system=system, messages=[{"role": "user", "content": user}],
        )
        return str(response.content[0].text)
    except Exception:  # noqa: BLE001 - any failure yields no proof, never a false claim
        return None
