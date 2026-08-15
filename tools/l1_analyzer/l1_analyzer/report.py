"""The full Slop Audit report, the way try.slopaudit.org renders it, from the CLI.

Ported into the engine so the CLI and the web produce the same report: the single A-F
grade, the verifiability verdict (CAN / COARSE / CANNOT), the finitely-testable share, the
audit checks with bands, and the concurrency layer (thread-surface + schedule-silence).
build_report is a pure mapping from analyzer results to a model; report_markdown and
report_html render it. No copy.md dependency; the prose is inlined here.

The grade rule (published, not hidden): verifiability first. CANNOT is F, COARSE is D, and
above the silence floor there is no grade at all. When every piece of state is finitely
testable and coverable, A/B/C is the weighted health of the audit checks - god-files and
type-escapes weigh most.
"""

from __future__ import annotations

import html as _html
from typing import TypedDict

from l1_analyzer import state_partition

_HYGIENE_WEIGHTS = {"L1.17": 3, "L1.15": 3, "L1.10": 2, "L1.11": 1, "L1.9": 1, "L1.16": 1}
_BAND_POINTS = {"Healthy": 1.0, "Not Healthy": 0.5, "Slop": 0.0}
_A_MIN, _B_MIN = 0.85, 0.60

# Above this share of undecided state, no grade is issued at all. The number is measured,
# not chosen: see candidate-methods/silence-index-for-finite-testability.md for the
# distribution it comes from. It gates only the good grades - a proven unbounded state is
# still F above the floor, because a proof stands whatever else went unread.
#
# It sits just above the worst silence the analyzer produces on the pinned corpus (libuv,
# 0.458), so no repository is refused a grade for a limit of OUR reading. That makes it a
# ratchet, not a quality bar: every builtin we teach the analyzer lowers observed silence,
# and this number comes down with it.
SILENCE_FLOOR = 0.50

# A finite, unordered partition wider than this is D. NO NUMBER IS SET, and that is the
# measurement result, not an omission.
#
# Measured over the six pinned corpus repositories and nine supplementary Python trees:
# 36 unordered partitions over state that decides something, distributed
# {2:6, 3:7, 4:7, 5:4, 6:1, 7:2, 8:4, 12:2, 13:2, 14:1}. The widest anything reached was 14.
# There is no upper tail at all. The distribution therefore fixes a FLOOR for any bound - a
# bound of 14 or less would put ordinary production state in D, which would be measuring our
# impatience rather than their testability - and says nothing whatever about where above 15
# to put it. Picking 20, or 100, would be inventing the number the data was supposed to give.
#
# The reason the tail is empty is worth stating, because it is a limit of the instrument and
# not a fact about code. The five-hundred-string-key dispatch table the rule was written for
# reaches this meter as a keyed read with a VARIABLE key, which is unbounded and already F.
# A partition is only counted here when the literals are written out one at a time, and
# nobody writes five hundred of those. So D as specified is close to unreachable by the
# current measurement, and a bound would be a rule with no observed instances.
#
# Set an integer here (or pass one to grade_summary) to switch D on. Until the measurement
# can see the shape the rule is about, None keeps the analyzer from issuing a grade it
# cannot support.
UNORDERED_CLASS_BOUND: int | None = None

