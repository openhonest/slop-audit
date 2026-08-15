# Browser runtime audit (CANDIDATE)

Build one thing, not a panel: a measure of how much JavaScript a site ships that real users never execute. That number is honest, the repository tool cannot produce it, and it needs no source maps. Most of the twenty-indicator panel cannot follow it into the browser.

**Status: candidate. Not canon, not part of the twenty-indicator panel, not citable as a property of the standard.** Written 2026-08-15. Nothing here is a measured result. The coverage table comes from reading `tools/l1_analyzer/l1_analyzer/`. The runtime mechanism comes from the Chrome DevTools Protocol reference and from what the existing JavaScript harness already does.

## 1. Bottom line

The bad news first. Fourteen of the twenty indicators cannot exist in a browser at all. Three more return a clean band on a bundle for the wrong reason. L1.16 is the clearest case. A minifier strips every trailing space, so trailing-whitespace density reads 0.0 and bands **Clean** on the sloppiest code in the world. A tool that reports Clean because it cannot see is worse than a tool that reports nothing. Any browser panel must mark those checks n/a rather than compute them.

The good news is narrow but sound. Three checks work in the browser and need no source maps. They are stronger there than in a repository: unused-code measurement, secret scanning, and hardcoded absolute paths. All three measure the artifact the public receives, which is not the artifact in the repository.

## 2. What this measures that the repo version cannot

The strongest argument is the one the brief proposes, and it holds, with one correction.

A test suite reports what someone remembered to check. Real traffic reports what the application does. The repo tool's L1.19 runs the project's own `npm test` under c8 and reads `total.branches.pct`. That number is bounded by the imagination of whoever wrote the tests. A browser measurement is bounded instead by what users do, which is the thing the code exists for.

The correction matters. Those two numbers do not measure the same quantity, so the browser one does not replace the repo one. Test coverage answers "did anyone verify this?" Runtime coverage answers "does anyone use this?" A branch can be covered and dead, or uncovered and carrying the whole feature. Both readings are useful and neither substitutes for the other. Anyone who markets runtime coverage as "honest test coverage" is lying, and the Slop Audit cannot afford that.

The genuinely new measurement is **shipped-and-never-run code**. V8 reports execution counts per source range. Ranges with a count of zero across a large sample of real sessions are code the user downloaded, parsed and paid for, and never ran. That is L1.12, the unreachable-code ratio, measured by execution instead of by static inference. Read the code: `_compute_external_indicators` returns n/a for L1.12 on every language except Python, and only when `vulture` is installed. So the browser gives the Slop Audit an L1.12 for JavaScript that the repo tool has never had.

Two smaller cases, both real:

**Secrets that actually shipped.** L1.14 runs `gitleaks detect --no-git --source .` over the working tree. That answers whether a secret is in the repository. It does not answer whether a secret reached the public. The two differ in both directions. A repo secret may be stripped at build time. A build-time environment variable may be inlined into the bundle. Only the browser sees the second case, and the second case is the one that leaks.

**Build-machine paths that actually shipped.** The `absolute_paths` check flags `/Users/...` and `/home/...` in source. Bundles carry these routinely, and source maps carry them by construction: the `sources` array of a published map is often a list of the build machine's absolute paths. That is a live disclosure, measurable only in the artifact.

## 3. The honest coverage table

Derived from the code, not from the documentation. Every "why" below is a fact about a specific function unless the row says I reasoned it.

