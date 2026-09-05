#!/usr/bin/env python
"""Which of the 200 corpus repositories are provably exhaustively testable.

One question, asked with the current instrument and no regard for what was pre-registered:
of the 200 repositories in the Paper A corpus, minus the one react project, how many can be
said with certainty to be exhaustively testable?

A repository qualifies only when EVERY piece of state it holds is NEUTRAL. The classifier
gives three verdicts and only one of them supports the claim:

  NEUTRAL      the decisions reaching this state divide its domain into a finite,
               statically enumerable set of classes. Testable by enumeration.
  PROMISCUOUS  that division is provably unbounded. Proof that it is NOT.
  UNRESOLVED   the classifier could not decide within its scope. Not a proof either way,
               so it cannot support "definitely", and a repository holding one does not
               qualify.

That is why the answer is a floor rather than an estimate. A repository counted here has no
piece of state the instrument could not resolve, and none it resolved against.

Both meters run: L1.18's mutable-state scalar alongside L1.18b's partition-count verdicts,
so the two readings sit beside each other per repository.

Streaming: shallow-clone, read, delete. Resumable: a repository with a result file is
skipped, so an interrupted run continues. Static analysis only, so no untrusted code runs.

Parallel across repositories, one worker per process. Each worker clones into its own
temporary directory and writes its own result file, so the workers share nothing and the
resume rule still holds: a file on disk means that repository is done. The first version of
this ran one repository at a time and used one core of twenty-four, which turned a
forty-five minute job into a three hour one.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import TypedDict

from l1_analyzer import state_bounds
from l1_analyzer.indicators import analyze_mutable_state

class Repo(TypedDict):
    """One corpus entry, as the manifest writes it.

    Written out rather than left a bare mapping. Every field below is read by name, and a
    mapping of anything to anything has no keys to be wrong about, so each read would be an
    assumption nothing could check. The type-escape gate said so on the commit that added
    this file."""

    full_name: str
    language: str
    stars: int
    default_branch: str
    url: str


class Reading(TypedDict, total=False):
    """What measuring one repository produced, or why it could not be measured.

    Not total: a repository that would not clone carries a status and a detail and none of
    the readings, and inventing the missing ones would be a blank nobody measured."""

    status: str
    detail: str
    clone_seconds: float
    v1_mutable_ratio: float | str | None
    v2_verdict: str
    v2_counts: dict[str, int]
    v2_coverage: dict[str, dict[str, int]]
    v2_resolvable: float
    v2_silence: dict[str, int]
    exhaustive: str


HERE = Path(__file__).resolve().parent
CORPUS = Path("/Users/adam/dev/honest/adamzwasserman/slop-audit/openhonest-paper-a-finite-testability/corpus.json")
RESULTS = HERE / "results"
CLONE_TIMEOUT = 900

# The corpus names a language per repository; the analyzer spells two of them differently.
ANALYZER_LANG = {"Java": "java", "Python": "python", "TypeScript": "typescript",
                 "C#": "csharp", "Rust": "rust"}


def boundary(fn):
    """Mark a function as one of this script's edges, and change nothing about it.

    Spelled here rather than imported, as its sibling arm does: this is a research script
    that uses the analyzer as a library, and its edges are its own."""
    return fn
# The one react project, excluded by instruction.
EXCLUDE = {"react-hook-form/react-hook-form"}


def wanted(corpus: list[Repo]) -> list[Repo]:
    """The repositories to measure: the corpus minus the excluded ones.

    Named rather than filtered inline so the count that goes in the report and the count
    that goes through the loop are the same number, read from one place."""
    return [r for r in corpus if r["full_name"] not in EXCLUDE]


def clone_command(repo: Repo, dest: Path) -> list[str]:
    """Shallow, single branch, and pinned to the branch the manifest names.

    Without the pin git takes whatever HEAD points at today, and a rerun would measure a
    different commit from the one recorded."""
    cmd = ["git", "clone", "--depth", "1", "--single-branch"]
    if repo.get("default_branch"):
        cmd += ["--branch", repo["default_branch"]]
    return cmd + [repo["url"], str(dest)]


def verdict_of(counts: dict[str, int]) -> str:
    """Whether this repository is provably exhaustively testable, and if not, why not.

    Four answers, kept apart because they are four different facts. `no state` is not a
    pass: a repository the classifier found nothing in has not been shown to be anything,
    and counting it as testable is the zero-denominator lie the instrument exists to refuse.

    A pass here is not the same as a pass over a whole codebase, and the summary prints the
    state count beside every one for that reason. On the first run two repositories passed
    on 2 and 5 pieces of state, against a median of 1,586 across the corpus; one of them
    had 338 declarations in 106 files and the classifier judged two of them. A verdict over
    six tenths of one per cent of what was looked at is not a finding about that codebase,
    and it read exactly like one in the tally. No threshold is applied, because any number
    would be invented: the count is printed instead, where a reader cannot miss it.
    """
    if counts["promiscuous"]:
        return "not testable"          # proven unbounded state
    if counts["unresolved"]:
        return "undetermined"          # the classifier could not decide
    if counts["neutral"]:
        return "exhaustively testable"
    return "no state found"


def measure(dest: Path, lang: str, clone_seconds: float) -> Reading:
    try:
        v1 = analyze_mutable_state(dest, lang)
        v2 = state_bounds.classify(dest, lang)
    except Exception as exc:  # noqa: BLE001 - one repository must not sink the run
        return {"status": "analyze_error", "detail": repr(exc)[:300], "clone_seconds": clone_seconds}
    counts = v2["counts"]
    return {
        "status": "ok",
        "clone_seconds": clone_seconds,
        "v1_mutable_ratio": v1.get("value"),
        "v2_verdict": v2["verdict"],
        "v2_counts": counts,
        "v2_coverage": v2.get("coverage"),
        "v2_resolvable": v2.get("resolvable_fraction"),
        # An empty table rather than absent: the classifier reports no silence and a
        # reading with no silence key are the same fact here, which is that nothing was
        # passed over. The reasons are read by name below.
        "v2_silence": (v2.get("silence") or {}).get("by_reason") or {},
        "exhaustive": verdict_of(counts),
    }


@boundary
def read_one(repo: Repo, results: Path) -> str:
    """Clone one repository, read it, delete it, and write its result file.

    An edge, and declared one. It clones, deletes and writes, which the clause check named
    on the commit that introduced it. The I/O cannot move to the caller here: this IS the
    unit of parallel work, and a worker that returned a path for the parent to write would
    put every result file through one process and undo the parallelism.

    Runs in a worker process. It writes its own file and shares nothing with the others,
    which is what lets the resume rule stay simple: a file on disk means done.

    The results directory is an argument. It was a module global, which a fork-based pool
    happens to inherit and a spawn-based one does not, so the same code would have written
    to two different places on Linux and macOS."""
    out = results / f"{repo['full_name'].replace('/', '__')}.json"
    if out.exists():
        return "already done"
    lang = ANALYZER_LANG.get(repo["language"])
    if lang is None:
        out.write_text(json.dumps({"status": "unsupported_language", **repo}, indent=1))
        return "unsupported language"
    with tempfile.TemporaryDirectory(prefix="ex200_") as tmp:
        dest = Path(tmp) / "repo"
        t0 = time.time()
        try:
            subprocess.run(clone_command(repo, dest), check=True,
                           capture_output=True, timeout=CLONE_TIMEOUT)
        except subprocess.TimeoutExpired:
            out.write_text(json.dumps({"status": "clone_timeout", **repo}, indent=1))
            return "clone timed out"
        except subprocess.CalledProcessError as e:
            out.write_text(json.dumps(
                {"status": "clone_failed",
                 "detail": e.stderr.decode("utf8", "ignore")[-200:], **repo}, indent=1))
            return "clone failed"
        reading = measure(dest, lang, round(time.time() - t0, 1))
        shutil.rmtree(dest, ignore_errors=True)
    out.write_text(json.dumps({**reading, **repo}, indent=1))
    return f"{reading.get('exhaustive', reading['status'])}  {reading.get('v2_counts')}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--aggregate-only", action="store_true")
    # Named on the command line or taken from the machine, never a number typed once and
    # forgotten: this runs on a laptop and on a twenty-four core server.
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    # Which corpus and where its results go, so a second corpus does not overwrite the
    # first's readings. The Rust arm was added on 2026-09-05 to test a prediction that
    # Rust's ownership rules would put at least half its repositories in the clear.
    ap.add_argument("--corpus", type=Path, default=CORPUS)
    ap.add_argument("--results", type=Path, default=RESULTS)
    args = ap.parse_args()
    results = args.results
    results.mkdir(parents=True, exist_ok=True)
    raw = json.loads(args.corpus.read_text())
    repos = wanted(raw["qualifying"] if isinstance(raw, dict) else raw)
    if args.limit:
        repos = repos[: args.limit]

    if not args.aggregate_only:
        todo = [r for r in repos if not (results / f"{r['full_name'].replace('/', '__')}.json").exists()]
        print(f"{len(repos)} repositories, {len(repos) - len(todo)} already done, "
              f"{len(todo)} to read, {args.workers} workers", flush=True)
        done = 0
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(read_one, repo, results): repo for repo in todo}
            for future in as_completed(futures):
                repo = futures[future]
                done += 1
                try:
                    line = future.result()
                except Exception as exc:  # noqa: BLE001 - one worker must not sink the run
                    line = f"worker failed: {exc!r}"
                print(f"[{done}/{len(todo)}] {repo['full_name']} ({repo['language']}): {line}",
                      flush=True)

    read = [json.loads(p.read_text()) for p in sorted(results.glob("*.json"))]
    ok = [r for r in read if r.get("status") == "ok"]
    tally: dict[str, int] = {}
    for r in ok:
        tally[r["exhaustive"]] = tally.get(r["exhaustive"], 0) + 1
    by_lang: dict[str, dict[str, int]] = {}
    for r in ok:
        by_lang.setdefault(r["language"], {}).setdefault(r["exhaustive"], 0)
        by_lang[r["language"]][r["exhaustive"]] += 1
    not_measured = [{"repo": str(r.get("full_name")), "status": str(r.get("status")),
                     "detail": str(r.get("detail"))} for r in read if r.get("status") != "ok"]
    summary = {
        "corpus": len(repos),
        "measured_ok": len(ok),
        "not_measured": not_measured,
        "tally": tally,
        "by_language": by_lang,
        "exhaustively_testable_share_of_measured":
            round(tally.get("exhaustively testable", 0) / len(ok), 4) if ok else None,
        "exhaustively_testable_share_of_corpus":
            round(tally.get("exhaustively testable", 0) / len(repos), 4) if repos else None,
    }
    (results.parent / f"summary-{results.name}.json").write_text(json.dumps(summary, indent=1))
    print("\n================ 200-repo corpus, exhaustive testability ================")
    print(f"corpus (react excluded): {len(repos)};  measured ok: {len(ok)}")
    for k, v in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"  {k:24} {v:4}  {v/len(ok):6.1%} of measured")

    # Every pass, with the state it was read over. A clean verdict is only as good as the
    # amount the classifier judged, and printing the two apart lets a reader see a pass that
    # rests on nothing.
    passes = [r for r in ok if r["exhaustive"] == "exhaustively testable"]
    if passes:
        sizes = sorted(sum(r["v2_counts"].values()) for r in ok)
        print(f"\nevery pass, with the state it was judged over "
              f"(corpus median {sizes[len(sizes) // 2]}):")
        for r in sorted(passes, key=lambda r: sum(r["v2_counts"].values())):
            print(f"  {r['full_name']:46} {sum(r['v2_counts'].values()):6} pieces")
    print(f"\nby language: {json.dumps(by_lang)}")
    if not_measured:
        print(f"\nnot measured: {len(not_measured)}")
        for n in not_measured[:10]:
            print(f"  {n['repo']}: {n['status']} {str(n['detail'])[:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
