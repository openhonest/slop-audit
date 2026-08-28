"""The live coverage-proof sweep: several repositories, one budget, a named key file.

This is the one thing in the prove loop no test can cover, because the thing under test is
a model answering. Everything around it is covered by injection. So this module is the
boundary that spends money, and it is built to make the spending legible rather than to
make it convenient.

Three properties it owes, each of them a way a sweep could lie about what it did.

The key comes from a NAMED FILE, never from the ambient environment. A sweep that silently
found a key somewhere is a sweep whose cost nobody authorised, and the file it read is
recorded in the result beside the numbers.

The ceiling is a RUN budget, not a per-repository one. Five per repo over six repos is
thirty calls, which is not what anyone means by starting at five. Each repository gets
whatever is left.

Every repository appears in the result, INCLUDING the ones that refused. A repo skipped
for a missing toolchain that vanishes from the report leaves a run that swept four of six
looking like a run that swept four.

Never a gate. It costs money and its answer varies between runs. It is run when asked and
its output is a dated record, the same as a validation run.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from l1_analyzer import budget, coverage_prove, python_coverage_prove

_KEY = "ANTHROPIC_API_KEY"

# One sweep per language that has one. Rust needs cargo and cargo-llvm-cov; Python needs
# pytest and coverage.py in the target's own environment. Each refuses by name when its
# toolchain is absent, which is why a refusing repo can still be reported rather than dropped.
SWEEPS = {
    "rust": coverage_prove.prove_coverage_repo,
    "python": python_coverage_prove.prove_coverage_repo,
}


def _value(line: str) -> str:
    """The value on one KEY=VALUE line, with shell quoting removed.

    Shell files quote. A key carrying its own quote marks fails at the API as an
    authentication error, which sends a reader to the account rather than to the file."""
    return line.split("=", 1)[1].strip().strip('"').strip("'")


def key_from(env_file: Path) -> str | None:
    """The Anthropic key on the named file, or nothing.

    Nothing, rather than a fall-through to os.environ: a run has to be able to say which
    file paid for it, and an ambient key makes that unanswerable."""
    try:
        lines = env_file.read_text().splitlines()
    except OSError:
        return None
    for line in lines:
        if line.strip().startswith(f"{_KEY}="):
            return _value(line) or None
    return None


def share(run_ceiling: int, per_repo: int, spent: int) -> int:
    """How many attempts the next repository may make.

    The rule itself lives in `budget`, because the module sweep computes the same thing and
    spelled it as a slice, which the duplicate-rule guard cannot see through."""
    return budget.allowance(per_repo, run_ceiling, spent)


def fair_share(ceiling: int, repos: int) -> int:
    """The default per-repository cap: the run ceiling divided across the repositories,
    rounded up, so every repository gets a turn.

    Without it, multi-repo is hollow at a small ceiling. A run ceiling of 5 with a
    per-repository cap of 5 over three repositories gives the whole budget to the first
    and reports the other two as not swept: a correct sweep of one repository wearing the
    shape of a sweep of three. Rounding up rather than down keeps the last repository from
    being offered nothing; the run ceiling still binds the total."""
    if ceiling <= 0 or repos <= 0:
        return 0
    return -(-ceiling // repos)


def language_of(repo: Path) -> str | None:
    """Which sweep to run, from what the repository is built of. None when neither applies,
    which is a reportable outcome rather than a skip."""
    if (repo / "Cargo.toml").exists():
        return "rust"
    if any((repo / name).exists() for name in ("pyproject.toml", "setup.py", "setup.cfg")):
        return "python"
    return None


def sweep(repos: list[Path], key: str | None, run_ceiling: int, per_repo: int,
          sweeps: dict[str, Callable[..., dict]]) -> dict:
    """Run the coverage-proof sweep over several repositories under one budget.

    Returns every repository that was offered, in order, each with what it attempted and
    what it retained or why it did neither.

    `sweeps` is required, and reaching for the module's own SWEEPS table instead is what
    made everything below the no-key refusal unreachable in a test: driving it would have
    meant overwriting a name in the module under test, which this package forbids. The body
    sat at 51% and the arithmetic that decides what a run spends had never been executed
    outside three live runs that spent real money.

    Fourth appearance of one lesson, and the first found by coverage rather than by
    reading. `_prove_one`, `prove_hazard` and `model_call.call` each reached for a
    collaborator and each now asks for one."""
    if key is None:
        return {"detail": f"no {_KEY} was read, so no repository was swept",
                "spent": 0, "run_ceiling": run_ceiling,
                "repos": [{"repo": str(r), "language": None, "attempted": 0, "retained": 0,
                           "detail": f"not swept: no {_KEY}"} for r in repos]}

    os.environ[_KEY] = key      # the one place the key enters the process
    reports: list[dict] = []
    spent = 0
    for repo in repos:
        language = language_of(repo) if language_of(repo) in sweeps else None
        allowance = share(run_ceiling, per_repo, spent)
        if language is None:
            reports.append({"repo": str(repo), "language": None, "attempted": 0, "retained": 0,
                            "detail": "no Cargo.toml and no Python project file; no sweep applies"})
            continue
        if allowance == 0:
            reports.append({"repo": str(repo), "language": language, "attempted": 0, "retained": 0,
                            "detail": f"not swept: the run ceiling of {run_ceiling} was already spent"})
            continue
        result = sweeps[language](repo, max_attempts=allowance)
        spent += int(result["attempted"])
        reports.append({"repo": str(repo), "language": language,
                        "attempted": int(result["attempted"]),
                        "retained": len(result["retained"]),
                        "proofs": result["retained"],
                        "detail": str(result["detail"])})
    swept = sum(1 for r in reports if r["attempted"])
    return {"detail": f"{spent} of a {run_ceiling} attempt ceiling spent across {swept} of "
                      f"{len(repos)} repositories",
            "spent": spent, "run_ceiling": run_ceiling, "repos": reports}
