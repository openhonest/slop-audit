#!/usr/bin/env python
"""Paper A v2 (finite-testability) re-analysis, Python subset.

Runs the corrected partition-count meter (l1_analyzer.state_bounds.classify)
alongside the pre-partition mutable-state ratio (analyze_mutable_state) on each of
the 50 qualifying Python repos, per the finite-testability supersession rule: report
the scalar and the three-verdict distribution side by side.

Streaming: shallow-clone, analyze, delete, so disk stays bounded even with large
repos. Resumable: a repo with an existing result file is skipped, so an interrupted
run continues. Static analysis only (no test execution), so no untrusted code runs.

Run inside the l1_analyzer venv so `import l1_analyzer` resolves:

    cd <slop-audit>/tools/l1_analyzer
    uv run python paper_a_v2/run_subset.py            # all 50
    uv run python paper_a_v2/run_subset.py --limit 2  # smoke test
    uv run python paper_a_v2/run_subset.py --aggregate-only
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

from l1_analyzer import state_bounds
from l1_analyzer.indicators import analyze_mutable_state

HERE = Path(__file__).resolve().parent
# One repository in the arm, and what analysing it produced. Both were written `dict`, the
# least precise mapping the language has, with the key always a string.
Repo = dict[str, object]
Reading = dict[str, object]



def boundary(fn):
    """Mark a function as one of this script's edges, and change nothing about it.

    Spelled here rather than imported: this is a research arm that uses the analyzer as a
    library, and its edges are its own."""
    return fn


CORPUS = HERE / "corpus_python.json"
RESULTS = HERE / "results"
CLONE_TIMEOUT = 900  # seconds; a repo that will not shallow-clone in 15 min is recorded and skipped


@boundary
def _load_repos() -> list[Reading]:
    return json.loads(CORPUS.read_text())["qualifying"]


def _slug(full_name: str) -> str:
    return full_name.replace("/", "__")


def clone_command(repo: Repo, dest: Path) -> list[str]:
    """The git command that fetches one repository for measurement.

    Shallow and single-branch, because this arm reads a checkout and never its history. The
    branch is pinned when the manifest names one: without that, git takes whatever HEAD
    points at today, and a rerun would measure a different commit from the one recorded.

    Lifted out of the clone below. A declaration on a function that still decides something
    is a stamp, and the write hook said so about this one."""
    cmd = ["git", "clone", "--depth", "1", "--single-branch"]
    branch = repo.get("default_branch")
    if branch:
        cmd += ["--branch", branch]
    return cmd + [repo["url"], str(dest)]


@boundary
def _clone(repo: Repo, dest: Path) -> tuple[bool, str, float]:
    cmd = clone_command(repo, dest)
    t0 = time.time()
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=CLONE_TIMEOUT)
        return True, "", round(time.time() - t0, 1)
    except subprocess.TimeoutExpired:
        return False, "clone_timeout", round(time.time() - t0, 1)
    except subprocess.CalledProcessError as e:
        return False, "clone_failed: " + e.stderr.decode("utf8", "ignore")[-200:], round(time.time() - t0, 1)


def _measured(dest: Path, clone_seconds: float) -> Reading:
    """One checkout, read by both meters, as a Reading.

    Not declared an edge and it touches nothing: the two meters do their own reading behind
    their own declarations, and this hands them a directory and assembles what they say. A
    parser crash on one repository must not sink a corpus run, so the failure is a reading
    too."""
    try:
        v1 = analyze_mutable_state(dest, "python")
        v2 = state_bounds.classify(dest, "python")
    except Exception as e:
        return {"status": "analyze_error", "detail": repr(e)[:300], "clone_seconds": clone_seconds}
    return {
        "status": "ok",
        "clone_seconds": clone_seconds,
        "v1_mutable_ratio": v1.get("value"),
        "v1_details": v1.get("details"),
        "v2_verdict": v2["verdict"],
        "v2_counts": v2["counts"],
        "v2_coverage": v2["coverage"],
        "v2_resolvable": v2["resolvable_fraction"],
        "v2_promiscuous": [
            {"state": f["state"], "file": f["file"], "line": f["line"]}
            for f in v2["findings"] if f["verdict"] == "promiscuous"
        ],
    }


@boundary
def _discard(dest: Path) -> None:
    """Remove one checkout. A checkout left behind after a failed clone fills the disk over
    a corpus run, which is why this runs on every path and not only the good one."""
    shutil.rmtree(dest, ignore_errors=True)


def _analyze(repo: Repo, workdir: Path) -> Reading:
    """Clone one repository, measure it, and remove the checkout either way.

    Not declared an edge, and it used to be, with a written excuse under it saying that Repo
    is really a locator. It is not an edge: it takes a repository record and hands back a
    reading, which is to say it received something, decided about it, and returned the
    decision. The edges are the three functions it calls, and each is declared where the
    world is actually touched."""
    dest = workdir / _slug(repo["full_name"])
    ok, err, clone_seconds = _clone(repo, dest)
    if not ok:
        _discard(dest)
        return {"status": err.split(":")[0], "detail": err, "clone_seconds": clone_seconds}
    try:
        return _measured(dest, clone_seconds)
    finally:
        _discard(dest)


@boundary
def run(limit: int | None, only: set[str] | None) -> None:
    """Clone each repository, analyze it, write one result file per repository.

    A driver. Every decision it makes about a repository is `_analyze`, and every number
    it reports at the end is `summarise`; what is left here obtains, writes and says where
    it got to."""
    RESULTS.mkdir(exist_ok=True)
    repos = _load_repos()
    if only:
        repos = [r for r in repos if r["full_name"] in only]
    if limit:
        repos = repos[:limit]
    workdir = Path(tempfile.mkdtemp(prefix="paperA_v2_"))
    print(f"[start] {len(repos)} python repos; workdir={workdir}", flush=True)
    for i, repo in enumerate(repos, 1):
        name = repo["full_name"]
        out = RESULTS / (_slug(name) + ".json")
        if out.exists():
            print(f"[{i}/{len(repos)}] {name}: cached", flush=True)
            continue
        print(f"[{i}/{len(repos)}] {name}: analyzing...", flush=True)
        res = _analyze(repo, workdir)
        res["repo"] = name
        res["stars"] = repo.get("stars")
        out.write_text(json.dumps(res, indent=1))
        if res["status"] == "ok":
            print(f"    v1={res['v1_mutable_ratio']}%  v2={res['v2_counts']}  "
                  f"resolvable={res['v2_resolvable']}  ({res['clone_seconds']}s clone)", flush=True)
        else:
            print(f"    {res['status']}: {res.get('detail', '')[:120]}", flush=True)
    shutil.rmtree(workdir, ignore_errors=True)
    aggregate()


def _quartiles(xs: list[float]) -> tuple[float, float, float]:
    xs = sorted(xs)
    q = statistics.quantiles(xs, n=4) if len(xs) >= 2 else [xs[0], xs[0], xs[0]]
    return round(q[0], 1), round(statistics.median(xs), 1), round(q[2], 1)


@boundary
def aggregate() -> None:
    """Read every result, compute the summary, write it and print it.

    A boundary. The arithmetic is `summarise` below, which takes the rows: these are the
    numbers a paper reports, and they used to be computable only by running the whole
    subset against a corpus of cloned repositories first."""
    rows = [json.loads(p.read_text()) for p in sorted(RESULTS.glob("*.json"))]
    if not [r for r in rows if r.get("status") == "ok"]:
        print("[aggregate] no successful repos yet", flush=True)
        return
    summary = summarise(rows)
    (HERE / "summary.json").write_text(json.dumps(summary, indent=1))

    print("\n================ Paper A v2: Python subset, v1 scalar vs v2 distribution ================", flush=True)
    print(f"repos analyzed: {summary['repos_ok']} ok, {summary['repos_failed']} failed", flush=True)
    print(f"v1 mutable-state ratio (percent): q25/median/q75 = {summary['v1_mutable_ratio_pct']['q25_median_q75']}  "
          f"(min {summary['v1_mutable_ratio_pct']['min']}, max {summary['v1_mutable_ratio_pct']['max']})", flush=True)
    print(f"v2 state analyzed: {summary['v2_state_total']} pieces", flush=True)
    print(f"v2 verdict totals: {summary['v2_verdict_totals']}  share={summary['v2_verdict_share']}", flush=True)
    print(f"v2 coverage matrix: {summary['v2_coverage_matrix']}", flush=True)
    print(f"v2 headline blind spot (UNRESOLVED & drives-a-decision): {summary['v2_headline_blind_spot_unresolved_drives_decision']}", flush=True)
    print(f"v2 resolvable fraction: q25/median/q75 = {summary['v2_resolvable_fraction'].get('q25_median_q75')}", flush=True)
    print(f"repos with >=1 promiscuous piece of state: {summary['repos_with_any_promiscuous']}/{summary['repos_ok']}", flush=True)
    print("summary written to summary.json", flush=True)


def summarise(rows: list[Reading]) -> Reading:
    """The numbers this arm reports, from the per-repository results.

    Lifted out of the reader above, which read every result file and computed from it in
    one function. These are the figures a paper carries, and checking one of them meant
    cloning a corpus and running the whole subset first."""
    ok = [r for r in rows if r.get("status") == "ok"]
    failed = [r for r in rows if r.get("status") != "ok"]
    v1_vals = [r["v1_mutable_ratio"] for r in ok if isinstance(r["v1_mutable_ratio"], (int, float))]
    resolvable = [r["v2_resolvable"] for r in ok if isinstance(r["v2_resolvable"], (int, float))]
    tot = {"neutral": 0, "promiscuous": 0, "unresolved": 0}
    cov = {v: {"observe_only": 0, "drives_decision": 0} for v in tot}
    repos_with_promiscuous = 0
    for r in ok:
        for k in tot:
            tot[k] += r["v2_counts"][k]
        for v in cov:
            for c in cov[v]:
                cov[v][c] += r["v2_coverage"][v][c]
        if r["v2_counts"]["promiscuous"] > 0:
            repos_with_promiscuous += 1

    total_state = sum(tot.values())
    return {
        "repos_ok": len(ok),
        "repos_failed": len(failed),
        "failed_detail": [{"repo": r["repo"], "status": r["status"]} for r in failed],
        "v1_mutable_ratio_pct": {"q25_median_q75": _quartiles(v1_vals), "min": round(min(v1_vals), 1), "max": round(max(v1_vals), 1)},
        "v2_state_total": total_state,
        "v2_verdict_totals": tot,
        "v2_verdict_share": {k: round(v / total_state, 3) for k, v in tot.items()} if total_state else {},
        "v2_coverage_matrix": cov,
        "v2_headline_blind_spot_unresolved_drives_decision": cov["unresolved"]["drives_decision"],
        "v2_resolvable_fraction": {"q25_median_q75": _quartiles(resolvable)} if resolvable else {},
        "repos_with_any_promiscuous": repos_with_promiscuous,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="only the first N repos (smoke test)")
    ap.add_argument("--only", default=None, help="comma-separated full_names to include")
    ap.add_argument("--aggregate-only", action="store_true", help="re-aggregate existing results, no cloning")
    args = ap.parse_args()
    if args.aggregate_only:
        aggregate()
        return
    only = set(args.only.split(",")) if args.only else None
    run(args.limit, only)


if __name__ == "__main__":
    main()
