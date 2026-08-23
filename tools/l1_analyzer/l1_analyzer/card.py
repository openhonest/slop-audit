"""The full Slop Audit scorecard - the try.slopaudit.org card, in the engine.

The card model, its prose, the compliance-framework mappings, the Jinja template, and the
CSS all live here, so the CLI and the website render the SAME card from one source. The
grade computation is the same single source too (report.grade_summary).

The one deliberate difference between the two surfaces is the runtime layer. The website
never executes the repo's code, so decision-space coverage and determinism are not
measured there and it says so. The CLI DOES run the test suite, so when build_card is
called with ran_tests=True the card reports the measured coverage and determinism and the
footer says the tests were run.
"""

from __future__ import annotations

import re
from pathlib import Path

from l1_analyzer import report
from l1_analyzer.report import UNORDERED_CLASS_BOUND, grade_summary

_TEMPLATES = Path(__file__).parent / "card_templates"
_CSS_PATH = Path(__file__).parent / "card_static" / "scorecard.css"

# All card prose, ported from the site's copy.md so the engine is self-contained.
CARD_COPY: dict[str, str] = {
    "question": "Can this code ever be fully tested?",
    "label.practical": "test runs cover every path through the code, both sides of every yes-or-no. This is the whole list you would work through.",
    "headline.can": "This code definitely CAN be exhaustively tested.",
    "headline.coarse": "This code can be exhaustively tested in principle, but not in practice.",
    "headline.cannot": "This code mathematically CANNOT be exhaustively tested.",
    "detail.can": "None of the data this code keeps can grow without limit, so a fixed number of tests can check every case. The Slop Audit worked out the fewest test runs that reach every path: {cover} runs cover them all.",
    "detail.can_nocover": "None of the data this code keeps can grow without limit, so a fixed number of tests can check every case. Run the [CLI](https://github.com/openhonest/slop-audit) to get the exact number of runs that cover every path.",
    "detail.coarse": "Every piece of data here has a limited set of cases, so a fixed number of tests would cover it. The trouble is how many, and that they have no order. When cases are ordered, such as numbers against a limit, you test each side of the limit and you are done, however wide the range. The cases below are names, and one name is not next to another, so there is no shortcut: covering them means one test each. Cut the number of distinct cases, or give them an order, and the count comes down.",
    "detail.cannot": "{n} {plural} of data here can be almost anything, and the code makes decisions based on it. Because it can be anything, there is always one more case to check, so no fixed number of tests can ever cover them all. Writing more tests will not fix this. The only fix is to limit what that data can be, or stop letting other parts of the code change it.",
    "detail.na": "Point it at a public repository with code in a language the analyzer reads: Python, TypeScript, JavaScript, Java, C#, Rust, Ruby, Go, or C.",
    "detail.na_unread": "We do not have enough to grade this, and we make no claim either way about whether this code can be tested. Reading the source we found {declared} {places} where it keeps data. Our tool did not read any of them, because every one is written as {kinds} and it has not learned that form. That is a limit of our reading rather than a finding about your code: we never got far enough to have an opinion. Every other number we publish is worked out over the data we did read, so on this repository each one is worked out over nothing, and we will not turn that into a good grade. Send us the repository and we will teach the tool to read that form.",
    "census.unread": "{unread} of the {declared} places where this code keeps data {verb} written as {kinds}. Our tool has not learned to read those, so it never looked at {verb2}. Nothing in the grade above counts {verb2}, for or against. Closing that gap is our job rather than yours: send us the repository and we will teach the tool to read {verb2}.",
    "detail.na_silent": "No grade. We could not work out what {silent} of the {total} pieces of data here are used for, and that is more than half of them. Most often the data is handed to a library we cannot see inside. We will not hand out a good grade on the part we happened to be able to read, because that would reward code that shows us the least. The list below is every place we stopped, so you can see exactly what we could not follow.",
    "culprits.heading.coarse": "What costs too many tests",
    "culprits.heading.cannot": "What makes it impossible",
    "culprits.note.coarse": "Each of these has a countable set of cases with nothing ordering them, and more of them than one test suite reasonably covers. The count shown is for that piece of data on its own: two pieces that decide the same branch multiply, so the real total is larger than any number here.",
    "culprits.note.cannot": "Each of these is data that can be almost anything, used to make a decision. Limit it to a fixed set of values, or stop letting other code change it, and it becomes testable.",
    "share.can": "{slug} passes the Slop Audit: none of its data can grow without limit, so a fixed number of tests can cover every case. slopaudit.org",
    "share.coarse": "{slug} can be fully tested in principle, but some of its data has too many unordered cases to cover in practice. slopaudit.org",
    "share.cannot": "{slug}: fully testing it would take an endless number of tests. Some of its data can be almost anything, and the code makes decisions on it, so no fixed set of tests can cover every case. slopaudit.org",
    "share.na": "I ran {slug} through the Slop Audit. slopaudit.org",
    "silence.heading": "What we could not follow",
    "group.core.title": "Can this code be verified?",
    "group.core.note": "The numbers behind the answer above. They carry no compliance tag on purpose: they set the ceiling on what every check below can ever prove.",
    "group.audit.title": "How it maps to your audit",
    "group.audit.note": "Each row below is matched to the enterprise audit areas and the compliance controls they answer to.",
    "scoped.why": "Docs, build and test tooling, and loose entry-point scripts are not the code under test. Everything set aside is listed so you can check it.",
    "footer.fine": "A full Slop Audit scores all 18 enterprise compliance dimensions and produces SOC 2 evidence as a byproduct. This page runs the static Layer 1 indicators only. It never executes the repo's code.",
    "footer.cli": "Run under the Slop Audit CLI: the repository's test suite was executed, so decision-space coverage (L1.19) and test determinism (L1.20) below are measured, not estimated. try.slopaudit.org runs the static Layer 1 indicators only and never executes your code.",
    "footer.cli_na": "Run under the Slop Audit CLI, which executes the repository's test suite to measure decision-space coverage (L1.19) and test determinism (L1.20). Those rows read n/a here: the runtime harness is Python-only so far, so it did not run this repo's suite. try.slopaudit.org never executes any repo's code; this is the difference between 'we did not run it' and 'we could not run it here yet.'",
    "grade.rubric": "The grade is verifiability first, by a rule we publish rather than hide. The verdict sets the tier: <strong>CANNOT &rarr; F</strong> (some state is provably unbounded, so no finite test suite covers it), <strong>COARSE &rarr; D</strong> (some state has a countable but unordered set of cases too wide to cover; a wide ORDERED range costs a handful of boundary tests, a wide unordered one costs one test per case). When every piece of state is finitely testable and coverable, the audit checks below decide <strong>A, B, or C</strong> by weighted health &mdash; god-files and type-escapes weigh most (3 each), then CI (2), then containers, pre-commit, and formatting (1 each). The number is the share of DECIDED state that is finitely testable. No hidden weights.",
    # Migrated from report.py when its renderers were deleted. The claim was published on
    # every report that module produced and on no card, so the surface people actually read
    # never carried it. Same argument as the silence note beside it: a limit disclosed only
    # when it happens to bite is not disclosed.
    "compose.note": "Each count of cases above is per piece of data and does not compose. Two pieces that decide the same branch multiply rather than add, so the real number of cases is larger than any figure here. A per-piece number we can stand behind beats a combined one we would be guessing.",
    # What each silent site means to the reader, and whose move it is next. The two that
    # matter most are opposite: an external boundary is something you can make readable with
    # an explicit contract, and an unmodeled callee is our backlog. A reader who cannot tell
    # them apart goes and fixes ours. The card listed the sites without the reason until the
    # dead renderer that carried these lines was deleted.
    "silence.reason.external_boundary": "handed to code we cannot read; an explicit contract at this boundary would make it decidable",
    "silence.reason.unmodeled_callee": "handed to a plain name we have not taught the reader; ours to fix, not yours",
    "silence.reason.dynamic_dispatch": "the call target is chosen while the program runs, so no reading enumerates it",
    "silence.reason.injected_slot": "an injected callable whose value at the call site is not provably the one injected",
    "silence.reason.unmodeled_construct": "consumed by a piece of syntax the reader has no rule for; ours to fix, not yours",
    "silence.note": "Anything the analyzer could not decide is reported separately, as silence, and never folded into the grade: state we did not read is not evidence about this code. Above half of it undecided, no grade is issued at all, so hiding state from the analyzer buys no letter.",
    "label.L1.19": "Decisions that could be exhaustively checked",
    "tech.L1.19": "L1.19 · decision-space coverage",
    "meaning.L1.19": "How many decisions in the code (branches, lookups, and the like) could be listed and checked one by one. The share your tests actually reach is the real number, and getting it means running your test suite; the value here is n/a until that run measures it.",
    "label.L1.20": "Does the test suite give the same answer twice",
    "tech.L1.20": "L1.20 · test determinism",
    "meaning.L1.20": "How many of five randomized-order suite runs passed cleanly. Flakiness here means shared mutable state leaking between tests, so a green suite is not a stable one.",
    "label.L1.12": "Code nothing can reach and nothing calls",
    "tech.L1.12": "L1.12 · unreachable-code ratio",
    "meaning.L1.12": "The share of production lines that either sit below a return, or define a name nothing in the repository ever uses. AI assistants write helpers nobody calls, because each generation sees only the prompt and not what already exists. Read this as a floor: anything reached by reflection, dynamic dispatch or a framework is reported separately as undecidable, never counted here.",
    "label.L1.14": "Credentials committed into the code",
    "tech.L1.14": "L1.14 · secret-scan hits",
    "meaning.L1.14": "How many distinct API keys, passwords and tokens are sitting in tracked files. In a regulated enterprise any non-zero count is disqualifying. No credential is tested against its issuer, so a hit means credential-shaped, not proven live.",
    "label.L1.15": "Escapes from the type system",
    "tech.L1.15": "L1.15 · type-escape density",
    "meaning.L1.15": "How often the code opts out of its own type checker (any, # type: ignore, interface{}, dynamic) per thousand lines. Each escape is a spot the compiler can no longer protect, so a test has to cover it by hand.",
    "label.L1.17": "“God-files”, files too big to hold in your head",
    "tech.L1.17": "L1.17 · god-file concentration",
    "meaning.L1.17": "The share of files over 1,000 lines, an AI smell. AI assistants pile new code into the biggest file they can find; without a reviewer forcing a split, these grow until every change touches them and merge conflicts multiply.",
    "label.L1.16": "Indications that a human ever edited the file",
    "tech.L1.16": "L1.16 · trailing-whitespace density",
    "meaning.L1.16": "Harmless on its own, but an AI smell: lines left with trailing whitespace mean no editor or formatter touched the file between 'the AI wrote it' and 'it landed on main', which usually means no human reviewed it either.",
    "label.L1.10": "Automated build-and-test pipelines",
    "tech.L1.10": "L1.10 · CI/CD pipelines",
    "meaning.L1.10": "How many pipelines build, test, and gate each change before it ships. Zero means every merge is a manual act of faith.",
    "label.L1.11": "A reproducible environment",
    "tech.L1.11": "L1.11 · containerization",
    "meaning.L1.11": "Whether the repo ships a container or orchestration config so it runs the same on every machine. The container is the constraint that keeps an AI's environment-coupling habits from becoming the classic 'it works on *my* machine.'",
    "label.L1.9": "Checks that run before every commit",
    "tech.L1.9": "L1.9 · pre-commit hooks",
    "meaning.L1.9": "Whether automated checks run before code can even be committed, the first gate that catches AI output before a human ever sees it.",
    "interleaving.heading": "Concurrency the model checkers do not cover",
    "interleaving.blurb": "Of the files carrying an exposed thread-safety surface, these are the ones no loom or shuttle model touches: {unmodeled} of {surface}. Each is a place where the compiler's guarantee was set aside by hand and nothing systematically explores the interleavings.",
    "interleaving.blurb.clean": "Every file carrying an exposed thread-safety surface is touched by a loom or shuttle model.",
    "interleaving.note": "Static: it reads which files a model checker names, never whether the model is adequate. A covered file can still hold an unexplored interleaving.",
    "thread.heading": "Thread-safety surface",
    "thread.blurb.exposed": "Places where the compiler's thread-safety guarantee is overridden by hand or absent, with no visible guard: {exposed}. Each is a site to verify under free-threading, not a proven race.",
    "thread.blurb.review": "No hand-overrides of the thread-safety guarantee. Lower-severity footguns worth a look (relaxed atomic ordering, mutable default arguments, shared state that sits behind a lock we could not tie to it): {review}.",
    "thread.blurb.candidate": "No hand-overrides and no review-level footguns. Low-precision candidate shapes only ({candidate}); confirm with the prove stage.",
    "thread.blurb.clean": "No concurrency escape hatches found. Nothing overrides or bypasses the language's own thread-safety guarantee.",
    "thread.blurb.na": "Not analyzed for {lang} yet.",
    "thread.blurb.unread": "Not measured, and no claim either way. We can read this language, but we got no source to read it in: {read} file(s) were in scope and we could parse {parsed} of them. \"Nothing overrides your thread-safety guarantee\" would be counted over no code at all, so we will not say it. What was set aside is listed above; if it should have been read, send us the repository.",
    "thread.note": "This measures audit surface, not races. It shows where a language's thread-safety guarantee is overridden or missing, so a human or a runtime tool knows where to look. It does not detect data races: that needs [ThreadSanitizer](https://doc.rust-lang.org/beta/unstable-book/compiler-flags/sanitizer.html#threadsanitizer) or an equivalent at runtime. A site here means \"verify this\", never \"a race exists\".",
    "proofs.heading": "Adoptable proofs",
    "proofs.note": "Each proof below is a runnable test slop-audit generated for one located gap and then executed. It is shown only because running it settled the matter: the coverage proof genuinely failed (so it pins a decision your suite never reached), or the concurrency proof fired a data race (so it reproduces the hazard). slop-audit proves the gap; it never writes into your test file. Adopting a surviving proof is your choice. Following Umbra's discipline, an unproven gap is reported but never dressed up as a test.",
    "proofs.blurb.coverage": "Coverage gap: the suite never exercised this decision. The test drives it and asserts the caller-facing behavior; it fails against the current code, so adopting it both closes the gap and documents the expectation.",
    "proofs.blurb.concurrency": "Concurrency hazard: the test reproduces a data race at the flagged site under contention. It is retained only because the race actually fired when run.",
}

