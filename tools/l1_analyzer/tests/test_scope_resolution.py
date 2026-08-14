"""Symbol identity is a binding, not a spelling.

Two defects with one root, both found by an external adopter on a production FastAPI
codebase rather than by the corpus.

  Import capture   `from app.auth import X` made the package name `app` a reference to
                   the module variable `app`, because the text matched.
  Scope collapse   a function parameter named `app` decided the verdict of a
                   module-level variable named `app`, for the same reason. Renaming the
                   parameter, and changing nothing else, flipped the file's verdict.

These tests are written before the fix and fail against it.
"""

from pathlib import Path

from l1_analyzer import state_bounds


def _classify(tmp_path: Path, source: str) -> dict:
    (tmp_path / "main.py").write_text(source)
    return state_bounds.classify(tmp_path, "python")


# --- import capture ---------------------------------------------------------

def test_a_package_name_in_an_import_is_not_a_reference_to_the_variable(tmp_path):
    """`app` in `from app.auth import X` is part of a module path. It binds nothing and
    it is not the variable `app` defined below it."""
    result = _classify(tmp_path, (
        "from app.auth.middleware import AuthMiddleware\n"
        "\n"
        "app = {}\n"
        "\n"
        "def register(key, value):\n"
        "    app[key] = value\n"
    ))
    findings = {f["state"]: f for f in result["findings"]}
    assert "app" in findings
    # The import sits on line 1; the binding is on line 3. With the import counted as a
    # reference the finding cannot be attributed correctly.
    assert findings["app"]["line"] == 3


def test_an_import_only_name_produces_no_state_at_all(tmp_path):
    """A name that appears ONLY inside an import is not state under any verdict."""
    result = _classify(tmp_path, (
        "from telemetry.client import emit\n"
        "\n"
        "counter = 0\n"
        "\n"
        "def bump():\n"
        "    global counter\n"
        "    counter += 1\n"
        "    emit(counter)\n"
    ))
    assert "telemetry" not in {f["state"] for f in result["findings"]}


# --- scope collapse ---------------------------------------------------------

_LIFESPAN = (
    "from fastapi import FastAPI\n"
    "\n"
    "async def lifespan({param}: FastAPI):\n"
    "    await {param}.state.scheduler.start({param})\n"
    "\n"
    "app = FastAPI(lifespan=lifespan)\n"
    "app.add_middleware(object)\n"
    "app.include_router(object)\n"
)


def test_a_parameter_does_not_decide_a_module_variables_verdict(tmp_path):
    """The ablation that isolated the defect. The module-level `app` is used only in ways
    that classify neutral; the PARAMETER is what fails closed. Renaming the parameter must
    not change the module variable's verdict, because they are different objects."""
    shadowed = _classify(tmp_path, _LIFESPAN.format(param="app"))
    (tmp_path / "main.py").unlink()
    distinct = _classify(tmp_path, _LIFESPAN.format(param="application"))
    assert shadowed["counts"] == distinct["counts"]


def test_the_module_variable_is_neutral_in_both_spellings(tmp_path):
    """Stated positively, so the test says what is true rather than only what is equal."""
    for name in ("app", "application"):
        (tmp_path / "main.py").write_text(_LIFESPAN.format(param=name))
        result = state_bounds.classify(tmp_path, "python")
        verdicts = {f["state"]: f["verdict"] for f in result["findings"]}
        assert verdicts.get("app") == "neutral", f"parameter spelled {name}: {verdicts}"


def test_a_genuinely_promiscuous_module_variable_is_still_caught(tmp_path):
    """The guard, and it must pass BEFORE the fix as well as after, because its job is to
    prove the scoping does not blunt the indicator.

    The first fixture written for this test asserted the wrong thing: a dict written by
    key and read back by key is cleared to neutral by the memoization filter, correctly.
    This shape is verified promiscuous against the current classifier, so the guard is
    anchored to real behaviour rather than to an assumption about it."""
    result = _classify(tmp_path, (
        "registry = []\n"
        "\n"
        "def add(item):\n"
        "    registry.append(item)\n"
        "\n"
        "def route(item):\n"
        "    if item in registry:\n"
        "        return \"known\"\n"
        "    return \"new\"\n"
    ))
    verdicts = {f["state"]: f["verdict"] for f in result["findings"]}
    assert verdicts.get("registry") == "promiscuous"