| Check | How the repo tool computes it | In a live browser | Why |
|---|---|---|---|
| L1.1 doc-only commits | `git log --numstat` | **Impossible** | A browser serves no commit history. |
| L1.2 code-only commits | `git log --numstat` | **Impossible** | Same. |
| L1.3 mixed commits | `git log --numstat` | **Impossible** | Same. |
| L1.4 doc-line ratio | `git log --numstat` | **Impossible** | Same. |
| L1.5 delete/add ratio | `git log --numstat` | **Impossible** | Same. |
| L1.6 net-negative commits | `git log --numstat` | **Impossible** | Same. |
| L1.7 high-delete commits | `git log --numstat` | **Impossible** | Same. |
| L1.8 test-to-prod ratio | Filesystem scan, **not git** | **Impossible** | `_test_to_prod_ratio` walks the tree and splits by path with `_is_test_file`. No site ships its tests. Computing it would return 0.00 and band Slop, a false accusation, so it must report n/a. |
| L1.9 pre-commit hooks | Does `.pre-commit-config.yaml` or `.husky` exist | **Impossible** | The file never leaves the repository. |
| L1.10 CI/CD pipelines | Count `.github/workflows/*.yml` | **Impossible** | Same. |
| L1.11 containerization | Does `Dockerfile` exist | **Impossible** | Same. |
| L1.12 dead code | `vulture`, Python only; **n/a for JavaScript today** | **Works, and improves** | V8 reports a zero execution count per source range. This is the one indicator the browser adds outright. |
| L1.13 clone ratio | `jscpd --mode weak` | **Degraded** | Reasoned, not verified. jscpd tokenizes, so minification may not defeat it, but a bundle mixes the client's code with every dependency, so the number describes npm rather than the client. |
| L1.14 secrets | `gitleaks detect --no-git` | **Works, no source maps needed** | The scan reads text. Minifiers preserve string literals, so a key survives the build intact. |
| L1.15 type escapes | tree-sitter, per-language token set | **Needs source maps** | `LANG_CFG["javascript"]["type_escape_patterns"]` is empty, so `_compute_type_escapes` already returns n/a for JavaScript. TypeScript types erase at compile time. Only original sources restore this. |
| L1.16 trailing whitespace | `ln.rstrip() != ln` per line | **Destroyed, and dangerously** | A minifier removes all whitespace. The check returns 0.0 and bands **Clean**. This is a false green, not a missing value. |
| L1.17 god files | Files over 1k code lines | **Excluded by the tool's own rule** | `_god_file_reason` already drops `.min.js` and anything `_is_generated` marks, and `_IGNORE_DIRS` already drops `dist`, `build` and `vendor`. The instrument has decided a bundle is not a god file. A browser has nothing else. |
| L1.18 mutable state | tree-sitter over `LANG_CFG` | **Degraded** | Reasoned. tree-sitter parses minified JavaScript fine, but bundlers wrap each module in a closure and hoist bindings, so the ratio describes the bundler's output shape, not the author's. |
| L1.18b state bounds | tree-sitter plus `LANG_SPEC["javascript"]` | **Degraded to meaningless** | The classifier reasons about identifiers and call targets. Minification renames every local and inlines call sites, which is exactly the input it cannot resolve. Expect a wall of `unresolved`. |
| L1.19 static decision points | `_DECISION_NODE_TYPES` over tree-sitter | **Degraded** | Verified from the frozen set: it counts `if_statement` and `ternary_expression` but **not** a `&&` or `||` binary expression. Minifiers rewrite `if` into short-circuit chains, so decision points disappear from the count. |
| L1.19 runtime coverage | c8 over the project's `npm test` | **Works, and this is the product** | c8 consumes V8 block ranges. `Profiler.takePreciseCoverage` supplies the same ranges from a live page. The numerator changes from the test suite to real usage. |
| L1.20 determinism | The suite re-run 5 times with shuffled seeds | **Impossible** | There is no suite to shuffle. A browser analogue exists (replay one journey and diff the output) but it measures something else and must not carry the L1.20 label. |
| path cover | tree-sitter CFG, minimum edge-covering walks | **Degraded** | Built on the same node types L1.19 uses, so it inherits the same rewriting problem. |
| thread surface | tree-sitter; for JavaScript, async TOCTOU only | **Works** | Reasoned but well grounded. `_JS_CHECK` and `_JS_MUTATE` hold built-in method names (`has`, `set`, `push`), which minifiers do not mangle, and the finding is a set intersection over receiver names, so consistent renaming preserves it. |
| schedule silence | Rust loom and shuttle markers | **n/a either way** | Already n/a for JavaScript in the repo tool. The browser changes nothing. |
| absolute paths | Regex for `/Users/`, `/home/`, drive letters | **Works, and improves** | Bundles carry build-machine paths, and a source map's `sources` array is often a list of them. |

Count the rows. Three work and need no source maps. One works and is the product. One improves. Five recover only with source maps. Four degrade. Fourteen cannot exist. Two of the last group, L1.8 and L1.16, must be forced to n/a rather than computed, because computing them produces a confident wrong answer.

I could not determine one thing from the code: whether jscpd's tokenizer produces stable clone classes on minified single-line input. That row is my reasoning, not a reading.

## 4. Architecture

Four components, flat, no new infrastructure. Honest Code applies: pure analysis in the middle, all input and output at the edges.

