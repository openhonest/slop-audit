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

import ast
import json
import os
import re
import subprocess
import tempfile
import textwrap
from collections.abc import Callable
from pathlib import Path

from l1_analyzer import coverage_prove, pytest_trace, python_facets
from l1_analyzer import model_call as llm
from l1_analyzer.coverage_prove import (
    CoverageProof,
    _call_model,
    _valid,
    ceiling_detail,
    model_available,
    sweep_detail,
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

# pytest's short-summary line for a failure/error: `FAILED file::proof_0 - AssertionError: ...`.
# NOT the only source of the verdict, because pytest truncates this line's ` - reason`
# suffix to the terminal width, and the proof file lives under a macOS tmpdir whose path
# alone overflows 80 columns. For as long as this regex was the only reader, the reason
# never survived, every fired assertion was binned "incidental", and the repair loop then
# rewrote the test until it agreed with the buggy code. Found on 2026-08-20 by a planted
# positive control whose two correct assertions both came back "passed (branch correct)".
_OUTCOME = re.compile(r"^(?:FAILED|ERROR)\s+\S*::proof_0\s*-\s*(\w+)", re.MULTILINE)
# The `--tb=line` row, `.../test_l1_coverage_proof.py:N: ExceptionName: msg`, which pytest
# does not truncate. Anchored to the proof file's own name so another file's traceback
# (a conftest raising while the proof fails to import) cannot claim the verdict.
_TB_LINE = re.compile(r"test_l1_coverage_proof\.py:\d+:\s*(\w+)")


# Directories that hold packages without being part of the import path. `src` is the
# convention; the repository root is the other stopping point and is passed in.
_SOURCE_ROOTS = frozenset({"src", "lib"})


def _import_path(repo: Path, file_path: Path) -> str:
    """The dotted import path of a module: every directory between the source root and the
    file, so src/pkg/sub/mod.py is pkg.sub.mod and planted/pricing.py is planted.pricing.

    It walked up only while `__init__.py` existed, which is a rule about REGULAR packages
    and PEP 420 namespace packages have no `__init__.py`. So `planted/pricing.py` resolved
    to `pricing`, the model was told a module name that does not import, and its correct
    proposals died on ModuleNotFoundError and were binned as incidental noise. The repair
    loop then spent its rounds trying to fix a test that was never wrong.

    Stopping at the source root rather than at the first missing `__init__.py` covers both:
    a namespace package is walked through like any other directory, and `src` is still
    dropped because it is where the import path starts, not part of it."""
    parts = [file_path.stem]
    directory = file_path.parent
    repo = repo.resolve()
    while directory.resolve() != repo and directory.name not in _SOURCE_ROOTS:
        parts.append(directory.name)
        parent = directory.parent
        if parent == directory:      # reached the filesystem root without meeting the repo
            break
        directory = parent
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
    return _valid(_call_model(_PROPOSE_INSTRUCTION, payload), body_asserts)


def repair(gap: dict, import_path: str, test_source: str, error: str) -> dict | None:
    payload = json.dumps({
        "module": import_path, "signature": _signature(gap), "function_source": gap["function_source"],
        "test_that_errored": test_source, "error": error[-4000:],
    })
    return _valid(_call_model(_REPAIR_INSTRUCTION, payload), body_asserts)


def _indent(body: str) -> str:
    return "\n".join(("    " + ln) if ln.strip() else ln for ln in body.splitlines())


# Statements that HOLD other statements and still execute them: a loop runs its body, a
# `with` runs its block, a branch runs one arm, a `try` runs its. A function, lambda or
# class definition does not: it binds a name, and the body has to call it. That is the whole
# distinction, and it is why the rule can be decided without running anything.
_EXECUTES_ITS_BODY = (ast.For, ast.AsyncFor, ast.While, ast.If, ast.With, ast.AsyncWith,
                      ast.Try, ast.TryStar, ast.Match, ast.match_case, ast.ExceptHandler,
                      ast.Module)


def body_asserts(body: str) -> bool:
    """Whether this proof body will evaluate an assertion when it runs.

    A body that asserts nothing cannot produce evidence either way, and the loop used to
    file it under `pass`, whose report reads "branch correct". Found 2026-08-19: hand the
    loop a whole test module rather than a body - a plausible model reply, and the shape of
    every pytest file a model has read - and the assertion lands inside a nested function
    nobody calls. pytest collects the wrapper, runs it, defines the inner function, and
    passes. A proof that measured nothing published a clean bill for the branch it was sent
    to cover, which is the category this package exists to name.

    `pytest.raises` and its kind count: the assertion IS the context manager, and a `with`
    block runs. A body that will not parse asserts nothing, since it will not run either."""
    try:
        tree = ast.parse(textwrap.dedent(body))
    except SyntaxError:
        return False

    def reachable(node: ast.AST) -> bool:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.Assert, ast.With, ast.AsyncWith)):
                return True
            if isinstance(child, _EXECUTES_ITS_BODY) and reachable(child):
                return True
        return False

    return reachable(tree)


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
    match = _OUTCOME.search(output) or _TB_LINE.search(output)
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