# Audit checks shown on the card, in order, with their published labels.
# L1.12 and L1.14 are listed but NOT weighted into the grade. They became measurable only
# when they went native (both reported n/a on any machine without vulture or gitleaks), and
# adding a check to _HYGIENE_WEIGHTS moves every published grade, which is a methodology
# decision and not a side effect of implementing an indicator.
_AUDIT = [
    ("L1.12", "L1.12 · unreachable-code ratio", "%"),
    ("L1.14", "L1.14 · secret-scan hits", ""),
    ("L1.15", "L1.15 · type-escape density", "/kloc"),
    ("L1.17", "L1.17 · god-file concentration", "%"),
    ("L1.16", "L1.16 · trailing-whitespace density", "%"),
    ("L1.10", "L1.10 · CI/CD pipelines", ""),
    ("L1.11", "L1.11 · containerization", ""),
    ("L1.9", "L1.9 · pre-commit hooks", ""),
]
_VERDICT_LINE = {
    "can": "CAN be exhaustively tested.",
    "coarse": "CAN be exhaustively tested in principle, but some state has too many unordered "
              "cases to cover in practice.",
    "cannot": "CANNOT be exhaustively tested (some state is provably unbounded).",
    "na": "not graded (too much of its state went undecided, or there is no source in a "
          "language the analyzer reads).",
}
# What each silence reason means to the reader, and whose move it is next. The two that
# matter most are opposite: an external boundary is something the adopter can make readable
# with an explicit contract, and an unmodeled callee is our backlog. A reader who cannot
# tell them apart will go and fix ours.
_SILENCE_REASON_LINE = {
    "external_boundary": "handed to code the analyzer cannot read; an explicit contract at "
                         "this boundary would make it decidable",
    "unmodeled_callee": "handed to a plain name the analyzer has not been taught; ours to fix, "
                        "not yours",
    "dynamic_dispatch": "the call target is chosen while the program runs, so no reading "
                        "enumerates it",
    "injected_slot": "an injected callable whose value at the call site is not provably the "
                     "one injected",
}
_COMPOSE_NOTE = (
    "Each cardinality below is per state and does not compose. Two states that decide the same "
    "branch multiply rather than add, so the real number of cases is larger than any figure here. "
    "A per-state number that is honest beats a composed number that is guessed."
)
_SILENCE_NOTE = (
    "Silence is what the analyzer could not decide, and it is reported beside the grade rather "
    "than inside it: a state we did not read is not evidence about this code. Above "
    f"{round(SILENCE_FLOOR * 100)}% silence no grade is issued at all, so hiding state from the "
    "analyzer buys no letter."
)
_RUBRIC = (
    "The grade is verifiability first, by a rule we publish rather than hide. The verdict sets the tier: "
    "CANNOT is F (some state is provably unbounded, so no finite test suite covers it). D is a state whose "
    "cases are finite and countable, but unordered and more numerous than a published bound: boundary values "
    "cover a large ORDERED domain with a handful of tests, and cover a large unordered one with none. No bound "
    "is set at present, so no repository is graded D; the measured distribution that has to fix it is in the "
    "method document. When every piece of state is finitely testable and coverable, the "
    "audit checks decide A, B, or C by weighted health - god-files and type-escapes weigh most (3 each), then "
    "CI (2), then containers, pre-commit, and formatting (1 each). The number is the share of DECIDED state "
    "that is finitely testable. No hidden weights."
)


class Report(TypedDict, total=False):
    slug: str
    lang: str
    status: str
    grade: str | None
    testable_pct: int | None
    neutral: int
    promiscuous: int
    unresolved: int
    paths: int | None
    decision_points: int | None
    audit: list[dict[str, str]]
    culprits: list[dict[str, object]]
    culprits_more: int
    silence: dict[str, object] | None
    thread_surface: dict[str, object] | None
    schedule_silence: dict[str, object] | None
    absolute_paths: dict[str, object] | None


def _meter_ran(l18b: dict) -> bool:
    return isinstance(l18b, dict) and isinstance(l18b.get("resolvable_fraction"), (int, float))


def silence_fraction(counts: dict) -> float:
    """The share of state whose disposition the analyzer could not decide.

    Derived from the same counts the status is derived from, rather than read from a
    second key, so the number that suppresses a grade and the number that sets it can
    never disagree about the same repository."""
    total = sum(counts.values())
    return (counts.get("unresolved", 0) / total) if total else 0.0


def _status(band: str, counts: dict, coarse: bool, meter_ran: bool) -> str:
    """The verifiability status, decided on OBSERVED state only.

    An undecided state used to produce `might`, and `might` graded D, so one call the
    analyzer could not read capped a whole repository at D. That reported a limit of ours
    as a defect in their code. Undecided state now leaves the status alone and is published
    as the silence index instead.

    The floor is the poka-yoke, and it is the part that cannot be dropped. Grading on
    observed state alone would hand an A to code that shows the analyzer nothing, because
    zero observed state is vacuously clean. Above the floor there is no grade at all, so
    hiding everything buys silence rather than a good letter."""
    if not meter_ran or band == "n/a":
        return "na"
    # A promiscuous finding is a PROOF, and a proof does not need coverage of everything
    # else to stand: one state that provably reaches an unbounded decision means no finite
    # suite covers the code, however much of the rest we could not read. So the proof is
    # reported before the floor is consulted. The floor exists to stop obscurity buying a
    # GOOD grade; letting it erase a proven bad one would be the same error backwards.
    if counts.get("promiscuous", 0) > 0:
        return "cannot"
    if silence_fraction(counts) > SILENCE_FLOOR:
        return "na"
    # D, now that silence has vacated it: the reaching partition is finite and countable,
    # its members are unordered, and there are more of them than the bound. Limit testing
    # defeats a large ORDERED domain with a handful of boundary values and defeats a large
    # unordered one with nothing, so cardinality alone was never the test.
    if coarse:
        return "coarse"
    return "can"


