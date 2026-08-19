"""The package constructs its Anthropic client in one place.

`prove.generate` and `coverage_prove._call_model` each carried the same preamble: check
the key, import the SDK, construct a client, swallow every exception so an unusable reply
never becomes a false proof. Two copies of a fallible boundary is two places for the
refusal to drift, and they had already drifted on the token limit, 4096 against 2048,
with nothing saying whether that was a decision.

What differs between them is the TAIL and only the tail. `generate` wants the text with
its fences stripped; `_call_model` wants that text parsed as JSON. So the call is one
function and the parsing is the caller's.

`python_coverage_prove` already imported `_call_model` rather than copying it, which is
the shape the other two now share.
"""

import pathlib
import re

import pytest
from l1_analyzer import coverage_prove, prove

_PKG = pathlib.Path(prove.__file__).parent


def test_the_sdk_client_is_constructed_in_exactly_one_place():
    source = "\n".join(p.read_text() for p in _PKG.glob("*.py"))
    sites = re.findall(r"Anthropic\(api_key", source)
    assert len(sites) == 1, f"{len(sites)} client constructions; the refusal can drift between them"


@pytest.mark.parametrize("call", [
    # Measured against the real TypedDict, not from memory: ProofRequest is
    # kind/file/line/symbol/context, and `context` is what the model is handed.
    lambda: prove.generate(prove.ProofRequest(
        kind="shared-mutable", file="src/lib.rs", line=1, symbol="s", context="fn f() {}")),
    lambda: coverage_prove._call_model("instruction", "payload"),
])
def test_both_callers_refuse_without_a_key(monkeypatch, call):
    """The behaviour the shared preamble owes: no key, no call, no claim."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert call() is None
