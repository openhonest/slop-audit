"""Behavioural spec for the interleaving-robustness meter (concurrency anti-coverage),
wired to the REAL interleaving_robustness module. Steps build tiny Rust repos on disk
and run the meter, or exercise the pure classifier directly.

Every scenario names the language it is about in its own Given. The meter is never
called with an assumed default, so a scenario that forgets to state its language fails
instead of quietly being measured as Rust.
"""

from pathlib import Path
from typing import TypedDict

from l1_analyzer import interleaving_robustness
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/interleaving_robustness.feature")

# A struct with a hand-asserted Sync: the exposed surface the meter cares about.
_SURFACE = (
    "struct Coord { p: *mut u8 }\n"
    "unsafe impl Sync for Coord {}\n"
)


class Tree(TypedDict):
    """The repository a scenario builds, and the language it is written in."""
    repo: Path
    lang: str


@given("a Rust file that hand-asserts Sync on a shared struct", target_fixture="tree")
def given_surface(tmp_path) -> Tree:
    (tmp_path / "coord.rs").write_text(_SURFACE)
    return {"repo": tmp_path, "lang": "rust"}


@given("no loom or shuttle model exists in the repository")
def given_no_model(tree):
    # State the precondition as a check on the repository just built, not as a comment.
    text = "".join(p.read_text() for p in tree["repo"].rglob("*.rs"))
    assert "loom" not in text and "shuttle" not in text


@given("that same file drives the struct under a loom model")
def given_model_in_file(tree):
    # Append a loom model to the same file that carries the surface.
    (tree["repo"] / "coord.rs").write_text(
        _SURFACE
        + "#[cfg(loom)]\n"
        "mod model {\n"
        "  #[test]\n"
        "  fn sync_holds() { loom::model(|| { let _c = super::Coord { p: std::ptr::null_mut() }; }); }\n"
        "}\n"
    )


@given("a Rust file with only an ordinary trait impl and safe atomics", target_fixture="tree")
def given_clean(tmp_path) -> Tree:
    (tmp_path / "ok.rs").write_text(
        "struct Bar { n: u64 }\n"
        "impl Clone for Bar { fn clone(&self) -> Bar { Bar { n: self.n } } }\n"
    )
    return {"repo": tmp_path, "lang": "rust"}


@given("a repository whose language the interleaving-robustness meter does not support", target_fixture="tree")
def given_unsupported(tmp_path) -> Tree:
    return {"repo": tmp_path, "lang": "java"}


@when("I run the interleaving-robustness meter", target_fixture="result")
def when_run(tree):
    return interleaving_robustness.analyze(tree["repo"], tree["lang"])


@then(parsers.parse("the verdict is {verdict}"))
def then_verdict(result, verdict):
    assert result["verdict"] == verdict


@then("that file is listed as unmodeled")
def then_unmodeled(result):
    assert any(f.endswith("coord.rs") for f in result["unmodeled"])


@then("that file is not listed as unmodeled")
def then_not_unmodeled(result):
    assert not any(f.endswith("coord.rs") for f in result["unmodeled"])


# --- pure classifier scenario ----------------------------------------------

@given(parsers.parse('flagged surface in "{path}"'), target_fixture="surface_files")
def given_flagged(path):
    return {path}


@given(
    parsers.parse('a model file that names the "{module}" module without clearly exercising it'),
    target_fixture="modeled_text",
)
def given_names_module(module):
    # A model that mentions the module by name but is not that file, and does not
    # exercise the racy interleaving: the weaker "modeled-elsewhere" signal.
    return f"use crate::storage::{module};\nloom::model(|| {{}});\n"


@when("I classify the surface against the models", target_fixture="split")
def when_classify(surface_files, modeled_text):
    return interleaving_robustness.classify(surface_files, set(), modeled_text)


@then(parsers.parse('"{path}" is modeled-elsewhere, not unmodeled'))
def then_elsewhere(split, path):
    assert path in split["modeled_elsewhere"]
    assert path not in split["unmodeled"]