def _hygiene(results: dict) -> float | None:
    num = den = 0.0
    for key, weight in _HYGIENE_WEIGHTS.items():
        points = _BAND_POINTS.get(str((results.get(key) or {}).get("band")))
        if points is None:
            continue
        num += weight * points
        den += weight
    return (num / den) if den else None


def _grade(status: str, pct: int | None, hygiene: float | None) -> str | None:
    if status == "na" or pct is None:
        return None
    if status == "cannot":
        return "F"
    if status == "coarse":
        return "D"
    if hygiene is None:
        return "A"
    return "A" if hygiene >= _A_MIN else "B" if hygiene >= _B_MIN else "C"


def _int(v: object) -> int | None:
    return v if isinstance(v, int) else None


def coarse_states(l18b: dict, bound: int | None) -> list[dict]:
    """State whose reaching partition is finite, unordered, and wider than the bound.

    The bound lives here rather than in the classifier because it is a reporting decision:
    the classifier measures the cardinality, and how many unordered cases are too many to
    cover is a judgement about who is doing the testing. A finding whose count could not be
    recovered is excluded, because an unknown count is a limit of ours, not a finding about
    their code. `bound` of None is the explicit "no bound configured" case: D is switched
    off and no state is coarse, which is different from every state being fine and is why
    absence is a case here rather than a default filled in somewhere out of sight."""
    if bound is None:
        return []
    flagged = [
        f for f in (l18b.get("findings") or [])
        if f.get("verdict") == "neutral"
        and state_partition.is_coarse(f.get("partition") or state_partition.UNKNOWN,
                                      bool(f.get("drives_decision")), bound)
    ]
    flagged.sort(key=lambda f: (-f["partition"]["classes"], f.get("file", ""), f.get("line", 0)))
    return flagged


class GradeSummary(TypedDict):
    status: str                 # can | coarse | cannot | na
    counts: dict[str, int]      # neutral / promiscuous / unresolved
    testable_pct: int | None    # share of DECIDED state that is finitely testable
    hygiene: float | None       # weighted health of the audit checks, 0..1
    grade: str | None           # A/B/C (can), D (coarse), F (cannot), None (na)
    silence: float              # share of state the analyzer could not decide
    coarse: list[dict]          # the states that made the verdict coarse, widest first


def grade_summary(results: dict, unordered_class_bound: int | None) -> GradeSummary:
    """The published grade computation - the SINGLE SOURCE of the A-F grade, used by both
    the CLI report and the web card. Verifiability first: CANNOT is F, COARSE is D, above
    the silence floor no grade at all, and when every piece of state is finitely testable
    and coverable, A/B/C is the weighted health of the audit checks.

    `unordered_class_bound` is policy, not a fact about the repository, so it is passed in
    rather than read from here: how many unordered cases are too many depends on who is
    doing the testing, and that answer belongs to whoever is publishing the grade."""
    l18 = results.get("L1.18") or {"band": "n/a"}
    band = str(l18.get("band", "n/a"))
    l18b = results.get("L1.18b") or {}
    counts = (l18b.get("counts") if isinstance(l18b, dict) else None) or {"neutral": 0, "promiscuous": 0, "unresolved": 0}
    coarse = coarse_states(l18b if isinstance(l18b, dict) else {}, unordered_class_bound)
    status = _status(band, counts, bool(coarse), _meter_ran(l18b))
    # The denominator is DECIDED state, not all state. Undecided state is no longer held
    # against the grade, so holding it against the published percentage would put the same
    # blind spot back through a second door.
    decided = counts.get("neutral", 0) + counts.get("promiscuous", 0)
    pct = None if status == "na" else (100 if decided == 0 else round(counts.get("neutral", 0) / decided * 100))
    hygiene = _hygiene(results)
    return {"status": status, "counts": counts, "testable_pct": pct, "hygiene": hygiene,
            "grade": _grade(status, pct, hygiene), "silence": silence_fraction(counts),
            "coarse": coarse}