**Collector.** One script drives a headless Chromium over the Chrome DevTools Protocol. It calls `Profiler.startPreciseCoverage` with `callCount: true` and `detailed: true`, drives the page, then calls `Profiler.takePreciseCoverage`. It records `Debugger.scriptParsed` events, which carry each script's URL and its `sourceMapURL`, and it fetches each script body with `Debugger.getScriptSource`. Output is one JSON file: scripts, source text, coverage ranges, source-map URLs. Nothing is analyzed here. Playwright and Puppeteer both wrap this domain, so the collector is thin either way.

**Resolver.** Given the collected JSON, fetch each source map and expand it into original files using its `sourcesContent` field. This step decides everything downstream, so it reports its own result honestly: for each script, "original sources recovered," "map published without `sourcesContent`," or "no map." A run where most bytes resolve to nothing must say so on the report, in the headline, not in a footnote.

**Analyzer.** Reuse `l1_analyzer` unchanged. Write the resolved sources into a temporary directory and point the existing entry points at it. The tree-sitter side needs no new parser, which was correct in the brief. Add one new module for the runtime half: convert V8 ranges into per-file executed and unexecuted byte counts. `v8-to-istanbul` already does this conversion and needs the original source text, which is what the resolver produced. Whether to shell out to it or reimplement the range mapping in Python is an open call. Reimplementing is maybe two hundred lines and removes a Node dependency from a Python tool.

**Reporter.** Reuse `report.py` and `card.py`. Add one section for the runtime number and one for the resolution result. Suppress every row the table above marks impossible, and mark them n/a with the reason, following the pattern `_na` already sets across the harnesses.

No database, no service, no queue. One command in, one JSON and one Markdown report out.

## 5. What breaks without source maps, and is it still worth shipping

Without source maps you lose the entire source-analysis half of the panel and you keep the entire runtime half.

Gone: L1.15, L1.16, L1.17, L1.18, L1.18b, the static half of L1.19, and path cover. That is every check that reads identifiers, line shapes, file boundaries or `if` statements, because a minifier destroys all four. Two of them fail silently rather than loudly, which is the part that requires a hard rule: L1.16 and L1.13 will both return a number, and both numbers will be wrong. Force them to n/a.

Kept, at full strength: runtime coverage, unused-code ratio, secret scanning, absolute paths, and the async-TOCTOU thread surface. None of the five depends on identifier names or whitespace.

**Answer: yes, ship it without source maps, but only if the product is the runtime half.** Those five checks measure what the site actually sent and what it actually ran. No repository tool can measure either. A product that reports "this site ships 2.4 MB of JavaScript, 71 percent of which no user in this sample ever executed, and here are two API keys in the bundle" is a real product with a real buyer, and it does not need a single source map.

What you must not do is ship the full twenty-indicator panel against minified code with the source-dependent rows quietly filled in. That would put the Slop Audit's name on numbers that measure a bundler.

## 6. The poka-yoke answer

**None. This is a measurement tool, not a prevention tool.** It does not make any category of bug structurally impossible. It reports facts after the fact, which is what the whole Slop Audit does, and the honest framing is that Layer 1 measures and the Honest Framework prevents.

One qualification, offered as a qualification and not as a rescue. If the browser secret scan runs as a release gate rather than as a report, it does eliminate a named category: **a build-time secret inlined into a shipped bundle**. That category is invisible to the repository scan by construction, because the secret is not in the repository. A gate at the deploy boundary refuses the artifact, which is the poka-yoke shape. That is one category, at one boundary, and it does not justify the rest of the product on its own.

By the principle's own rule, a capability that eliminates no named bug category does not earn its complexity. This product earns its complexity on measurement value, not on prevention, and the document should say so rather than reach for a prevention story that is not there.

## 7. First milestone

**The smallest thing that produces a real number on a real site: unused JavaScript bytes on one page load.**

Deliverable: a command that takes a URL, loads it in headless Chromium, drives one scripted journey, and prints the total shipped JavaScript bytes, the executed bytes, and the unexecuted percentage, per script and in total. No source maps. No source analysis. No report card.

What it takes:

