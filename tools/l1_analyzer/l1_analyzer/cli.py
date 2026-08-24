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
    thread_surface,
)
from l1_analyzer.boundary import boundary, text_or_empty
from l1_analyzer.gate import _audited_language, _run_gate
from l1_analyzer.incomplete import IncompleteCode

# Which indicators each stage computes. One table, read by the branches below.
#
# These were three literal tuples inside three `if` conditions, so nothing held the set of
# valid indicators and nothing could refuse a value outside it. `--indicators banana`
# selected no stage, produced an empty panel and exited 0, and a caller could not tell that
# from an audit that ran and found nothing. An input space left open by a dispatch that
# reads closed is L1.21.18, and this tool reports that clause against other people's code.
_GIT_INDICATORS = frozenset({"1", "2", "3", "4", "5", "6", "7", "8"})
_CONFIG_INDICATORS = frozenset({"9", "10", "11"})
_SOURCE_INDICATORS = frozenset({"12", "13", "14", "15", "16", "17", "18", "19", "20"})

INDICATORS = _GIT_INDICATORS | _CONFIG_INDICATORS | _SOURCE_INDICATORS


def _selected_indicators(given: str) -> frozenset[str] | None:
    """The indicators the caller asked for, or None for every one of them.

    Refuses a value no stage can run. Exiting 0 with an empty panel told a caller their
    audit found nothing, when what happened is that nothing recognised what they typed."""
    if given == "all":
        return None
    asked = frozenset(part.strip() for part in given.split(",") if part.strip())
    unknown = sorted(asked - INDICATORS)
    if unknown or not asked:
        # Printed here rather than carried on the exception. A message riding on SystemExit
        # is shown by the interpreter, so anything embedding this CLI gets the exit code
        # and no reason at all.
        print(f"--indicators: cannot run {', '.join(unknown) or 'an empty list'}. "
              f"It takes bare numbers or 'all', so L1.17 is written 17. "
              f"Known: {', '.join(sorted(INDICATORS, key=int))}.", file=sys.stderr)
        raise SystemExit(2)
    return asked

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


def _hazard_context(repo: Path, finding: dict[str, object]) -> str:
    """The code around a located hazard, handed to the generator as the only context."""
    located = (f"Located hazard: {finding['kind']} on `{finding['symbol']}` at "
               f"{finding['file']}:{finding['line']}.")
    text = text_or_empty(repo / finding["file"])
    if not text:
        return located
    return f"{located}\nSurrounding Rust source:\n{window_around(text.splitlines(), finding['line'])}"


def window_around(lines: list[str], line: int) -> str:
    """The thirty lines either side of one, clipped to what the file holds.

    Lifted out of the reader above, which read a file and then chose from it in one
    function, so a question as small as what a hazard near the top of a five-line file looks
    like needed a temporary directory to ask."""
    low, high = max(0, line - 30), min(len(lines), line + 30)
    return "\n".join(lines[low:high])


def _run_prove(repo: Path, lang: str, thread_surface_result: object, prove_max: int, timeout: float) -> dict[str, object]:
    """Locate -> generate -> run -> retain over the review-tier findings. Deterministic
    locate; the model only fills a located gap; the execution gate keeps only what fires."""
    import tempfile

    from l1_analyzer import prove
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
        # The real collaborators, named here because this is the boundary that knows a run
        # is meant to spend money and build a crate. They used to be defaults inside
        # prove_hazard, one forgotten argument away from any test.
        work = str(work_root / f"proof-{i}")
        outcome = prove.prove_hazard(
            request,
            prove.generate,
            lambda test, at=work: prove.write_crate_and_stress(test, at, 100, timeout),
        )
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


_OUTSIDE_THE_INDEX = (
    ("undeclared_domain", "undeclared domains",
     ("Closed by declaring a type, not by adding a test, so these are not counted in the "
      "Silence index.")),
    ("honesty_unverified", "properties that could not be verified",
     ("The audit could not determine these safely, so no test could have shown them. They "
      "are outside the Silence index rather than charged to the suite, and each carries "
      "the reason verification was not possible.")),
)


