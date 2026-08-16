# Amendment 2026-08-14: L1.8 learns the .NET and JVM test conventions

L1.8 reported the inverse of the truth on C# repositories. This is a bug fix to a scored, frozen indicator, and it moves a band, so it is recorded here in full.

## What was wrong

`_is_test_file` recognised test code by three conventions: a path component named `test`, `tests`, `spec`, `specs` or `__tests__`; a file name starting `test_`; and a file name ending `_test`, `.test` or `.spec` before its extension. Those are the Python, Go and JavaScript conventions.

.NET writes neither. A test project is a sibling directory named `<Project>.Tests`, and its files are `XTests.cs`. Nothing in the predicate could see either.

The consequence, measured on the pinned corpus:

| Repo | Before | After |
|---|---|---|
| JamesNK/Newtonsoft.Json | 0.0, **Slop**, "0 test / 193720 production LOC" | 1.8, **Healthy**, "124411 test / 69309 production LOC" |

That repository has 704 test files and roughly 124,000 lines of test code. L1.8 called it the worst possible reading, zero tests, on a codebase that is more than half tests. A reader of that panel would conclude the opposite of the truth about the one property L1.8 exists to report.

## The two new arms

**A dotted project directory is a test directory.** A path component whose lowercase form ends in `.test`, `.tests`, `.spec` or `.specs` counts, alongside the existing exact names. This is the same rule the production scope learned earlier the same day, in `amendment-2026-08-14-csharp-test-scope.md`; the two are now consistent about what a .NET test project looks like.

**A capitalised test stem is a test file.** A file whose stem ends in `Test`, `Tests`, `Spec` or `Specs`, in its original casing, counts.

The capital is doing real work and is not a stylistic choice. Lowercasing first would make `Latest.java`, `manifest.py` and `Protest.cs` test files, because each ends in `test` once folded. Requiring the capital means the arm fires on a CamelCase boundary, which is exactly where the .NET and JVM conventions put it, and nowhere else. The regression tests hold all three of those names on the production side.

## What moved elsewhere

| Repo | Before | After |
|---|---|---|
| junit-team/junit4 | 1.27, "25384 test / 20006 production" | 1.29, "25585 test / 19805 production" |
| google/gson | 1.42 | unchanged |
| restsharp/RestSharp | 1.02 | unchanged |
| json-c/json-c | 0.44 | unchanged |
| libuv/libuv | 0.77 | unchanged |

junit4 moves by about 200 lines: a handful of `*Test.java` files outside the `src/test` tree, which the new stem arm now reads correctly. RestSharp does not move, because its test projects already sat under a plain `test/` parent, which makes it the control for this change.

## Scope of the correction

Any C# figure measured before this fix, over a repository whose tests are not under a plain `test/` parent, understated the test ratio and in the limiting case reported zero. The 50 C# repositories in the 200-repository study are the population to re-check; that re-measurement is not part of this amendment.

## What this does NOT change

The production-scope rule is untouched here. L1.15, L1.17 and L1.19 keep the narrower `tests`/`test`/`.tests`/`.test` vocabulary they were given earlier today. Widening the production scope to `spec`, `specs`, `__tests__` and the filename conventions would remove code from those three indicators in the flattering direction, which is a measurement change rather than a repair, and it is not made here.

The two definitions of "test code" therefore still differ, deliberately: L1.8 asks "is this file test code", and the scope rule asks "should this file be excluded from a production measurement". They now agree about .NET, which is what was broken. The remaining divergence is recorded in `amendment-2026-08-14-csharp-test-scope.md`.

## Regression cover

Python, `tests/test_basic.py`: a dotted .NET project is test code; a capitalised stem is test code; `Latest.java`, `manifest.py` and `Protest.cs` are not; and an end-to-end `_test_to_prod_ratio` on a .NET layout splits into test and production instead of reporting everything as production.

Rust, `src/indicators/git_ratios.rs`: the same four, plus one that holds the original Python, Go and JavaScript arms in place.

Each test was run against the unfixed code first and fails there, so it measures the fix rather than the fixture.

## The port

Landed in both tools in the same change. Parity re-verified: 16 of 16 indicators equal across all six corpus repositories and the in-tree targets.
