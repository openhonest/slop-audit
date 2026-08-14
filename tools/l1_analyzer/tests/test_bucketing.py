"""Scope bucketing + mandatory disclosure.

The meter scopes out files that are not the library under audit (docs, conventional
tooling, and loose entry-point scripts sitting beside packages) and LISTS exactly
what it skipped. The disclosure is the cone of light on the meter's own choice of
scope: over-bucketing a real entry point must be visible and challengeable, never a
silent skip. A flat, script-only repo keeps its root scripts, because there they are
the code. Pure assertions, no mocks.
"""

from pathlib import Path

from l1_analyzer import state_bounds
from l1_analyzer.indicators import _bucket_reason, _repo_has_packages


def _mkrepo(tmp_path, files):
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return tmp_path


def test_root_scripts_docs_tooling_are_bucketed_and_disclosed(tmp_path):
    repo = _mkrepo(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/mod.py": (
            "class C:\n"
            "    def __init__(self):\n"
            "        self.cache = {}\n"
            "    def get(self, k):\n"
            "        if k in self.cache:\n"
            "            return self.cache[k]\n"
            "        return None\n"
        ),
        "main.py": "x = {}\ndef run(k):\n    return k in x\n",        # loose root script beside a package
        "docs/conf.py": "project = 'x'\nextensions = []\n",
        "setup.py": "from setuptools import setup\nsetup()\n",
    })
    r = state_bounds.classify(repo, "python")
    reasons = {b["path"]: b["reason"] for b in r["bucketed"]["paths"]}
    assert reasons.get("main.py") == "root-script"
    assert reasons.get("docs/conf.py") == "docs"
    assert reasons.get("setup.py") == "tooling"
    # the package module IS analyzed: its unbounded-key cache is flagged
    assert any(f["file"] == "pkg/mod.py" and f["verdict"] == "promiscuous" for f in r["findings"])
    # the loose script's state was NOT counted
    assert not any(f["file"] == "main.py" for f in r["findings"])


def test_flat_script_only_repo_keeps_its_root_scripts(tmp_path):
    # No packages anywhere: root .py are the code, not tooling. No root-script bucket.
    repo = _mkrepo(tmp_path, {
        "app.py": "cache = {}\ndef get(k):\n    return k in cache\n",
    })
    assert _repo_has_packages(repo) is False
    r = state_bounds.classify(repo, "python")
    assert not any(b["reason"] == "root-script" for b in r["bucketed"]["paths"])
    assert any(f["file"] == "app.py" for f in r["findings"])   # app.py IS analyzed


def test_dotted_csharp_test_project_is_scoped_out():
    """C# convention is a project directory named `<Project>.Tests`, which an exact
    component match never catches. Every C# repository's test tree was therefore measured
    as production code by L1.15, L1.17, L1.19 and the absolute-path check. A component is
    a test directory when, lowercased, it equals "tests"/"test" or ends ".tests"/".test"."""
    repo = Path("/r")
    extra = ("tests", "test")
    assert _bucket_reason(repo / "Src/Newtonsoft.Json.Tests/Schema/T.cs", repo, False, extra) == "tests"
    assert _bucket_reason(repo / "Src/Newtonsoft.Json.Test/Legacy.cs", repo, False, extra) == "test"
    assert _bucket_reason(repo / "Src/Tests/T.cs", repo, False, extra) == "tests"          # capitalised
    assert _bucket_reason(repo / "Src/tests/t.py", repo, False, extra) == "tests"          # unchanged
    # Production code keeps its scope: the marker must be the whole component after the dot.
    assert _bucket_reason(repo / "Src/Newtonsoft.Json/Serializer.cs", repo, False, extra) is None
    assert _bucket_reason(repo / "Src/Contests/Entry.cs", repo, False, extra) is None
    assert _bucket_reason(repo / "Src/Latest/Entry.cs", repo, False, extra) is None
