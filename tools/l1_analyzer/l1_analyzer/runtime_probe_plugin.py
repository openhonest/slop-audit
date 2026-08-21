"""The pytest plugin that watches the audited module's functions while the suite runs.

A real module rather than a string the probe writes to a temp file. It began as source
inside a string literal, which put a module's worth of logic where the linter, the type
checker, the coverage run and this project's own facet reader could all see nothing. Code
no tool can measure is the shape this instrument exists to name.

It is loaded with `-p l1_analyzer.runtime_probe_plugin` and told what to wrap through two
environment variables, because a pytest plugin has no other way to take an argument.

`pytest_configure` runs before collection, so the wrappers are in place on the module
object by the time a test says `from m import band` and binds the name.
"""

import importlib
import inspect
import json
import os
from collections.abc import Callable
from functools import partial
from typing import TypedDict


class Observation(TypedDict):
    """One watched call. `before` and `after` are the reprs of the positional arguments on
    either side of it, which is what makes a change in place visible.

    It lives here, in the plugin that produces it, rather than in the module that reads it.
    That is what lets both name the same shape without either importing the other in a
    circle, and it removed the `Any` that stood in for it."""

    function: str
    before: list[str]
    after: list[str]
    keywords: dict[str, str]
    result: str
    raised: str
    opaque: bool
    state_before: str
    state_after: str


MODULE_VARIABLE = "L1_PROBE_MODULE"
OUTPUT_VARIABLE = "L1_PROBE_OUT"

# How much of a value the observer will read. Auditing this module killed the run: two of
# its functions take the observation list as an argument, so every call wrote the whole
# accumulated log into the log, and the next call wrote that. The growth is exponential and
# the process was killed before pytest printed a line.
#
# The limit is not only a guard against that one shape. A value too large to read is a
# value that cannot be compared, and a truncated repr that pretended otherwise would
# compare two different values as equal. Over the limit, the call is unreadable, which is
# the same answer the observer already gives for a default repr.
READ_LIMIT = 2000
UNREADABLE = "<too-large-to-read>"


def safe_repr(value: object) -> str:
    """A repr that cannot fail the suite it is watching, and cannot swamp it either.

    An object whose own `__repr__` raises would turn an audit into a test failure in the
    audited code. A value longer than the limit is reported unreadable rather than
    truncated, because a truncated repr compares two different values as equal."""
    try:
        shown = repr(value)
    except Exception:  # noqa: BLE001 - any repr failure, and the reason is not useful here
        return "<unreprable>"
    return shown if len(shown) <= READ_LIMIT else UNREADABLE


def opaque(texts: list[str]) -> bool:
    """Whether any repr is one the observer could not read.

    A default repr carries an address and so compares equal to nothing; a value over the
    read limit was never read at all. One such value makes the whole call unreadable."""
    return any(t in (UNREADABLE, "<unreprable>")
               or (t.startswith("<") and t.endswith(">") and " object at 0x" in t)
               for t in texts)


def describe(args: tuple[object, ...], kwargs: dict[str, object],
             read: Callable[[object], str] = safe_repr) -> tuple[list[str], dict[str, str]]:
    """The reprs of one call's arguments and keywords.

    `read` is bound here at definition time, for the same reason `observe` binds `describe`:
    every link in the wrapper's chain has to be held before the wrapping starts. Binding
    only the first link left `describe` reaching for `safe_repr` through the module
    namespace, which by then held the wrapped one, and the recursion came straight back."""
    return ([read(a) for a in args],
            {name: read(value) for name, value in kwargs.items()})


def module_state(module: object, read: Callable[[object], str] = safe_repr) -> str:
    """The module's own mutable data, as one string.

    Functions, classes and dunders are left out: what a call can change and the return
    value does not mention is the data. An empty string means it could not be read, which
    is not the same as a module holding nothing."""
    try:
        return read(sorted(
            (name, read(value)) for name, value in vars(module).items()
            if not name.startswith("__") and not callable(value)
            and not isinstance(value, type)))
    except Exception:  # noqa: BLE001 - an unorderable namespace is unreadable, not a failure
        return ""


