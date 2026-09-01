"""The plugin that records which files a suite opened, and nothing had asked it anything.

The tool reports a file the suite never opened. To know that, it runs the suite with this
plugin loaded, and the plugin installs an interpreter audit hook that fires on every open.
Get this wrong and the tool names files as untouched that the suite read, or misses ones it
did not, in a client's audit and with no sign that anything went wrong.

Nothing tested it. It reads zero per cent under coverage, and that number is an artefact:
the plugin runs inside the suite it is watching, in another process, so coverage never sees
it. Zero on a report is not evidence of anything, which is the whole of what this instrument
teaches, and it applied here.

Everything below runs the plugin's own functions in this process. The audit hook itself is
installed once per process and cannot be removed, so what is asked here is the recorder it
installs, not the installing.
"""

import json

from l1_analyzer import probe_record
from l1_analyzer import unopened_files_plugin as plugin
from l1_analyzer.unopened_files import OPENS_VARIABLE


class _Config:
    """Stands in for pytest's config object, which is only a place to hang the record."""


def test_an_open_is_recorded_by_path():
    seen: set[str] = set()
    plugin.watcher(seen)("open", ("/src/lib.rs", "r", 0))
    assert seen == {"/src/lib.rs"}


def test_an_event_that_is_not_an_open_is_ignored():
    """The hook fires on every audited event in the interpreter, which is hundreds of kinds.
    Recording any of the others would name files the suite never opened."""
    seen: set[str] = set()
    watch = plugin.watcher(seen)
    watch("import", ("json", None, None))
    watch("subprocess.Popen", (["ls"],))
    watch("compile", ("x = 1", "<string>"))
    assert seen == set()


def test_a_file_opened_twice_is_recorded_once():
    seen: set[str] = set()
    watch = plugin.watcher(seen)
    watch("open", ("/src/lib.rs", "r", 0))
    watch("open", ("/src/lib.rs", "w", 0))
    assert seen == {"/src/lib.rs"}


def test_an_open_of_something_that_is_not_a_path_is_passed_over():
    """`open` also fires for a file descriptor, which is an integer. Recording it would put
    a number in a list of paths, and the caller compares those against the tree."""
    seen: set[str] = set()
    watch = plugin.watcher(seen)
    watch("open", (3, "r", 0))
    watch("open", ())
    assert seen == set()


def test_two_watchers_do_not_share_a_record():
    """The recorder takes its store rather than reaching for one. A set at module level
    would be shared mutable state, which this project's own state check reports, inside the
    tool that reports it."""
    first: set[str] = set()
    second: set[str] = set()
    plugin.watcher(first)("open", ("/a", "r", 0))
    plugin.watcher(second)("open", ("/b", "r", 0))
    assert first == {"/a"}
    assert second == {"/b"}


def test_what_was_opened_is_written_where_the_caller_asked(tmp_path):
    destination = tmp_path / "opened.json"
    assert probe_record.write_record(sorted({"/b", "/a"}), str(destination)) is True
    assert json.loads(destination.read_text()) == ["/a", "/b"]


def test_the_paths_come_back_in_a_settled_order(tmp_path):
    """The caller compares this against a listing of the tree. Two runs over one suite have
    to produce the same file, or a comparison between them reports changes nobody made."""
    destination = tmp_path / "opened.json"
    probe_record.write_record(sorted({"/z", "/a", "/m"}), str(destination))
    assert json.loads(destination.read_text()) == ["/a", "/m", "/z"]


def test_a_run_nobody_asked_to_watch_writes_nothing(tmp_path):
    """The plugin is registered by name, so it loads in runs that are not audits too.
    Writing to a path left over from a previous run would overwrite one answer with
    another."""
    assert probe_record.write_record(["/a"], "") is False


def test_a_suite_that_opened_nothing_writes_an_empty_list_rather_than_no_file(tmp_path):
    """An empty list is a measured answer. No file at all is what a run that died before
    finishing leaves, and the caller reads that as a run it could not watch."""
    destination = tmp_path / "opened.json"
    assert probe_record.write_record([], str(destination)) is True
    assert json.loads(destination.read_text()) == []


def test_the_record_is_handed_back_when_the_run_ends(tmp_path, monkeypatch):
    destination = tmp_path / "opened.json"
    monkeypatch.setenv(OPENS_VARIABLE, str(destination))
    config = _Config()
    setattr(config, plugin.STASH, {"/src/lib.rs"})
    plugin.pytest_unconfigure(config)
    assert json.loads(destination.read_text()) == ["/src/lib.rs"]


def test_a_run_that_never_started_watching_writes_no_file_at_all(tmp_path, monkeypatch):
    """The distinction the whole reading turns on, from the end nobody had checked.

    The caller treats a missing file as a run it could not watch. A run whose configure
    never installed the hook has no record hanging off its config, and this defaulted that
    to an empty set and wrote an empty list, which says the suite opened no files. The two
    are opposite answers and they were the same bytes."""
    monkeypatch.setenv(OPENS_VARIABLE, str(tmp_path / "opened.json"))
    plugin.pytest_unconfigure(_Config())
    assert not (tmp_path / "opened.json").exists()


def test_a_run_that_never_started_watching_does_not_raise(tmp_path, monkeypatch):
    """Raising here would turn a suite that died early into a crash in the audit."""
    monkeypatch.setenv(OPENS_VARIABLE, str(tmp_path / "opened.json"))
    plugin.pytest_unconfigure(_Config())
