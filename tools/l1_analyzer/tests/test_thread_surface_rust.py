"""Thread-safety surface meter, Rust conformance.

The meter does NOT detect data races (undecidable statically; that is a
ThreadSanitizer job). It measures the concurrency AUDIT SURFACE: every site where
Rust's compiler-enforced thread-safety guarantee is overridden by hand or absent.
A finding is a fact about the syntax ("here is surface to verify"), never a verdict
that a race exists.

Rust surface, first pass:
  EXPOSED  unsafe impl Send / unsafe impl Sync  - the Send/Sync guarantee is hand-asserted
  EXPOSED  static mut                            - global mutable state, no compiler guard
  REVIEW   Ordering::Relaxed                     - the atomics ordering footgun (no happens-before)

The motivating case is turso: `unsafe impl Sync for MappedSharedWalCoordination`
is the struct whose hand-asserted thread-safety turned out to be wrong under
free-threading. The meter cannot see the missing guard inside it, but it must put
that struct on the audit list.

Red first: thread_surface.scan(repo, "rust") does not exist until the module lands.
"""

import json

from l1_analyzer import cli, thread_surface


def _scan(tmp_path, src):
    (tmp_path / "case.rs").write_text(src)
    return thread_surface.scan(tmp_path, "rust")


def _find(result, kind, symbol):
    return next(
        (f for f in result.get("findings", []) if f["kind"] == kind and f["symbol"] == symbol),
        None,
    )


def test_unsafe_impl_sync_is_exposed(tmp_path):
    # The turso-shaped case: a struct whose Sync is asserted by hand.
    result = _scan(
        tmp_path,
        "struct MappedSharedWalCoordination { p: *mut u8 }\n"
        "unsafe impl Send for MappedSharedWalCoordination {}\n"
        "unsafe impl Sync for MappedSharedWalCoordination {}\n",
    )
    send = _find(result, "unsafe_impl_send", "MappedSharedWalCoordination")
    sync = _find(result, "unsafe_impl_sync", "MappedSharedWalCoordination")
    assert send is not None, "unsafe impl Send not surfaced"
    assert sync is not None, "unsafe impl Sync not surfaced"
    assert send["severity"] == "exposed"
    assert sync["severity"] == "exposed"
    assert sync["line"] == 3
    assert result["verdict"] == "exposed"


def test_static_mut_is_exposed(tmp_path):
    result = _scan(
        tmp_path,
        "static mut COUNT: i32 = 0;\n"
        "fn tick() { unsafe { COUNT += 1; } }\n",
    )
    f = _find(result, "static_mut", "COUNT")
    assert f is not None, "static mut not surfaced"
    assert f["severity"] == "exposed"
    assert result["verdict"] == "exposed"


def test_relaxed_ordering_is_review(tmp_path):
    result = _scan(
        tmp_path,
        "use std::sync::atomic::{AtomicU64, Ordering};\n"
        "fn bump(x: &AtomicU64) { x.store(1, Ordering::Relaxed); }\n",
    )
    f = _find(result, "relaxed_ordering", "Ordering::Relaxed")
    assert f is not None, "Ordering::Relaxed not surfaced"
    assert f["severity"] == "review"
    # A review-only repo is REVIEW, not EXPOSED.
    assert result["verdict"] == "review"


def test_ordinary_impl_and_safe_atomics_are_clean(tmp_path):
    # A normal trait impl, a plain (immutable) static, and a happens-before
    # ordering carry no hand-override of the thread-safety guarantee.
    result = _scan(
        tmp_path,
        "use std::sync::atomic::{AtomicU64, Ordering};\n"
        "struct Bar { n: u64 }\n"
        "impl Clone for Bar { fn clone(&self) -> Bar { Bar { n: self.n } } }\n"
        "static SAFE: i32 = 0;\n"
        "fn read(x: &AtomicU64) -> u64 { x.load(Ordering::Acquire) }\n",
    )
    assert result["findings"] == []
    assert result["verdict"] == "clean"


def test_exposed_dominates_review(tmp_path):
    result = _scan(
        tmp_path,
        "static mut G: i32 = 0;\n"
        "use std::sync::atomic::{AtomicU64, Ordering};\n"
        "fn bump(x: &AtomicU64) { x.store(1, Ordering::Relaxed); }\n",
    )
    assert result["counts"]["exposed"] == 1
    assert result["counts"]["review"] == 1
    assert result["verdict"] == "exposed"


def test_unknown_language_is_na(tmp_path):
    (tmp_path / "case.rs").write_text("static mut X: i32 = 0;\n")
    result = thread_surface.scan(tmp_path, "cobol")
    assert result["verdict"] == "n/a"
    assert result["findings"] == []


# --- CLI wiring -----------------------------------------------------------

def test_gate_ratchet_fails_when_overrides_exceed_baseline(tmp_path):
    (tmp_path / "case.rs").write_text(
        "struct Foo { p: *mut u8 }\n"
        "unsafe impl Sync for Foo {}\n"
    )
    # Baseline 0: the single hand-override must fail the gate.
    assert cli.main([str(tmp_path), "--lang", "rust", "--gate", "--max-thread-exposed", "0"]) == 1
    # Baseline 1: at the current count, the gate passes (no NEW override).
    assert cli.main([str(tmp_path), "--lang", "rust", "--gate", "--max-thread-exposed", "1"]) == 0


def test_gate_thread_ratchet_is_noop_without_flag(tmp_path):
    (tmp_path / "case.rs").write_text(
        "struct Foo { p: *mut u8 }\n"
        "unsafe impl Sync for Foo {}\n"
    )
    # No --max-thread-exposed: surface is reported by the analyzer, never gated by default.
    assert cli.main([str(tmp_path), "--lang", "rust", "--gate"]) == 0


def test_cli_json_includes_thread_surface(tmp_path, capsys):
    (tmp_path / "case.rs").write_text(
        "struct Foo { p: *mut u8 }\n"
        "unsafe impl Sync for Foo {}\n"
    )
    cli.main([str(tmp_path), "--lang", "rust", "--indicators", "17", "--format", "json"])
    envelope = json.loads(capsys.readouterr().out)
    ts = envelope["results"]["thread_surface"]
    assert ts["verdict"] == "exposed"
    assert ts["counts"]["exposed"] == 1
