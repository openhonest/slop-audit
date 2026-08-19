"""Coverage-gap prove loop for Python - the pytest counterpart to coverage_prove (Rust).

Same discipline: the structure is deterministic, the model only fills an already-located gap,
and EXECUTION decides. The gap is an uncovered decision branch:

  locate   python_facets over the module + coverage.py's per-file missing lines
  propose  a model writes one calling test: import, build the inputs, call, assert a property
  render   a pytest test function that imports the module under test
  run      via the TARGET's own interpreter (dir-agnostic, so imports and deps resolve)
  repair   (optional, on by default) when the test errors on setup, feed the error back and
           let the model rewrite the arrange step
  retain   iff the test FAILS ON ITS OWN ASSERTION (an AssertionError) - the uncovered branch
           is also a bug. A test that errors on setup (ImportError, TypeError building args) is
           the tool's own noise, reported separately, never dressed up as a proven bug.

slop-audit proves the gap; it never writes into the user's test file. Opt-in and CLI-only (it
runs code): needs ANTHROPIC_API_KEY and the target's pytest environment.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from l1_analyzer import pytest_trace, python_facets
from l1_analyzer.coverage_prove import (
    CoverageProof,
    _call_model,
    _valid,
    model_available,
)

_PROPOSE_INSTRUCTION = (
    "You are given ONE Python function and one of its decision branches that no test ever reached. "
    "The function's module is importable as the given dotted path. Infer the caller-facing behaviour the "
    "branch SHOULD have from the function name, its parameters, and the branch - do not just echo what the "
    "code visibly does. Write the BODY of a pytest test that exercises exactly that branch: import what you "
    "need from the module (a plain `from <module> import name`), construct the argument values, call the "
    "function into a binding named `result`, then `assert <property>, <message>` on `result`. If the function "
    "is a method (is_method true) construct an instance first. The proof is kept only if execution contradicts "
    "your assertion, so assert the behaviour a correct implementation MUST have, not a prediction of the "
    "current output. Return ONLY a JSON object with keys: \"body\" (the Python statements, NOT indented and "
    "with no def wrapper) and \"explanation\" (one plain sentence stating the behaviour you assert)."
)
_REPAIR_INSTRUCTION = (
    "The pytest test below errored during setup (not on its assertion). Here is the exact error. Rewrite the "
    "test BODY so it imports and constructs correctly and still asserts the same intended behaviour. Keep the "
    "final `result = ...` and the `assert` on `result`. Return ONLY a JSON object with keys \"body\" and "
    "\"explanation\"."
)

# pytest's short-summary line for a failure/error: `FAILED file::proof_3 - AssertionError: ...`.
_OUTCOME = re.compile(r"^(?:FAILED|ERROR)\s+\S*::proof_0\s*-\s*(\w+)", re.MULTILINE)


def _import_path(repo: Path, file_path: Path) -> str:
    """The dotted import path of a module: walk up while __init__.py exists, so a src-layout
    package resolves to its installed name (src/pkg/sub/mod.py -> pkg.sub.mod)."""
    parts = [file_path.stem]
    directory = file_path.parent
    while (directory / "__init__.py").exists():
        parts.append(directory.name)
        directory = directory.parent
    return ".".join(reversed(parts))


def _signature(gap: dict) -> str:
    params = ", ".join(p["name"] + (f": {p['annotation']}" if p["annotation"] else "") for p in gap["parameters"])
    return f"def {gap['function']}({params})"



def propose(gap: dict, import_path: str) -> dict | None:
    """First calling test for the located gap: {body, explanation} or None."""
    payload = json.dumps({
        "module": import_path, "function_source": gap["function_source"], "signature": _signature(gap),
        "is_method": gap["is_method"],
        "uncovered_branch": f"the `{gap['kind']}` branch at line {gap['line']} is never exercised",
    })
    return _valid(_call_model(_PROPOSE_INSTRUCTION, payload))


def repair(gap: dict, import_path: str, test_source: str, error: str) -> dict | None:
    payload = json.dumps({
        "module": import_path, "signature": _signature(gap), "function_source": gap["function_source"],
        "test_that_errored": test_source, "error": error[-4000:],
    })
    return _valid(_call_model(_REPAIR_INSTRUCTION, payload))


def _indent(body: str) -> str:
    return "\n".join(("    " + ln) if ln.strip() else ln for ln in body.splitlines())


def render_test(body: str) -> str:
    """One proof as a pytest function. The body carries its own imports and its assert (with
    the explanation as the message), so a failing AssertionError is attributable to the test.
    `python_functions=proof_*` (passed on the pytest command) makes pytest collect it."""
    return f"def proof_0():\n{_indent(body)}\n"


def _classify(output: str, returncode: int) -> str:
    """pass | divergence | incidental | error from one pytest run of a single proof. A failure
    whose exception is AssertionError is the test's own assert firing (a proven divergence); any
    other exception, or a collection ERROR, is a setup failure (incidental noise)."""
    if returncode == 124:
        return "error"
    match = _OUTCOME.search(output)
    if match:
        return "divergence" if match.group(1) == "AssertionError" else "incidental"
    if returncode == 0 and "1 passed" in output:
        return "pass"
    return "incidental"  # collection/usage error, or the file did not import


def _run(repo: Path, interpreter: str, test_source: str, timeout_seconds: float) -> tuple[int, str]:
    with tempfile.TemporaryDirectory(prefix="l1-pyproof-") as directory:
        test_file = Path(directory) / "test_l1_coverage_proof.py"
        test_file.write_text(test_source)
        run = pytest_trace._run_untrusted(
            [interpreter, "-m", "pytest", str(test_file), "-q", "-p", "no:cacheprovider",
             "--tb=line", "-o", "python_functions=proof_*"],
            cwd=repo, env={}, timeout_seconds=timeout_seconds)
    return run.returncode, (run.stdout or "") + (run.stderr or "")


def _prove_one(repo: Path, interpreter: str, gap: dict, import_path: str,
               repair_rounds: int, timeout_seconds: float,
               propose_fn: Callable[..., dict | None],
               repair_fn: Callable[..., dict | None],
               run_fn: Callable[..., tuple[int, str]]) -> tuple[str, dict | None, str]:
    """Propose -> run -> (repair -> run)* for one gap. Returns (bucket, proposal, test_source):
    divergence (retained), pass, incidental (setup error), error (timeout), or skipped (no reply).

    THE THREE COLLABORATORS ARE PARAMETERS, as `prove.prove` already takes `model_call` and
    `run_generated`. They were module-level lookups, so the only way to test this loop was
    to patch the module's own globals, and a test that reaches in to replace what it is
    testing asserts against its own fixture. Those tests went in the 2026-08-17 sweep and
    the orchestration has been uncovered since.

    Required, not defaulted. A default would put the real model call and a real subprocess
    one forgotten argument away from a test, which is the open-input failure this
    repository refuses everywhere else."""
    proposal = propose_fn(gap, import_path)
    if proposal is None:
        return "skipped", None, ""
    source = render_test(proposal["body"])
    rc, output = run_fn(repo, interpreter, source, timeout_seconds)
    bucket = _classify(output, rc)
    rounds = 0
    while bucket == "incidental" and rounds < repair_rounds:
        rounds += 1
        fixed = repair_fn(gap, import_path, source, output)
        if fixed is None:
            break
        proposal = fixed
        source = render_test(fixed["body"])
        rc, output = run_fn(repo, interpreter, source, timeout_seconds)
        bucket = _classify(output, rc)
    return bucket, proposal, source


def _prove_module(repo: Path, relpath: str, interpreter: str, gaps: list[dict],
                  repair_rounds: int, timeout_seconds: float,
                  propose_fn: Callable[..., dict | None],
                  repair_fn: Callable[..., dict | None],
                  run_fn: Callable[..., tuple[int, str]]) -> tuple[list[dict], dict]:
    """Every gap in one module. Threads the three collaborators through rather than
    reaching for the module's globals, for the reason `_prove_one` gives."""
    outcomes = {"divergence": 0, "incidental": 0, "pass": 0, "error": 0}
    import_path = _import_path(repo, repo / relpath)
    retained: list[dict] = []
    for gap in gaps:
        bucket, proposal, source = _prove_one(repo, interpreter, gap, import_path, repair_rounds,
                                              timeout_seconds, propose_fn, repair_fn, run_fn)
        if bucket == "skipped":
            continue
        outcomes[bucket] += 1
        if bucket == "divergence":
            entry: CoverageProof = {
                "function": gap["function"], "language": "python",
                "location": f"{relpath}:{gap['line']}",
                "explanation": proposal["explanation"], "test_source": source.strip(),
            }
            retained.append(entry)
    return retained, outcomes