_BAND_WORD = {"Healthy": "Clean", "Not Healthy": "Caution", "Slop": "Slop", "n/a": "No data"}
_WANT = {"cannot": "promiscuous", "coarse": "coarse"}


def band_word(band: str) -> str:
    """The reader-facing word for one band, or a sentence naming the band nobody has a
    word for.

    Read by membership rather than with a default. `_BAND_WORD` carries a real `"n/a": "No
    data"` row, so `.get(band, "No data")` rendered a band the card does not recognise
    exactly like a measurement that was refused, and a reader could not tell an indicator
    that declined to grade from one that produced a grade nobody here has a word for."""
    known = _BAND_WORD.get(band)
    return known if known is not None else f"unknown band {band!r}"
_CULPRIT_CAP = 25
_ZERO = {"neutral": 0, "promiscuous": 0, "unresolved": 0}

# The one absent-indicator result. Complete, because L1Result is total: a stand-in for a
# reading that never happened still has to say so in its details line, the same as every
# reading that did. Written once so the next `results.get(key, {...})` cannot invent a
# differently-shaped absence.
ABSENT_INDICATOR = {"value": "n/a", "band": "n/a",
                    "details": "this indicator was not in the panel"}
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

# The core (verifiability) metrics and the audit checks, with their framework mappings.
_CORE_STATIC = ({"key": "L1.19", "unit": "", "maps_to": []},)
_CORE_RAN = ({"key": "L1.19", "unit": "", "maps_to": []}, {"key": "L1.20", "unit": "", "maps_to": []})
_AUDIT = (
    # The canon's own mapping: L1.12 triangulates tech debt with L1.5/L1.6/L1.7
    # (../../../spec/dimensions/17-tech-debt-management.md), and L1.14 is the first check of the
    # configuration-and-secrets dimension (../../../spec/dimensions/07-configuration-secrets.md).
    {"key": "L1.12", "unit": "%", "maps_to": [{"dimension": "Tech-debt management · 4.17", "frameworks": "NIST CM-8 / SA-15 · SOC 2 CC7.1 · ISO/IEC 25010"}]},
    {"key": "L1.14", "unit": "", "maps_to": [{"dimension": "Configuration and secrets · 4.7", "frameworks": "NIST IA-5 / SC-28 · SOC 2 CC6.1 · OWASP ASVS V6 · Quebec Law 25"}]},
    {"key": "L1.15", "unit": "/kloc", "maps_to": [{"dimension": "Dependency injection · 4.12", "frameworks": "NIST SA-11 · ISO/IEC 25010 (testability)"}]},
    {"key": "L1.17", "unit": "%", "maps_to": [{"dimension": "Tech-debt management · 4.17", "frameworks": "NIST CM-8 / SA-15 · SOC 2 CC7.1 · ISO/IEC 25010"}]},
    {"key": "L1.16", "unit": "%", "maps_to": [{"dimension": "SDLC with AI safeguards · 4.16", "frameworks": "NIST SA-3 / SA-8 · SOC 2 CC8.1 · OSFI B-13 §4.1.3"}]},
    {"key": "L1.10", "unit": "", "maps_to": [{"dimension": "CI/CD · 4.10", "frameworks": "NIST SA-11 / SA-15 / CM-3 · SOC 2 CC8.1 · OSFI B-13 §4.7 · SSDF PW.7"}]},
    {"key": "L1.11", "unit": "", "maps_to": [{"dimension": "Containerization · 4.11", "frameworks": "NIST SP 800-190 · SP 800-53 SA-11 / SI-7"}]},
    {"key": "L1.9", "unit": "", "maps_to": [{"dimension": "CI/CD · 4.10 + SDLC safeguards · 4.16", "frameworks": "NIST SA-11 · SOC 2 CC8.1"}]},
)
_THREAD_KINDS = {
    "unsafe_impl_send": "unsafe impl Send", "unsafe_impl_sync": "unsafe impl Sync", "static_mut": "static mut",
    "relaxed_ordering": "Ordering::Relaxed", "relaxed_guard": "Relaxed gates a branch", "nonatomic_rmw": "non-atomic RMW",
    "check_then_act": "check-then-act", "async_toctou": "async TOCTOU", "goroutine_shared_write": "goroutine captured write",
    "static_mutable_field": "static mutable field", "mutable_default_arg": "mutable default arg",
    "unguarded_shared_state": "shared state, no lock in file", "possibly_unguarded_shared_state": "shared state, lock present",
}
_THREAD_CAP = 12


