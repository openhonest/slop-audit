# Changelog — slop-audit-l1

This is the Python reference implementation. It is versioned separately from the Slop Audit methodology, which is still a v0 frame draft: `spec/00-frontmatter.md` says so, and `spec/dimensions/README.md` records that the eighteen-dimension catalog is a stub. A 1.0 here is a promise about this instrument, not about the standard it implements.

## 1.0.0

The first release that promises a stable surface.

**What is stable from here.** The `slop-audit-l1` command's flags and their meanings. The JSON document from `--format json`: its top-level keys, the `results` map keyed by indicator code, and `analyzer_version`, which reads from this package so the JSON and the package can never disagree. The exit codes: 0 for a completed run, 1 for a gate that failed, 2 for a refused argument. Breaking any of those means 2.0.0.

**L1.21 is outside the promise, and it moves.** The Honest Code conformity check is opt-in, states an opinion, and is still being built out. Its output shape and its exit behaviour changed twice on the day 1.0.0 shipped, both times additively. Treat its JSON as unstable and read the README section before consuming it.

**What is not covered by the promise.** The prose in reports and cards, which is written for a person and will keep improving. The `research/candidates/` directory, which is candidate work by definition. Anything behind `--prove`, which calls a model and is opt-in.

**What this version can and cannot read.** Twenty-six indicators across nine languages. The L1.21 Honest Code assessment carries nineteen clauses; ten read every language the node vocabulary covers, two read the file's text, and nine still read Python's own parser and report `unreadable` with a reason on any other language. That count is published per file rather than assumed, so a share is always over the clauses that actually read the file.

**Known, measured, and open.** Run against itself, the package holds 855 of 868 clause-readings, or 98.5%. Every failure is clause 4, I/O below the boundary, at 21 sites in 13 of 62 modules. They are listed by running the tool on itself and are not suppressed.

**Fixed on the way to this release.**

- The documented install did not work. `uv sync` could resolve a free-threaded Python 3.14, which satisfies `requires-python`, and none of the nine tree-sitter grammars build there. `.python-version` now pins the interpreter the suite is tested against. CI had no pin either, so a passing build was never evidence the documented path worked.
- `--indicators banana` selected nothing and exited 0. A caller could not tell a typo from an audit that found nothing. The valid set is one table now, and an unknown value is refused with the value named and the working form shown.
- The card's disclosure of what it could not read was written in this project's own vocabulary. It now says what was counted, how many were not opened, why not, and that the grade counts those neither way.

## 0.1.0

Initial public implementation.
