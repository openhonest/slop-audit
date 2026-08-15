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
    "detail.na_unread": "Insufficient basis. No grade, and no claim either way about whether this code can be tested. Reading the source directly, we found {declared} places where it declares data it keeps — struct and class fields, instance attributes, file-scope and package-level bindings — and our analysis reached a verdict on none of them. That is a limit of our reading, not a finding about your code: it means we never got far enough to have an opinion. Every other number we publish is worked out over the data we did recognise, so on this repository they are all worked out over nothing, and we will not turn that into a good grade. The most common cause is a construct our reader does not know yet: a C struct field, or a language feature we have not taught it. Send us the repository and we will fix our end.",
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
_CULPRIT_CAP = 25
_ZERO = {"neutral": 0, "promiscuous": 0, "unresolved": 0}
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

# The core (verifiability) metrics and the audit checks, with their framework mappings.
_CORE_STATIC = ({"key": "L1.19", "unit": "", "maps_to": []},)
_CORE_RAN = ({"key": "L1.19", "unit": "", "maps_to": []}, {"key": "L1.20", "unit": "", "maps_to": []})
_AUDIT = (
    # The canon's own mapping: L1.12 triangulates tech debt with L1.5/L1.6/L1.7
    # (dimensions/17-tech-debt-management.md), and L1.14 is the first check of the
    # configuration-and-secrets dimension (dimensions/07-configuration-secrets.md).
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
    v = result.get("value", "n/a")
    return "n/a" if v == "n/a" else f"{v}{unit}"


def _metric(spec: dict, result: dict, group: str) -> dict:
    band = str(result.get("band", "n/a"))
    k = spec["key"]
    return {"label": _t(f"label.{k}"), "tech": _t(f"tech.{k}"), "value": _value_str(result, spec["unit"]),
            "band": band, "band_word": _BAND_WORD.get(band, "No data"), "meaning": _t(f"meaning.{k}"),
            "group": group, "maps_to": spec["maps_to"]}


def _metrics(specs: tuple, results: dict, group: str) -> list[dict]:
    return [_metric(s, results[s["key"]], group) for s in specs if s["key"] in results]


def _culprits(l18b: dict, status: str, coarse: list[dict]) -> tuple[list[dict], int]:
    """What limits the grade. CANNOT is limited by proven unbounded state, COARSE by finite
    state with too many unordered cases. The two lists are selected by different rules - one
    reads the verdict, the other reads the cardinality against a bound - so they cannot
    share a single verdict filter without one of them silently coming back empty."""
    if status == "coarse":
        flagged = coarse
    elif status == "cannot":
        flagged = [f for f in (l18b.get("findings") or []) if f.get("verdict") == "promiscuous"]
        flagged.sort(key=lambda f: (not f.get("drives_decision", False), f.get("file", ""), f.get("line", 0)))
    else:
        return [], 0
    shown = [{"file": f.get("file", ""), "line": f.get("line", 0), "state": f.get("state", "?"),
              "verdict": f.get("verdict", ""), "drives_decision": bool(f.get("drives_decision", False)),
              "classes": (f.get("partition") or {}).get("classes", 0)}
             for f in flagged[:_CULPRIT_CAP]]
    return shown, max(0, len(flagged) - _CULPRIT_CAP)


def _scoped_out(l18b: dict) -> dict | None:
    bucketed = l18b.get("bucketed", {}) if isinstance(l18b, dict) else {}
    counts = bucketed.get("counts", {}) or {}
    paths = [p["path"] for p in bucketed.get("paths", [])]
    total = sum(counts.values())
    if not total:
        return None
    return {"total": total, "reasons": ", ".join(f"{n} {r}" for r, n in sorted(counts.items())),
            "paths": paths[:12], "paths_more": max(0, len(paths) - 12)}


def _thread_surface(lang: str, results: dict) -> dict | None:
    ts = results.get("thread_surface")
    if not isinstance(ts, dict):
        return None
    verdict = str(ts.get("verdict", "n/a"))
    counts = ts.get("counts") or {}
    if verdict == "n/a":
        blurb = _t("thread.blurb.na", lang=lang)
    else:
        # Every blurb gets every field. The unread blurb needs the file counts and the other
        # three need the severity counts, and a per-verdict argument list would be one more
        # place a new verdict can KeyError on a card the reader is looking at.
        blurb = _t(f"thread.blurb.{verdict}", exposed=counts.get("exposed", 0),
                   review=counts.get("review", 0), candidate=counts.get("candidate", 0),
                   read=ts.get("files_read", 0), parsed=ts.get("files_parsed", 0))
    findings = ts.get("findings") if isinstance(ts.get("findings"), list) else []
    sites = [{"file": f.get("file", ""), "line": f.get("line", 0),
              "kind": _THREAD_KINDS.get(f.get("kind", ""), f.get("kind", "")),
              "symbol": f.get("symbol", ""), "severity": f.get("severity", "")} for f in findings[:_THREAD_CAP]]
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
            return _t("detail.na_unread", declared=census.get("declared", 0))
        return _t("detail.na_silent", silent=counts.get("unresolved", 0),
                  total=sum(counts.values())) if sum(counts.values()) else _t("detail.na")
    if status == "cannot":
        return _t("detail.cannot", n=promiscuous, plural="piece" if promiscuous == 1 else "pieces")
    if status == "can":
        return _t("detail.can", cover=f"{cover:,}") if cover else _t("detail.can_nocover")
    return _t("detail.coarse")


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
        for o in concurrency.get("outcomes", []):
            if o.get("verdict") == "demonstrated" and o.get("generated_test"):
                out.append({
                    "layer": "concurrency", "language": "rust",
                    "target": o.get("symbol", "?"),
                    "location": f"{o.get('file', '?')}:{o.get('line', 0)}",
                    "blurb": _t("proofs.blurb.concurrency"),
                    "detail": o.get("detail", ""),
                    "test_source": o["generated_test"].rstrip(),
                })

    coverage = results.get("coverage_proofs")
    if isinstance(coverage, dict):
        for p in coverage.get("retained", []):
            if p.get("test_source"):
                out.append({
                    "layer": "coverage", "language": p.get("language", "python"),
                    "target": p.get("function", "?"),
                    "location": p.get("location", ""),
                    "blurb": _t("proofs.blurb.coverage"),
                    "detail": p.get("explanation", ""),
                    "test_source": p["test_source"].rstrip(),
                })
    return out[:_PROOF_CAP]


def build_card(slug: str, lang: str, results: dict, ran_tests: bool = False) -> dict:
    """The full scorecard model, identical to the site's. ran_tests=True (the CLI) adds
    the measured runtime metrics (L1.19 coverage, L1.20 determinism); False (the site) omits
    them and the footer says the code was never executed."""
    l18 = results.get("L1.18", {"value": "n/a", "band": "n/a"})
    band = str(l18.get("band", "n/a"))
    l18b = results.get("L1.18b") if isinstance(results.get("L1.18b"), dict) else {}
    counts = l18b.get("counts") or _ZERO
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
    tests_measured = ran_tests and isinstance(l20, dict) and str(l20.get("band", "n/a")) != "n/a"
    return {
        "slug": slug, "lang": lang, "question": _t("question"), "status": status, "grade": grade,
        "grade_pct": pct, "ran_tests": ran_tests, "tests_measured": tests_measured,
        "headline": "" if status == "na" else _t(f"headline.{status}"),
        "basis": g["basis"], "census": g["census"],
        "detail": _detail(status, g["basis"], promiscuous, cover, counts, g["census"]),
        "paths": cover if status == "can" else None,
        "band": band, "band_word": _BAND_WORD.get(band, "No data"),
        "testable": None if pct is None else f"{pct}%",
        "neutral_count": counts.get("neutral", 0), "promiscuous_count": promiscuous,
        "unresolved_count": counts.get("unresolved", 0),
        "culprits_heading": _t(f"culprits.heading.{status}") if status in _WANT else "",
        "culprits_note": _t(f"culprits.note.{status}") if status in _WANT else "",
        "culprits": culprits, "culprits_more": culprits_more,
        "silence": l18b.get("silence") if isinstance(l18b.get("silence"), dict) else None,
        "silence_note": _t("silence.note"),
        "scoped_out": _scoped_out(l18b),
        "core": _metrics(core_specs, results, "core"),
        "audit": _metrics(_AUDIT, results, "audit"),
        "thread_surface": _thread_surface(lang, results),
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


def _silence_lines(card: dict) -> list[str]:
    """Every site the analyzer stopped at. On the `na` card this is the whole content: the
    repository was refused a grade because of silence, so the sites ARE the report."""
    sil = card.get("silence")
    if not isinstance(sil, dict) or not sil.get("sites"):
        return []
    return ["", f"## {_t('silence.heading')}", ""] + [
        f"- `{s['file']}:{s['line']}` — `{s['state']}`" for s in sil["sites"]]


def _verdict_lines(card: dict, strip: re.Pattern) -> list[str]:
    """The state verdict and what limits it. Empty on an ungraded card: the grade sentence,
    the capability claim, the three counts and the path-cover figure are all statements about
    state, and an ungraded card is one where no state was read. Printing the counts alone
    would put "0 provably unbounded" under a refusal to grade, which reads as good news."""
    lines: list[str] = []
    if card["grade"] is not None:
        lines += [f"**Grade: {card['grade']}** — {card['grade_pct']}% of its state is finitely testable", ""]
    lines += [card["headline"], "", strip.sub("", card["detail"]), "",
              f"- Finitely testable: {card['neutral_count']}",
              f"- Provably unbounded: {card['promiscuous_count']}",
              f"- Undecided by the analyzer (silence): {card['unresolved_count']}"]
    if card["status"] == "can" and card["paths"]:
        lines.append(f"- {_t('label.practical').split('.')[0]}: {card['paths']:,}")
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
    # An ungraded card keeps the checks that WERE measured. Withholding the state verdict is
    # a statement about the state classifier, and god-files, secrets, type escapes and CI were
    # measured by other indicators that the missing state has nothing to do with. The first
    # version of this returned here and printed one paragraph, which threw away eight measured
    # results to avoid publishing the one it did not have.
    lines += [strip.sub("", card["detail"])] if card["status"] == "na" else _verdict_lines(card, strip)
    lines += _silence_lines(card)
    if card["status"] != "na":
        lines += ["", "> " + strip.sub("", _t("silence.note"))]
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
