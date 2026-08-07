"""Behavioural spec for the schedule-silence meter (concurrency anti-coverage), wired
to the REAL schedule_silence module. Steps build tiny Rust repos on disk and run the
meter, or exercise the pure classifier directly. State threads through a `ctx` fixture.
"""

import pytest
from l1_analyzer import schedule_silence
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/schedule_silence.feature")

# A struct with a hand-asserted Sync: the exposed surface the meter cares about.
_SURFACE = (
    "struct Coord { p: *mut u8 }\n"
    "unsafe impl Sync for Coord {}\n"
)


@pytest.fixture
def ctx():
    return {}


@given("a Rust file that hand-asserts Sync on a shared struct")
def given_surface(ctx, tmp_path):
    (tmp_path / "coord.rs").write_text(_SURFACE)
    ctx["repo"] = tmp_path


@given("no loom or shuttle model exists in the repository")
def given_no_model(ctx):
    pass  # the repo built above has none


@given("that same file drives the struct under a loom model")
def given_model_in_file(ctx):
    # Append a loom model to the same file that carries the surface.
    (ctx["repo"] / "coord.rs").write_text(
        _SURFACE
        + "#[cfg(loom)]\n"
        "mod model {\n"
        "  #[test]\n"
        "  fn sync_holds() { loom::model(|| { let _c = super::Coord { p: std::ptr::null_mut() }; }); }\n"
        "}\n"
    )


@given("a Rust file with only an ordinary trait impl and safe atomics")
def given_clean(ctx, tmp_path):
    (tmp_path / "ok.rs").write_text(
        "struct Bar { n: u64 }\n"
        "impl Clone for Bar { fn clone(&self) -> Bar { Bar { n: self.n } } }\n"
    )
    ctx["repo"] = tmp_path


@given("a repository whose language the schedule-silence meter does not support")
def given_unsupported(ctx, tmp_path):
    ctx["repo"], ctx["lang"] = tmp_path, "java"


@when("I run the schedule-silence meter")
def when_run(ctx):
    ctx["result"] = schedule_silence.analyze(ctx["repo"], ctx.get("lang", "rust"))


@then(parsers.parse("the verdict is {verdict}"))
def then_verdict(ctx, verdict):
    assert ctx["result"]["verdict"] == verdict


@then("that file is listed as unmodeled")
def then_unmodeled(ctx):
    assert any(f.endswith("coord.rs") for f in ctx["result"]["unmodeled"])


@then("that file is not listed as unmodeled")
def then_not_unmodeled(ctx):
    assert not any(f.endswith("coord.rs") for f in ctx["result"]["unmodeled"])


# --- pure classifier scenario ----------------------------------------------

@given(parsers.parse('flagged surface in "{path}"'))
def given_flagged(ctx, path):
    ctx["surface_files"] = {path}


@given(parsers.parse('a model file that names the "{module}" module without clearly exercising it'))
def given_names_module(ctx, module):
    # A model that mentions the module by name but is not that file, and does not
    # exercise the racy interleaving: the weaker "modeled-elsewhere" signal.
    ctx["modeled_text"] = f"use crate::storage::{module};\nloom::model(|| {{}});\n"


@when("I classify the surface against the models")
def when_classify(ctx):
    ctx["split"] = schedule_silence.classify(ctx["surface_files"], set(), ctx["modeled_text"])


@then(parsers.parse('"{path}" is modeled-elsewhere, not unmodeled'))
def then_elsewhere(ctx, path):
    assert path in ctx["split"]["modeled_elsewhere"]
    assert path not in ctx["split"]["unmodeled"]