def prove_coverage_repo(repo: Path, cap_per_module: int = 5, repair_rounds: int = 3,
                        timeout_seconds: float = 600.0, python_executable: str | None = None, progress=None) -> dict:
    """Sweep the whole package: one coverage run to locate uncovered branches, then every module
    with uncovered branches is proven. Retained proofs (assertion-divergences) aggregate across
    the package. Directory-insensitive: the suite runs under the target's own interpreter."""
    if not model_available():
        return {"retained": [], "attempted": 0, "detail": "needs ANTHROPIC_API_KEY to generate coverage proofs"}
    interpreter, provenance = pytest_trace.resolve_interpreter(repo, python_executable)
    if not pytest_trace._module_available("pytest", interpreter) or not pytest_trace._module_available("coverage", interpreter):
        return {"retained": [], "attempted": 0, "detail": f"needs pytest and coverage.py in the target environment ({provenance})"}
    cov = _uncovered_lines(repo, interpreter, timeout_seconds)
    if not cov["measured"]:
        return {"retained": [], "attempted": 0, "detail": f"coverage not measured: {cov['reason']}"}

    retained: list[dict] = []
    outcomes = {"divergence": 0, "incidental": 0, "pass": 0, "error": 0}
    modules = 0
    for relpath, lines in sorted(cov["files"].items()):
        try:
            functions = python_facets.module_functions((repo / relpath).read_text(errors="ignore"))
        except OSError:
            continue
        gaps = python_facets.uncovered_gaps(functions, lines)[:cap_per_module]
        if not gaps:
            continue
        modules += 1
        if progress:
            progress(relpath, len(gaps), len(retained))
        # The real three, named at the one place that knows which they are.
        module_retained, module_outcomes = _prove_module(
            repo, relpath, interpreter, gaps, repair_rounds, timeout_seconds,
            propose, repair, _run)
        retained.extend(module_retained)
        for k in outcomes:
            outcomes[k] += module_outcomes[k]
    attempted = sum(outcomes.values())
    detail = (f"{len(retained)} coverage proofs retained across {modules} modules with uncovered branches "
              f"(ran under {provenance}). Of {attempted} generated tests: {outcomes['divergence']} retained as "
              f"behavioural divergences (bug proven), {outcomes['pass']} passed (branch correct), "
              f"{outcomes['incidental']} errored on setup (kept out of findings), {outcomes['error']} timed out."
              ) if attempted else f"no proof-ready uncovered branches located across {modules} modules"
    return {"retained": retained, "attempted": attempted, "outcomes": outcomes, "modules": modules, "detail": detail}


