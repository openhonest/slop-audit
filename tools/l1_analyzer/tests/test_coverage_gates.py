"""The deterministic retention gates, measured against the real shapes from the 176-module
turso sweep: the two findings that must survive (NOT type inference, the Debug typo) and the
false-positive classes that must not (mem::zeroed construction, a non-Linux cfg arm, a
completion-channel read). Each body below is a candidate the sweep actually retained. Pure
assertions, no mocks."""

from l1_analyzer import coverage_gates as g

# --- assertion message extraction ------------------------------------------

def test_assertion_message_is_the_last_string_even_when_the_condition_holds_strings():
    # candidate 05 (real NOT bug): the condition names Some("INTEGER"); the message is last.
    body = ('let result = infer_expression_primitive(&expr, None);\n'
            'assert!(result == Some("INTEGER"), "logical NOT must infer an INTEGER result");')
    assert g.assertion_message(body) == "logical NOT must infer an INTEGER result"


def test_assertion_message_none_when_the_test_carries_no_message():
    assert g.assertion_message("let result = f(); assert!(result);") is None


# --- panic parsing ---------------------------------------------------------

_SINGLE = ("running 1 test\ntest l1_coverage_proof::proof ... FAILED\n\nfailures:\n\n"
           "---- l1_coverage_proof::proof stdout ----\n"
           "thread 'l1_coverage_proof::proof' panicked at core/src/statement.rs:2010:9:\n"
           "logical NOT must infer an INTEGER result\n"
           "note: run with `RUST_BACKTRACE=1` ...\n")


def test_parse_panic_reads_location_and_message_from_a_single_run():
    p = g.parse_panic(_SINGLE, "proof")
    assert p is not None and p["message"] == "logical NOT must infer an INTEGER result"
    assert p["location"] == "core/src/statement.rs:2010:9"


def test_parse_panic_isolates_one_test_of_a_batch():
    out = ("failures:\n\n"
           "---- l1_coverage_proof::proof_0 stdout ----\n"
           "thread '..' panicked at core/src/buffer_pool.rs:88:9:\n"
           "assertion failed: arena_size >= MIN_ARENA\n"
           "---- l1_coverage_proof::proof_1 stdout ----\n"
           "thread '..' panicked at core/src/statement.rs:2010:9:\n"
           "logical NOT must infer an INTEGER result\n")
    assert g.parse_panic(out, "proof_0")["message"] == "assertion failed: arena_size >= MIN_ARENA"
    assert g.parse_panic(out, "proof_1")["message"] == "logical NOT must infer an INTEGER result"


def test_parse_panic_none_when_the_proof_did_not_panic():
    assert g.parse_panic("test l1_coverage_proof::proof ... ok\n", "proof") is None


# --- attribution: the assertion fired vs an incidental panic ---------------

def test_attribution_assertion_when_the_panic_is_the_tests_own_message():
    panic = {"location": "src/statement.rs:2010:9", "message": "logical NOT must infer an INTEGER result"}
    assert g.attribution("logical NOT must infer an INTEGER result", panic) == "assertion"


def test_attribution_incidental_when_a_constructor_panics_with_its_own_message():
    # candidate 07: BufferPool::new panics below its arena minimum, a different message.
    panic = {"location": "src/buffer_pool.rs:88:9", "message": "assertion failed: arena_size >= MIN_ARENA"}
    assert g.attribution("finalizing with a valid page size should succeed", panic) == "incidental"


def test_attribution_incidental_when_there_is_no_message_block():
    assert g.attribution("some assertion", None) == "incidental"


# --- invalid fixture markers + the permutation check -----------------------

def test_invalid_fixture_flags_mem_zeroed_and_null_pointers():
    # candidate 01: register_vtab_module fed a zeroed module and null pointers.
    body = ("let ctx = std::ptr::null_mut();\nlet module: VTabModuleImpl = unsafe { std::mem::zeroed() };\n"
            "let result = unsafe { register_vtab_module(ctx, name, module, kind) };")
    assert g.invalid_fixture_marker(body) in ("mem::zeroed", "null_mut")


def test_invalid_fixture_none_for_a_normally_constructed_test():
    # candidate 05 builds its Expr through real constructors: no fabricated-invalid marker.
    body = "let expr = Expr::Unary(UnaryOperator::Not, Box::new(inner));\nlet result = infer(&expr, None);"
    assert g.invalid_fixture_marker(body) is None


def test_permute_scalar_raises_a_bitmap_count_to_a_valid_one():
    # candidate 09/10: AtomicSlotBitmap::new(1) and new(0) violate the multiple-of-64 count.
    assert "AtomicSlotBitmap::new(64)" in g.permute_scalar_construction("let s = AtomicSlotBitmap::new(1);")
    assert "AtomicSlotBitmap::new(64)" in g.permute_scalar_construction("let s = AtomicSlotBitmap::new(0);")


