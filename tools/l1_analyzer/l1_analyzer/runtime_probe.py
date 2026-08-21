"""Runtime properties, watched while the suite executes.

The fifth facet kind, and the only one that cannot be read from the source. Umbra's
glossary sets the discipline: a runtime property counts only when the test run clearly
shows it holding or breaking, and when the tests never make it happen the answer is that
nobody looked, not that it holds.

  mutation      does the function change the data it was handed
  determinism   does the same call give the same answer twice
  idempotency   does running it again on its own output change anything

Nothing here re-invokes the audited code to manufacture evidence. The suite is watched
doing what it already does, because a property observed by calling the function again is a
property of the audit rather than of the suite, and it would run the caller's I/O a second
time to say so.

The observation is repr-based, and that limit is named rather than hidden. An object
carrying the default repr shows its address, so two distinct objects never compare equal
and a change in place is invisible. Those calls are marked opaque and count toward nothing.
"""

import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TypedDict

from l1_analyzer import runtime_probe_plugin
from l1_analyzer.facets import Facet, Undeclared, _annotation, import_root, is_declared

PROPERTIES = ("mutation", "determinism", "idempotency")

# Types whose value can be changed in place, so "did you mutate my argument" is a question
# a test can put to the function. An int cannot be mutated, and charging a suite for not
# showing that would put an unclosable facet in the denominator.
_MUTABLE = frozenset({"list", "dict", "set", "bytearray", "deque", "Counter", "defaultdict"})

_UNOBSERVED = "unobserved"

# A property nobody could read is not a property nobody tested. The glossary keeps it out
# of the Silence index, numerator and denominator both, and carries the reason instead.
# Charging the suite for it says "you did not test this" about a property no test could
# have shown, which is the undeclared-domain mistake in the runtime half.
_UNVERIFIED = "unverified"


# One watched call, defined in the plugin that produces it. Named here so a reader of this
# module finds the shape where the readers are.
Observation = runtime_probe_plugin.Observation

def is_opaque(text: str) -> bool:
    """Whether a repr is the default one, which carries an address and compares equal to
    nothing. `'at 0x'` as a string literal is not: the marker has to be the whole shape."""
    return text.startswith("<") and text.endswith(">") and " object at 0x" in text


def invites(fn: ast.FunctionDef) -> tuple[str, ...]:
    """Which of the three properties are a meaningful question about this function.

    A property nobody could ever exercise is not a silence. `band(n: int)` cannot mutate an
    int, and a function returning a type unlike its argument cannot be fed its own output,
    so those facets are never enumerated rather than enumerated and reported unclosable."""
    arguments = [a for a in fn.args.args if a.arg not in ("self", "cls")]
    returns = _annotation(fn.returns)
    asked: list[str] = []
    if any(_annotation(a.annotation) in _MUTABLE for a in arguments):
        asked.append("mutation")
    if is_declared(fn.returns) and returns != "None":
        asked.append("determinism")
        # Exactly one argument. `f(f(x))` only exists when `f` takes one thing, and
        # feeding a result back as the first of three is not running it again on its own
        # output: the tool read `allowance(cap, ceiling, spent)` as breaking idempotency.
        one = len(arguments) == 1 and not fn.args.kwonlyargs
        first = _annotation(arguments[0].annotation) if arguments else ""
        if one and first and returns and first == returns:
            asked.append("idempotency")
    return tuple(asked)


def verdicts(seen: list[Observation]) -> dict[str, dict[str, str]]:
    """What the watched run showed about each function it reached.

    `holds`, `breaks`, `unobserved` or `unverified`, per property. A function the suite
    never called does not appear at all, because absence of a key and a claim about the key
    are different facts and the caller has to be able to tell them apart.

    `unobserved` means the suite could have shown it and did not, which is a closeable
    silence. `unverified` means nothing could be read, so no test could have shown it."""
    by_function: dict[str, list[Observation]] = {}
    for call in seen:
        by_function.setdefault(call["function"], []).append(call)
    return {name: {"mutation": _mutation(calls),
                   "determinism": _determinism(calls),
                   "idempotency": _idempotency(calls)}
            for name, calls in by_function.items()}


def _readable(calls: list[Observation]) -> list[Observation]:
    return [c for c in calls if not c["opaque"]]


def _mutation(calls: list[Observation]) -> str:
    """One observed change outweighs any number of clean calls: a function that mutates on
    one path mutates, and the clean calls are the paths that did not reach it."""
    readable = _readable(calls)
    if not readable:
        return _UNVERIFIED if calls else _UNOBSERVED
    if any(call["before"] != call["after"] for call in readable):
        return "breaks"
    return "holds"


def _signature(call: Observation) -> tuple[str, ...]:
    """Everything the caller passed. Keywords were left out, so every call made by keyword
    had an empty argument list and they all grouped together as the same call."""
    return tuple(call["before"]) + tuple(
        f"{name}={value}" for name, value in sorted(call["keywords"].items()))


