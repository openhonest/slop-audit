"""A Jest repository is measured, not returned as null.

The module docstring has claimed Jest support since it was written, and nothing had ever
run this harness against a Jest project. A capability asserted and never verified is the
category this whole instrument exists to name, one level up: unmeasured is not clean, and
"we support Jest" with no run behind it is unmeasured.

The prompt for this was a sibling tool returning Coverage null and Silence null on a Jest
repository, because it binds to Vitest and node:test. That is not a JavaScript problem, it
is a runner-coupling problem, and the two tools differ in exactly one decision.

This one wraps the project's OWN test command in c8, which sets NODE_V8_COVERAGE. V8
honours that variable in child processes, so Jest's worker pool is covered without the
harness knowing Jest exists. A harness that instead drives a named runner has to be taught
each one, and returns nothing for the rest.

Determinism is the opposite case and worth keeping beside it: there the runner DOES matter,
because only a runner with a seed can be ordered. Jest has `--seed` from 30, Vitest has
`--sequence.shuffle`, and node:test still has no shuffle flag in Node 26 - so it is named
undrivable rather than measured as 0/5.

The fixture installs Jest, so this test is skipped when the registry is unreachable. It
says so rather than passing quietly.
"""

import json
import pathlib
import shutil
import subprocess

import pytest
from l1_analyzer import js_trace

PACKAGE = {
    "name": "fixture",
    "version": "0.0.0",
    "scripts": {"test": "jest"},
    "devDependencies": {"jest": "^30.0.0", "c8": "^10.1.3"},
}

SOURCE = (
    "function band(n) {\n"
    '  if (n > 10) return "high";\n'
    '  if (n > 5) return "mid";\n'
    '  return "low";\n'
    "}\n"
    "module.exports = { band };\n"
)

# Two of three arms reached, so 80% is the arithmetic of the fixture rather than whatever
# the harness happened to return.
TESTS = (
    'const { band } = require("../band");\n\n'
    'test("high", () => { expect(band(20)).toBe("high"); });\n'
    'test("low", () => { expect(band(1)).toBe("low"); });\n'
)


def _registry_reachable() -> bool:
    if shutil.which("npm") is None:
        return False
    probe = subprocess.run(["npm", "ping", "--loglevel=error"],
                           capture_output=True, timeout=120, check=False)
    return probe.returncode == 0


pytestmark = pytest.mark.skipif(
    not _registry_reachable(), reason="the npm registry is unreachable, so Jest cannot be installed")


@pytest.fixture(scope="module")
def jest_project(tmp_path_factory) -> pathlib.Path:
    root = tmp_path_factory.mktemp("jest")
    (root / "package.json").write_text(json.dumps(PACKAGE, indent=2) + "\n")
    (root / "band.js").write_text(SOURCE)
    (root / "__tests__").mkdir()
    (root / "__tests__" / "band.test.js").write_text(TESTS)
    install = subprocess.run(["npm", "install", "--silent", "--no-audit", "--no-fund"],
                             cwd=root, capture_output=True, text=True, timeout=900, check=False)
    if install.returncode != 0:
        pytest.skip(f"npm install failed: {install.stderr[-200:]}")
    return root


def test_coverage_is_a_number_rather_than_null(jest_project):
    """The claim, verified. Null here would be the failure the sibling tool hit."""
    result = js_trace.decision_space_coverage(jest_project, 900.0, runtime_override=None)
    assert result["band"] != "n/a", result["details"]
    assert isinstance(result["value"], (int, float))


def test_the_number_is_the_one_the_fixture_implies(jest_project):
    """Two of three arms are reached, so the harness has to say so. A figure that is merely
    non-null could still be measuring the wrong thing."""
    result = js_trace.decision_space_coverage(jest_project, 900.0, runtime_override=None)
    assert 60 <= float(result["value"]) <= 90, result["details"]


def test_the_worker_processes_are_covered(jest_project):
    """Why it works at all, asserted rather than assumed. Jest runs tests in a worker pool,
    so a harness that only watched the parent would report near-nothing. c8 sets
    NODE_V8_COVERAGE and V8 inherits it into children, which is what makes the runner
    irrelevant to coverage."""
    result = js_trace.decision_space_coverage(jest_project, 900.0, runtime_override=None)
    assert float(result["value"]) > 0, (
        "coverage came back at zero, which is what a parent-only collector reports when the "
        f"runner forks: {result['details']}"
    )


def test_determinism_drives_jest_by_its_seed(jest_project):
    """The opposite case, and the reason it is not a contradiction: only a runner with a
    seed can be ordered, so here the runner does matter and is named."""
    result = js_trace.test_determinism(jest_project, 3, 900.0, runtime_override=None)
    assert result["value"] == "3/3"
    assert result["band"] == "Healthy"
    assert "jest" in result["details"]


def test_node_test_is_named_undrivable_rather_than_scored(tmp_path):
    """node:test has no shuffle flag in Node 26, so 0/5 would read as a suite that falls
    over when reordered rather than one that was never reordered. Checked against the real
    node on this machine rather than taken from the table."""
    assert "node --test" in js_trace._UNDRIVABLE
    flags = subprocess.run(["node", "--help"], capture_output=True, text=True, check=False).stdout
    assert "--test-shuffle" not in flags, (
        "node grew a shuffle flag, so the undrivable classification is now stale and this "
        "runner can be measured"
    )