def _report_facets(module: Path, tests: tuple[Path, ...], output_format: str,
                   proof_cap: int) -> int:
    """One module's closeable facets, printed for a reader or as JSON.

    Several test files are read as one body of evidence, because a suite split across two
    files is still one suite and reading only the first reports the other as absent."""
    from l1_analyzer import facets, proof

    audit = facets.audit(module, tests)
    # Nothing is asked for unless the caller sets a cap. A request is what gets sent to a
    # model, so how many are made is their decision about money and about what leaves the
    # machine, not a default chosen here.
    asked = proof.requests(audit, proof_cap)
    if output_format == "json":
        print(json.dumps({**audit, "proof_requests": asked}, indent=2, default=str))
        return 0

    coverage = f"{audit['coverage_percent']}%" if audit["coverage_measured"] else "not measured"
    index = f"{audit['silence_index']}%" if audit["silence_index"] is not None else "not measured"
    print(f"# Facets — {module.name} against {', '.join(t.name for t in tests)}")
    print(f"_slop-audit-l1 {version()}_\n")
    print(f"Coverage: {coverage} | Silence index: {index}")
    print(f"{audit['closeable_silence_sites']} of {audit['total_checkable_facets']} closeable "
          f"facets lack evidence\n")
    if audit["unusable_reason"]:
        print(f"> {audit['unusable_reason']}\n")
    for kind in facets.FACET_KINDS:
        silent = [f for f in audit["facets"] if f["kind"] == kind and f["silent"]]
        if not silent:
            continue
        print(f"## {kind.replace('_', ' ')} ({len(silent)})\n")
        for facet in silent:
            print(f"- `{facet['function']}:{facet['line']}` — {facet['detail']}")
        print()
    # Both of these sit outside the Silence index, numerator and denominator, and for
    # different reasons a reader has to be able to tell apart. One is a gap in the
    # signature the author closes; the other is a gap in what the audit could see.
    for kind, heading, why in _OUTSIDE_THE_INDEX:
        gaps = [g for g in audit["undeclared"] if g["kind"] == kind]
        if not gaps:
            continue
        print(f"## {heading} ({len(gaps)})\n")
        print(f"> {why}\n")
        for gap in gaps:
            print(f"- `{gap['function']}:{gap['line']}` — {gap['detail']}")
        print()
    if asked:
        print(f"## proof requests ({len(asked)})\n")
        print("> Each carries one signature and one gap, and no source. Write the test "
              "yourself and run it through `--prove-facet MODULE TESTS INDEX INPUT "
              "PROPERTY WHY`; only a test that FAILS is retained.\n")
        for request in asked:
            print(f"- [{request['index']}] `{request['function']}:{request['line']}` — "
                  f"{request['detail']}")
            print(f"      `{request['signature']}`")
            print(f"      {request['instruction']}")
        print()
    return 0


def _report_honest_code(paths: list[Path], output_format: str) -> int:
    """L1.21 for the files named, in whichever of the three shapes the caller asked for.

    Several files are measured in ONE process, which is the whole saving. The analysis
    costs about nothing: on a small file a real run takes as long as `--help`, so the bill
    is interpreter startup plus tree-sitter grammars for nine languages, and paying it once
    for twenty files instead of twenty times is the difference between two seconds and
    seventy milliseconds.

    One file returns exactly what it always returned, JSON object and all. A consumer
    already reads that shape, and changing it to serve the batch case would break a working
    integration to add a feature.

    The hook shape is the default because it is the one that runs thousands of times. It
    writes to stderr, where a hook runner puts what a blocked tool call said, and it writes
    nothing when there is nothing to change."""
    from l1_analyzer import honest_code

    assessments = [honest_code.assess_file(path) for path in paths]
    # A broken clause exits non-zero in every shape, not only the hook's. L1.21 is opt-in
    # and states an opinion, so running it and finding a violation IS the gate failing,
    # which is what exit 1 has always meant here. The hook shape already did this and the
    # other two returned 0 while printing violations, so a caller could not gate on them.
    broken = any(c["decided"] and c["findings"] for a in assessments for c in a["clauses"])
    if output_format == "json":
        one = assessments[0] if len(assessments) == 1 else assessments
        print(json.dumps(one, indent=2, default=str))
        return 1 if broken else 0
    if output_format == "text":
        for assessment in assessments:
            print(honest_code.report(assessment))
        return 1 if broken else 0

    lines: list[str] = []
    for path, assessment in zip(paths, assessments):
        if assessment["unreadable_reason"]:
            lines.append(f"{path}: {assessment['unreadable_reason']}")
            continue
        printed = honest_code.hook_report(assessment)
        if printed:
            lines.append(printed)
    if not lines:
        return 0
    print("\n".join(lines), file=sys.stderr)
    return 1


