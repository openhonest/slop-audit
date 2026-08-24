"""Clause 4 in the race harness: two decisions that needed a Rust toolchain to exercise.

`_rust_toolchain_reason` ran `rustup toolchain list` and then decided from its output
whether a nightly is installed. `_host_target` ran `rustc -vV` and then found the host
triple in what came back. Both mixed the running with the reading, so neither could be
checked on a machine without Rust, which is most machines that run this suite.

The strings are what these functions actually decide, and they are the half worth testing:
the output of one tool, read for one fact.
"""

import pathlib

from l1_analyzer import race_harness

_RUSTUP_LIST = (
    "stable-aarch64-apple-darwin (default)\n"
    "nightly-aarch64-apple-darwin\n"
)


def test_a_toolchain_list_naming_a_nightly_gives_no_reason_to_refuse():
    assert race_harness.toolchain_reason_in(_RUSTUP_LIST) is None


def test_a_toolchain_list_with_no_nightly_says_what_is_missing():
    reason = race_harness.toolchain_reason_in("stable-aarch64-apple-darwin (default)\n")
    assert reason and "nightly" in reason


def test_the_host_triple_is_found_in_the_compiler_banner():
    banner = ("rustc 1.83.0 (90b35a623 2026-11-26)\n"
              "binary: rustc\n"
              "host: aarch64-apple-darwin\n"
              "release: 1.83.0\n")
    assert race_harness.host_target_in(banner) == "aarch64-apple-darwin"


def test_a_banner_naming_no_host_yields_nothing():
    """The caller turns this into a refusal that names the cause, so it must not guess."""
    assert race_harness.host_target_in("rustc 1.83.0\n") is None


def test_both_deciders_run_nothing():
    source = pathlib.Path(race_harness.__file__).read_text()
    for name in ("toolchain_reason_in", "host_target_in"):
        body = source.split(f"def {name}")[1].split("\ndef ")[0]
        for reach in ("subprocess", "Popen", "which(", "read_text"):
            assert reach not in body, (name, reach)
