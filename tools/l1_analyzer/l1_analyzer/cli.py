"""CLI for slop-audit-l1 analyzer.

Run against any repo (language auto-detected or specified).
Example:
  uv run --project . slop-audit-l1 /path/to/repo --since 2025-01-01
  uv run --project . slop-audit-l1 /path/to/repo --indicators 1,18 --lang python
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from l1_analyzer import (
    card,
    indicators,
    interleaving_robustness,
    prove,
    report,
    thread_surface,
)
from l1_analyzer.incomplete import IncompleteCode
from l1_analyzer.indicators import detect_primary_language
from l1_analyzer.scope import PRODUCTION

# Why the thread-safety meter has no reading, by the verdict it returned instead of one. A
# dict rather than a chain of ifs, and one entry per way of not reading, so a new way added to
# the meter shows up here as a missing key.
#
# READ BY SUBSCRIPT, and the first version of this was not. It used `.get(verdict, "the meter
# returned no verdict")` while its own comment promised a missing key would show up, which is
# the opposite of what a default does: a new verdict would have been filed under a plausible
# sentence about a measurement that did not happen. The default was dead as well as wrong,
# because `_verdict_of` returns "n/a" when a panel entry carries no verdict at all and
# NO_SCANNER is "n/a", so the two cases arrive here as one string and the third branch could
# never fire. That collision is real and is filed separately; it is not repaired by a default
# that hides it.
# The absent-verdict case, named so it stops colliding with NO_SCANNER. Both used to be
# the bare string "n/a": thread_surface says "n/a" for a language it has no scanner for,
# and `_verdict_of` said "n/a" for a panel entry carrying no verdict at all. The gate then
# told an adopter their language has no scanner when what happened was that the meter
# returned nothing, which sends them looking for a scanner that exists.
#
# Deliberately not "n/a". A distinct fact needs a distinct string, and reusing the token
# with a comment saying which one it means is how the collision was written the first time.
ABSENT_VERDICT = "absent-verdict"

_UNMEASURED_THREAD_SURFACE = {
    thread_surface.UNREAD: "the meter read no source",
    thread_surface.NO_SCANNER: "no scanner for this language",
    ABSENT_VERDICT: "the meter returned no verdict for this language",
}


def _count_type_escapes(repo: Path, lang: str) -> int:
    """Count the analyzer's own type-escape hatches (the Any token, # type: ignore
    comments, suppression annotations), the same way L1.15 does, so the gate can ratchet
    on the raw number rather than a per-kLOC density.

    The whole vocabulary travels in `cfg`, so the gate cannot count by an older rule than
    the indicator it is meant to enforce."""
    cfg = indicators.LANG_CFG.get(lang)
    if cfg is None or not cfg["type_escape_patterns"]:
        return 0
    parser = indicators._get_parser(lang)
    files, _skipped = indicators._read_source_bytes(repo, cfg["extensions"], scope=PRODUCTION)
    return sum(indicators._count_type_escapes_in_tree(parser.parse(src).root_node, cfg) for _path, src in files)


def _slack(actual: int, baseline: int, label: str) -> list[str]:
    """A baseline looser than reality is slack, and slack is a defect.

    A ratchet set at 4 against 0 actual findings passes silently and leaves room for four
    free regressions. Nobody notices, because the gate only ever looks upward. So the
    ratchet has to be tight in both directions: fixing the findings obliges you to lower
    the number, in the same reviewable edit that raising it would take.

    Borrowed from declaro-persistum, whose KNOWN_ORPHANS list carries a companion test,
    `test_the_allowlist_does_not_outlive_what_it_excuses`, that fails when an entry no
    longer excuses anything. An exemption that outlives its reason is the shape this
    codebase keeps finding, and that is a mechanical answer to it.
    """
    if actual >= baseline:
        return []
    return [(f"{label}: the ratchet is set at {baseline} and the repo has {actual}. "
             f"Lower it to {actual} in .pre-commit-config.yaml. A baseline above the real "
             f"count is {baseline - actual} regression(s) nobody will be told about.")]


def _verdict_of(result: object) -> str:
    """A panel entry's verdict, or ABSENT_VERDICT when it carries none.

    Not "n/a", which is what thread_surface says for a language it has no scanner for.
    The two are different facts and shared one string until 2026-08-18, so the gate could
    not tell them apart and printed the scanner sentence for both.

    The panel is typed `dict[str, L1Result]` and L1Result declares only value, band and
    details, so the richer results stored in it - the surface scan among them - are read
    across a gap that predates this function. Reading through `object` keeps the gap where
    it is instead of widening it to Any or papering over it with a type: ignore, either of
    which this repository's own L1.15 ratchet counts against it.
    """
    return str(result["verdict"]) if isinstance(result, dict) and "verdict" in result else ABSENT_VERDICT


def _audited_language(results: dict, requested: str, repo: Path) -> str:
    """The language the audit actually read, settled once.

    Six places spelled `str(results.get("lang", requested))`. Two things were wrong with
    the copy. It is six spellings of one question, so a change to how the language is
    settled reaches only the ones somebody remembers. And its fall-through is the
    REQUESTED language, which is `auto` by default: a run that skipped the source pass
    handed the literal string "auto" to the race harness and the prove loop, which then
    reported that "auto" is a language they do not support yet.

    detect_primary_language is what settles it, and the source pass already calls it. When
    no source pass ran, this calls it too. An explicit `--lang rust` with no source pass is
    an instruction rather than a guess, so it stands."""
    settled = results.get("lang")
    if settled is not None:
        return str(settled)
    return detect_primary_language(repo) if requested == "auto" else requested


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
    audited_lang = _audited_language(results, lang, repo)
    problems: list[str] = []

    # `results.get` is the real absence: an indicator the source pass did not run is not in
    # the panel. Past that, L1Result is total and the analyzer's verdict counts carry all
    # three verdicts, so the fields are subscripted rather than defaulted.
    l17 = results.get("L1.17")
    if isinstance(l17, dict) and isinstance(l17["value"], (int, float)) and l17["value"] > 0:
        problems.append(f"god-file (L1.17): {l17['details']}")

    l18b = results.get("L1.18b")
    counts = l18b["counts"] if isinstance(l18b, dict) else {"promiscuous": 0}
    if counts["promiscuous"] > 0:
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
        problems.extend(_slack(escapes, max_type_escapes, "type escapes (L1.15)"))

    # Thread-safety surface ratchet (opt-in via --max-thread-exposed): the count of
    # hand-overrides of the compiler's thread-safety guarantee (unsafe impl Send/Sync,
    # static mut) must not exceed the baseline. Like the type-escape ratchet, this is a
    # bright line at the current number, not a density band: a NEW override fails the
    # commit unless the baseline is raised deliberately. It is a fact about surface, not
    # a race claim - the meter never says "safe". n/a for a language with no scanner
    # (so it is a no-op on a Python repo until the Python scanner lands).
    #
    # The ratchet is skipped, not passed, when the meter read nothing. Zero overrides over
    # no source is not zero overrides, and worse, the downward arm below would then demand
    # the baseline be lowered to 0 on the strength of a reading that never happened - the
    # ratchet would ratchet itself open. `thread_ratchet` records which of the two the pass
    # line is reporting, so it says "not measured" rather than "0/N".
    exposed: int | None = None
    thread_ratchet = ""
    if max_thread_exposed is not None:
        ts = results.get("thread_surface") or thread_surface.scan(repo, audited_lang)
    # a race claim - the meter never says "safe". Python, Rust, Go, Java, Ruby, TypeScript
    # and JavaScript have a scanner; C, C# and any language the detector does not recognise
    # have none, and there the meter reads nothing at all.
    #
    # The ratchet is skipped, not passed, when the meter read nothing. Zero overrides over
    # no source is not zero overrides, and worse, the downward arm below would then demand
    # the baseline be lowered to 0 on the strength of a reading that never happened - the
    # ratchet would ratchet itself open. `thread_ratchet` records which of the two the pass
    # line is reporting, so it says "not measured" rather than "0/N".
    #
    # `thread_surface.measured` is asked, rather than the verdict compared against UNREAD.
    # That comparison named ONE of the three ways of not reading and let the other two
    # through: until 2026-08-16 a C repository printed "0/0 thread-safety overrides", and at
    # a baseline of 4 it failed the commit demanding the baseline be lowered to zero.
    exposed: int | None = None
    thread_ratchet = ""
    if max_thread_exposed is not None:
        ts = results.get("thread_surface") or thread_surface.scan(repo, audited_lang)
        if thread_surface.measured(ts):
            exposed = ts["counts"].get(thread_surface.EXPOSED, 0)
            thread_ratchet = f", {exposed}/{max_thread_exposed} thread-safety overrides"
        else:
            why = _UNMEASURED_THREAD_SURFACE[_verdict_of(ts)]
            thread_ratchet = f", thread-safety surface not measured ({why})"
        if exposed is not None and exposed > max_thread_exposed:
            problems.append(
                f"thread-safety surface: {exposed} hand-overrides of the thread-safety guarantee "
                f"(unsafe impl Send/Sync, static mut), over the ratchet of {max_thread_exposed}. "
                "This is not a race verdict - it is new audit surface. Verify the override holds "
                "under free-threading; if it is sound, raise the baseline in .pre-commit-config.yaml "
                "as a deliberate, reviewable change."
            )
        if exposed is not None:
            problems.extend(_slack(exposed, max_thread_exposed, "thread-safety surface"))

    if problems:
        print("Slop audit gate FAILED - the audit flags this repo's own code:")
        for p in problems:
            print(f"  - {p}")
        print("Fix the above (split the file, resolve the state, type the escape) before committing.")
        return 1
    ratchet = "" if escapes is None else f", {escapes}/{max_type_escapes} type escapes"
    ratchet += thread_ratchet
    # The pass line reports what the gate CHECKED, not a property it inferred from an empty
    # count. "Finitely testable" was the same manufactured claim the card was making: zero
    # promiscuous findings is the bright line, and on a repository the classifier never read
    # it is zero of nothing. The gate still passes - no proven unbounded state is a real
    # result and the bright line is a proof, not a survey - but it says which of the two it
    # got. The census supplies the denominator that tells them apart.
    census = (results.get("L1.18b") or {}).get("census")
    if report.census_unread(census):
        declared = census.get("declared") if isinstance(census, dict) else 0
        one = declared == 1
        state = (f"no proven unbounded state, but the state classifier reached no verdict "
                 f"({'the' if one else 'all'} {declared} "
                 f"{'declaration' if one else 'declarations'} here "
                 f"{'is' if one else 'are'} {report.unread_kinds_phrase(census)}, which it has "
                 f"no rule for), so finite testability is unmeasured")
    else:
        state = "finitely testable"
    print(f"Slop audit gate passed: 0 production god-files, {state}{ratchet}.")
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
        return {"verdict": "n/a", "detail": "needs ANTHROPIC_API_KEY to generate proofs", "demonstrated": 0, "outcomes": []}
    ts = thread_surface_result if isinstance(thread_surface_result, dict) else thread_surface.scan(repo, lang)
    # SurfaceResult and its Finding are both total, and `ts` above is either a scan result
    # or a fresh scan, so both reads are guaranteed. A default here would have quietly
    # proven nothing on a malformed surface rather than saying it could not read one.
    candidates = [f for f in ts["findings"] if f["severity"] == "review"][:prove_max]
    work_root = Path(tempfile.mkdtemp(prefix="l1-prove-"))
    outcomes: list[prove.ProofRecord] = []
    for i, f in enumerate(candidates):
        request = prove.proof_request(f, _hazard_context(repo, f))
        outcome = prove.prove_hazard(request, str(work_root / f"proof-{i}"), timeout_seconds=timeout)
        # Keep the generated test on the outcome so the card can expose a retained (demonstrated)
        # proof as an adoptable test - the runnable repro, not just a verdict line.
        recorded: prove.ProofRecord = {
            "file": f["file"], "line": f["line"], "symbol": f["symbol"],
            "verdict": outcome["verdict"], "detail": outcome["detail"],
            "generated_test": outcome.get("generated_test"),
        }
        outcomes.append(recorded)
    demonstrated = sum(o["verdict"] == prove.DEMONSTRATED for o in outcomes)
    return {"verdict": "demonstrated" if demonstrated else "none",
            "demonstrated": demonstrated, "attempted": len(outcomes), "outcomes": outcomes}


def main(argv: list[str] | None = None) -> int:
    # The name the console script is installed under, so `--help` prints a command the
    # reader can actually run. argparse defaults `prog` to sys.argv[0], which is right
    # only by accident; naming it wrong sends a new adopter to a command that does not
    # exist, at the moment they are most likely to trust the output.
    parser = argparse.ArgumentParser(prog="slop-audit-l1")
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
        "--python",
        default=None,
        metavar="PATH",
        help="Interpreter that runs the target suite for L1.19/L1.20. Defaults to the analyzer's "
             "own interpreter; point it at the target repo's venv python when the target needs a "
             "different Python (e.g. a 3.11 target audited from a 3.12+ analyzer). The target "
             "package must be importable there, or coverage/determinism report n/a with the reason.",
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
             "gate decides. Needs ANTHROPIC_API_KEY, cargo, and the anthropic package (pip install anthropic). "
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
        "--prove-coverage-repo",
        action="store_true",
        help="Prove coverage gaps across the ENTIRE Rust crate: one coverage build, then every module "
             "with uncovered branches is swept (batched into one compile per module, with per-gap repair "
             "fallback). Retained proofs from all modules land in the report's Adoptable proofs section. "
             "Long-running (one build per module); native slop-audit; needs ANTHROPIC_API_KEY, cargo, "
             "cargo-llvm-cov. --prove-max caps gaps per module.",
    )
    parser.add_argument(
        "--prove-coverage",
        default=None,
        metavar="MODULE",
        help="Prove coverage gaps for one Rust MODULE (a path relative to the repo, e.g. "
             "src/foo.rs): locate the module's uncovered decision branches, ask a model for a calling "
             "test per gap, run each in-crate under `cargo test`, and keep it only if it genuinely "
             "fails - a runnable test that closes the gap. Retained tests appear in the report's "
             "Adoptable proofs section. Native slop-audit; needs ANTHROPIC_API_KEY, cargo, and "
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

    # The analyzer audits a repository (a directory), not a single file: the git, config,
    # coverage, and test-run steps all operate on a tree. A file argument used to reach the
    # coverage runner and crash with a stack trace; give a clear message instead.
    if not args.repo.exists():
        print(f"error: path does not exist: {args.repo}", file=sys.stderr)
        return 2
    if not args.repo.is_dir():
        print(f"error: point me at a directory (a repo root), not a single file: {args.repo}", file=sys.stderr)
        return 2

    if args.gate:
        return _run_gate(args.repo, args.lang, args.max_type_escapes, args.max_thread_exposed)

    # object, not Any: the panel holds L1Result dicts beside the detected language
    # string and the additive payloads, and a reader must narrow before use.
    results: dict[str, object] = {}

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
            classify_state_bounds=not args.no_state_bounds, python_executable=args.python,
        )
        results.update(source_results)
        # Interleaving robustness (static, cheap): of the flagged concurrency surface,
        # which files no loom/shuttle model touches. Named for what it measures rather
        # than for silence, which this instrument reserves for what the analyzer could
        # not read.
        results["interleaving_robustness"] = interleaving_robustness.analyze(
            args.repo, _audited_language(results, args.lang, args.repo))

    # Runtime thread-safety (opt-in): the dynamic counterpart to the static surface
    # meter. Runs untrusted code, so only on explicit --race, never by default.
    if args.race:
        from l1_analyzer import race_harness
        lang = _audited_language(results, args.lang, args.repo)
        race = race_harness.detect_races(args.repo, lang, args.timeout)
        surface = results.get("thread_surface")
        # The panel may not carry a surface scan at all, which is a real absence; a scan
        # that IS there carries its findings, so only the first step defaults.
        surface_files = {f["file"] for f in surface["findings"]} if isinstance(surface, dict) else set()
        race["confirmed_surface"] = race_harness.confirmed_surface(race["findings"], surface_files)
        results["race"] = race

    # Prove (opt-in): locate -> generate -> run -> retain, in one command. Generates and
    # runs code, so CLI-only and explicit.
    if args.prove:
        results["proofs"] = _run_prove(args.repo, _audited_language(results, args.lang, args.repo),
                                       results.get("thread_surface"), args.prove_max, args.timeout)

    # Coverage-gap proofs (opt-in): locate -> propose -> render -> run in-crate -> retain.
    # Generates and runs code, so CLI-only and explicit. --prove-coverage-repo sweeps the
    # whole crate; --prove-coverage does one module.
    if args.prove_coverage_repo:
        def _cov_progress(relpath: str, n_gaps: int, retained: int) -> None:
            print(f"[prove-coverage] {relpath}: {n_gaps} gap(s), retained so far {retained}",
                  file=sys.stderr, flush=True)
        if _audited_language(results, args.lang, args.repo) == "python":
            from l1_analyzer import python_coverage_prove
            results["coverage_proofs"] = python_coverage_prove.prove_coverage_repo(
                args.repo, cap_per_module=args.prove_max, repair_rounds=args.coverage_repair_rounds,
                timeout_seconds=args.timeout, python_executable=args.python, progress=_cov_progress)
        else:
            from l1_analyzer import coverage_prove
            results["coverage_proofs"] = coverage_prove.prove_coverage_repo(
                args.repo, cap_per_module=args.prove_max, repair_rounds=args.coverage_repair_rounds,
                timeout_seconds=args.timeout, progress=_cov_progress)
    elif args.prove_coverage:
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
    # The card is the last boundary, and a refusal has to reach the reader as a refusal. It
    # must not become a grade, a percentage or a headline, because the whole reason the
    # measures raise is that every earlier attempt to render "we read nothing" ended up
    # rendering it as "we read everything and it was clean". Exit 2: not a crash, not a pass.
    try:
        model = card.build_card(slug, _audited_language(results, args.lang, args.repo), results, ran_tests=ran_tests)
    except IncompleteCode as refusal:
        print(f"\n{refusal}\n\nNo grade is issued. The analyzer has no rule for what this "
              f"repository contains, so any letter it printed would be about its own blind "
              f"spot rather than about the code.", file=sys.stderr)
        return 2

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
