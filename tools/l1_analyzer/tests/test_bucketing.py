"""Scope bucketing + mandatory disclosure.

The meter scopes out files that are not the library under audit (docs, conventional
tooling, and loose entry-point scripts sitting beside packages) and LISTS exactly
what it skipped. The disclosure is the cone of light on the meter's own choice of
scope: over-bucketing a real entry point must be visible and challengeable, never a
silent skip. A flat, script-only repo keeps its root scripts, because there they are
the code. Pure assertions, no mocks.
"""

from l1_analyzer import state_bounds
from l1_analyzer.indicators import _repo_has_packages


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


def test_scripts_and_seed_dirs_are_bucketed_and_disclosed(tmp_path):
    # A `scripts/` directory is the directory-level counterpart to a loose root
    # script: dev/ops/entry-point tooling, not the library under test. `seed/`
    # holds data-population scripts. Both are scoped out (and disclosed), while the
    # package module beside them is still analyzed.
    repo = _mkrepo(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/mod.py": (
            "class C:\n"
            "    def __init__(self):\n"
            "        self.cache = {}\n"
            "    def get(self, k):\n"
            "        return self.cache[k]\n"
        ),
        "scripts/nightly/monitor.py": (
            "class M:\n"
            "    def __init__(self):\n"
            "        self.metrics = []\n"
            "    def run(self):\n"
            "        return self.metrics[0]\n"
        ),
        "seed/seeder.py": "class S:\n    def __init__(self):\n        self.rows = {}\n    def go(self, k):\n        return self.rows[k]\n",
    })
    r = state_bounds.classify(repo, "python")
    reasons = {b["path"]: b["reason"] for b in r["bucketed"]["paths"]}
    assert reasons.get("scripts/nightly/monitor.py") == "scripts"
    assert reasons.get("seed/seeder.py") == "scripts"
    # tooling state is NOT counted...
    assert not any(f["file"].startswith("scripts/") or f["file"].startswith("seed/") for f in r["findings"])
    # ...but the package module beside them still is (not over-scoped).
    assert any(f["file"] == "pkg/mod.py" for f in r["findings"])


def test_flat_script_only_repo_keeps_its_root_scripts(tmp_path):
    # No packages anywhere: root .py are the code, not tooling. No root-script bucket.
    repo = _mkrepo(tmp_path, {
        "app.py": "cache = {}\ndef get(k):\n    return k in cache\n",
    })
    assert _repo_has_packages(repo) is False
    r = state_bounds.classify(repo, "python")
    assert not any(b["reason"] == "root-script" for b in r["bucketed"]["paths"])
    assert any(f["file"] == "app.py" for f in r["findings"])   # app.py IS analyzed