def build_report(slug: str, lang: str, results: dict) -> Report:
    # The CLI is a boundary, so the configured bound is resolved here rather than deeper in.
    g = grade_summary(results, UNORDERED_CLASS_BOUND)
    status, counts, pct, grade = g["status"], g["counts"], g["testable_pct"], g["grade"]
    l18b = results.get("L1.18b") or {}

    audit = [
        {"tech": label, "value": f"{(results[k].get('value'))}{unit if results[k].get('value') != 'n/a' else ''}",
         "band": str(results[k].get("band", "n/a"))}
        for k, label, unit in _AUDIT if k in results
    ]

    # What limits the grade, by status. CANNOT is limited by proven unbounded state; COARSE
    # by finite state with too many unordered cases, which is a different list selected by a
    # different rule, so the two cannot share one verdict filter.
    flagged: list[dict] = []
    if status == "cannot":
        flagged = [f for f in (l18b.get("findings") or []) if f.get("verdict") == "promiscuous"]
        flagged.sort(key=lambda f: (not f.get("drives_decision"), f.get("file", ""), f.get("line", 0)))
    elif status == "coarse":
        flagged = g["coarse"]
    culprits = [{"file": f.get("file", ""), "line": f.get("line", 0), "state": f.get("state", "?"),
                 "verdict": f.get("verdict", ""), "drives": bool(f.get("drives_decision")),
                 "classes": (f.get("partition") or {}).get("classes", 0)} for f in flagged[:15]]
    culprits_more = max(0, len(flagged) - 15)

    return {
        "slug": slug, "lang": lang, "status": status, "grade": grade, "testable_pct": pct,
        "neutral": counts.get("neutral", 0), "promiscuous": counts.get("promiscuous", 0),
        "unresolved": counts.get("unresolved", 0),
        "paths": _int((results.get("path_cover") or {}).get("value")),
        "decision_points": _int((results.get("L1.19") or {}).get("value")),
        "audit": audit, "culprits": culprits, "culprits_more": culprits_more,
        "silence": l18b.get("silence") if isinstance(l18b.get("silence"), dict) else None,
        "thread_surface": results.get("thread_surface"),
        "schedule_silence": results.get("schedule_silence"),
        "absolute_paths": results.get("absolute_paths"),
    }


def _silence_lines(r: Report) -> list[str]:
    """Every silent site, not a sample. A share tells the reader nothing they can act on;
    the sites do, and their next move is to open each one and decide whether to put an
    explicit contract at that boundary.

    This runs on the `na` report too. The repository most in need of the list is the one
    that was refused a grade BECAUSE of silence, and the first version of this function
    returned before reaching it: the report said "not graded" and named not one site."""
    sil = r.get("silence")
    if not isinstance(sil, dict) or not sil.get("sites"):
        return []
    total = r["neutral"] + r["promiscuous"] + r["unresolved"]
    heading = (f"## What the analyzer could not read ({sil['count']} of {total} states, "
               f"{round(float(sil['fraction']) * 100)}%)")
    lines = ["", heading, ""]
    return lines + [f"- `{s['file']}:{s['line']}` — `{s['state']}` ({_SILENCE_REASON_LINE[s['reason']]})"
                    for s in sil["sites"]]