def _t(key: str, **f: object) -> str:
    v = CARD_COPY.get(key, key)
    return v.format(**{k: str(x) for k, x in f.items()}) if f else v


def _value_str(result: dict, unit: str) -> str:
    # Subscripted. L1Result is total and its only caller passes a panel entry it has
    # already found by key, so a default here would print n/a for a result that measured
    # something and lost the field on the way.
    v = result["value"]
    return "n/a" if v == "n/a" else f"{v}{unit}"


def _metric(spec: dict, result: dict, group: str) -> dict:
    band = str(result["band"])
    k = spec["key"]
    return {"label": _t(f"label.{k}"), "tech": _t(f"tech.{k}"), "value": _value_str(result, spec["unit"]),
            "band": band, "band_word": band_word(band), "meaning": _t(f"meaning.{k}"),
            "group": group, "maps_to": spec["maps_to"]}


def _metrics(specs: tuple, results: dict, group: str) -> list[dict]:
    return [_metric(s, results[s["key"]], group) for s in specs if s["key"] in results]


def _culprits(l18b: dict | None, status: str, coarse: list[dict]) -> tuple[list[dict], int]:
    """What limits the grade. CANNOT is limited by proven unbounded state, COARSE by finite
    state with too many unordered cases. The two lists are selected by different rules - one
    reads the verdict, the other reads the cardinality against a bound - so they cannot
    share a single verdict filter without one of them silently coming back empty."""
    if status == "coarse":
        flagged = coarse
    elif status == "cannot":
        flagged = [f for f in (l18b["findings"] if l18b else []) if f["verdict"] == "promiscuous"]
        flagged.sort(key=lambda f: (not f["drives_decision"], f["file"], f["line"]))
    else:
        return [], 0
    # Subscripted, not defaulted. Finding is a total TypedDict, so every one of these is
    # present on every finding the analyzer produces; a default here would defend a
    # contract the signature already holds, and would render a fabricated line 0 at file
    # "" if the contract ever did break. An absent field must stop the render.
    shown = [{"file": f["file"], "line": f["line"], "state": f["state"],
              "verdict": f["verdict"], "drives_decision": bool(f["drives_decision"]),
              "classes": f["partition"]["classes"]}
             for f in flagged[:_CULPRIT_CAP]]
    return shown, max(0, len(flagged) - _CULPRIT_CAP)