def _uncovered_lines(repo: Path, interpreter: str, timeout_seconds: float) -> dict:
    """{measured, files: {relpath: frozenset(missing lines)}, reason} from one branch-coverage
    run of the target's suite, via coverage.py's per-file missing_lines."""
    with tempfile.TemporaryDirectory(prefix="l1-pycov-") as directory:
        data_file = Path(directory) / ".coverage"
        report_file = Path(directory) / "coverage.json"
        env = {"COVERAGE_FILE": str(data_file)}
        run = pytest_trace._run_untrusted(
            [interpreter, "-m", "coverage", "run", "--branch", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
            cwd=repo, env=env, timeout_seconds=timeout_seconds)
        if run.returncode == 124:
            return {"measured": False, "files": {}, "reason": "the suite timed out before coverage could be measured"}
        if run.returncode not in (0, 1):
            return {"measured": False, "files": {}, "reason": f"the suite did not complete a valid run (pytest exit {run.returncode})"}
        subprocess.run([interpreter, "-m", "coverage", "json", "-o", str(report_file)],
                       cwd=str(repo), env={**os.environ, **env}, capture_output=True, text=True, check=False)
        if not report_file.exists():
            return {"measured": False, "files": {}, "reason": "coverage produced no data"}
        try:
            report = json.loads(report_file.read_text())
        except (OSError, json.JSONDecodeError):
            return {"measured": False, "files": {}, "reason": "coverage report was unreadable"}
    root = repo.resolve()
    files: dict[str, frozenset[int]] = {}
    for path_str, data in report.get("files", {}).items():
        missing = data.get("missing_lines") or []
        if not missing:
            continue
        resolved = (repo / path_str).resolve()
        if root == resolved or root in resolved.parents:
            files[str(resolved.relative_to(root))] = frozenset(int(n) for n in missing)
    return {"measured": True, "files": files, "reason": ""}