def report_markdown(r: Report) -> str:
    lines = [f"# Slop Audit — {r['slug']} ({r['lang']})", ""]
    if r["status"] == "na":
        return "\n".join(lines + [f"This repo is {_VERDICT_LINE['na']}"]
                          + _silence_lines(r) + ["", f"> {_SILENCE_NOTE}"])
    if r["grade"] is not None:
        lines += [f"**Grade: {r['grade']}** — {r['testable_pct']}% of its state is finitely testable", ""]
    lines += [f"This code {_VERDICT_LINE.get(r['status'], '')}", "",
              f"- Finitely testable: {r['neutral']}",
              f"- Provably unbounded: {r['promiscuous']}",
              f"- Undecided by the analyzer (silence): {r['unresolved']}"]
    if r["status"] == "can" and r.get("paths"):
        lines.append(f"- Runs that cover every branch: {r['paths']:,}")
    if r.get("culprits"):
        lines += ["", "## What limits it", ""]
        for c in r["culprits"]:
            cases = f", {c['classes']} unordered cases" if r["status"] == "coarse" else ""
            lines.append(f"- `{c['file']}:{c['line']}` — `{c['state']}` ({c['verdict']}{cases}{', drives a decision' if c['drives'] else ''})")
        if r["culprits_more"]:
            lines.append(f"- …and {r['culprits_more']} more")
    lines += _silence_lines(r)
    # Both notes go on every report, not only the ones where the number appears. They say
    # what the measurement does NOT do, and a limit that is only disclosed when it happens
    # to bite is not disclosed - the reader learns the rule from the report they have.
    lines += ["", f"> {_COMPOSE_NOTE}", "", f"> {_SILENCE_NOTE}"]
    if r.get("audit"):
        lines += ["", "## Audit checks", "", "| Check | Value | Band |", "|---|---|---|"]
        lines += [f"| {m['tech']} | {m['value']} | {m['band']} |" for m in r["audit"]]
    ts = r.get("thread_surface")
    if isinstance(ts, dict) and ts.get("verdict") != "n/a":
        lines += ["", f"## Thread-safety surface — {ts['verdict']}", "", str(ts.get("details", ""))]
        for f in (ts.get("findings") or [])[:12]:
            lines.append(f"- `{f['file']}:{f['line']}` — {f['kind']} ({f['severity']}) `{f['symbol']}`")
        lines += ["", "> Audit surface, not a race verdict. A site here means \"verify this\", never \"a race exists\"."]
    ss = r.get("schedule_silence")
    if isinstance(ss, dict) and ss.get("verdict") not in (None, "n/a"):
        lines += ["", f"## Schedule-silence (concurrency anti-coverage) — {ss['verdict']}", ""]
        for f in (ss.get("unmodeled") or []):
            lines.append(f"- `{f}` — flagged surface no loom/shuttle model touches")
    ap = r.get("absolute_paths")
    if isinstance(ap, dict) and ap.get("verdict") == "flagged":
        lines += ["", f"## Hardcoded absolute paths — {ap['band']}", "", str(ap.get("details", ""))]
        for f in (ap.get("findings") or [])[:12]:
            lines.append(f"- `{f['file']}:{f['line']}` — `{f['path']}`")
        lines += ["", "> A machine-specific path in source couples the code to one filesystem and leaks the author's layout."]
    lines += ["", "## How the grade is computed", "", _RUBRIC, "", "Full methodology: https://slopaudit.org"]
    return "\n".join(lines)


_CSS = """
:root{--bg:#fff;--fg:#1a1a1a;--muted:#666;--line:#e5e5e5;--healthy:#16a34a;--nothealthy:#ca8a04;--slop:#dc2626;--na:#71717a}
@media(prefers-color-scheme:dark){:root{--bg:#0f1115;--fg:#e8e8e8;--muted:#9aa0a6;--line:#2a2d33}}
body{max-width:820px;margin:2rem auto;padding:0 1.2rem;font:16px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;color:var(--fg);background:var(--bg)}
h1{font-size:1.7rem;margin:.2rem 0}h2{margin-top:1.8rem;border-bottom:1px solid var(--line);padding-bottom:.3rem;font-size:1.15rem}
.grade{display:inline-flex;align-items:center;gap:.6rem;font-size:2.4rem;font-weight:800}
.grade small{font-size:.9rem;font-weight:500;color:var(--muted)}
.verdict{font-weight:700}.can{color:var(--healthy)}.coarse{color:var(--nothealthy)}.cannot{color:var(--slop)}
.dist{display:flex;gap:1.2rem;margin:.6rem 0;font-size:.9rem}.dist b{font-size:1.1rem}
table{border-collapse:collapse;width:100%;margin:.8rem 0}th,td{text-align:left;padding:.4rem .6rem;border-bottom:1px solid var(--line)}
th{font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
code{font-family:ui-monospace,Menlo,monospace;font-size:.88em;background:color-mix(in srgb,var(--fg) 8%,transparent);padding:.05rem .3rem;border-radius:4px}
.band-Healthy{color:var(--healthy)}.band-NotHealthy{color:var(--nothealthy)}.band-Slop{color:var(--slop)}
.note{color:var(--muted);font-size:.9rem;border-left:3px solid var(--line);padding-left:.9rem}
.rubric{color:var(--muted);font-size:.9rem}
"""


def _silence_html(r: Report, e) -> str:
    """The silent sites as HTML. Same list as the Markdown, same reason it runs on `na`."""
    sil = r.get("silence")
    if not isinstance(sil, dict) or not sil.get("sites"):
        return ""
    rows = "".join(f"<li><code>{e(s['file'])}:{s['line']}</code> — <code>{e(str(s['state']))}</code> "
                   f"({e(_SILENCE_REASON_LINE[s['reason']])})</li>" for s in sil["sites"])
    return (f"<h2>What the analyzer could not read</h2><p>{sil['count']} states, "
            f"{round(float(sil['fraction']) * 100)}% of all state.</p><ul>{rows}</ul>")