def _scoped_out(l18b: dict | None) -> dict | None:
    # The isinstance guard is the absence: L1.18b may not be in the panel at all. Past it
    # the analyzer always writes a bucketed section carrying its counts and paths, even
    # when both are empty, so those two are subscripted.
    if l18b is None:
        return None
    bucketed = l18b["bucketed"]
    counts = bucketed["counts"]
    paths = [p["path"] for p in bucketed["paths"]]
    total = sum(counts.values())
    if not total:
        return None
    return {"total": total, "reasons": ", ".join(f"{n} {r}" for r, n in sorted(counts.items())),
            "paths": paths[:12], "paths_more": max(0, len(paths) - 12)}


def _honest_code(results: dict) -> dict | None:
    """The card's view of L1.21, or None when the caller did not ask for it.

    The share is over the clauses that were DECIDED, so the card prints how many of the
    nineteen those were. Without that a reader would take 100% to mean nineteen clauses
    held, when it can mean sixteen held and three were never looked at."""
    entry = results.get("honest_code")
    if not isinstance(entry, dict) or entry["band"] == "n/a":
        return None
    counted: dict[str, int] = {}
    for finding in entry["findings"]:
        counted[finding["clause"]] = counted.get(finding["clause"], 0) + 1
    broken = sorted(counted.items())
    return {"verdict": str(entry["band"]), "value": entry["value"],
            "detail": str(entry["details"]),
            "broken": [{"clause": code, "count": n} for code, n in broken[:_THREAD_CAP]],
            "broken_more": max(0, len(broken) - _THREAD_CAP)}