def _report_call_map(module: Path, tests: tuple[Path, ...], layer: str) -> int:
    """The module's four-column map, as a `.hd` file on stdout.

    It runs the watch, because the violation this map exists to show is a write in the pure
    lane and reading the source alone can only guess at one."""
    import ast

    from l1_analyzer import callmap, runtime_probe

    source = text_or_empty(module)
    seen = runtime_probe.watch(module, tests)
    watched = runtime_probe.verdicts(seen["observations"])
    roles = callmap.classify(ast.parse(source), watched)
    if seen["reason"]:
        print(f"# the suite could not be watched, so no write is charged to the pure lane: "
              f"{seen['reason']}")
    print(callmap.render(roles, module.stem, layer))
    return 0


def _prove_facet(module: Path, tests: tuple[Path, ...], index: int, proposal: dict,
                 output_format: str) -> int:
    """Run one caller-written proposal through the execution gate.

    A separate command from `--facets` on purpose. One command would have to write the test
    itself, and a tool that both proposes and accepts its own proposal has no gate."""
    from l1_analyzer import facets, proof

    audit = facets.audit(module, tests)
    asked = proof.requests(audit, index + 1)
    request = next((r for r in asked if r["index"] == index), None)
    if request is None:
        print(f"no proof request carries index {index}; this audit made {len(asked)}. "
              "Run --facets with --proof-cap to see them.")
        return 1

    verdict = proof.verify(module, request, proposal)
    if output_format == "json":
        print(json.dumps({**verdict, "request": request}, indent=2, default=str))
        return 0

    state = "RETAINED" if verdict["retained"] else "DISCARDED"
    print(f"# Proof {index} — {request['function']}:{request['line']} — {state}\n")
    print(f"{verdict['outcome']}: {verdict['reason']}\n")
    if verdict["rendered"]:
        print("```python")
        print(verdict["rendered"].rstrip())
        print("```")
        print("\nNothing was written into your test file. Adopting this is your decision.")
    return 0


def version() -> str:
    """Which build this is, from the installed package metadata.

    One source. A constant here would be a second owner of the same fact with nothing
    checking the two agreed, which is the shape that let an adopter ship a release the
    marketplace never served while `plugin update` reported the plugin current.

    A measurement that cannot name the build behind it cannot be cited later, and the bands
    and the denominators in this instrument have both moved under readers before."""
    from importlib import metadata

    return metadata.version("slop-audit-l1")


def run() -> int:
    """The console-script entry point.

    setuptools calls the installed script with no arguments, so something here has to be
    callable with none. That is this, and it is one line: it reads the process arguments
    and hands them to `main`, which now requires them.

    `main(argv=None)` used to be that callable itself, and the default meant every other
    caller could omit the argument too, so nothing distinguished a caller who meant the
    process arguments from one who forgot to say."""
    return main(sys.argv[1:])


