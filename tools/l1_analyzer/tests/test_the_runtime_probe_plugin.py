"""The pytest plugin that watches the audited module, called directly.

It began as source inside a string literal in `runtime_probe.py`, which put a module's
worth of logic where the linter, the type checker, the coverage run and this project's own
facet reader could all see nothing. Code no tool can measure is the shape this instrument
exists to name, and it was sitting in the instrument.

Nothing here starts pytest. The plugin's three decisions are what to wrap, what to record
about a call, and what to do when reading a value fails, and each of them is a function.
"""

import json

import pytest
from l1_analyzer import runtime_probe_plugin as plugin


def _fresh() -> list[dict]:
    return []


# --------------------------------------------------------------------------
# Reading a value without breaking the suite
# --------------------------------------------------------------------------

def test_a_value_is_read_by_its_repr():
    assert plugin.safe_repr([1, 2]) == "[1, 2]"


def test_a_value_whose_repr_raises_does_not_fail_the_suite():
    """An audit that turns into a test failure inside the audited code has changed the
    thing it was measuring."""
    class Hostile:
        def __repr__(self):
            raise RuntimeError("no")

    assert plugin.safe_repr(Hostile()) == "<unreprable>"


def test_a_value_too_large_to_read_is_reported_unreadable_rather_than_truncated():
    """Auditing this module killed the run. Two of its functions take the observation list
    as an argument, so every call wrote the whole accumulated log into the log and the next
    call wrote that. Exponential, and the process died before pytest printed a line.

    Unreadable rather than truncated, because a truncated repr compares two different
    values as equal, which would report determinism holding on a function that answers
    differently past the cut."""
    assert plugin.safe_repr(list(range(5000))) == plugin.UNREADABLE
    assert plugin.safe_repr([1, 2]) == "[1, 2]"


def test_an_unreadable_value_makes_the_call_evidence_for_nothing():
    assert plugin.opaque([plugin.UNREADABLE]) is True
    assert plugin.opaque(["<unreprable>"]) is True


def test_an_observed_call_stays_the_size_of_its_own_record():
    """The blowup, at the level it happened. The observer reprs an argument that is the
    growing log itself."""
    seen = _fresh()
    watched = plugin.observe(lambda log: len(log), seen)
    for _ in range(20):
        watched(seen)
    assert len(str(seen)) < 200_000, "the record is growing on what it recorded"


def test_a_default_repr_makes_the_whole_call_unreadable():
    assert plugin.opaque(["[1]", "<X object at 0x104f2a3b0>"]) is True
    assert plugin.opaque(["[1]", "'x'"]) is False
    assert plugin.opaque([]) is False


# --------------------------------------------------------------------------
# What one watched call records
# --------------------------------------------------------------------------

def test_a_watched_call_returns_what_the_function_returned():
    seen = _fresh()
    watched = plugin.observe(lambda items: len(items), seen)
    assert watched([1, 2]) == 2


def test_a_watched_call_records_its_arguments_on_both_sides():
    """Both sides is what makes a change in place visible. One side would show the result
    of the mutation and no way to know it was one."""
    seen = _fresh()

    def collect(items):
        items.append("added")
        return items

    plugin.observe(collect, seen)([])
    assert seen[0]["before"] == ["[]"]
    assert seen[0]["after"] == ["['added']"]


def test_a_watched_call_records_its_keywords():
    seen = _fresh()
    plugin.observe(lambda cap, ceiling=0: cap, seen)(5, ceiling=3)
    assert seen[0]["keywords"] == {"ceiling": "3"}
    assert seen[0]["before"] == ["5"]


def test_a_call_that_raises_still_records_and_still_raises():
    """The exception belongs to the suite, not to the audit. Swallowing it would turn a
    failing test green, which is the worst thing an observer could do."""
    seen = _fresh()

    def explode(items):
        items.append("added")
        raise ValueError("no")

    with pytest.raises(ValueError):
        plugin.observe(explode, seen)([])
    assert seen[0]["raised"] == "ValueError"
    assert seen[0]["result"] == ""
    assert seen[0]["after"] == ["['added']"], "mutation before the raise is still readable"


def test_a_watched_function_keeps_its_name_and_its_docstring():
    def band(n):
        """Three arms."""
        return n

    watched = plugin.observe(band, _fresh())
    assert watched.__name__ == "band"
    assert watched.__doc__ == "Three arms."
    assert watched.__wrapped__ is band


def test_an_opaque_argument_marks_the_call():
    class Box:
        pass

    seen = _fresh()
    plugin.observe(lambda box: 1, seen)(Box())
    assert seen[0]["opaque"] is True


# --------------------------------------------------------------------------
# What gets wrapped
# --------------------------------------------------------------------------