def _interleaving_robustness(results: dict) -> dict | None:
    """The card's view of the interleaving-robustness check, or None when it did not run.

    It was computed in cli.py, published into the JSON panel, and mentioned nowhere here,
    so a Rust repository with unmodeled concurrency surface showed the finding only to a
    reader who parses `--format json`. The section it had been written for lived on a
    renderer with no caller outside the test suite, which has since been deleted.

    test_every_panel_key_is_rendered.py is the invariant that keeps the next section from
    going the same way: a published key is on the card or on a named exclusion list."""
    ir = results.get("interleaving_robustness")
    # The isinstance guard is what handles absence: an indicator that did not run is not
    # in the panel at all. Past it, InterleavingRobustnessResult is a total TypedDict and
    # `verdict` is present, so it is subscripted rather than defaulted to "n/a" - a default
    # there would report not-measured for a result that was measured and malformed.
    if not isinstance(ir, dict) or str(ir["verdict"]) == "n/a":
        return None
    unmodeled = ir.get("unmodeled") if isinstance(ir.get("unmodeled"), list) else []
    blurb = (_t("interleaving.blurb.clean") if not unmodeled
             else _t("interleaving.blurb", unmodeled=len(unmodeled),
                     surface=ir.get("surface_files", len(unmodeled))))
    return {"verdict": str(ir.get("verdict")), "blurb": blurb,
            "files": [str(f) for f in unmodeled[:_THREAD_CAP]],
            "files_more": max(0, len(unmodeled) - _THREAD_CAP)}


def _thread_surface(lang: str, results: dict) -> dict | None:
    ts = results.get("thread_surface")
    if not isinstance(ts, dict):
        return None
    verdict = str(ts["verdict"])          # SurfaceResult is total; the guard above is absence
    counts = ts["counts"]
    if verdict == "n/a":
        blurb = _t("thread.blurb.na", lang=lang)
    else:
        # Every blurb gets every field. The unread blurb needs the file counts and the other
        # three need the severity counts, and a per-verdict argument list would be one more
        # place a new verdict can KeyError on a card the reader is looking at.
        blurb = _t(f"thread.blurb.{verdict}", exposed=counts.get("exposed", 0),
                   review=counts.get("review", 0), candidate=counts.get("candidate", 0),
                   read=ts["files_read"], parsed=ts["files_parsed"])
    findings = ts.get("findings") if isinstance(ts.get("findings"), list) else []
    # thread_surface.Finding is total too, so a site's fields are subscripted. Only the
    # kind's DISPLAY name defaults, and to the kind itself: a kind with no copy yet is shown
    # as the analyzer named it rather than as an empty cell.
    sites = [{"file": f["file"], "line": f["line"],
              "kind": _THREAD_KINDS.get(f["kind"], f["kind"]),
              "symbol": f["symbol"], "severity": f["severity"]} for f in findings[:_THREAD_CAP]]
    return {"verdict": verdict, "exposed": counts.get("exposed", 0), "review": counts.get("review", 0),
            "blurb": blurb, "sites": sites, "sites_more": max(0, len(findings) - _THREAD_CAP)}