def _determinism(calls: list[Observation]) -> str:
    """Evidence needs the same call twice. A call that raised carries no result, so it is
    not one of the two."""
    answers: dict[tuple[str, ...], list[str]] = {}
    for call in _readable(calls):
        if call["raised"]:
            continue
        answers.setdefault(_signature(call), []).append(call["result"])
    if calls and not _readable(calls):
        return _UNVERIFIED
    repeated = [results for results in answers.values() if len(results) > 1]
    if not repeated:
        return _UNOBSERVED
    return "holds" if all(len(set(results)) == 1 for results in repeated) else "breaks"


def _idempotency(calls: list[Observation]) -> str:
    """A call whose first argument is a result this function returned earlier. Holding means
    the second pass changed nothing."""
    produced: dict[str, str] = {}
    verdict = _UNVERIFIED if (calls and not _readable(calls)) else _UNOBSERVED
    for call in _readable(calls):
        if call["raised"] or len(call["before"]) != 1 or call["keywords"]:
            continue
        argument = call["before"][0]
        if argument in produced:
            verdict = "holds" if call["result"] == argument else "breaks"
            if verdict == "breaks":
                return verdict
        produced[call["result"]] = call["function"]
    return verdict


_OPAQUE_REASON = ("every watched call passed or returned a value whose repr carries its "
                  "address, so a change in place is invisible and two distinct values "
                  "never compare equal")


def runtime_facets(fn: ast.FunctionDef, verdict: dict[str, str],
                   unwatchable: str = "") -> tuple[list[Facet], list[Undeclared]]:
    """One facet per property this function invites, silent while nobody has watched it,
    and one reason apiece for the properties that could not be read at all.

    `unwatchable` is why the run itself produced nothing. When it is set, every property is
    unverified rather than unobserved: a suite that was never watched has not failed to
    exercise anything, and calling it silent charges the suite for the audit's own
    failure."""
    found: list[Facet] = []
    unverified: list[Undeclared] = []
    for prop in invites(fn):
        answer = _UNVERIFIED if unwatchable else verdict.get(prop, _UNOBSERVED)
        if answer == _UNVERIFIED:
            unverified.append({
                "kind": "honesty_unverified", "function": fn.name, "line": fn.lineno,
                "detail": f"{prop} could not be read: {unwatchable or _OPAQUE_REASON}",
            })
            continue
        found.append({
            "kind": "runtime_property", "function": fn.name, "line": fn.lineno,
            "detail": f"{prop} {answer}", "silent": answer == _UNOBSERVED,
        })
    return found, unverified


def dotted_name(module: Path, root: Path) -> str:
    """The name the tests will import the module by, which is the name the probe has to
    wrap. Wrapping a second copy loaded under another name leaves the tests calling the
    original and reports a suite that exercised nothing."""
    relative = module.resolve().relative_to(root.resolve()).with_suffix("")
    return ".".join(relative.parts)


class Watched(TypedDict):
    """What one watched run produced, and why it produced nothing when it did.

    The reason is the whole point of the pair. A run that crashed used to come back as an
    empty list, and every runtime property was then reported UNOBSERVED, which reads as
    "your suite never exercised this" about a suite that was never watched at all. That is
    this instrument's own bug category, inside the instrument."""

    observations: list[Observation]
    reason: str


def watch(module: Path, tests: tuple[Path, ...]) -> Watched:
    """Run the suite once with the module's functions wrapped, and read back what they saw."""
    module = Path(module)
    root = import_root(module)
    with tempfile.TemporaryDirectory(prefix="l1-probe-") as directory:
        out = Path(directory) / "seen.json"
        environment = dict(os.environ)
        environment[runtime_probe_plugin.MODULE_VARIABLE] = dotted_name(module, root)
        environment[runtime_probe_plugin.OUTPUT_VARIABLE] = str(out)
        environment["PYTHONPATH"] = os.pathsep.join(
            [str(root), environment.get("PYTHONPATH", "")]).rstrip(os.pathsep)
        try:
            run = subprocess.run(
                [sys.executable, "-m", "pytest", *[str(t) for t in tests], "-q",
                 "-p", "no:cacheprovider", "-p", "l1_analyzer.runtime_probe_plugin"],
                cwd=root, capture_output=True, text=True, timeout=600, check=False,
                env=environment)
        except subprocess.TimeoutExpired:
            # A suite that ran too long leaves the other four facet kinds perfectly
            # readable. Letting the timeout out of here crashed the whole audit and
            # reported nothing at all about a module whose branches had already been read.
            return {"observations": [],
                    "reason": "the watched run did not finish inside its time limit"}
        # Exit 0 is a green suite and 1 is a red one; both RAN, so what they were seen doing
        # is evidence. Anything else means the run itself failed, and its observations are
        # the absence of a measurement rather than a measurement of absence.
        if run.returncode not in (0, 1):
            return {"observations": [],
                    "reason": f"the watched run failed before it could finish "
                              f"(pytest exit {run.returncode}): "
                              f"{(run.stderr or run.stdout).strip()[-200:]}"}
        if not out.exists():
            return {"observations": [], "reason": "the watched run wrote no observations"}
        return {"observations": json.loads(out.read_text()), "reason": ""}
