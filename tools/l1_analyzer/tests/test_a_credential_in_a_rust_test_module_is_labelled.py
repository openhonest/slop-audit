"""A fixture credential in a Rust unit test was reported as being in production code (L1.14).

This scanner reports a credential wherever it sits, which is right: a credential committed to
a repository is committed. It then splits the count three ways, production, documentation and
tests, because a fixture key and a production key are not the same finding to an auditor. Both
halves of that split were decided on the PATH, and a Rust unit test lives inside the file it
tests, so there was no path to read.

The instrument caught itself. A twenty-character AWS key written as a fixture in the Rust
port's own secret_rules.rs raised this repository's L1.14 from three secrets to four, and the
fourth was reported as production. The workaround was to assemble the key from two pieces at
run time so no literal in the file matched, and it stood for a year. The scanner now reads the
test region, so the fixture says what it means.

NOT EXCLUDED, LABELLED, and the difference matters. Dropping the region here would stop
reporting a real credential that happens to be written inside a test, which is a thing that
happens and a thing an auditor needs told.
"""

from __future__ import annotations

import pathlib
import tempfile

from l1_analyzer import secret_scan
from l1_analyzer.boundary import boundary

# Written in pieces here for the same reason the port's fixture no longer has to be: this file
# IS in the test tree, so the path rule already covers it, and a key spelled out in a docstring
# above would be read by the scanner running over this repository.
_KEY = "AKIA" + "QWERTYUIOPASDFGH"

_CRATE = f'''pub fn sign(key: &str) -> String {{
    format!("signed:{{key}}")
}}

#[cfg(test)]
mod tests {{
    use super::*;

    #[test]
    fn it_signs() {{
        assert_eq!(sign("{_KEY}"), "signed:{_KEY}");
    }}
}}
'''

_IN_PRODUCTION = f'''pub fn sign() -> String {{
    format!("signed:{_KEY}")
}}
'''


@boundary
def _analyze(files: dict[str, str]) -> dict:
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        for name, body in files.items():
            (p / name).parent.mkdir(parents=True, exist_ok=True)
            (p / name).write_text(body)
        return secret_scan.analyze(p, "rust")


def test_a_key_inside_a_test_module_is_counted_and_called_a_test():
    r = _analyze({"src/sign.rs": _CRATE})
    assert r["counts"]["total"] == 1, r["details"]
    assert r["counts"]["in_tests"] == 1, r["details"]
    assert r["counts"]["in_production"] == 0, r["details"]


def test_the_same_key_outside_the_test_module_is_production():
    """The other half of the split, so a label that is always 'test' cannot pass."""
    r = _analyze({"src/sign.rs": _IN_PRODUCTION})
    assert r["counts"]["total"] == 1, r["details"]
    assert r["counts"]["in_tests"] == 0, r["details"]
    assert r["counts"]["in_production"] == 1, r["details"]