def _detail(status: str, basis: str, promiscuous: int, cover: int | None, counts: dict, census: dict) -> str:
    # Three different things produce `na`, and telling the reader the wrong one wastes their
    # time: "there is no code here I can read" sends them to check the language, "I could not
    # follow most of your state" sends them to the sites, and "I read none of your state"
    # sends them to us. The basis names which, and it is read rather than re-derived from the
    # counts, because the counts are exactly what the unread case has none of: zero neutral,
    # zero promiscuous and zero unresolved is indistinguishable from a clean repository if you
    # only look here, and that indistinguishability was the defect.
    if status == "na":
        if basis == report.UNREAD:
            declared = census.get("declared", 0)
            return _t("detail.na_unread", declared=declared,
                      places="place" if declared == 1 else "places",
                      kinds=report.unread_kinds_phrase(census))
        return _t("detail.na_silent", silent=counts.get("unresolved", 0),
                  total=sum(counts.values())) if sum(counts.values()) else _t("detail.na")
    if status == "cannot":
        return _t("detail.cannot", n=promiscuous, plural="piece" if promiscuous == 1 else "pieces")
    if status == "can":
        return _t("detail.can", cover=f"{cover:,}") if cover else _t("detail.can_nocover")
    return _t("detail.coarse")


def _census_note(census: dict) -> str:
    """What this repository declares that the reader never reached, on a card that GRADED.

    The refusal used to fire whenever nothing was admitted, which caught this case by
    accident; it now fires only when the enumerator reached NOTHING this repository declares,
    so a repository with one visited binding and two hundred nothing looked at is graded.
    Those two hundred have to be said out loud on the card a reader actually gets, or relaxing
    the refusal simply deletes the disclosure.

    The counts and the kind vocabulary come from the census and from
    report.unread_kinds_phrase, so this module keeps its own voice without being able to
    disagree with the measurement."""
    declared, visited = census.get("declared"), census.get("visited")
    if not isinstance(declared, int) or not isinstance(visited, int) or declared == visited:
        return ""
    unread = declared - visited
    return _t("census.unread", unread=unread, declared=declared,
              verb="is" if unread == 1 else "are", verb2="it" if unread == 1 else "them",
              kinds=report.unread_kinds_phrase(census))


def _int(v: object) -> int | None:
    return v if isinstance(v, int) else None


_PROOF_CAP = 20


def _proofs(results: dict) -> list[dict]:
    """The adoptable proofs: runnable tests slop-audit generated for a located gap and
    retained only because running them settled it (Umbra's discipline). Two producers feed
    one surface - the concurrency prove loop (results['proofs']) and the coverage-gap prove
    loop (results['coverage_proofs']) - and each proof carries the test source to adopt."""
    out: list[dict] = []

    concurrency = results.get("proofs")
    if isinstance(concurrency, dict):
        # ProofOutcome is declared, so every field but generated_test is guaranteed. That
        # one is None when the model produced nothing, which is a real case and the reason
        # this loop tests it before exposing anything.
        for o in concurrency["outcomes"]:
            if o["verdict"] == "demonstrated" and o["generated_test"]:
                out.append({
                    "layer": "concurrency", "language": "rust",
                    "target": o["symbol"],
                    "location": f"{o['file']}:{o['line']}",
                    "blurb": _t("proofs.blurb.concurrency"),
                    "detail": o["detail"],
                    "test_source": o["generated_test"].rstrip(),
                })

    coverage = results.get("coverage_proofs")
    if isinstance(coverage, dict):
        for p in coverage["retained"]:
            if p["test_source"]:
                out.append({
                    "layer": "coverage", "language": p["language"],
                    "target": p["function"],
                    "location": p["location"],
                    "blurb": _t("proofs.blurb.coverage"),
                    "detail": p["explanation"],
                    "test_source": p["test_source"].rstrip(),
                })
    return out[:_PROOF_CAP]


