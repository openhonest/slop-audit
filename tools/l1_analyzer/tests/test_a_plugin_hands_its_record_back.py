"""Both plugins that watch a suite from inside it hand their record back the same way.

One records every file the suite opens, one records what the audited module's functions did.
They are different probes with nothing else in common, and the last twenty lines of each were
the same twenty lines: read the record off pytest's config, write nothing when there is none,
write nothing when nobody asked to watch, otherwise write it where the caller said.

Those twenty lines carried the same defect in both, found and fixed on the same day. Each
defaulted an absent record to empty, so a run whose configure never installed its hook wrote
an empty list. That says the suite opened no files, or the module has no runtime properties.
The readers treat a MISSING file as a run they could not watch, so those are opposite
answers and they were the same bytes.

One copy now. The two probes differ in which environment variable names their destination
and in whether their record needs sorting before it is written, and both of those are
arguments.
"""

import json

import pytest
from l1_analyzer import probe_record


class _Config:
    """Stands in for pytest's config object, which is only a place to hang the record."""


def test_a_run_that_never_started_watching_writes_no_file(tmp_path):
    """The defect both plugins had. The reader treats a missing file as a run it could not
    watch, and an empty list as a suite that saw nothing. Those must not be the same bytes."""
    probe_record.hand_back(_Config(), "_stash", str(tmp_path / "out.json"), sorted)
    assert not (tmp_path / "out.json").exists()


def test_a_run_nobody_asked_to_watch_writes_nothing(tmp_path):
    """Both plugins are registered by name, so they load in runs that are not audits too.
    Writing to a path left over from a previous run would overwrite one answer with
    another."""
    config = _Config()
    config._stash = {"/a"}
    probe_record.hand_back(config, "_stash", "", sorted)
    assert list(tmp_path.iterdir()) == []


def test_a_run_that_watched_and_saw_nothing_writes_an_empty_list(tmp_path):
    """An empty list is a measured answer, and it has to reach the reader as one."""
    config = _Config()
    config._stash = set()
    probe_record.hand_back(config, "_stash", str(tmp_path / "out.json"), sorted)
    assert json.loads((tmp_path / "out.json").read_text()) == []


def test_the_record_is_prepared_the_way_its_own_probe_asks(tmp_path):
    """One probe keeps a set of paths and wants them sorted, so two runs over one suite give
    the same file and a comparison between them reports no changes nobody made. The other
    keeps a list of calls already in the order they happened."""
    config = _Config()
    config._stash = {"/z", "/a"}
    probe_record.hand_back(config, "_stash", str(tmp_path / "out.json"), sorted)
    assert json.loads((tmp_path / "out.json").read_text()) == ["/a", "/z"]


def test_a_record_that_is_already_in_order_is_written_as_it_stands(tmp_path):
    config = _Config()
    config._stash = [{"function": "f"}, {"function": "g"}]
    probe_record.hand_back(config, "_stash", str(tmp_path / "out.json"), list)
    assert json.loads((tmp_path / "out.json").read_text()) == [
        {"function": "f"}, {"function": "g"}]


@pytest.mark.parametrize("plugin_name", ["unopened_files_plugin", "runtime_probe_plugin"])
def test_neither_plugin_keeps_a_copy_of_the_handoff(plugin_name):
    """The copy is how one defect came to sit in two files. Each plugin asks this once and
    holds no writing of its own."""
    import ast
    import importlib
    import inspect

    module = importlib.import_module(f"l1_analyzer.{plugin_name}")
    tree = ast.parse(inspect.getsource(module))
    writes = [node for node in ast.walk(tree)
              if isinstance(node, ast.Call) and ast.unparse(node.func) in ("open", "json.dump")]
    assert writes == [], f"{plugin_name} still writes its own record"