def test_only_the_functions_the_module_defines_are_wrapped(tmp_path, monkeypatch):
    """A function the module merely imported belongs to another module, and watching it
    here would attribute its behaviour to this one."""
    (tmp_path / "target.py").write_text(
        "from json import dumps\n\n\ndef mine(n: int) -> int:\n    return n\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    seen = _fresh()
    assert plugin.wrap_module("target", seen) == 1

    import target
    target.mine(1)
    target.dumps({})
    assert [call["function"] for call in seen] == ["mine"]


def test_a_module_defining_no_function_wraps_nothing(tmp_path, monkeypatch):
    (tmp_path / "bare.py").write_text("X = 1\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    assert plugin.wrap_module("bare", _fresh()) == 0


# --------------------------------------------------------------------------
# Handing the observations back
# --------------------------------------------------------------------------

class _Config:
    """What pytest hands the hooks. The observations ride on it rather than in a module
    level list, which this project's own L1.18 gate flagged as unbounded shared state in
    the tool that measures unbounded shared state."""


def test_the_observations_are_written_where_the_probe_asked(tmp_path):
    destination = tmp_path / "seen.json"
    assert plugin.write_observations([{"function": "f"}], str(destination)) is True
    assert json.loads(destination.read_text()) == [{"function": "f"}]


def test_nothing_is_written_when_no_destination_was_named(tmp_path):
    """The plugin is registered by name, so it also loads in runs nobody asked to watch.
    Writing to a path from a previous run would overwrite one audit with another."""
    assert plugin.write_observations([{"function": "f"}], "") is False
    assert list(tmp_path.iterdir()) == []


def test_configuring_wraps_the_module_the_probe_named(tmp_path, monkeypatch):
    (tmp_path / "configured.py").write_text("def f(n: int) -> int:\n    return n\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv(plugin.MODULE_VARIABLE, "configured")
    config = _Config()
    plugin.pytest_configure(config)

    import configured
    configured.f(1)
    assert [call["function"] for call in getattr(config, plugin.STASH)] == ["f"]


def test_unconfiguring_hands_back_what_the_run_saw(tmp_path, monkeypatch):
    destination = tmp_path / "seen.json"
    monkeypatch.setenv(plugin.OUTPUT_VARIABLE, str(destination))
    config = _Config()
    setattr(config, plugin.STASH, [{"function": "f"}])
    plugin.pytest_unconfigure(config)
    assert json.loads(destination.read_text()) == [{"function": "f"}]


def test_unconfiguring_a_run_that_never_configured_writes_an_empty_record(tmp_path, monkeypatch):
    monkeypatch.setenv(plugin.OUTPUT_VARIABLE, str(tmp_path / "seen.json"))
    plugin.pytest_unconfigure(_Config())
    assert json.loads((tmp_path / "seen.json").read_text()) == []


# --------------------------------------------------------------------------
# Watching the watcher
# --------------------------------------------------------------------------

def test_the_wrapper_does_not_reach_through_the_namespace_it_is_changing():
    """Auditing this module hung the whole tool. `describe` and `safe_repr` are among the
    functions the plugin wraps when pointed at itself, and they are also what the wrapper
    calls to describe a call, so describing a call described the describing of it, without
    bound.

    A self-audit is not an exotic case: it is the first thing anyone points an instrument
    at. `describe` is bound at wrap time, so replacing the module attribute afterwards
    cannot reach the wrapper."""
    seen = _fresh()
    watched = plugin.observe(lambda n: n, seen)
    plugin.describe = plugin.observe(plugin.describe, seen)
    try:
        assert watched(1) == 1
    finally:
        plugin.describe = plugin.describe.__wrapped__
    assert [call["function"] for call in seen] == ["<lambda>"], seen


def test_the_wrapper_holds_every_collaborator_it_uses():
    """The rule, enforced against the compiled code rather than stated in a docstring.

    A wrapper that looks a collaborator up by module-global name, in a module whose globals
    it has just replaced, calls itself without bound. Binding the first link left the
    recursion one level down in `describe`; binding that left it a level down again in
    `opaque`. Fixing instances of this one at a time is how it survived three rounds.

    `co_names` holds the global names the compiled body reaches for. None of them may be a
    function this plugin defines."""
    body = plugin.observe(lambda n: n, [])
    ours = {name for name, value in vars(plugin).items()
            if callable(value) and getattr(value, "__module__", "") == plugin.__name__}
    reached = set(body.__code__.co_names) & ours
    assert reached == set(), (
        f"the wrapper reaches for {sorted(reached)} through the namespace it replaces; "
        "bind it as a parameter with a default instead")


def test_the_reader_a_wrapper_uses_can_be_handed_in():
    """It is a parameter, which is what makes the binding testable rather than a claim."""
    seen = _fresh()
    plugin.observe(lambda n: n, seen, reader=lambda a, k: (["fixed"], {}))(1)
    assert seen[0]["before"] == ["fixed"]


def test_a_nested_call_to_another_audited_function_is_still_recorded():
    """The guard covers the bookkeeping, not the call. A module whose functions call each
    other is doing real work and every one of those calls is evidence."""
    seen = _fresh()
    inner = plugin.observe(lambda n: n + 1, seen)
    outer = plugin.observe(lambda n: inner(n) * 2, seen)
    assert outer(1) == 4
    assert len(seen) == 2


# --------------------------------------------------------------------------
# Describing a call, and the boundaries of one
# --------------------------------------------------------------------------

@pytest.mark.parametrize(("args", "kwargs", "before", "keywords"), [
    ((), {}, [], {}),
    ((1, "x"), {}, ["1", "'x'"], {}),
    ((), {"cap": 5}, [], {"cap": "5"}),
    (([],), {"flag": True}, ["[]"], {"flag": "True"}),
])
def test_a_call_is_described_by_its_arguments_and_its_keywords(args, kwargs, before, keywords):
    assert plugin.describe(args, kwargs) == (before, keywords)


def test_a_call_with_nothing_in_it_is_described_as_nothing():
    """A no-argument call is a real call. Describing it as anything else would put a region
    in the record that the caller never supplied."""
    assert plugin.describe((), {}) == ([], {})


def test_wrapping_a_module_that_is_not_there_says_so():
    with pytest.raises(ModuleNotFoundError):
        plugin.wrap_module("a_module_nobody_has", [])


def test_wrapping_appends_to_a_list_that_already_holds_observations():
    """The list is handed in, so a caller accumulating across modules keeps what it had."""
    seen = [{"function": "earlier"}]
    watched = plugin.observe(lambda n: n, seen)
    watched(1)
    assert [call["function"] for call in seen] == ["earlier", "<lambda>"]


# --------------------------------------------------------------------------
# The readers are functions, shown rather than assumed
# --------------------------------------------------------------------------

@pytest.mark.parametrize(("reader", "arguments"), [
    (plugin.safe_repr, ([1, 2],)),
    (plugin.opaque, (["[1]"],)),
    (plugin.describe, ((1,), {})),
])
def test_a_reader_called_twice_the_same_way_answers_the_same_way(reader, arguments):
    """Determinism, shown for the readers themselves. Nothing had called one twice, so the
    property was unobserved on the module that observes the property."""
    assert reader(*arguments) == reader(*arguments)


def test_describing_a_call_does_not_change_what_was_passed():
    """Mutation, shown. An observer that altered the arguments it was reading would be
    reporting on a call nobody made."""
    items = [1, 2]
    plugin.describe((items,), {})
    assert items == [1, 2]


def test_wrapping_a_module_a_second_time_wraps_nothing(tmp_path, monkeypatch):
    """A wrapper belongs to THIS module, not to the target, so the second pass does not
    recognise it as one of the target's functions. That is the behaviour worth having:
    double wrapping would record every call twice and halve the apparent determinism."""
    (tmp_path / "twice.py").write_text("def f(n: int) -> int:\n    return n\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    assert plugin.wrap_module("twice", []) == 1
    assert plugin.wrap_module("twice", []) == 0

    import twice
    twice.f(1)
    assert plugin.wrap_module("twice", _fresh()) == 0, "the wrapper was wrapped again"


# --------------------------------------------------------------------------
# The module's own data, which purity is about
# --------------------------------------------------------------------------

def test_the_module_state_is_its_data_and_not_its_functions(tmp_path, monkeypatch):
    """Purity asks what a call changed that its return value does not mention. Functions,
    classes and dunders are not that: they are what the module IS, not what it holds."""
    (tmp_path / "stateful.py").write_text(
        "CACHE = {}\nLIMIT = 5\n\n\nclass Box:\n    pass\n\n\ndef f(n: int) -> int:\n    return n\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    import stateful
    shown = plugin.module_state(stateful)
    assert "CACHE" in shown and "LIMIT" in shown
    assert "Box" not in shown and "__name__" not in shown


def test_the_module_state_changes_when_its_data_does(tmp_path, monkeypatch):
    (tmp_path / "changing.py").write_text("CACHE = {}\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    import changing
    before = plugin.module_state(changing)
    changing.CACHE["a"] = 1
    assert plugin.module_state(changing) != before


def test_a_module_state_that_cannot_be_read_is_reported_empty(tmp_path, monkeypatch):
    """Empty means unreadable, which is not the same as a module holding nothing. The
    verdict reader treats the two differently and has to be able to."""
    (tmp_path / "bare.py").write_text("")
    monkeypatch.syspath_prepend(str(tmp_path))
    import bare

    def refuse(_value: object) -> str:
        raise RuntimeError("no")

    assert plugin.module_state(bare, read=refuse) == ""


def test_a_module_holding_no_data_still_reads_as_readable(tmp_path, monkeypatch):
    (tmp_path / "empty_module.py").write_text("def f(n: int) -> int:\n    return n\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    import empty_module
    assert plugin.module_state(empty_module) == "[]"


def test_wrapping_a_module_with_no_name_says_so():
    with pytest.raises(ValueError):
        plugin.wrap_module("", [])


def test_writing_no_observations_still_records_the_run(tmp_path):
    """An audit that watched a suite and saw nothing is a different fact from an audit that
    could not watch one. The empty file is what says the first happened."""
    destination = tmp_path / "seen.json"
    assert plugin.write_observations([], str(destination)) is True
    assert json.loads(destination.read_text()) == []
