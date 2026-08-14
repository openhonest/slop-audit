# Amendment 2026-08-14: the meter stops charging itself for its own vocabulary

Five changes across two checks. Every one of them removes a case where the instrument reported on documentation, test fixtures, or its own pattern tables rather than on code. All five change measured numbers, so they are recorded here.

The trigger was running the portable Rust bundle against this repo. The panel came back with 57 absolute-path findings and 14 type escapes. Not one of the 57 was a machine-specific path, and 3 of the 14 were the meter reading its own source.

## The shared cause

A detector that ships with a pattern table, and documents what it detects, contains the strings it looks for. Nothing in either check separated a pattern from an instance of that pattern. That is not a quirk of this repo. It fires on any audited codebase that writes about the thing it is doing, and it fires hardest on the languages whose escape token is an ordinary English word.

## 1. A bare root is not a machine path (L1 additive, absolute paths)

`/tmp/` names a convention. `/tmp/scratch/out.json` names one machine's file. The unix arm required nothing after the root, so a tool that lists roots was flagged once per root, and this module was flagged eight times for defining its own vocabulary.

The arm now requires at least one character after the root.

## 2. Two characters separate a drive path from an escape sequence (L1 additive, absolute paths)

The Windows arm read a letter, a colon and a backslash as a drive path. A single letter, a colon and a one-character escape is a string escape in every language that has strings. Source writing `"x:\n"` was reported as a hardcoded path on drive X. This false positive fired 21 times on this repo's own tests.

The arm now requires two characters after the drive backslash. Every real drive path still matches, down to a four-character directory at the drive root.

## 3. The absolute-path check moves to the production scope (L1 additive, absolute paths)

It scanned every source file, including the test tree. A test that proves a path detector fires has to contain the path it detects, so scanning the test tree measures the fixtures.

It now applies the same `("tests", "test")` exclusion L1.15, L1.17 and L1.19 already use. This is a scope change, not a bug fix: a genuine leaked path inside a test tree is no longer reported. The consistency argument wins, because the alternative is a check that reports Slop on any repository disciplined enough to test its own path handling.

## 4. A type token inside a string is data (L1.15)

`("Any",)` in a pattern table does not opt out of a type checker. Neither does an `"object"` key in a C# message or a `"dynamic"` label. A leaf whose ancestors include a string node is no longer counted.

The cost is a stringified forward reference, `x: "Any"`, which is rare. The benefit is that C# and Java, whose escape tokens are `object` and `Object`, stop being charged for every string containing an ordinary English word.

## 5. A comment counts only when it begins with the marker (L1.15)

A real suppression starts with `# type: ignore` or `// @ts-ignore`. A comment that mentions the marker while explaining the rule is documentation. This module's own pattern list described the marker three times and was charged three escapes for saying so.

The comment rule now matches on a prefix rather than anywhere in the text.

## What this repo's panel did

| Check | Before | After |
|---|---|---|
| Absolute paths | 57, Slop | 0, Healthy |
| L1.15 type escapes | 1.47/kLOC, Not Healthy | 0.0/kLOC, Healthy |

The L1.15 move is two effects, and they should not be confused. Four real `dict[str, Any]` hatches were typed away (a `BucketedPaths` TypedDict, a `PathCover` TypedDict, and `object` in place of `Any` where the payload is heterogeneous by construction), and two dead `from typing import Any` imports were removed from `ui-audit`. That took 14 to 3. Changes 4 and 5 took 3 to 0. The pre-commit ratchet drops from 14 to 0 accordingly.

## Regression cover

`tests/test_absolute_paths.py`: an escape sequence is not a Windows path; a short drive path still is; a bare root is not flagged; the test tree is scoped out.

`tests/test_basic.py`: a type token inside a string is data; a comment explaining the marker is documentation; a real suppression carrying an error code still counts.

## The port

Every change landed in `tools/slop-audit-rs` in the same commit and the panels were re-diffed. The Rust bundle and the Python reference remain equal on all sixteen ported indicators, across a repository in each of the nine supported languages.

## Not fixed here

`@SuppressWarnings` sits in the comment-marker list, but in Java it is an annotation node, not a comment, so it has never been counted where it actually appears. Java's real suppression marker is therefore invisible to L1.15. Recorded as a defect rather than fixed, because it widens the measure rather than narrowing a false positive.
