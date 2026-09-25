"""What a stranger's test suite is allowed to see of the machine running the audit.

THE AUDIT EXECUTES THE AUDITED PROJECT'S OWN CODE. L1.19 measures the share of decisions the
project's suite reaches and L1.20 runs that suite five times, in nine languages, by driving
seventeen external programs. Every one of those runs is somebody else's code on our machine.

Until 2026-09-25 the child inherited the auditor's whole environment: both tools built it from
the parent's and added to it. Every API key, token and credential on the machine running the
audit was readable by the code being audited, by opening `os.environ` in a test. Nothing about
that was disclosed, and an auditor with a shell full of client secrets was handing them to the
next client's test suite.

AN ALLOWLIST RATHER THAN A DENYLIST, because a denylist is a guess at the names secrets have
and every new tool invents another one. What passes through is what a toolchain needs to find
itself: where its programs are, where its caches live, and how to reach a proxy or a
certificate store. Nothing here carries a credential.

WHAT THIS DOES NOT DO. It is not a sandbox. The suite still reads and writes the filesystem as
the auditor's user, still opens sockets, and still runs for as long as the timeout allows. The
honest sandbox for nine ecosystems is a container with the checkout mounted and one network
policy chosen deliberately; this closes the widest door while that is built, and it closes it
for all nine languages at once.

The Rust port reads the same two lists, generated from this file. One owner, because two tools
that ran a suite in two different environments would disagree about the suite's result and
neither would be wrong.
"""

from __future__ import annotations

from collections.abc import Mapping

# Names that pass through, exactly as spelled.
#
# Grouped by what needs them, because the next person to add one has to say which toolchain
# broke without it. Anything not named here does not reach the audited code.
PASSED_THROUGH: tuple[str, ...] = (
    # Every program on earth. Without PATH nothing runs at all.
    "PATH",
    # Where a toolchain keeps its caches and its downloaded packages: cargo, maven, npm,
    # bundler, nuget and rustup all resolve theirs under the home directory.
    "HOME", "USERPROFILE",
    # Scratch space. A test suite that cannot open a temporary file fails for a reason that
    # has nothing to do with the code under audit.
    "TMPDIR", "TMP", "TEMP",
    # Text encoding. A suite whose output is read back as text needs to agree with us about
    # what its bytes mean, and a missing locale turns accented output into a decode error.
    "LANG", "LC_ALL", "LC_CTYPE",
    # Who the process is. Some runners name the user in their output and some refuse without
    # one; neither is a credential.
    "USER", "LOGNAME",
    # Terminal shape. Absent, several runners pick a default width and their output wraps
    # differently between machines, which this instrument has already been bitten by once.
    "TERM", "COLUMNS",
    # Reaching the network at all, on a machine behind a proxy or with its own certificate
    # store. A proxy address is not a secret; a proxy PASSWORD would be, and is not here.
    "SSL_CERT_FILE", "SSL_CERT_DIR", "CURL_CA_BUNDLE", "REQUESTS_CA_BUNDLE",
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
    "http_proxy", "https_proxy", "no_proxy",
    # Where each toolchain lives, for the ones that cannot find themselves from PATH alone.
    "JAVA_HOME", "M2_HOME", "MAVEN_OPTS",
    "GOROOT", "GOPATH", "GOCACHE", "GOMODCACHE",
    "CARGO_HOME", "RUSTUP_HOME", "RUSTUP_TOOLCHAIN",
    "DOTNET_ROOT", "NUGET_PACKAGES",
    "GEM_HOME", "GEM_PATH",
    "VIRTUAL_ENV",
    # The LLVM coverage tools, which Rust coverage needs by name on a machine whose rustup
    # component is not installed. Both are paths to programs.
    "LLVM_COV", "LLVM_PROFDATA",
    # The version managers, which resolve which runtime a repository asked for. The whole
    # directory-insensitivity claim rests on these being reachable.
    "PYENV_ROOT", "RBENV_ROOT", "JENV_ROOT", "ASDF_DIR", "ASDF_DATA_DIR", "MISE_DATA_DIR",
    # Windows cannot start a process without these. A cross-built binary that stripped them
    # would run nothing at all and report it as the project's fault.
    "SYSTEMROOT", "SystemRoot", "COMSPEC", "ComSpec", "PATHEXT",
    "APPDATA", "LOCALAPPDATA", "ProgramData", "ProgramFiles", "ProgramFiles(x86)",
    "WINDIR", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
)

# There is no prefix list, and its absence is the decision rather than an omission.
#
# `NPM_CONFIG_*` and `BUNDLE_*` look like infrastructure and are the two places a private
# registry's token is spelled: `NPM_CONFIG__AUTH` and `BUNDLE_GEMS__EXAMPLE__COM` are both
# credentials wearing a toolchain's prefix. Allowing the namespace would have let exactly the
# secrets this exists to stop through the one door that looked safe. The harnesses do not
# install dependencies during an audit, so they do not need either.


def child_environment(parent: Mapping[str, str], extra: Mapping[str, str]) -> dict[str, str]:
    """The environment one untrusted run gets: the allowed names, then the caller's own.

    `extra` wins, and it is the caller's deliberate word: the coverage harnesses set
    COVERAGE_FILE and the Java one pins a JDK. A caller naming something the list withholds is
    choosing to hand it over for this one run, which is a different act from every secret on
    the machine leaking by default.

    Both arguments are required. A default parent would read the process environment from
    inside a function whose whole purpose is to decide what escapes it, and a default extra
    would let a caller that forgot to pass its own settings look like one that had none."""
    allowed = {name: parent[name] for name in PASSED_THROUGH if name in parent}
    return {**allowed, **extra}


def withheld(parent: Mapping[str, str]) -> list[str]:
    """The names this machine carries that an audited suite will not see.

    Read by nothing that decides anything. It exists so a run can say how much it withheld
    without printing what it withheld, and so a person can check the list against their own
    shell rather than against this file."""
    return sorted(name for name in parent if name not in PASSED_THROUGH)
