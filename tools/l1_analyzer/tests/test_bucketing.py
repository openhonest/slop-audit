"""Scope bucketing + mandatory disclosure.

The meter scopes out files that are not the library under audit (docs, conventional
tooling, and loose entry-point scripts sitting beside packages) and LISTS exactly
what it skipped. The disclosure is the cone of light on the meter's own choice of
scope: over-bucketing a real entry point must be visible and challengeable, never a
silent skip. A flat, script-only repo keeps its root scripts, because there they are
the code. Pure assertions, no mocks.
"""


from l1_analyzer import indicators, scope, state_bounds
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


def test_dotted_csharp_test_project_is_scoped_out(tmp_path):
    """C# convention is a project directory named `<Project>.Tests`, which an exact
    component match never catches. A component is a test directory when, lowercased, it
    equals "tests"/"test" or ends ".tests"/".test" AND its contents corroborate the claim."""
    (tmp_path / "Src/Newtonsoft.Json.Tests/Schema").mkdir(parents=True)
    (tmp_path / "Src/Newtonsoft.Json.Tests/Schema/T.cs").write_text("using Xunit;\n[Fact] void A(){}\n")
    (tmp_path / "Src/Newtonsoft.Json").mkdir(parents=True)
    (tmp_path / "Src/Newtonsoft.Json/Serializer.cs").write_text("class Serializer {}\n")

    assert _bucket_reason(tmp_path / "Src/Newtonsoft.Json.Tests/Schema/T.cs", tmp_path, False, scope.PRODUCTION) == "tests"
    # Production code keeps its scope: the marker must be the whole component after the dot.
    assert _bucket_reason(tmp_path / "Src/Newtonsoft.Json/Serializer.cs", tmp_path, False, scope.PRODUCTION) is None


def test_a_renamed_production_directory_is_still_measured(tmp_path):
    """The aperture-capture vector, closed. Renaming a production package to `Core.Tests`
    used to remove it from every indicator declared under a test-excluding scope (the list
    is scope.SCOPES, and tests/test_scope_policy.py measures it), and flipped `--gate` from
    fail to pass, with zero bytes of code changed. A directory named like a test directory
    is now believed only if its contents corroborate the claim, so a bare rename buys
    nothing."""
    (tmp_path / "Core.Tests").mkdir()
    (tmp_path / "Core.Tests/app.py").write_text("from typing import Any\nCACHE = {}\ndef f(x: Any): return x\n")

    assert _bucket_reason(tmp_path / "Core.Tests/app.py", tmp_path, False, scope.PRODUCTION) is None


def test_corroboration_cannot_be_satisfied_by_the_directory_name_itself(tmp_path):
    """The first attempt at this fix corroborated with _is_test_file, which believes a
    path component, so every file under Core.Tests corroborated Core.Tests and the hole
    stayed open. Corroboration reads file NAMES and file CONTENT only."""
    (tmp_path / "Core.Tests").mkdir()
    (tmp_path / "Core.Tests/plain.py").write_text("x = 1\n")
    assert _bucket_reason(tmp_path / "Core.Tests/plain.py", tmp_path, False, scope.PRODUCTION) is None

    # A test-framework import corroborates it; so would a test-shaped file name.
    (tmp_path / "Real.Tests").mkdir()
    (tmp_path / "Real.Tests/suite.py").write_text("import pytest\ndef check(): pass\n")
    assert _bucket_reason(tmp_path / "Real.Tests/suite.py", tmp_path, False, scope.PRODUCTION) == "tests"

    (tmp_path / "Named.Tests").mkdir()
    (tmp_path / "Named.Tests/test_thing.py").write_text("def test_thing(): pass\n")
    assert _bucket_reason(tmp_path / "Named.Tests/test_thing.py", tmp_path, False, scope.PRODUCTION) == "tests"


# --- nested checkouts are a different repository ----------------------------

def test_a_nested_checkout_is_not_measured(tmp_path):
    """A directory below the root carrying its own .git is a submodule working copy, a
    vendored clone or a git worktree. Its code is not in this commit, and measuring it
    reports another repository's numbers as this one's. The tool caught this on itself:
    an agent worktree under .claude/worktrees/ held an older checkout and the gate
    charged eleven type escapes that existed only there."""
    (tmp_path / ".git").mkdir()
    (tmp_path / "mine.py").write_text("x = 1\n")

    nested = tmp_path / "vendored-clone"
    nested.mkdir()
    (nested / ".git").mkdir()
    (nested / "theirs.py").write_text("y = 2\n")

    found = {p.name for p in indicators._rglob_files(tmp_path, "*.py")}
    assert found == {"mine.py"}


def test_a_worktree_dot_git_file_is_recognised_too(tmp_path):
    """A git worktree carries .git as a FILE, not a directory, so the test is existence
    rather than is_dir. This is the exact shape that produced the false reading."""
    (tmp_path / ".git").mkdir()
    (tmp_path / "mine.py").write_text("x = 1\n")

    worktree = tmp_path / "agent-worktree"
    (worktree / "pkg").mkdir(parents=True)
    (worktree / ".git").write_text("gitdir: /somewhere/else\n")
    (worktree / "pkg" / "theirs.py").write_text("y = 2\n")

    found = {p.name for p in indicators._rglob_files(tmp_path, "*.py")}
    assert found == {"mine.py"}


def test_the_root_repository_is_still_measured(tmp_path):
    """The root's own .git must not prune the whole scan."""
    (tmp_path / ".git").mkdir()
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("x = 1\n")
    (tmp_path / "b.py").write_text("y = 2\n")

    found = {p.name for p in indicators._rglob_files(tmp_path, "*.py")}
    assert found == {"a.py", "b.py"}