def observe(fn: Callable[..., object], seen: list[Observation],
            reader: Callable[..., tuple[list[str], dict[str, str]]] = describe,
            unreadable: Callable[[list[str]], bool] = opaque,
            state: Callable[[], str] = lambda: "") -> Callable[..., object]:
    """`fn`, wrapped so every call appends one observation to `seen`.

    The arguments are read on both sides of the call, which is what makes a change in place
    visible. A call that raises still records its arguments, because what they look like
    afterwards is readable and is evidence about mutation.

    EVERY collaborator the bookkeeping uses is a parameter with a default bound HERE, at
    definition time, and `describe` binds `safe_repr` the same way. That is the whole of
    the fix for a self-audit: all of them are among the functions this plugin wraps when
    pointed at itself, so a wrapper that resolved any of them through the module namespace
    it had just mutated called itself without bound.

    The rule is the shape, not the list. Binding the first link left the recursion one
    level down in `describe`, and binding that left it a level down again in `opaque`. A
    wrapper must not reach for ANY of its own collaborators through the namespace it is
    changing, and `test_the_wrapper_holds_every_collaborator_it_uses` reads the compiled
    code to keep it that way rather than trusting this paragraph."""
    def watched(*args: object, **kwargs: object) -> object:
        before, keywords = reader(args, kwargs)
        state_before = state()
        raised, result = "", None
        try:
            result = fn(*args, **kwargs)
        except BaseException as error:
            raised = type(error).__name__
            raise
        finally:
            after, _ = reader(args, {})
            shown = "" if raised else reader((result,), {})[0][0]
            seen.append({
                "function": fn.__name__, "before": before, "after": after,
                "keywords": keywords, "result": shown, "raised": raised,
                "opaque": unreadable(before + after + list(keywords.values())
                                     + ([shown] if shown else [])),
                "state_before": state_before, "state_after": state(),
            })
        return result

    watched.__name__ = fn.__name__
    watched.__doc__ = fn.__doc__
    setattr(watched, "__wrapped__", fn)  # noqa: B010 - the name is fixed by convention
    return watched


def wrap_module(name: str, seen: list[Observation]) -> int:
    """Replace every function the module DEFINES with a watched one, and say how many.

    Functions the module merely imported are left alone: they belong to another module and
    watching them here would attribute their behaviour to this one."""
    module = importlib.import_module(name)
    read_state = partial(module_state, module)
    wrapped = 0
    for attribute, value in list(vars(module).items()):
        if inspect.isfunction(value) and getattr(value, "__module__", "") == name:
            setattr(module, attribute, observe(value, seen, state=read_state))
            wrapped += 1
    return wrapped


STASH = "_l1_probe_seen"


def pytest_configure(config: object) -> None:
    """Wrap before collection, so a test's `from m import band` binds the watched name.

    The observations ride on pytest's own config object rather than in a module-level list.
    That list was shared mutable state, and this project's own L1.18 gate said so: two
    functions referencing unbounded external state, in the tool that measures it."""
    seen: list[Observation] = []
    setattr(config, STASH, seen)
    wrap_module(os.environ[MODULE_VARIABLE], seen)


def pytest_unconfigure(config: object) -> None:
    """Hand back what was seen. A run killed before this point loses its observations, and
    the probe reports that as a run it could not watch rather than as a module with no
    runtime properties."""
    write_observations(getattr(config, STASH, []), os.environ.get(OUTPUT_VARIABLE, ""))


def write_observations(seen: list[Observation], destination: str) -> bool:
    """Write the observations where the probe asked, and say whether it did.

    No destination means nobody asked to watch this run. The plugin is registered by name,
    so it also loads in runs that are not audits, and writing to a path from a previous one
    would overwrite one audit with another."""
    if not destination:
        return False
    with open(destination, "w") as handle:
        json.dump(seen, handle)
    return True