1. A collector script over CDP or Playwright. `Profiler.startPreciseCoverage`, drive, `Profiler.takePreciseCoverage`, plus `Debugger.getScriptSource` for each script's length. Small.
2. Range arithmetic. Sum the covered ranges per script, subtract from the script length. This is byte counting, not the Istanbul conversion, so no source map is involved and no dependency is needed.
3. One honest denominator decision, which is the only real design question in the milestone. Do third-party scripts count? Analytics and ad tags are mostly unused on any given page, and including them inflates the headline while measuring someone else's code. Recommendation: report first-party and third-party separately, and headline the first-party number.
4. A run against three or four public sites to see whether the numbers separate. If every site reads 65 to 75 percent unused, the metric has no discriminating power and the product is dead at the first milestone, which is worth finding out for the price of a day.

Effort: I estimate a few days to a first number. That estimate is a guess and I did not build it.

Add the second milestone only if the first number separates: fetch source maps, report the resolution rate across a sample of real sites, and decide from that measurement whether the source-analysis half is reachable at all. Do not guess the source-map availability rate. Measure it, because the whole question in section 5 turns on it.

## 8. Risks and open questions

**A single session is not evidence of dead code.** Code unexecuted in one journey may be the checkout flow. Calling it dead is a false accusation, and it is the most likely way this product embarrasses the standard. The measurement needs many sessions and a stated sampling frame, and the report must state the frame beside the number. Until that exists, the honest label is "unexecuted in this sample," never "dead."

**Measuring sites you do not own.** Loading a public page and reading what the server sent you is ordinary browsing, and the reading happens on your machine, on data addressed to you. I see no access problem there. Three real problems sit next to it. Automated access often breaches a site's terms of service, which is a contract question, not a computer-misuse one. Publishing a named, scored verdict about a company's code invites a commercial-disparagement claim whether or not the number is right. And a crawl that follows links into an authenticated area is a different act with a different answer. I am not a lawyer and this paragraph is not advice; get one before publishing any named result.

**Source maps that were not meant to be public.** A map sitting on the server that no script references was never offered to you. Fetching it by guessing the path is a different act from following a `sourceMapURL` the site handed you. Recommendation: follow only the reference the script gives, never guess a path, and record which of the two happened.

**Privacy.** A crawl that records page state can capture personal data, which brings Law 25 and the GDPR into scope. Coverage ranges and script bodies carry none, so a collector restricted to those two artifacts stays clean. Keep it restricted, and say so.

**Third-party code dominates the denominator.** On a typical commercial site most shipped JavaScript is not the client's. Every headline number needs a first-party and third-party split or it measures the ad stack.

**Open: what is the real source-map rate?** Nobody in this document knows. Milestone two is the measurement.

**Open: does the unused-bytes number discriminate?** If every site clusters, there is no instrument. Milestone one is the measurement.

**Open: does the Slop Audit want a second, differently grounded instrument at all?** The panel's authority rests on every indicator meaning one thing. A browser panel where fourteen rows read n/a and three read n/a-because-we-refuse invites a reader to treat a partial panel as a panel. That is a naming and packaging problem, and it is the reason this belongs in `candidate-methods/` rather than in the canon.

## 9. What I verified against what I reasoned

**Verified by reading the code.** The git and filesystem split, including the correction that L1.8 is a filesystem scan and not a git query. L1.9 through L1.11 as file-presence checks. L1.12 returning n/a for every language but Python. L1.14 running `gitleaks` with `--no-git`. `type_escape_patterns` being empty for JavaScript, so L1.15 is already n/a there. `_god_file_reason` excluding `.min.js` and generated files, and `_IGNORE_DIRS` excluding `dist`, `build` and `vendor`. `_DECISION_NODE_TYPES` counting ternaries but not `&&` or `||`. `LANG_SPEC` including a `javascript` entry. `_SCANNERS` including a JavaScript thread-surface scanner, and that scanner's method sets holding built-in names. `schedule_silence` being Rust-only. The JavaScript L1.19 harness reading `total.branches.pct` from c8, and L1.20 requiring vitest or jest with a seed.

**Verified against external references.** `Profiler.startPreciseCoverage` taking `callCount` and `detailed` and producing block-granularity source ranges, and `v8-to-istanbul` requiring the original source text and handling source maps.

**Reasoned, not verified.** Every claim about what minification does to each indicator. I did not run the analyzer against a minified bundle. That test is cheap and should happen before anyone builds anything: take one real bundle, run `slop-audit-l1` on it, and check whether L1.16 reports Clean. If it does not, this document's central warning is wrong and section 5 needs rewriting.