def report_html(r: Report) -> str:
    e = _html.escape
    if r["status"] == "na":
        body = f"<p>This repo is {_VERDICT_LINE['na']}</p>{_silence_html(r, e)}<p class=note>{e(_SILENCE_NOTE)}</p>"
        return f"<!doctype html><meta charset=utf-8><title>Slop Audit — {e(r['slug'])}</title><style>{_CSS}</style><h1>Slop Audit — {e(r['slug'])}</h1>{body}"
    grade = f"<div class=grade><span>{r['grade']}</span><small>{r['testable_pct']}% finitely testable</small></div>" if r["grade"] else ""
    audit_rows = "".join(
        f"<tr><td>{e(m['tech'])}</td><td>{e(m['value'])}</td><td class='band-{e(m['band'].replace(' ',''))}'>{e(m['band'])}</td></tr>"
        for m in (r.get("audit") or [])
    )
    culprits = ""
    if r.get("culprits"):
        cases = (lambda c: f", {c['classes']} unordered cases") if r["status"] == "coarse" else (lambda c: "")
        items = "".join(f"<li><code>{e(c['file'])}:{c['line']}</code> — <code>{e(str(c['state']))}</code> ({e(str(c['verdict']))}{cases(c)}{', drives a decision' if c['drives'] else ''})</li>" for c in r["culprits"])
        more = f"<li>and {r['culprits_more']} more</li>" if r["culprits_more"] else ""
        culprits = f"<h2>What limits it</h2><ul>{items}{more}</ul>"
    ts = r.get("thread_surface")
    ts_html = ""
    if isinstance(ts, dict) and ts.get("verdict") != "n/a":
        sites = "".join(f"<li><code>{e(f['file'])}:{f['line']}</code> — {e(f['kind'])} ({e(f['severity'])}) <code>{e(f['symbol'])}</code></li>" for f in (ts.get("findings") or [])[:12])
        ts_html = (f"<h2>Thread-safety surface — {e(str(ts['verdict']))}</h2><p>{e(str(ts.get('details','')))}</p><ul>{sites}</ul>"
                   f"<p class=note>Audit surface, not a race verdict. A site here means \"verify this\", never \"a race exists\".</p>")
    ss = r.get("schedule_silence")
    ss_html = ""
    if isinstance(ss, dict) and ss.get("verdict") not in (None, "n/a"):
        um = "".join(f"<li><code>{e(f)}</code></li>" for f in (ss.get("unmodeled") or []))
        ss_html = f"<h2>Schedule-silence — {e(str(ss['verdict']))}</h2><p class=note>Flagged concurrency surface that no loom/shuttle model touches.</p><ul>{um}</ul>"
    silence_html = _silence_html(r, e)
    ap = r.get("absolute_paths")
    ap_html = ""
    if isinstance(ap, dict) and ap.get("verdict") == "flagged":
        hits = "".join(f"<li><code>{e(f['file'])}:{f['line']}</code> — <code>{e(f['path'])}</code></li>" for f in (ap.get("findings") or [])[:12])
        ap_html = (f"<h2>Hardcoded absolute paths — {e(str(ap['band']))}</h2><p>{e(str(ap.get('details','')))}</p><ul>{hits}</ul>"
                   f"<p class=note>A machine-specific path in source couples the code to one filesystem and leaks the author's layout.</p>")
    return (
        f"<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>Slop Audit — {e(r['slug'])}</title><style>{_CSS}</style></head><body>"
        f"<h1>Slop Audit — {e(r['slug'])} <small style='font-size:.6em;color:var(--muted)'>{e(r['lang'])}</small></h1>"
        f"{grade}"
        f"<p class='verdict {r['status']}'>This code {_VERDICT_LINE.get(r['status'],'')}</p>"
        f"<div class=dist><span><b>{r['neutral']}</b> finitely testable</span><span><b>{r['promiscuous']}</b> provably unbounded</span><span><b>{r['unresolved']}</b> undecided (silence)</span></div>"
        f"{culprits}{silence_html}<p class=note>{e(_COMPOSE_NOTE)}</p><p class=note>{e(_SILENCE_NOTE)}</p>"
        f"<h2>Audit checks</h2><table><thead><tr><th>Check</th><th>Value</th><th>Band</th></tr></thead><tbody>{audit_rows}</tbody></table>"
        f"{ts_html}{ss_html}{ap_html}"
        f"<h2>How the grade is computed</h2><p class=rubric>{e(_RUBRIC)}</p>"
        f"<p class=rubric>Full methodology: <a href='https://slopaudit.org'>slopaudit.org</a></p>"
        f"</body></html>"
    )
