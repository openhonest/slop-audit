"""The dogfood gate: what a pre-commit hook calls, rather than what a person calls.

Split out of `cli` when that module crossed the god-file threshold, at the seam that was
already there. Everything else in the CLI renders a panel for somebody reading it. This
answers one question for a machine: would this tool flag the code about to be committed.

THE RATCHETS ARE THE PART WORTH READING. Three of the four checks here are bright lines: a
production god-file, promiscuous state, and nothing else. The rest are baselines set at the
current count, so a NEW violation fails the commit while the existing debt does not block
every commit until it is paid. Raising a baseline is a deliberate, reviewable change in the
hook config, which is the only place it can be done.

Slack fails too. A baseline looser than reality lets the next violation in for free, so the
gate reports the gap and fails rather than quietly honouring a number nobody updated.
"""

from __future__ import annotations

from pathlib import Path

from l1_analyzer import indicators, report, thread_surface
from l1_analyzer.indicators import detect_primary_language
from l1_analyzer.scope import PRODUCTION

# Deliberately not "n/a". A distinct fact needs a distinct string, and reusing the token
# with a comment saying which one it means is how the collision was written the first time.
ABSENT_VERDICT = "absent-verdict"

_UNMEASURED_THREAD_SURFACE = {
    thread_surface.UNREAD: "the meter read no source",
    thread_surface.NO_SCANNER: "no scanner for this language",
    ABSENT_VERDICT: "the meter returned no verdict for this language",
}

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


def _run_gate(repo: Path, lang: str, max_type_escapes: int | None,
              max_thread_exposed: int | None, max_honest_code: int | None) -> int:
    """Dogfood gate for a pre-commit hook: run the source indicators against the repo
    and fail the commit if the tool would flag its own code. Bright-line invariants:
      - L1.17: no production god-file (a file over 1000 CODE lines).
      - L1.18b: no promiscuous state (the code stays exhaustively testable).
      - L1.21 ratchet (opt-in via --max-honest-code): the Honest Code clause findings
        must not exceed the baseline. Opt-in because L1.21 states an opinion and grades
        nobody who has not chosen it; a ratchet rather than a bright line because a
        package part-way through adopting it would otherwise be unable to commit at all.
      - L1.15 ratchet (opt-in via --max-type-escapes): the Any / # type: ignore count
        must not exceed the baseline. This is not the density band (a moving
        threshold); it is a bright line at the current number, so a new escape fails
        the commit unless the baseline is deliberately raised in the hook config."""
    results = indicators.compute_source_indicators(
        repo, lang=lang, exec_tests=False, timeout_seconds=5.0, classify_state_bounds=True,
        # Stated rather than defaulted, and None is the honest value: with exec_tests False
        # no suite runs, so there is no interpreter for this call to choose. The signature
        # used to supply the None itself, which is what let this call site be missed when
        # every other one was updated.
        python_executable=None,
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

    if max_honest_code is not None:
        from l1_analyzer import honest_code

        # The list, counted here. `analyze` publishes the findings themselves, and reading
        # its length as if it were already a count is a mistake this file made once.
        found = len(honest_code.analyze(repo, audited_lang)["findings"])
        if found > max_honest_code:
            problems.append(
                f"Honest Code (L1.21): {found} clause finding(s), over the ratchet of "
                f"{max_honest_code}. Fix it, or declare the site with a "
                "`# honest-code-allow: L1.21.N - <reason>` comment carrying a reason a "
                "reader can audit. If the baseline must rise, raise it in "
                ".pre-commit-config.yaml as a deliberate, reviewable change."
            )
        problems.extend(_slack(found, max_honest_code, "Honest Code findings (L1.21)"))

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