def build_card(slug: str, lang: str, results: dict, ran_tests: bool,
               analyzer_version: str) -> dict:
    """The full scorecard model, identical to the site's. ran_tests=True (the CLI) adds
    the measured runtime metrics (L1.19 coverage, L1.20 determinism); False (the site) omits
    them and the footer says the code was never executed."""
    l18 = results.get("L1.18", ABSENT_INDICATOR)
    band = str(l18["band"])
    # None, not an empty dict. The empty dict was a SECOND spelling of absent, and it was
    # the one that got past every `isinstance(l18b, dict)` guard downstream: the readers
    # then subscripted a result that was never there. Absence has one spelling here.
    l18b = results.get("L1.18b")
    l18b = l18b if isinstance(l18b, dict) else None
    counts = l18b["counts"] if l18b else _ZERO
    # The site and CLI are the boundary, so the configured bound is resolved here.
    g = grade_summary(results, UNORDERED_CLASS_BOUND)
    status, pct, grade = g["status"], g["testable_pct"], g["grade"]
    pc = results.get("path_cover", {})
    # The path-cover figure is coverage of the ENUMERATED state, so on an ungraded card it
    # would be a precise number standing next to a refusal to give one. It was the worst part
    # of the defect: "1,080 runs cover them all" is a coverage claim over an empty set.
    cover = _int(pc.get("value")) if status != "na" else None
    culprits, culprits_more = _culprits(l18b, status, g["coarse"])
    promiscuous = counts.get("promiscuous", 0)
    core_specs = _CORE_RAN if ran_tests else _CORE_STATIC
    # tests_measured tells the two runtime-CLI cases apart honestly: the suite actually ran
    # and produced a number (Python), versus the CLI tried but the runtime harness does not
    # support this language yet (Rust and the rest), so L1.19/L1.20 read n/a. The footer says
    # which. The site (ran_tests=False) is a third case: it never runs code at all.
    l20 = results.get("L1.20")
    tests_measured = ran_tests and isinstance(l20, dict) and str(l20["band"]) != "n/a"
    return {
        "slug": slug, "lang": lang, "question": _t("question"), "status": status, "grade": grade,
        "grade_pct": pct, "ran_tests": ran_tests, "tests_measured": tests_measured,
        "headline": "" if status == "na" else _t(f"headline.{status}"),
        "basis": g["basis"], "census": g["census"],
        "census_note": "" if status == "na" else _census_note(g["census"]),
        "detail": _detail(status, g["basis"], promiscuous, cover, counts, g["census"]),
        "paths": cover if status == "can" else None,
        "band": band, "band_word": band_word(band),
        "testable": None if pct is None else f"{pct}%",
        "neutral_count": counts.get("neutral", 0), "promiscuous_count": promiscuous,
        "unresolved_count": counts.get("unresolved", 0),
        "culprits_heading": _t(f"culprits.heading.{status}") if status in _WANT else "",
        "culprits_note": _t(f"culprits.note.{status}") if status in _WANT else "",
        "culprits": culprits, "culprits_more": culprits_more,
        "silence": l18b["silence"] if l18b and isinstance(l18b["silence"], dict) else None,
        "silence_note": _t("silence.note"), "compose_note": _t("compose.note"),
        "silence_sites": _silence_sites(l18b),
        "scoped_out": _scoped_out(l18b),
        "core": _metrics(core_specs, results, "core"),
        "audit": _metrics(_AUDIT, results, "audit"),
        "thread_surface": _thread_surface(lang, results),
        "interleaving_robustness": _interleaving_robustness(results),
        "honest_code": _honest_code(results),
        "analyzer_version": analyzer_version,
        "proofs": _proofs(results),
        "share_text": _t(f"share.{status}", slug=slug),
    }


def _copy_for_html() -> dict[str, str]:
    """CARD_COPY with markdown links rendered to <a>, for the template's | safe fields."""
    return {k: _LINK.sub(r'<a href="\2" target="_blank" rel="noopener">\1</a>', v) for k, v in CARD_COPY.items()}


def card_html(card: dict) -> str:
    """Render the card via the site's own template + CSS - a standalone page."""
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    env = Environment(loader=FileSystemLoader(str(_TEMPLATES)), autoescape=select_autoescape(["html"]))
    env.globals["copy"] = _copy_for_html()
    fragment = env.get_template("scorecard.html").render(card=card)
    css = _CSS_PATH.read_text()
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Slop Audit — {card['slug']}</title>"
        f"<style>{css}\nbody{{max-width:860px;margin:2rem auto;padding:0 1.2rem}}</style>"
        f"</head><body>{fragment}</body></html>"
    )


def _silence_sites(l18b: dict | None) -> list[dict]:
    """Every site the analyzer stopped at, with the reason in the reader's words, for the
    HTML card. The model carried `silence` and the template rendered none of it, so the site
    published a grade and named not one place it stopped."""
    sil = l18b["silence"] if l18b else None
    if not isinstance(sil, dict):
        return []
    return [{"file": s["file"], "line": s["line"], "state": s["state"],
             "why": _t("silence.reason." + s["reason"])} for s in (sil.get("sites") or [])]


def _silence_lines(card: dict) -> list[str]:
    """Every site the analyzer stopped at. On the `na` card this is the whole content: the
    repository was refused a grade because of silence, so the sites ARE the report."""
    sil = card.get("silence")
    if not isinstance(sil, dict) or not sil.get("sites"):
        return []
    return ["", f"## {_t('silence.heading')}", ""] + [
        f"- `{s['file']}:{s['line']}` — `{s['state']}` ({_t('silence.reason.' + s['reason'])})"
        for s in sil["sites"]]


