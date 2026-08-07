"""The full Slop Audit report, the way try.slopaudit.org renders it, from the CLI.

Ported into the engine so the CLI and the web produce the same report: the single A-F
grade, the verifiability verdict (CAN / MIGHT / CANNOT), the finitely-testable share, the
audit checks with bands, and the concurrency layer (thread-surface + schedule-silence).
build_report is a pure mapping from analyzer results to a model; report_markdown and
report_html render it. No copy.md dependency; the prose is inlined here.

The grade rule (published, not hidden): verifiability first. CANNOT is F, MIGHT is D. When
every piece of state is finitely testable, A/B/C is the weighted health of the audit
checks - god-files and type-escapes weigh most.
"""

from __future__ import annotations

import html as _html
from typing import TypedDict

_HYGIENE_WEIGHTS = {"L1.17": 3, "L1.15": 3, "L1.10": 2, "L1.11": 1, "L1.9": 1, "L1.16": 1}
_BAND_POINTS = {"Healthy": 1.0, "Not Healthy": 0.5, "Slop": 0.0}
_A_MIN, _B_MIN = 0.85, 0.60

# Audit checks shown on the card, in order, with their published labels.
_AUDIT = [
    ("L1.15", "L1.15 · type-escape density", "/kloc"),
    ("L1.17", "L1.17 · god-file concentration", "%"),
    ("L1.16", "L1.16 · trailing-whitespace density", "%"),
    ("L1.10", "L1.10 · CI/CD pipelines", ""),
    ("L1.11", "L1.11 · containerization", ""),
    ("L1.9", "L1.9 · pre-commit hooks", ""),
]
_VERDICT_LINE = {
    "can": "CAN be exhaustively tested.",
    "might": "MIGHT be exhaustively testable (some state is undetermined).",
    "cannot": "CANNOT be exhaustively tested (some state is provably unbounded).",
    "na": "not analyzable (no source in a language the analyzer reads).",
}
_RUBRIC = (
    "The grade is verifiability first, by a rule we publish rather than hide. The verdict sets the tier: "
    "CANNOT is F (some state is provably unbounded, so no finite test suite covers it), MIGHT is D (some state "
    "is undetermined). When every piece of state is finitely testable, the audit checks decide A, B, or C by "
    "weighted health - god-files and type-escapes weigh most (3 each), then CI (2), then containers, pre-commit, "
    "and formatting (1 each). The number is the share of state that is finitely testable. No hidden weights."
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
    thread_surface: dict[str, object] | None
    schedule_silence: dict[str, object] | None


def _meter_ran(l18b: dict) -> bool:
    return isinstance(l18b, dict) and isinstance(l18b.get("resolvable_fraction"), (int, float))


def _status(band: str, counts: dict, meter_ran: bool) -> str:
    if not meter_ran or band == "n/a":
        return "na"
    if counts.get("promiscuous", 0) > 0:
        return "cannot"
    if counts.get("unresolved", 0) > 0:
        return "might"
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
    if status == "might":
        return "D"
    if hygiene is None:
        return "A"
    return "A" if hygiene >= _A_MIN else "B" if hygiene >= _B_MIN else "C"


def _int(v: object) -> int | None:
    return v if isinstance(v, int) else None


class GradeSummary(TypedDict):
    status: str                 # can | might | cannot | na
    counts: dict[str, int]      # neutral / promiscuous / unresolved
    testable_pct: int | None    # share of state that is finitely testable
    hygiene: float | None       # weighted health of the audit checks, 0..1
    grade: str | None           # A/B/C (can), D (might), F (cannot), None (na)


def grade_summary(results: dict) -> GradeSummary:
    """The published grade computation - the SINGLE SOURCE of the A-F grade, used by both
    the CLI report and the web card. Verifiability first: CANNOT is F, MIGHT is D, and when
    every piece of state is finitely testable, A/B/C is the weighted health of the audit
    checks (god-files and type-escapes weigh most)."""
    l18 = results.get("L1.18") or {"band": "n/a"}
    band = str(l18.get("band", "n/a"))
    l18b = results.get("L1.18b") or {}
    counts = (l18b.get("counts") if isinstance(l18b, dict) else None) or {"neutral": 0, "promiscuous": 0, "unresolved": 0}
    status = _status(band, counts, _meter_ran(l18b))
    total = sum(counts.values())
    pct = None if status == "na" else (100 if total == 0 else round(counts.get("neutral", 0) / total * 100))
    hygiene = _hygiene(results)
    return {"status": status, "counts": counts, "testable_pct": pct, "hygiene": hygiene,
            "grade": _grade(status, pct, hygiene)}


def build_report(slug: str, lang: str, results: dict) -> Report:
    g = grade_summary(results)
    status, counts, pct, grade = g["status"], g["counts"], g["testable_pct"], g["grade"]
    l18b = results.get("L1.18b") or {}

    audit = [
        {"tech": label, "value": f"{(results[k].get('value'))}{unit if results[k].get('value') != 'n/a' else ''}",
         "band": str(results[k].get("band", "n/a"))}
        for k, label, unit in _AUDIT if k in results
    ]

    want = {"cannot": "promiscuous", "might": "unresolved"}.get(status)
    culprits, culprits_more = [], 0
    if want:
        flagged = [f for f in (l18b.get("findings") or []) if f.get("verdict") == want]
        flagged.sort(key=lambda f: (not f.get("drives_decision"), f.get("file", ""), f.get("line", 0)))
        culprits = [{"file": f.get("file", ""), "line": f.get("line", 0), "state": f.get("state", "?"),
                     "verdict": f.get("verdict", ""), "drives": bool(f.get("drives_decision"))} for f in flagged[:15]]
        culprits_more = max(0, len(flagged) - 15)

    return {
        "slug": slug, "lang": lang, "status": status, "grade": grade, "testable_pct": pct,
        "neutral": counts.get("neutral", 0), "promiscuous": counts.get("promiscuous", 0),
        "unresolved": counts.get("unresolved", 0),
        "paths": _int((results.get("path_cover") or {}).get("value")),
        "decision_points": _int((results.get("L1.19") or {}).get("value")),
        "audit": audit, "culprits": culprits, "culprits_more": culprits_more,
        "thread_surface": results.get("thread_surface"),
        "schedule_silence": results.get("schedule_silence"),
    }


def report_markdown(r: Report) -> str:
    lines = [f"# Slop Audit — {r['slug']} ({r['lang']})", ""]
    if r["status"] == "na":
        return "\n".join(lines + [f"This repo is {_VERDICT_LINE['na']}"])
    if r["grade"] is not None:
        lines += [f"**Grade: {r['grade']}** — {r['testable_pct']}% of its state is finitely testable", ""]
    lines += [f"This code {_VERDICT_LINE.get(r['status'], '')}", "",
              f"- Finitely testable: {r['neutral']}",
              f"- Provably unbounded: {r['promiscuous']}",
              f"- Undetermined: {r['unresolved']}"]
    if r["status"] == "can" and r.get("paths"):
        lines.append(f"- Runs that cover every branch: {r['paths']:,}")
    if r.get("culprits"):
        lines += ["", "## What limits it", ""]
        for c in r["culprits"]:
            lines.append(f"- `{c['file']}:{c['line']}` — `{c['state']}` ({c['verdict']}{', drives a decision' if c['drives'] else ''})")
        if r["culprits_more"]:
            lines.append(f"- …and {r['culprits_more']} more")
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
    lines += ["", "## How the grade is computed", "", _RUBRIC, "", "Full methodology: https://slopaudit.org"]
    return "\n".join(lines)


_CSS = """
:root{--bg:#fff;--fg:#1a1a1a;--muted:#666;--line:#e5e5e5;--healthy:#16a34a;--nothealthy:#ca8a04;--slop:#dc2626;--na:#71717a}
@media(prefers-color-scheme:dark){:root{--bg:#0f1115;--fg:#e8e8e8;--muted:#9aa0a6;--line:#2a2d33}}
body{max-width:820px;margin:2rem auto;padding:0 1.2rem;font:16px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;color:var(--fg);background:var(--bg)}
h1{font-size:1.7rem;margin:.2rem 0}h2{margin-top:1.8rem;border-bottom:1px solid var(--line);padding-bottom:.3rem;font-size:1.15rem}
.grade{display:inline-flex;align-items:center;gap:.6rem;font-size:2.4rem;font-weight:800}
.grade small{font-size:.9rem;font-weight:500;color:var(--muted)}
.verdict{font-weight:700}.can{color:var(--healthy)}.might{color:var(--nothealthy)}.cannot{color:var(--slop)}
.dist{display:flex;gap:1.2rem;margin:.6rem 0;font-size:.9rem}.dist b{font-size:1.1rem}
table{border-collapse:collapse;width:100%;margin:.8rem 0}th,td{text-align:left;padding:.4rem .6rem;border-bottom:1px solid var(--line)}
th{font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
code{font-family:ui-monospace,Menlo,monospace;font-size:.88em;background:color-mix(in srgb,var(--fg) 8%,transparent);padding:.05rem .3rem;border-radius:4px}
.band-Healthy{color:var(--healthy)}.band-NotHealthy{color:var(--nothealthy)}.band-Slop{color:var(--slop)}
.note{color:var(--muted);font-size:.9rem;border-left:3px solid var(--line);padding-left:.9rem}
.rubric{color:var(--muted);font-size:.9rem}
"""


def report_html(r: Report) -> str:
    e = _html.escape
    if r["status"] == "na":
        body = f"<p>This repo is {_VERDICT_LINE['na']}</p>"
        return f"<!doctype html><meta charset=utf-8><title>Slop Audit — {e(r['slug'])}</title><style>{_CSS}</style><h1>Slop Audit — {e(r['slug'])}</h1>{body}"
    grade = f"<div class=grade><span>{r['grade']}</span><small>{r['testable_pct']}% finitely testable</small></div>" if r["grade"] else ""
    audit_rows = "".join(
        f"<tr><td>{e(m['tech'])}</td><td>{e(m['value'])}</td><td class='band-{e(m['band'].replace(' ',''))}'>{e(m['band'])}</td></tr>"
        for m in (r.get("audit") or [])
    )
    culprits = ""
    if r.get("culprits"):
        items = "".join(f"<li><code>{e(c['file'])}:{c['line']}</code> — <code>{e(str(c['state']))}</code> ({e(str(c['verdict']))}{', drives a decision' if c['drives'] else ''})</li>" for c in r["culprits"])
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
    return (
        f"<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>Slop Audit — {e(r['slug'])}</title><style>{_CSS}</style></head><body>"
        f"<h1>Slop Audit — {e(r['slug'])} <small style='font-size:.6em;color:var(--muted)'>{e(r['lang'])}</small></h1>"
        f"{grade}"
        f"<p class='verdict {r['status']}'>This code {_VERDICT_LINE.get(r['status'],'')}</p>"
        f"<div class=dist><span><b>{r['neutral']}</b> finitely testable</span><span><b>{r['promiscuous']}</b> provably unbounded</span><span><b>{r['unresolved']}</b> undetermined</span></div>"
        f"{culprits}"
        f"<h2>Audit checks</h2><table><thead><tr><th>Check</th><th>Value</th><th>Band</th></tr></thead><tbody>{audit_rows}</tbody></table>"
        f"{ts_html}{ss_html}"
        f"<h2>How the grade is computed</h2><p class=rubric>{e(_RUBRIC)}</p>"
        f"<p class=rubric>Full methodology: <a href='https://slopaudit.org'>slopaudit.org</a></p>"
        f"</body></html>"
    )
