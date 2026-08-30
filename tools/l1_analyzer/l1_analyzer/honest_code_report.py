"""What an L1.21 assessment looks like when a person or an agent reads it.

Two readers and two shapes. `report` is the per-clause document, with the clauses nobody
could decide listed apart from the score so a reader can see what the number covers.
`hook_report` is what an agent gets mid-edit: where, which clause, and what to do instead,
and nothing at all when the file is clean.

Split out of honest_code.py on 2026-08-30, when that file crossed a thousand lines of code
and the audit reported it as a god-file. The seam is real: what the clauses ARE is a
different question from how a result PRINTS, and the printing half changes on what a reader
needs while the clause list changes on what the canon says.
"""

from __future__ import annotations

from pathlib import Path

from l1_analyzer.honest_code import CLAUSES, Assessment

# The principles this instrument does not check, named in every report. A share over the
# clauses that exist cannot see a principle nobody wrote a clause for, and a reader told the
# denominator but not what sits outside it reads a hundred per cent as covering the canon.
# That is the failure this instrument reports in other people's code.
NO_CLAUSE_MEASURES = (
    "Two of the principles have no clause and are outside the share above. Constrain AI "
    "with Data Shape Contracts mitigates a failure rather than eliminating one, so "
    "reporting a repository for declining it would report a choice as a defect. Watch the "
    "Test Fail First cannot be checked by anything: the evidence is destroyed by the act of "
    "passing, because a test that failed and now passes is byte-identical to a test that "
    "never failed.")


def report(assessment: Assessment) -> str:
    """The per-clause result a person reads.

    The clauses nobody could decide are listed apart from the score, each with its reason,
    so a reader can see what the number covers rather than assume it covered everything."""
    lines = [f"# L1.21 — Honest Code conformity — {Path(assessment['path']).name}", ""]
    share = assessment["conformity"]
    shown = f"{share}%" if share is not None else "not measured"
    lines += [(f"Conformity: {shown} ({assessment['band']}), over "
               f"{assessment['decided_clauses']} of {len(CLAUSES)} clauses that were "
               "decided"), ""]
    lines += [f"> {NO_CLAUSE_MEASURES}", ""]
    if assessment["unreadable_reason"]:
        lines += [f"> {assessment['unreadable_reason']}", ""]
    for block in assessment["unexamined"]:
        # The language is named only where the findings corroborate it. A block that fires
        # nothing may well not be the language a grammar accepted it as: twelve lines of SQL
        # are accepted whole by the ruby grammar, there is no SQL grammar, and a database
        # driver holds dozens of them. Printing that guess dozens of times teaches a reader
        # to skip the field, which costs the embedded-widget case it exists for.
        if not block["findings"]:
            lines += [(f"> line {block['line']}: {block['lines']} lines are not this file's "
                       "language. Every clause that could read them found nothing, and they "
                       "are outside the share above either way."), ""]
            continue
        lines += [(f"> line {block['line']}: {block['lines']} lines of {block['language']} "
                   f"that the share above does not cover. {len(block['findings'])} finding(s) "
                   "in them:"), ""]
        for finding in block["findings"]:
            lines.append(f"- `{finding['clause']}:{finding['line']}` — {finding['detail']}")
        lines.append("")

    broken = [c for c in assessment["clauses"] if c["decided"] and c["findings"]]
    held = [c for c in assessment["clauses"] if c["decided"] and not c["findings"]]
    undecided = [c for c in assessment["clauses"] if not c["decided"]]
    declared = [a for c in assessment["clauses"] for a in c["allowed"]]
    by_declaration = [a for c in assessment["clauses"] for a in c["declared"]]

    for clause in broken:
        lines.append(f"## {clause['code']} — {clause['name']} ({len(clause['findings'])})")
        lines.append("")
        for finding in clause["findings"]:
            lines.append(f"- `{finding['symbol']}:{finding['line']}` — {finding['detail']}")
            lines.append(f"      instead: {finding['instead']}")
            if finding["undecided"]:
                lines.append(f"      not decided: {finding['undecided']}")
        lines.append("")
    if held:
        lines += ["## clauses that hold", "", ", ".join(c["code"] for c in held), ""]
    if declared:
        lines += [f"## declared exceptions ({len(declared)})", "",
                  ("> Sites the author stated a reason for. They are not violations and "
                   "they are not invisible: a reader audits the reason here."), ""]
        for entry in declared:
            lines.append(f"- `{entry['clause']}:{entry['line']}` — {entry['reason']}")
        lines.append("")
    if by_declaration:
        lines += [f"## boundary declarations ({len(by_declaration)})", "",
                  ("> Sites a boundary decorator withheld. The declaration overrode this "
                   "reader's call-graph inference, which is the case worth seeing; a "
                   "declaration that agreed with it withheld nothing and is not listed."), ""]
        for entry in by_declaration:
            lines.append(f"- `{entry['symbol']}:{entry['line']}` — {entry['detail']}")
        lines.append("")
    if undecided:
        lines += [f"## clauses not decided ({len(undecided)})", "",
                  ("> These are outside the share, numerator and denominator both. A clause "
                   "nobody checked is not a clause that passed."), ""]
        for clause in undecided:
            lines.append(f"- {clause['code']} — {clause['name']}: {clause['reason']}")
        lines.append("")
    return "\n".join(lines)


def hook_report(assessment: Assessment) -> str:
    """The one thing an agent needs mid-edit: where, which clause, and what to do instead.

    Two lines per finding rather than one. The locator has to be readable at a glance, and
    the instruction has to be complete enough to act on; welding them into a single
    two-hundred-character line makes neither.

    Silence on a clean write is the correct output. A hook that congratulates the agent on
    every file teaches it to skip the output, and then the one that matters is skipped
    too."""
    name = assessment["path"]
    lines: list[str] = []
    for block in assessment["unexamined"]:
        # A block that fires nothing is not worth an agent's attention mid-edit. It was read
        # by every clause that could read it and they found nothing, and the language it was
        # named as may well be wrong: a database driver's SQL is accepted whole by the ruby
        # grammar and there is no SQL grammar. Printing that guess on every query is what
        # teaches an agent to skip the output.
        for finding in block["findings"]:
            lines.append(f"{name}:{finding['line']} {finding['clause']} "
                         f"in embedded {block['language']}: {finding['detail']}")
            lines.append(f"    instead: {finding['instead']}")
    for clause in assessment["clauses"]:
        for finding in clause["findings"]:
            lines.append(f"{name}:{finding['line']} {clause['code']} {finding['detail']}")
            lines.append(f"    instead: {finding['instead']}")
    return "\n".join(lines)