def _verdict_lines(card: dict, strip: re.Pattern) -> list[str]:
    """The state verdict and what limits it. Empty on an ungraded card: the grade sentence,
    the capability claim, the three counts and the path-cover figure are all statements about
    state, and an ungraded card is one where no state was read. Printing the counts alone
    would put "0 provably unbounded" under a refusal to grade, which reads as good news."""
    lines: list[str] = []
    if card["grade"] is not None:
        lines += [f"**Grade: {card['grade']}** — {card['grade_pct']}% of its state is finitely testable", ""]
    lines += [card["headline"], "", strip.sub("", card["detail"])]
    if card["grade"] is None:
        # Withheld, which is what the paragraph above says and what the code did not do:
        # the three count lines were appended unconditionally, so an ungraded card rendered
        # "Provably unbounded: 0" under a refusal to grade. Three clean-looking zeroes over
        # state nobody read. Found on 2026-08-20 by rendering an ungraded card, which this
        # repository never produces because it is clean.
        return lines
    lines += ["",
              f"- Finitely testable: {card['neutral_count']}",
              f"- Provably unbounded: {card['promiscuous_count']}",
              f"- Undecided by the analyzer (silence): {card['unresolved_count']}"]
    if card["status"] == "can" and card["paths"]:
        lines.append(f"- {_t('label.practical').split('.')[0]}: {card['paths']:,}")
    # Directly under the counts, because it qualifies those counts. A reader who meets it
    # after the audit table has already read them as the whole story.
    if card["census_note"]:
        lines += ["", "> " + strip.sub("", card["census_note"])]
    if card["culprits"]:
        lines += ["", f"## {card['culprits_heading']}", ""]
        for c in card["culprits"]:
            drives = ", drives a decision" if c["drives_decision"] else ""
            cases = f", {c['classes']} unordered cases" if card["status"] == "coarse" else ""
            lines.append(f"- `{c['file']}:{c['line']}` — `{c['state']}` ({c['verdict']}{cases}{drives})")
        if card["culprits_more"]:
            lines.append(f"- …and {card['culprits_more']} more")
        if card["status"] == "coarse":
            lines += ["", "> " + strip.sub("", _t("culprits.note.coarse"))]
    return lines


def card_markdown(card: dict) -> str:
    """The same card as Markdown, for the CLI and agent-facing output."""
    strip = re.compile(r"<[^>]+>")
    lines = [f"# Slop Audit — {card['slug']} ({card['lang']})", ""]
    # Which build made this. A card is a published measurement, and a reader cannot tell
    # whether a number came from the build that fixed L1.13's denominator or the one before
    # it unless the card says so.
    if card["analyzer_version"]:
        lines += [f"_slop-audit-l1 {card['analyzer_version']}_", ""]
    # An ungraded card keeps the checks that WERE measured. Withholding the state verdict is
    # a statement about the state classifier, and god-files, secrets, type escapes and CI were
    # measured by other indicators that the missing state has nothing to do with. The first
    # version of this returned here and printed one paragraph, which threw away eight measured
    # results to avoid publishing the one it did not have.
    lines += [strip.sub("", card["detail"])] if card["status"] == "na" else _verdict_lines(card, strip)
    lines += _silence_lines(card)
    if card["status"] != "na":
        lines += ["", "> " + strip.sub("", _t("compose.note")),
                  "", "> " + strip.sub("", _t("silence.note"))]
    for group, title in (("core", "group.core.title"), ("audit", "group.audit.title")):
        rows = card[group]
        if not rows:
            continue
        lines += ["", f"## {_t(title)}", "", "| Check | Value | Band | Counts toward |", "|---|---|---|---|"]
        for m in rows:
            maps = "; ".join(f"{d['dimension']} · {d['frameworks']}" for d in m["maps_to"]) or "—"
            lines.append(f"| {m['tech']} | {m['value']} | {m['band_word']} | {maps} |")
    ts = card.get("thread_surface")
    if ts and ts["verdict"] != "n/a":
        lines += ["", f"## {_t('thread.heading')} — {ts['verdict']}", "", strip.sub("", ts["blurb"])]
        for s in ts["sites"]:
            lines.append(f"- `{s['file']}:{s['line']}` — {s['kind']} ({s['severity']}) `{s['symbol']}`")
        lines += ["", "> " + strip.sub("", _t("thread.note"))]
    ir = card.get("interleaving_robustness")
    if ir:
        lines += ["", f"## {_t('interleaving.heading')} — {ir['verdict']}", "", strip.sub("", ir["blurb"])]
        for f in ir["files"]:
            lines.append(f"- `{f}`")
        if ir["files_more"]:
            lines.append(f"- and {ir['files_more']} more")
        lines += ["", "> " + strip.sub("", _t("interleaving.note"))]
    hc = card.get("honest_code")
    if hc:
        lines += ["", f"## Honest Code conformity (L1.21) — {hc['value']}% ({hc['verdict']})",
                  "", hc["detail"]]
        for entry in hc["broken"]:
            lines.append(f"- {entry['clause']} — {entry['count']} sites")
        if hc["broken_more"]:
            lines.append(f"- and {hc['broken_more']} more clauses")
        lines += ["", ("> The share is over the clauses that were DECIDED. A clause nobody "
                       "could check is outside it, numerator and denominator both, and is "
                       "named above rather than counted as a pass.")]
    proofs = card.get("proofs") or []
    if proofs:
        lines += ["", f"## {_t('proofs.heading')}", "", strip.sub("", _t("proofs.note"))]
        for p in proofs:
            loc = f" (`{p['location']}`)" if p.get("location") else ""
            lines += ["", f"### {p['layer']}: `{p['target']}`{loc}", "", p["blurb"]]
            if p.get("detail"):
                lines.append(f"\n_{p['detail']}_")
            lines += ["", f"```{p['language']}", p["test_source"], "```"]
    footer = "footer.fine" if not card["ran_tests"] else ("footer.cli" if card["tests_measured"] else "footer.cli_na")
    lines += ["", "---", "", strip.sub("", _t(footer))]
    return "\n".join(lines)
