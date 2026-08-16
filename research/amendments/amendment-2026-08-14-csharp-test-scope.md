# Amendment 2026-08-14: a C# test project is a test directory

## What was wrong

The shared production-scope rule matched a path component exactly against the scope-out markers `tests` and `test`. C# convention is a project directory named `<Project>.Tests`, which an exact match never catches. Every C# repository's whole test tree was therefore measured as production code by L1.15, L1.17, L1.19, L1.18, L1.18b and the absolute-path check.

The evidence is JamesNK/Newtonsoft.Json at its pinned corpus commit. It reported 31 hardcoded machine-specific absolute paths across 13 files, and every one of them was fixture data under `Src/Newtonsoft.Json.Tests/`: strings like `c:\schema\Person.json` embedded in stack-trace test data. Nothing in the library carried one. A test that proves a path detector fires has to contain the path it detects, which is exactly why the scope rule exists; it just did not fire on the directory C# uses.

The rule lives in `_bucket_reason` (L1.15, L1.17, L1.19, L1.17's god-file scope, the state meters) and in `_read_text_files` via `_in_ignored_dir` (the absolute-path check). One definition, both readers, so both were wrong the same way.

## The new rule

**A path component is a test directory when, lowercased, it equals `tests` or `test`, or ends with `.tests` or `.test`.**

Deliberately that narrow. `spec`, `specs`, `fixtures` and `__tests__` are not added: they are not the directory convention in the languages this scope covers, and widening the scope-out rule removes code from measurement, which is the direction that flatters a repository. Any widening should be argued on its own.

Two consequences worth naming:

- The match is now case-insensitive **for the test markers only**. `Src/Tests/` and `Src/Test/` scope out where they did not before. Every other marker — `conformance`, `docs` — keeps its exact, case-sensitive match, so this change touches nothing outside the test-directory concept.
- The dotted form must be the whole component after the final dot. `Contests`, `Latest` and `Newtonsoft.Json` stay in production scope. `Foo.Tests.Integration` does not match on `.Tests` and stays in scope, which is the narrow reading; the corpus has no such directory outside an already-excluded `test/` parent.

The matching lives in two new helpers, `_component_scoped_out` and `_extra_reason`, so `_bucket_reason` and `_in_ignored_dir` share one implementation instead of two copies of `e in parts`.

## What the numbers did

Both C# corpus repositories at their pinned commits, Python reference, `--lang csharp --no-exec`:

| Repo | Measure | Before | After |
|---|---|---|---|
| JamesNK/Newtonsoft.Json | absolute paths | 31 across 13 files (Slop) | 0 (Healthy) |
| | L1.15 type-escape density | 10.61/kLOC (2056 escapes, ~193 kLOC) | 15.22/kLOC (1056 escapes, ~69 kLOC) |
| | L1.17 god-file concentration | 4.87% (46/945 files >1k LOC, 1 >4k) | 7.85% (19/242 files >1k LOC, 0 >4k, 27 scoped out) |
| | L1.19 decision points | 11329 across 945 files | 10338 across 242 files |
| | L1.18 external mutable state | 0.9% (68/7291 functions) | 0.0% (0/2670 functions) |
| | L1.18b finite testability | 886 neutral / 41 promiscuous / 228 unresolved | 464 / 33 / 143 |
| restsharp/RestSharp | every indicator | unchanged | unchanged |

RestSharp is the control. Its test projects sit under a `test/` parent (`test/RestSharp.Tests/`), which the exact match already caught, so not one of its numbers moves. That is the shape of the defect: it hid wherever a repository happened to nest its test projects under a plain `test/`, and bit wherever it did not.

Newtonsoft.Json's densities rise because the denominator shrinks by two thirds — 193 kLOC of "production code" was 124 kLOC of tests. No band changed on either repository. L1.16 (trailing whitespace) and L1.8 (test-to-production ratio) are outside this scope rule and did not move.

The Java and C corpus entries do not move either. Their test directories are already named `test` or `tests` exactly, and no directory anywhere in the four repositories ends in `.test` or `.tests`.

## Regression cover

`tests/test_bucketing.py::test_dotted_csharp_test_project_is_scoped_out` calls `_bucket_reason` directly: `Src/Newtonsoft.Json.Tests/`, `Src/Newtonsoft.Json.Test/`, `Src/Tests/` and `Src/tests/` all scope out with the right reason, while `Src/Newtonsoft.Json/`, `Src/Contests/` and `Src/Latest/` stay in scope.

`tests/test_absolute_paths.py::test_scopes_out_a_dotted_csharp_test_project` proves the same through the reader that produced the 31 findings: a repository with one path in the library and one in each of `.Tests` and `.Test` reports exactly one finding, in the library.

`src/lib.rs::tests::a_dotted_csharp_test_project_is_scoped_out` carries the same eight cases against `bucket_reason`.

All three were run against the unfixed code first and failed there, so they measure the fix and not the fixture.

## The port

`tools/slop-audit-rs` landed the change in the same commit. `lib.rs` gains `TEST_DIR_MARKERS`, `component_scoped_out` and `extra_reason`; `bucket_reason` and `absolute_paths::production_files` both call `extra_reason` instead of matching components inline, which removes the port's own second copy of the rule. Parity was re-run: 16/16 indicators equal on this repository, and 16/16 on each of Newtonsoft.Json and RestSharp.

## Reported, not fixed: two definitions of "test code"

`indicators.py` holds a second and richer definition. `_TEST_PATH_MARKERS = {"test", "tests", "spec", "specs", "__tests__"}` feeds `_is_test_path`, which also matches a filename starting `test_` or ending `_test`, `.test` or `.spec` before the extension. L1.8 (test-to-production LOC ratio) uses it; nothing else does.

It has the same blind spot and a visible consequence. L1.8 reports Newtonsoft.Json as **0.0 — 0 test LOC against 193,720 production LOC, band Slop**, for a repository whose test project is roughly 124 kLOC. No component of `Src/Newtonsoft.Json.Tests/Serialization/JsonSerializerTests.cs` equals a marker, and the filename convention it does match is the Python and Go one (`test_x`, `x_test.go`), not the C# one (`XTests.cs`).

Unifying them is right in principle and is not trivially safe, so it is not done here:

- The two definitions answer different questions. The scope rule asks "is this file outside the code under audit?" and must stay conservative, because over-matching removes real production code from measurement. L1.8 asks "is this file a test?" and must stay generous, because under-matching makes a well-tested repository look untested.
- Unifying on the scope rule would narrow L1.8 (it would lose `spec`, `specs`, `__tests__` and the filename arm) and make its already-false Newtonsoft.Json answer no better.
- Unifying on `_TEST_PATH_MARKERS` would widen the production scope-out to `spec`, `specs` and `__tests__` and to any filename matching the test-filename conventions. That removes files from L1.15, L1.17 and L1.19 across every language, in the flattering direction, and needs its own pre-registration.

The correct shape is one predicate, `is_test_path(path) -> bool`, defined once and used by both, with the scope rule and L1.8 differing only in what they do with the answer — not in what "test" means. Getting there means deciding the single definition on the merits and re-running the full corpus, in both tools. It is a measurement change, not a repair. The L1.8 C# defect (a large test suite counted as zero) should be fixed as part of it, and is recorded here so it is not lost.

## Note for Paper A

C# L1.15, L1.17, L1.19, L1.18 and L1.18b numbers move under this fix, from measurements taken over a mixed production-and-test tree to measurements taken over production code alone. It is a defect correction, not a definitional change, and belongs in the v1-vs-v2 side-by-side re-run per the finite-testability supersession rule. Any previously published C# figure taken over a repository whose test projects are not nested under a plain `test/` is affected.
