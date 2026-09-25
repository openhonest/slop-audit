"""The audit runs somebody else's code, and it used to hand them the whole machine.

L1.19 measures the share of decisions a project's own suite reaches and L1.20 runs that suite
five times, in nine languages, by driving seventeen external programs. Every one of those runs
is a stranger's code on the auditor's machine.

Until 2026-09-25 both tools built the child's environment from the parent's and added to it,
so every API key, token and credential in the shell that started the audit was one
`os.environ` away from the code being audited. An auditor with a client's secrets loaded was
handing them to the next client's test suite, and nothing in the output said so.

These tests hold the allowlist from both ends: a name nobody allowed does not get through, and
the names a toolchain needs do. The second half is not a formality. An allowlist that strips
PATH runs nothing at all and reports it as the audited project's failure, which is a worse
answer than the leak.

The Rust port carries the same three tests against the same generated list.
"""

from __future__ import annotations

from l1_analyzer.environment import PASSED_THROUGH, child_environment, withheld

# A shell with the shape of a real one: a few names a toolchain needs, and a few that are
# nobody's business but ours.
A_MACHINE = {
    "PATH": "/usr/bin:/bin",
    "HOME": "/home/auditor",
    "ANTHROPIC_API_KEY": "not-a-real-key",
    "AWS_SECRET_ACCESS_KEY": "not-a-real-key",
    "GITHUB_TOKEN": "not-a-real-token",
    "NPM_CONFIG__AUTH": "not-a-real-token",
    "BUNDLE_GEMS__EXAMPLE__COM": "not-a-real-token",
}


def test_a_name_nobody_allowed_does_not_reach_the_audited_code():
    given = child_environment(A_MACHINE, {})
    leaked = sorted(name for name in given if "KEY" in name or "TOKEN" in name or "AUTH" in name)
    assert leaked == [], f"these reached the code being audited: {leaked}"


def test_the_names_a_toolchain_needs_do_reach_it():
    """An allowlist that strips PATH runs nothing at all and reports it as the audited
    project's failure, which is a worse answer than the leak it was closing."""
    given = child_environment(A_MACHINE, {})
    assert given["PATH"] == "/usr/bin:/bin"
    assert given["HOME"] == "/home/auditor"


def test_the_two_namespaces_that_look_like_infrastructure_are_not_allowed():
    """`NPM_CONFIG_*` and `BUNDLE_*` read as toolchain settings and are the two places a
    private registry's token is spelled. Allowing the namespace would have let exactly the
    secrets this exists to stop through the one door that looked safe."""
    assert not any(name.startswith(("NPM_CONFIG", "BUNDLE_")) for name in PASSED_THROUGH)


def test_the_callers_own_setting_wins():
    """The coverage harnesses name their report path and the Java one pins a JDK. A caller
    naming something the list withholds is choosing to hand it over for one run, which is a
    different act from every secret on the machine leaking by default."""
    given = child_environment(A_MACHINE, {"COVERAGE_FILE": "/tmp/x", "PATH": "/only/here"})
    assert given["COVERAGE_FILE"] == "/tmp/x"
    assert given["PATH"] == "/only/here"


def test_what_was_withheld_can_be_named_without_being_printed():
    """A run can say how much it kept back without printing what it kept back, and a person
    can check the list against their own shell rather than against the source."""
    names = withheld(A_MACHINE)
    assert "ANTHROPIC_API_KEY" in names
    assert "PATH" not in names


def test_nothing_in_the_list_looks_like_a_credential():
    """The list is read by people, and the next person to add a name has to be able to see at
    a glance that it carries none. A name with SECRET, TOKEN, PASSWORD or KEY in it does not
    belong, and the two proxy entries that do name a URL are the only near miss."""
    suspicious = sorted(name for name in PASSED_THROUGH
                        if any(word in name.upper()
                               for word in ("SECRET", "TOKEN", "PASSWORD", "CREDENTIAL"))
                        or name.upper().endswith("_KEY"))
    assert suspicious == [], f"these read as credentials: {suspicious}"