@boundary
def main(argv: list[str] | None) -> int:
    """The command line, and the only thing in this package that IS one.

    Declared rather than split, because there is nothing here to lift out:
    argparse in, exit code out, and every decision already lives in a module
    this calls."""
    # The name the console script is installed under, so `--help` prints a command the
    # reader can actually run. argparse defaults `prog` to sys.argv[0], which is right
    # only by accident; naming it wrong sends a new adopter to a command that does not
    # exist, at the moment they are most likely to trust the output.
    parser = argparse.ArgumentParser(prog="slop-audit-l1")
    # Optional, because the single-file modes do not audit a repository. --honest-code runs
    # behind a write hook, and making a hook name a repository it does not read would be
    # ceremony on every write.
    parser.add_argument("repo", type=Path, nargs="?", default=None,
                        help="Path to git repository root")
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
    # None rather than "text", so a mode can tell "the caller asked for text" from "the
    # caller asked for nothing". --honest-code answers the second with its hook shape,
    # which is the one that runs thousands of times.
    parser.add_argument("--format", choices=["text", "json", "hook"], default=None)
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
        "--max-honest-code",
        type=int,
        default=None,
        help="Ratchet the Honest Code conformity check: with --gate, fail if L1.21's clause "
             "findings exceed this baseline. Opt-in, because L1.21 states an opinion and "
             "grades nobody who has not chosen it. Set it to the current count so a NEW "
             "violation fails the commit. No effect without --gate.",
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
        help="With --prove, the maximum number of located hazards to attempt (default 3). "
             "With --prove-coverage-repo it is the per-MODULE cap: how many gaps one module "
             "may offer.",
    )
    parser.add_argument(
        "--prove-max-total",
        type=int,
        default=5,
        help="With --prove-coverage-repo, the total gaps the whole run may hand to a model "
             "(default 5). The per-module cap and this one bound different things: five per "
             "module over forty modules is two hundred attempts, and this is what stops that. "
             "A sweep that stops here says so in its own report.",
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
        "--version",
        action="store_true",
        help="Print which build this is and exit. Every panel and every card carries the "
             "same string, so a measurement can be traced to the instrument that made it.",
    )
    parser.add_argument(
        "--honest-code",
        nargs="+",
        default=None,
        metavar="FILE",
        help="L1.21 for one or more files: mechanical conformity with the nineteen Honest Code "
             "principles, one subclause each. Built for a write hook, so it prints only "
             "what to change, prints it to stderr where a hook runner feeds it back, says "
             "nothing at all when the file is clean, and exits 1 when it is not. "
             "--format text gives the full per-clause report a person reads. Several files "
             "are measured in one process, which is the whole saving: the analysis costs "
             "about nothing and the bill is interpreter startup, paid once here instead of "
             "once per file. One file returns exactly what it always returned.",
    )
    parser.add_argument(
        "--honest-code-clauses",
        action="store_true",
        help="Add L1.21 to the full audit. Off by default: nineteen clauses over a large "
             "tree is a cost a caller chooses rather than one imposed on every run.",
    )
    parser.add_argument(
        "--call-map",
        nargs="+",
        default=None,
        metavar="PATH",
        help="Emit the four-column call-stack map for ONE module and its test file(s), as "
             "a `.hd` file. Roles are function prefixes: boundary_in reads a source, "
             "orchestrator composes, a bare fn is pure, boundary_out writes a target. A "
             "write in the pure lane is marked, and the charge rests on the watched run "
             "rather than on a guess, so a function nobody watched is not accused.",
    )
    parser.add_argument(
        "--layer",
        default="",
        choices=["", "foundation", "data", "domain", "ui", "tooling"],
        help="The layer to declare in the emitted .hd. Left out by default: a layer is an "
             "architectural intent and no reading of the source decides it.",
    )
    parser.add_argument(
        "--proof-cap",
        type=int,
        default=0,
        metavar="N",
        help="With --facets: ask for up to N isolated proof requests. Each carries one "
             "signature and one gap and no source, so what leaves this machine is a "
             "function's shape rather than a repository. Nothing is asked for by default, "
             "because a request is what gets sent to a model.",
    )
    parser.add_argument(
        "--prove-facet",
        nargs=6,
        default=None,
        metavar="ARG",
        help="Run one proposal through the execution gate: MODULE TESTS INDEX INPUT "
             "PROPERTY WHY. INDEX comes from --proof-cap. The proposal is rendered as one "
             "test and run alone; only a test that FAILS, or that makes the audited "
             "function raise, is retained. A passing test proves the opposite of the claim "
             "and is discarded. Nothing is written into your test file.",
    )
    parser.add_argument(
        "--facets",
        nargs='+',
        default=None,
        metavar="PATH",
        help="Audit ONE module against the test file(s) holding evidence about it: every "
             "closeable facet and the Silence "
             "index over them. Coverage records what ran; silence records evidence the suite "
             "lacks, so a branch that executed and was never asserted on is covered and silent "
             "at once. Reports unexercised branches, candidate input regions, unasserted return "
             "contracts and exception paths, and lists undeclared domains separately because "
             "those are closed by declaring a type rather than by adding a test.",
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

    if args.facets:
        # A different unit of audit from the panel, and it returns before the repository
        # checks below: this takes one module and the test file that is supposed to hold
        # evidence about it, so the "point me at a directory" rule does not apply and the
        # twenty indicators have nothing to say about which function is silent.
        if len(args.facets) < 2:
            parser.error("--facets takes a module and at least one test file")
        # Checked here, at the boundary, because a path that is not there used to reach the
        # reader and come back as a stack trace.
        missing = [p for p in args.facets if not Path(p).is_file()]
        if missing:
            parser.error("--facets needs files that exist: " + ", ".join(missing))
        return _report_facets(Path(args.facets[0]),
                              tuple(Path(t) for t in args.facets[1:]), args.format,
                              args.proof_cap)

    if args.version:
        # Before every path check: it answers a question about the tool rather than about a
        # tree, so requiring a repository would ask for something the answer never uses.
        print(f"slop-audit-l1 {version()}")
        return 0

    if args.honest_code:
        # Before the repository checks, and before --format is defaulted: this takes ONE
        # file, and a bare invocation gets the hook shape.
        # Returns before the repository checks: this takes ONE file, because it runs behind
        # a hook that fires on every write and the panel has nothing to say about the file
        # an agent just saved.
        # Every path is checked before any is measured. A run that quietly skipped a
        # missing one and measured the rest would report a coverage it did not have, and a
        # caller who named a file that is not there has a different problem from one whose
        # file is clean.
        missing = [p for p in args.honest_code if not Path(p).is_file()]
        if missing:
            parser.error("--honest-code needs files that exist: " + ", ".join(missing))
        return _report_honest_code([Path(p) for p in args.honest_code], args.format or "hook")

    args.format = args.format or "text"

    if args.call_map:
        module, *tests = args.call_map
        for path in args.call_map:
            if not Path(path).is_file():
                parser.error(f"--call-map needs files that exist: {path}")
        return _report_call_map(Path(module), tuple(Path(t) for t in tests), args.layer)

    if args.prove_facet:
        module, tests, index, argument, expected, why = args.prove_facet
        for path in (module, tests):
            if not Path(path).is_file():
                parser.error(f"--prove-facet needs files that exist: {path}")
        if not index.lstrip("-").isdigit():
            parser.error("--prove-facet takes the request INDEX as a number")
        return _prove_facet(Path(module), (Path(tests),), int(index),
                            {"concrete_input": argument, "expected_property": expected,
                             "plain_explanation": why}, args.format)

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
        return _run_gate(args.repo, args.lang, args.max_type_escapes,
                         args.max_thread_exposed, args.max_honest_code)

    # object, not Any: the panel holds L1Result dicts beside the detected language
    # string and the additive payloads, and a reader must narrow before use.
    results: dict[str, object] = {}

    inds = _selected_indicators(args.indicators)

    # L1.1-8: git based, language agnostic
    if inds is None or inds & _GIT_INDICATORS:
        git_results = indicators.compute_git_indicators(
            args.repo, since=args.since, until=args.until
        )
        results.update(git_results)

    # L1.9-11: config presence
    if inds is None or inds & _CONFIG_INDICATORS:
        config_results = indicators.compute_config_indicators(args.repo)
        results.update(config_results)

    # L1.12-20: source based -> tree-sitter, plus the runtime L1.19/L1.20 harness
    if inds is None or inds & _SOURCE_INDICATORS:
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

    # L1.21 (opt-in): nineteen clauses of Honest Code conformity. Off by default because
    # nineteen clauses over a large tree is a cost a caller chooses rather than one imposed
    # on every run.
    if args.honest_code_clauses:
        from l1_analyzer import honest_code
        results["honest_code"] = honest_code.analyze(
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
                timeout_seconds=args.timeout, python_executable=args.python,
                progress=_cov_progress, max_attempts=args.prove_max_total)
        else:
            from l1_analyzer import coverage_prove
            results["coverage_proofs"] = coverage_prove.prove_coverage_repo(
                args.repo, cap_per_module=args.prove_max, repair_rounds=args.coverage_repair_rounds,
                timeout_seconds=args.timeout, progress=_cov_progress,
                max_attempts=args.prove_max_total)
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
        model = card.build_card(slug, _audited_language(results, args.lang, args.repo), results, ran_tests=ran_tests, analyzer_version=version())
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
            # Which build produced these numbers. A panel that cannot name its instrument
            # cannot be cited later, and the bands and the denominators here have both
            # moved under readers before.
            "analyzer_version": version(),
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
    raise SystemExit(run())
