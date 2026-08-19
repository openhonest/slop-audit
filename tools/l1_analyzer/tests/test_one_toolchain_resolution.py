"""Each language resolves its toolchain once, not once per indicator.

L1.19 and L1.20 for Java both had to find Maven, pin a JDK and name it; L1.19 and L1.20
for JS/TS both had to find node, check node_modules and read package.json. Each pair
carried the preamble twice, so each pair could start refusing on different grounds: one
indicator could learn a new precondition and the other keep running without it, and the
panel would then report n/a for coverage and a number for determinism on a repo where
neither could be measured.

These count the call sites. The behaviour of the shared resolver is asserted beside them:
a repo with no toolchain yields a refusal and no half-resolved tools.
"""

import pathlib
import re

from l1_analyzer import java_trace, js_trace

_JAVA = pathlib.Path(java_trace.__file__).read_text()
_JS = pathlib.Path(js_trace.__file__).read_text()


def test_java_pins_its_jdk_in_one_place():
    sites = re.findall(r"^    env, prov = _pin_jdk\(", _JAVA, re.MULTILINE)
    assert len(sites) == 1, f"{len(sites)} JDK resolutions; the two indicators can drift apart"


def test_javascript_looks_for_node_in_one_place():
    sites = re.findall(r'^    if _node\(\) is None:', _JS, re.MULTILINE)
    assert len(sites) == 1, f"{len(sites)} node lookups; the two indicators can drift apart"


def test_java_refuses_a_repo_with_no_maven_project(tmp_path):
    """No pom.xml is not a Java repo, so the resolver refuses and hands back no tools."""
    refusal, tools = java_trace._toolchain(tmp_path, timeout_seconds=5)
    assert refusal is not None
    assert refusal["band"] == "n/a"
    assert tools is None


def test_javascript_refuses_a_repo_with_no_package_json(tmp_path):
    """A directory with no package.json cannot have a runner, whatever is on PATH."""
    refusal, pkg = js_trace._toolchain(tmp_path)
    assert refusal is not None
    assert refusal["band"] == "n/a"
    assert pkg is None
