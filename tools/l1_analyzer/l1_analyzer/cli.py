"""CLI for slop-audit-l1 analyzer.

Run against any repo (language auto-detected or specified).
Example:
  uv run --project . l1-analyzer /path/to/repo --since 2025-01-01
  uv run --project . l1-analyzer /path/to/repo --indicators 1,18 --lang python
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from l1_analyzer import card, indicators, schedule_silence, thread_surface


def _count_type_escapes(repo: Path, lang: str) -> int:
    """Count the analyzer's own type-escape hatches (the Any token + # type: ignore
    comments), the same way L1.15 does, so the gate can ratchet on the raw number
    rather than a per-kLOC density."""
    cfg = indicators.LANG_CFG.get(lang)
    patterns = cfg.get("type_escape_patterns") if cfg else None
    if not patterns:
        return 0
    tokens = frozenset(patterns)
    parser = indicators._get_parser(lang)
    files, _skipped = indicators._read_source_bytes(repo, cfg["extensions"], extra_ignore=("tests", "test"))
    return sum(indicators._count_type_escapes_in_tree(parser.parse(src).root_node, tokens) for _path, src in files)


def _run_gate(repo: Path, lang: str, max_type_escapes: int | None, max_thread_exposed: int | None) -> int:
    """Dogfood gate for a pre-commit hook: run the source indicators against the repo
    and fail the commit if the tool would flag its own code. Bright-line invariants:
      - L1.17: no production god-file (a file over 1000 CODE lines).
      - L1.18b: no promiscuous state (the code stays exhaustively testable).
      - L1.15 ratchet (opt-in via --max-type-escapes): the Any / # type: ignore count
        must not exceed the baseline. This is not the density band (a moving
        threshold); it is a bright line at the current number, so a new escape fails
        the commit unless the baseline is deliberately raised in the hook config."""
    results = indicators.compute_source_indicators(
        repo, lang=lang, exec_tests=False, timeout_seconds=5.0, classify_state_bounds=True
    )
    audited_lang = str(results.get("lang", lang))
    problems: list[str] = []

    l17 = results.get("L1.17", {})
    if isinstance(l17.get("value"), (int, float)) and l17["value"] > 0:
        problems.append(f"god-file (L1.17): {l17.get('details', '')}")

    l18b = results.get("L1.18b", {})
    counts = l18b.get("counts", {}) if isinstance(l18b, dict) else {}
    if counts.get("promiscuous", 0) > 0:
        problems.append(
            f"finite-testability (L1.18b): {counts['promiscuous']} promiscuous piece(s) of state "
            "- the code is no longer exhaustively testable"
        )

    escapes: int | None = None
    if max_type_escapes is not None:
        escapes = _count_type_escapes(repo, audited_lang)
        if escapes > max_type_escapes:
            problems.append(
                f"type escapes (L1.15): {escapes} Any / # type: ignore hatches, over the ratchet "
                f"of {max_type_escapes}. Type it (Node / a TypedDict); do not add Any or "
                "# type: ignore. If a new escape is truly unavoidable, raise the baseline in "
                ".pre-commit-config.yaml as a deliberate, reviewable change."
            )

    # Thread-safety surface ratchet (opt-in via --max-thread-exposed): the count of
    # hand-overrides of the compiler's thread-safety guarantee (unsafe impl Send/Sync,
    # static mut) must not exceed the baseline. Like the type-escape ratchet, this is a
    # bright line at the current number, not a density band: a NEW override fails the
    # commit unless the baseline is raised deliberately. It is a fact about surface, not
    # a race claim - the meter never says "safe". n/a for a language with no scanner
    # (so it is a no-op on a Python repo until the Python scanner lands).
    exposed: int | None = None
    if max_thread_exposed is not None:
        ts = results.get("thread_surface") or thread_surface.scan(repo, audited_lang)
        exposed = ts["counts"].get(thread_surface.EXPOSED, 0)
        if exposed > max_thread_exposed:
            problems.append(
                f"thread-safety surface: {exposed} hand-overrides of the thread-safety guarantee "
                f"(unsafe impl Send/Sync, static mut), over the ratchet of {max_thread_exposed}. "
                "This is not a race verdict - it is new audit surface. Verify the override holds "
                "under free-threading; if it is sound, raise the baseline in .pre-commit-config.yaml "
                "as a deliberate, reviewable change."
            )

    if problems:
        print("Slop audit gate FAILED - the audit flags this repo's own code:")
        for p in problems:
            print(f"  - {p}")
        print("Fix the above (split the file, resolve the state, type the escape) before committing.")
        return 1
    ratchet = "" if escapes is None else f", {escapes}/{max_type_escapes} type escapes"
    ratchet += "" if exposed is None else f", {exposed}/{max_thread_exposed} thread-safety overrides"
    print(f"Slop audit gate passed: 0 production god-files, finitely testable{ratchet}.")
    return 0


def _hazard_context(repo: Path, finding: dict[str, object]) -> str:
    """The code around a located hazard, handed to the generator as the only context."""
    path = repo / finding["file"]
    try:
        lines = path.read_text(errors="ignore").splitlines()
    except OSError:
        return f"Located hazard: {finding['kind']} on {finding['symbol']} at {finding['file']}:{finding['line']}."
    lo, hi = max(0, finding["line"] - 30), min(len(lines), finding["line"] + 30)
    window = "\n".join(lines[lo:hi])
    return (f"Located hazard: {finding['kind']} on `{finding['symbol']}` at "
            f"{finding['file']}:{finding['line']}.\nSurrounding Rust source:\n{window}")


def _run_prove(repo: Path, lang: str, thread_surface_result: object, prove_max: int, timeout: float) -> dict[str, object]:
    """Locate -> generate -> run -> retain over the review-tier findings. Deterministic
    locate; the model only fills a located gap; the execution gate keeps only what fires."""
    import tempfile

    from l1_analyzer import prove, thread_surface
    if lang != "rust":
        return {"verdict": "n/a", "detail": f"prove is Rust-only for now; {lang} not supported", "demonstrated": 0, "outcomes": []}
    if not prove.model_available():
        return {"verdict": "n/a", "detail": "needs OPENAI_API_KEY to generate proofs", "demonstrated": 0, "outcomes": []}
    ts = thread_surface_result if isinstance(thread_surface_result, dict) else thread_surface.scan(repo, lang)
    candidates = [f for f in ts.get("findings", []) if f.get("severity") == "review"][:prove_max]
    work_root = Path(tempfile.mkdtemp(prefix="l1-prove-"))
    outcomes: list[dict[str, object]] = []
    for i, f in enumerate(candidates):
        request = prove.proof_request(f, _hazard_context(repo, f))
        outcome = prove.prove_hazard(request, str(work_root / f"proof-{i}"), timeout_seconds=timeout)
        # Keep the generated test on the outcome so the card can expose a retained (demonstrated)
        # proof as an adoptable test - the runnable repro, not just a verdict line.
        outcomes.append({"file": f["file"], "line": f["line"], "symbol": f["symbol"],
                         "verdict": outcome["verdict"], "detail": outcome["detail"],
                         "generated_test": outcome.get("generated_test")})
    demonstrated = sum(o["verdict"] == prove.DEMONSTRATED for o in outcomes)
    return {"verdict": "demonstrated" if demonstrated else "none",
            "demonstrated": demonstrated, "attempted": len(outcomes), "outcomes": outcomes}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="l1-analyzer")
    parser.add_argument("repo", type=Path, help="Path to git repository root")
    parser.add_argument("--since", default=None, help="Start date for git log (e.g. 2025-01-01)")
    parser.add_argument("--until", default=None, help="End date")
    parser.add_argument(
        "--indicators",
        default="all",
        help="Comma-separated L1 numbers or 'all' (default). E.g. 1,2,18",
    )
    parser.add_argument(
        "--lang",
        default="auto",
        choices=["auto", *sorted(indicators.LANG_CFG)],
        help="Primary language for source-based indicators (L1.12+). 'auto' detects from files.",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument(
        "--no-exec",
        action="store_true",
        help="Do not execute the target repo's test suite (skips the runtime half of L1.19 and all of L1.20).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="Seconds allowed for each test-suite execution in L1.19/L1.20 (default 300).",
    )
    parser.add_argument(
        "--no-state-bounds",
        action="store_true",
        help="Turn off the additive L1.18b state-bounds classifier. Pre-registered runs use this "
             "so the output is exactly the frozen L1.18 set; on by default for everyone else.",
    )
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--gate",
        action="store_true",
        help="Dogfood mode for a pre-commit hook: run the source indicators against the repo and "
             "exit non-zero if the audit flags the repo's own code (a production god-file, or "
             "promiscuous state that breaks exhaustive testability). Ignores git/config indicators.",
    )
    parser.add_argument(
        "--max-type-escapes",
        type=int,
        default=None,
        help="Ratchet the L1.15 type-escape count (Any / # type: ignore): with --gate, fail if the "
             "count exceeds this baseline. Set it to the current count so a NEW escape fails the "
             "commit; lower it as escapes are typed away. No effect without --gate.",
    )
    parser.add_argument(
        "--max-thread-exposed",
        type=int,
        default=None,
        help="Ratchet the thread-safety surface: with --gate, fail if the count of hand-overrides "
             "of the compiler's thread-safety guarantee (unsafe impl Send/Sync, static mut) exceeds "
             "this baseline. A fact about audit surface, not a race verdict. Set it to the current "
             "count so a NEW override fails the commit. No effect without --gate.",
    )
    parser.add_argument(
        "--race",
        action="store_true",
        help="Runtime thread-safety: build and run the repo's test suite under ThreadSanitizer "
             "(Rust) and report data races that actually fire. The dynamic counterpart to the "
             "static surface meter. Runs untrusted code and needs a nightly toolchain, so this is "
             "CLI/CI only and opt-in. A race observed is proven; no race observed is bounded by the "
             "suite, never a proof of safety.",
    )
    parser.add_argument(
        "--prove",
        action="store_true",
        help="Prove located hazards: for each review-tier concurrency finding, ask a model to write a "
             "Rust test that reproduces the race, run it under the stress runner, and keep it only if it "
             "genuinely fires. Locate is deterministic; the model only fills a located gap; the execution "
             "gate decides. Needs OPENAI_API_KEY, cargo, and the openai package (pip install openai). "
             "Opt-in and CLI-only - it generates and runs code.",
    )
    parser.add_argument(
        "--prove-max",
        type=int,
        default=3,
        help="With --prove, the maximum number of located hazards to attempt (default 3).",
    )
    parser.add_argument(
        "--coverage-repair-rounds",
        type=int,
        default=3,
        help="With --prove-coverage, the max compiler-feedback repair rounds per gap: when a generated "
             "test does not compile, rustc's error is fed back to the model to rebuild the arrange step "
             "(construct the real argument values), up to this many times. Generic (the compiler is the "
             "oracle; no per-type knowledge), but each round is another in-crate compile - set 0 to skip "
             "repair and take only the first attempt.",
    )
    parser.add_argument(
        "--prove-coverage",
        default=None,
        metavar="MODULE",
        help="Prove coverage gaps for one Rust MODULE (a path relative to the repo, e.g. "
             "src/foo.rs): locate the module's uncovered decision branches, ask a model for a calling "
             "test per gap, run each in-crate under `cargo test`, and keep it only if it genuinely "
             "fails - a runnable test that closes the gap. Retained tests appear in the report's "
             "Adoptable proofs section. Native slop-audit; needs OPENAI_API_KEY, cargo, and "
             "cargo-llvm-cov. Opt-in and CLI-only (it runs code).",
    )
    parser.add_argument(
        "--report",
        nargs="?",
        const=".",
        default=None,
        metavar="DIR",
        help="Write the full Slop Audit report (the grade, verdict, audit checks, and concurrency "
             "layer - the way try.slopaudit.org renders it) as <slug>.md and <slug>.html into DIR "
             "(default the current directory).",
    )

    args = parser.parse_args(argv)

    if args.gate:
        return _run_gate(args.repo, args.lang, args.max_type_escapes, args.max_thread_exposed)

    results: dict[str, Any] = {}

    inds = [i.strip() for i in args.indicators.split(",")] if args.indicators != "all" else None

    # L1.1-8: git based, language agnostic
    if inds is None or any(i in ("1","2","3","4","5","6","7","8","all") for i in (inds or [])):
        git_results = indicators.compute_git_indicators(
            args.repo, since=args.since, until=args.until
        )
        results.update(git_results)

    # L1.9-11: config presence
    if inds is None or any(i in ("9","10","11","all") for i in (inds or [])):
        config_results = indicators.compute_config_indicators(args.repo)
        results.update(config_results)

    # L1.12-20: source based -> tree-sitter, plus the runtime L1.19/L1.20 harness
    if inds is None or any(i in ("12","13","14","15","16","17","18","19","20","all") for i in (inds or [])):
        source_results = indicators.compute_source_indicators(
            args.repo, lang=args.lang, exec_tests=not args.no_exec, timeout_seconds=args.timeout,
            classify_state_bounds=not args.no_state_bounds,
        )
        results.update(source_results)
        # Schedule-silence (static, cheap): of the flagged concurrency surface, which
        # files no loom/shuttle model touches. The concurrency form of Umbra's Silence.
        results["schedule_silence"] = schedule_silence.analyze(args.repo, str(results.get("lang", args.lang)))

    # Runtime thread-safety (opt-in): the dynamic counterpart to the static surface
    # meter. Runs untrusted code, so only on explicit --race, never by default.
    if args.race:
        from l1_analyzer import race_harness
        lang = str(results.get("lang", args.lang))
        race = race_harness.detect_races(args.repo, lang, args.timeout)
        surface_files = {f["file"] for f in results.get("thread_surface", {}).get("findings", [])}
        race["confirmed_surface"] = race_harness.confirmed_surface(race["findings"], surface_files)
        results["race"] = race

    # Prove (opt-in): locate -> generate -> run -> retain, in one command. Generates and
    # runs code, so CLI-only and explicit.
    if args.prove:
        results["proofs"] = _run_prove(args.repo, str(results.get("lang", args.lang)),
                                       results.get("thread_surface"), args.prove_max, args.timeout)

    # Coverage-gap proofs (opt-in): locate -> propose -> render -> run in-crate -> retain
    # over one Rust module. Generates and runs code, so CLI-only and explicit.
    if args.prove_coverage:
        from l1_analyzer import coverage_prove
        results["coverage_proofs"] = coverage_prove.prove_coverage(
            args.repo, args.prove_coverage, cap=args.prove_max, timeout_seconds=args.timeout,
            repair_rounds=args.coverage_repair_rounds)

    # The full Slop Audit scorecard - the SAME card try.slopaudit.org renders, from the
    # same engine module (l1_analyzer.card). The one difference is the runtime layer: the
    # site never executes the repo's code and says so, while the CLI runs the test suite by
    # default, so ran_tests carries that fact into the card (measured L1.19 coverage + L1.20
    # determinism, and a footer that says the tests were run). --no-exec flips it back.
    slug = args.repo.name or str(args.repo)
    ran_tests = not args.no_exec
    model = card.build_card(slug, str(results.get("lang", args.lang)), results, ran_tests=ran_tests)

    if args.report is not None:
        out_dir = Path(args.report)
        out_dir.mkdir(parents=True, exist_ok=True)
        base = slug.replace("/", "-")
        (out_dir / f"{base}.md").write_text(card.card_markdown(model))
        (out_dir / f"{base}.html").write_text(card.card_html(model))
        print(f"wrote {out_dir / (base + '.md')} and {out_dir / (base + '.html')}")

    if args.format == "json":
        # Provenance: record which mode produced this, so a result is never
        # ambiguous about whether the additive L1.18b classifier was active.
        envelope = {
            "repo": str(args.repo),
            "state_bounds": "off" if args.no_state_bounds else "on",
            "results": results,
        }
        print(json.dumps(envelope, indent=2))
    else:
        print(card.card_markdown(model))
        # Runtime results (race / prove) are not part of the static report; append them.
        race = results.get("race")
        if isinstance(race, dict):
            print(f"\n## Thread-safety race (runtime/{race['tool']}) — {race['verdict']}\n\n{race['details']}")
            for f in race["findings"]:
                mark = " [confirms flagged surface]" if f in race.get("confirmed_surface", []) else ""
                print(f"- race at `{f['file']}:{f['line']}` in {f['symbol']}{mark}")
        proofs = results.get("proofs")
        if isinstance(proofs, dict):
            print(f"\n## Prove (locate → generate → run → retain) — {proofs['verdict']} "
                  f"({proofs.get('demonstrated', 0)}/{proofs.get('attempted', 0)} demonstrated)")
            for o in proofs.get("outcomes", []):
                print(f"- `{o['file']}:{o['line']}` {o['symbol']}: {o['verdict']} — {o['detail']}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