def test_permute_scalar_none_when_there_is_no_literal():
    assert g.permute_scalar_construction("let s = Pool::new(cfg);") is None


# --- host cfg exclusion ----------------------------------------------------

_LINUX = g.host_cfg_atoms('debug_assertions\ntarget_arch="x86_64"\ntarget_os="linux"\n'
                          'target_family="unix"\nunix\ntarget_pointer_width="64"\n')
_MAC = g.host_cfg_atoms('target_arch="aarch64"\ntarget_os="macos"\ntarget_family="unix"\nunix\n')


def test_cfg_excludes_the_non_linux_arm_on_a_linux_host():
    # candidate 03/04: the LinuxOfd arm sits under #[cfg(not(target_os = "linux"))].
    assert g.cfg_excluded('not(target_os = "linux")', _LINUX) is True


def test_cfg_keeps_the_same_arm_live_on_a_non_linux_host():
    assert g.cfg_excluded('not(target_os = "linux")', _MAC) is False


def test_cfg_excludes_a_foreign_target_os_by_exhaustive_key():
    assert g.cfg_excluded('target_os = "windows"', _LINUX) is True
    assert g.cfg_excluded("windows", _LINUX) is True


def test_cfg_never_excludes_an_unknown_feature_flag():
    # an unknown key could be set; a gap must never be hidden on a guess.
    assert g.cfg_excluded('feature = "serde"', _LINUX) is False
    assert g.cfg_excluded('all(unix, feature = "serde")', _LINUX) is False


def test_cfg_any_and_all_combine_three_valued():
    assert g.cfg_excluded('any(target_os = "windows", target_os = "redox")', _LINUX) is True
    assert g.cfg_excluded('all(unix, not(target_os = "linux"))', _LINUX) is True
    assert g.cfg_excluded('any(unix, feature = "x")', _LINUX) is False   # unix is true -> live


# --- deferred channel ------------------------------------------------------

def test_deferred_return_detects_a_completion_handle():
    # candidate 11: read_page returns Result<Completion>; the short read arrives by callback.
    assert g.is_deferred_return("Result<Completion>") is True
    assert g.is_deferred_return("Result<bool>") is False
    assert g.is_deferred_return("Option<&'static str>") is False


# --- the combined verdict on each real candidate ---------------------------

def _panic(msg: str) -> dict:
    return {"location": "src/x.rs:1:1", "message": msg}


def test_verdict_retains_the_real_not_type_bug_as_a_divergence():
    body = ('let result = infer_expression_primitive(&expr, None);\n'
            'assert!(result == Some("INTEGER"), "logical NOT must infer INTEGER");')
    assert g.classify_failure(body, "Option<&'static str>", _panic("logical NOT must infer INTEGER")) == "divergence"


def test_verdict_retains_the_real_debug_typo_as_a_divergence():
    body = ('let result = format!("{handler:?}");\n'
            'assert!(result == "BusyHandler::Timeout(1s)", "the debug repr must close its paren");')
    assert g.classify_failure(body, "std::fmt::Result", _panic("the debug repr must close its paren")) == "divergence"


def test_verdict_drops_the_mem_zeroed_construction_as_invalid_fixture():
    body = ("let module: VTabModuleImpl = unsafe { std::mem::zeroed() };\n"
            "let result = unsafe { register_vtab_module(ctx, name, module, kind) };\n"
            'assert!(matches!(result, ResultCode::Error), "must reject null pointers");')
    # the process aborts / a library assert fires: not the test's own message.
    assert g.classify_failure(body, "ResultCode", _panic("assertion failed: !ptr.is_null()")) == "invalid_fixture"


def test_verdict_holds_a_constructor_panic_for_review_not_as_a_bug():
    # candidate 07: BufferPool::new panics; no zeroed/null marker, so it is an incidental panic.
    body = ("let pool = BufferPool::new(BufferPool::DEFAULT_PAGE_SIZE * 10);\n"
            "let result = pool.finalize_with_page_size(page_size);\n"
            'assert!(result.is_ok(), "finalizing with a valid page size should succeed");')
    assert g.classify_failure(body, "Result<()>", _panic("assertion failed: arena_size >= MIN_ARENA")) == "incidental_panic"


def test_verdict_drops_the_completion_read_as_wrong_channel():
    body = ("let result = subjournal.read_page(0, buffer, page, page_size);\n"
            'assert!(result.is_err(), "reading a full page from an empty subjournal must short-read");')
    # the assertion DID fire (is_err on the returned handle), but the channel is wrong.
    msg = "reading a full page from an empty subjournal must short-read"
    assert g.classify_failure(body, "Result<Completion>", _panic(msg)) == "wrong_channel"