EMPTY_OUTCOMES = {"divergence": 0, "incidental": 0, "pass": 0, "error": 0, "declined": 0}


def _prove_one(repo: Path, interpreter: str, gap: dict, import_path: str,
               repair_rounds: int, timeout_seconds: float,
               propose_fn: Callable[..., dict | None],
               repair_fn: Callable[..., dict | None],
               run_fn: Callable[..., tuple[int, str]]) -> tuple[str, dict | None, str]:
    """Propose -> run -> (repair -> run)* for one gap. Returns (bucket, proposal, test_source):
    divergence (retained), pass, incidental (setup error), error (timeout), or declined
    (no reply, and counted: a model call that produced nothing still cost money).

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
        return "declined", None, ""
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
    outcomes = dict(EMPTY_OUTCOMES)
    import_path = _import_path(repo, repo / relpath)
    retained: list[dict] = []
    for gap in gaps:
        bucket, proposal, source = _prove_one(repo, interpreter, gap, import_path, repair_rounds,
                                              timeout_seconds, propose_fn, repair_fn, run_fn)
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
                        timeout_seconds: float = 600.0, python_executable: str | None = None,
                        progress=None, max_attempts: int = 5) -> dict:
    """Sweep the whole package: one coverage run to locate uncovered branches, then every module
    with uncovered branches is proven. Retained proofs (assertion-divergences) aggregate across
    the package. Directory-insensitive: the suite runs under the target's own interpreter."""
    # Read before anything else, so a ceiling of zero costs nothing: no interpreter probe,
    # no coverage run, no key, no network. A budget of nothing must be free to honour.
    if max_attempts <= 0:
        return {"retained": [], "attempted": 0, "outcomes": {}, "modules": 0,
                "detail": f"attempted nothing: the ceiling is {max_attempts}"}
    if not model_available():
        return {"retained": [], "attempted": 0,
                "detail": f"no coverage proofs generated: {llm.WHY[llm.unavailable_reason()]}"}
    interpreter, provenance = pytest_trace.resolve_interpreter(repo, python_executable)
    if not pytest_trace._module_available("pytest", interpreter) or not pytest_trace._module_available("coverage", interpreter):
        return {"retained": [], "attempted": 0, "detail": f"needs pytest and coverage.py in the target environment ({provenance})"}
    cov = _uncovered_lines(repo, interpreter, timeout_seconds)
    if not cov["measured"]:
        return {"retained": [], "attempted": 0, "detail": f"coverage not measured: {cov['reason']}"}

    retained: list[dict] = []
    outcomes = dict(EMPTY_OUTCOMES)
    modules = 0
    located = 0            # every gap the sweep found, whether or not the ceiling let it try
    attempted_gaps = 0     # every gap the sweep handed to a model
    for relpath, lines in sorted(cov["files"].items()):
        try:
            functions = python_facets.module_functions((repo / relpath).read_text(errors="ignore"))
        except OSError:
            continue
        module_gaps = python_facets.uncovered_gaps(functions, lines)[:cap_per_module]
        located += len(module_gaps)
        # The repo-wide ceiling, applied after `located` counts the whole gap so the report
        # can say what was left. Truncating before counting would hide the size of the miss.
        gaps = module_gaps[:max(0, max_attempts - attempted_gaps)]
        attempted_gaps += len(gaps)
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
    # `attempted` is every gap handed to a model, declines included: that is the unit that
    # cost money, and a budget that did not count the declines could not be reconciled.
    # `ran` is the subset that produced a test to execute, which is what the breakdown counts.
    attempted = sum(outcomes.values())
    ran = attempted - outcomes["declined"]
    detail = sweep_detail(len(retained), modules, located, outcomes, provenance,
                          coverage_prove.LAST_REFUSAL["reason"],
                          coverage_prove.LAST_REFUSAL["cause"])
    if ran:
        detail += (f"Of {ran} generated tests: {outcomes['divergence']} retained as "
                   f"behavioural divergences (bug proven), {outcomes['pass']} passed (branch correct), "
                   f"{outcomes['incidental']} errored on setup (kept out of findings), "
                   f"{outcomes['error']} timed out.")
    detail += ceiling_detail(attempted_gaps, located, max_attempts)
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
