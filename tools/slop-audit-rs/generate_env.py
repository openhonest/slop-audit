"""Generate src/runtime/environment.rs from the Python reference's allowlist.

The third generated table, and it exists for the same reason as the other two. What a
stranger's test suite sees of the machine running the audit is one fact. Two tools that ran a
suite in two different environments would disagree about that suite's result, and neither
would be wrong, so the list has one owner and the port reads a copy nobody typed.

    uv run generate_env.py            # write src/runtime/environment.rs
    uv run generate_env.py --check    # exit 1 if the committed file is stale

The rendering helper comes from generate_lang_spec, which already had it.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from generate_lang_spec import rust_str
from parity_harness import boundary

HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent / "l1_analyzer"
TARGET = HERE / "src" / "runtime" / "environment.rs"

READER = """
import json
from l1_analyzer.environment import PASSED_THROUGH
print(json.dumps(list(PASSED_THROUGH)))
"""

HEADER = '''//! What a stranger's test suite is allowed to see of the machine running the audit.
//!
//! GENERATED from l1_analyzer.environment by generate_env.py. Do not edit: the list has one
//! owner, because two tools that ran a suite in two different environments would disagree
//! about that suite's result and neither would be wrong.
//!
//! The audit executes the audited project's own code. Until 2026-09-25 the child inherited
//! the auditor's whole environment, so every API key on the machine running the audit was
//! readable by the code being audited. An allowlist rather than a denylist, because a
//! denylist is a guess at the names secrets have and every new tool invents another one.
//!
//! It is not a sandbox. The suite still reads and writes the filesystem as the auditor's
//! user and still opens sockets. This closes the widest door, for all nine languages at once.

/// The names that pass through, exactly as spelled. The reference explains what needs each.
pub const PASSED_THROUGH: &[&str] = &[
'''

FOOTER = '''];

/// The environment one untrusted run gets: the allowed names, then the caller's own.
///
/// `extra` wins, and it is the caller's deliberate word: the coverage harnesses set their
/// report path and the Java one pins a JDK. A caller naming something the list withholds is
/// choosing to hand it over for this one run, which is a different act from every secret on
/// the machine leaking by default.
pub fn child_environment(extra: &[(String, String)]) -> Vec<(String, String)> {
    let mut passed: Vec<(String, String)> = PASSED_THROUGH
        .iter()
        .filter_map(|name| std::env::var(name).ok().map(|value| (name.to_string(), value)))
        .collect();
    for (key, value) in extra {
        passed.retain(|(name, _)| name != key);
        passed.push((key.clone(), value.clone()));
    }
    passed
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The defect this exists for, stated as the thing that must not happen.
    #[test]
    fn a_name_nobody_allowed_does_not_reach_the_child() {
        // SAFETY: a test-only variable this process owns, read back on the next line.
        std::env::set_var("SLOP_AUDIT_TEST_FAKE_TOKEN", "not-a-real-secret");
        let given = child_environment(&[]);
        assert!(!given.iter().any(|(name, _)| name == "SLOP_AUDIT_TEST_FAKE_TOKEN"),
                "a name outside the list reached the audited code");
        std::env::remove_var("SLOP_AUDIT_TEST_FAKE_TOKEN");
    }

    /// Without PATH nothing runs at all, and a suite that cannot start reads as a project
    /// whose tests fail rather than as an audit that broke its own harness.
    #[test]
    fn the_names_a_toolchain_needs_do_reach_it() {
        let given = child_environment(&[]);
        assert!(given.iter().any(|(name, _)| name == "PATH"), "PATH was withheld");
    }

    /// The caller's own word wins, and it replaces rather than duplicates: a child handed one
    /// name twice takes whichever the runtime happens to prefer.
    #[test]
    fn the_callers_own_setting_wins_and_is_set_once() {
        let given = child_environment(&[("PATH".into(), "/only/here".into())]);
        let paths: Vec<&String> = given.iter()
            .filter(|(name, _)| name == "PATH").map(|(_, value)| value).collect();
        assert_eq!(paths, vec![&"/only/here".to_string()]);
    }
}
'''


def rendered(names: list[str]) -> str:
    """The Rust file, one name per line so a diff names the one that changed."""
    body = "".join(f"    {rust_str(name)},\n" for name in names)
    return HEADER + body + FOOTER


@boundary
def from_reference() -> list[str]:
    """The allowlist, asked of the reference rather than read from a file here."""
    out = subprocess.run(["uv", "run", "python", "-c", READER], cwd=REFERENCE,
                         capture_output=True, text=True, check=True).stdout
    import json
    return json.loads(out)


def main(argv: list[str]) -> int:
    want = rendered(from_reference())
    if "--check" in argv:
        have = TARGET.read_text() if TARGET.exists() else ""
        if have == want:
            print(f"{TARGET} matches the reference")
            return 0
        print(f"{TARGET} is STALE; run `uv run generate_env.py`")
        return 1
    TARGET.write_text(want)
    print(f"wrote {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
