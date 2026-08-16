# Paper 1 Pre-Registration

**Working title.** Finite Testability of Enterprise Software: A Quantitative Survey of Mutable State and Decision-Space Coverage Across Public Open-Source Codebases.

**Author.** Adam Z. Wasserman.

**Pre-registration date.** 2026-04-12.

---

## 1. What this paper tests

Enterprise software teams report test coverage numbers (typically 70-90% line coverage) as evidence that their code is tested. This paper tests whether that evidence is meaningful by measuring two properties that line coverage does not capture:

1. **What proportion of the code has a mathematically infinite state space** (mutable state ratio), making exhaustive testing impossible regardless of test budget?
2. **Of the code whose decision space IS finitely enumerable, what proportion is actually covered by the test suite** (decision-space coverage)?

The hypothesis: most enterprise codebases have a high mutable state ratio (the majority of functions depend on state outside their parameters) and a low decision-space coverage (even the testable portion is mostly untested at the decision level). If confirmed, the finding means that standard test-coverage metrics give enterprises a false sense of verification, and that the actual degree of behavioral verification in enterprise software is far lower than reported.

## 2. Design

**Quantitative survey of public open-source repositories.** No proprietary codebases. No company participation required. No NDAs. No IRB approval. Every repository in the study is publicly accessible and the experiment is reproducible by anyone with the published scripts and random seeds.

### 2.1 Corpus definition

The corpus is the set of all public GitHub repositories matching ALL of the following mechanical filters:

| Filter | Criterion | Rationale |
|---|---|---|
| Primary language | Java, Python, TypeScript, or C# | The four dominant enterprise application languages |
| Repository type | Application, not library/framework/tutorial | Libraries have different architectural patterns than applications; the claim is about enterprise applications specifically |
| Stars | At least 100 | Filters out abandoned personal projects; indicates community recognition |
| Production code | At least 10,000 lines (excluding tests, generated code, vendored dependencies) | Filters out trivial projects |
| Commit history | At least 12 months of activity | Filters out one-shot projects |
| Test directory | Must have a recognizable test directory or test files | Required for L1.19 and L1.20 to be computable |

The filter is implemented as a GitHub API query. The query, including all parameters, is published in the paper's supplementary materials so anyone can reproduce the corpus.

**Application vs library classification.** A repository is classified as an "application" if it contains at least one of: a web framework entry point (e.g., `manage.py`, `app.py`, `server.ts`, `Program.cs`, `config.ru`), a Dockerfile or docker-compose file, CI/CD pipeline definitions, or database migration files. Repositories that contain none of these are excluded as likely libraries or frameworks.

### 2.2 Industry-sector tiering

Every qualifying repository is classified into one of four industry-sector tiers. The classification uses two mechanisms depending on the tier:

**Tier assignment mechanism for Tiers 1 and 2: NAICS codes.**

For each GitHub organization in the corpus, the parent company is identified from the organization's public profile or linked website. The parent company's North American Industry Classification System (NAICS) code is looked up from a public source: SEC filings (US companies), Statistics Canada business register (Canadian companies), or equivalent national registries for other jurisdictions. The NAICS code determines the tier:

| Tier | NAICS codes | Sector | Examples |
|---|---|---|---|
| **Tier 1: Financial services** | 52xxxx (Finance and insurance) | Banks, insurers, asset managers, payment processors, financial data providers | Goldman Sachs (`goldmansachs/`), JPMorgan (`jpmorganchase/`), Capital One (`capitalone/`), Bloomberg (`bloomberg/`), Stripe (`stripe/`), Square (`square/`) |
| **Tier 2: Enterprise software and infrastructure** | 5112xx (Software publishers), 518xxx (Data processing, hosting, related services), 5415xx (Computer systems design and related services) | Enterprise SaaS, enterprise infrastructure, systems integrators | Salesforce (`salesforce/`), SAP (`SAP/`), Oracle (`oracle/`), IBM (`IBM/`), VMware (`vmware/`), Shopify (`Shopify/`), Palantir (`palantir/`), Red Hat (`RedHatOfficial/`) |

**Tier assignment mechanism for Tier 3: named list.**

NAICS does not cleanly separate "Big Tech / consumer tech giants" from other internet or software companies. Tier 3 is therefore defined as a named list of companies whose primary revenue comes from consumer-facing internet or mobile products and whose market capitalization or most recent private valuation exceeds $10 billion. The named list is fixed at the time of pre-registration and does not change during the study:

| Company | GitHub organization(s) |
|---|---|
| Alphabet / Google | `google/`, `googleapis/`, `GoogleCloudPlatform/` |
| Amazon | `aws/`, `amzn/`, `amazon/` |
| Apple | `apple/` |
| Meta | `facebook/`, `facebookresearch/`, `meta-llama/` |
| Microsoft | `microsoft/`, `Azure/`, `dotnet/` |
| Netflix | `Netflix/` |
| Uber | `uber/` |
| Airbnb | `airbnb/` |
| LinkedIn | `linkedin/` |
| Twitter / X | `twitter/` |
| Spotify | `spotify/` |
| Snap | `Snapchat/` |
| Pinterest | `pinterest/` |
| Dropbox | `dropbox/` |
| Lyft | `lyft/` |
| DoorDash | `doordash/` |
| Coinbase | `coinbase/` |
| Robinhood | `robinhood/` |
| ByteDance / TikTok | `bytedance/` |

A company on this list that also has a NAICS code in the Tier 1 or Tier 2 range (e.g., Stripe could be classified as either financial services or consumer tech) is assigned to **Tier 3** (the named list takes precedence over NAICS for dual-classified companies). This ensures Tier 1 contains only traditional financial services companies, not fintech/consumer-finance hybrids.

**Tier 4: everything else.**

| Tier | Definition | Examples |
|---|---|---|
| **Tier 4: Community enterprise-grade** | Repos from GitHub organizations not matched to a Tier 1, 2, or 3 company, or from personal accounts, that meet all corpus filters | CNCF projects, Apache Foundation projects, Eclipse Foundation projects, community-maintained enterprise tools |

**Published mapping.** The full assignment chain is published as a CSV in the supplementary materials: `github_org, parent_company, naics_code (or "Tier 3 named list"), tier, verification_source`. The verification source column documents how the GitHub org was linked to the parent company (org profile statement, company website link, LICENSE file trademark, or README header). Anyone can verify or dispute individual assignments.

### 2.3 Sampling

Three independent random samples are drawn from the corpus:

- **Sample A:** 100 repositories, drawn using a published random seed
- **Sample B:** 100 different repositories, drawn using a different published random seed
- **Sample C:** 100 different repositories, drawn using a third published random seed

Each sample is stratified by two dimensions:

1. **Language:** 25 repositories per language (Java, Python, TypeScript, C#) per sample
2. **Industry sector:** within each language stratum, repositories are drawn proportionally to the tier distribution in the corpus. If a tier has fewer qualifying repos than the proportional allocation, all qualifying repos from that tier are included and the shortfall is documented.

Total: 300 unique repositories across three independent samples. Results are reported both in aggregate and per tier, so that a reader can compare financial services code to consumer tech code to community code.

If a language-tier cell is empty (e.g., no qualifying C# repos from Goldman Sachs), the cell is reported as empty and the proportional allocation shifts to the next-most-represented tier for that language.

### 2.3 Measurements

Three indicators are computed for every repository in every sample:

**L1.18 Mutable state ratio.** Percentage of functions/methods in the production tree that reference mutable state outside their parameter list. Computed by static analysis: count functions whose body reads or writes variables not declared in the function's parameter list or local scope (instance variables via `self.`/`this.`, class variables, global variables, module-level mutable state). I/O boundary functions (route handlers, database adapters, CLI entry points) are excluded because they interact with external state by design. The exclusion criteria are defined per language in the supplementary materials.

**L1.19 Decision-space coverage.** Percentage of finitely enumerable decision points (dispatch table keys, match/case arms, enum variants used in branching, explicit configuration flag values) that are exercised by at least one test case. Computed by: (a) enumerate all dispatch tables, match statements, and enum-driven branches in the production tree; (b) count the total number of distinct keys/arms/variants; (c) run the test suite with branch-level tracing; (d) count how many of those keys/arms/variants were exercised. The ratio (d)/(b) is the decision-space coverage.

**L1.20 Test determinism.** Run the full test suite 5 times with randomized execution order. Count passing runs. Test determinism = passing runs / 5. Repositories where the test suite cannot be run (missing dependencies, broken build) are recorded as "build failed" and excluded from L1.20 analysis but retained for L1.18 and L1.19 (which are static analysis only).

### 2.4 Per-language tool mapping

| Language | L1.18 static analysis tool | L1.19 decision enumeration | L1.20 randomized runner |
|---|---|---|---|
| Python | AST visitor counting `self.` attribute access in method bodies | AST visitor counting dict-literal keys used as dispatch + match/case arms | `pytest --randomly-seed=random` |
| TypeScript | TS compiler API counting `this.` property access in method bodies | AST visitor counting object-literal keys used as dispatch + switch/case arms | `jest --randomize` |
| Java | JavaParser counting field access in method bodies | Visitor counting switch arms + enum usage in conditionals | `mvn test -Dsurefire.runOrder=random` |
| C# | Roslyn analyzer counting field/property access in method bodies | Visitor counting switch arms + enum usage in conditionals | `dotnet test --` with randomized ordering |

The tools are published as open-source scripts in the paper's supplementary materials.

## 3. Pre-registered predictions

### 3.1 Mutable state ratio

| Prediction | Value | Basis |
|---|---|---|
| Median mutable state ratio across all 300 repos | **> 50%** | Most enterprise code is class-based with methods that reference instance state; the majority of functions in a typical OOP codebase are methods on mutable objects |
| Language with highest median mutable state ratio | **Java or C#** | The most class-heavy enterprise ecosystems |
| Language with lowest median mutable state ratio | **Python** | Python supports functional patterns more naturally than the other three languages, and has a strong tradition of standalone utility functions in parts of the ecosystem |
| Interquartile range | **30% to 70%** | Substantial variation expected between projects that use functional patterns and projects that are heavily OOP |

### 3.2 Decision-space coverage

| Prediction | Value | Basis |
|---|---|---|
| Median decision-space coverage across all 300 repos | **< 40%** | Most test suites are written for line coverage, not decision coverage; many dispatch keys and enum branches are not explicitly tested |
| Correlation between mutable state ratio and decision-space coverage | **Negative** | Higher mutable state ratio means fewer enumerable decisions exist, and of those that do, fewer are tested because the team relies on integration tests rather than decision-level tests |

### 3.3 Test determinism

| Prediction | Value | Basis |
|---|---|---|
| Percentage of repos achieving 5/5 determinism | **< 50%** | Many test suites share mutable state between tests (database fixtures, in-memory singletons, class-level setup/teardown) |
| Percentage of repos achieving < 3/5 determinism | **> 20%** | A significant minority of test suites are substantially order-dependent |

### 3.4 Cross-sample consistency

| Prediction | Value | Basis |
|---|---|---|
| Difference in median L1.18 between Sample A and Sample B | **< 5 percentage points** | If the corpus is large enough and the random draw is unbiased, independent samples should produce similar distributions |
| Difference in median L1.19 between Sample A and Sample B | **< 5 percentage points** | Same reasoning |

### 3.5 Cross-sector prediction (the paradigm hypothesis)

| Prediction | Value | Basis |
|---|---|---|
| Difference in median L1.18 between Tier 1 (financial services) and Tier 3 (FAANG/Big Tech) | **< 10 percentage points** | The untestability problem is a property of the dominant coding paradigm (class-based OOP with mutable state), not a property of engineering skill or organizational maturity. FAANG companies hire from the top 1% of CS graduates and invest billions in engineering tooling. If their code has a similar mutable state ratio to financial services code, the problem cannot be solved by hiring better engineers or adopting better tools. It can only be solved by changing the paradigm. |
| Tier 3 (FAANG) median L1.18 | **> 35%** | Even elite engineering organizations produce code with substantial mutable state because the paradigm (OOP with mutable state) is the industry default across all tiers |

### 3.6 The headline prediction

> The median enterprise codebase has more than half its functions depending on mutable state that cannot be exhaustively tested, and less than 40% of its finitely enumerable decisions verified by any test. Standard line-coverage metrics (typically reported as 70-90%) overstate the degree of behavioral verification by a factor of at least 2x. The mutable state ratio does not vary dramatically between financial services, enterprise SaaS, and consumer tech organizations because the untestability is a property of the paradigm, not the organization.

## 4. Falsification criteria

1. **The mutable-state hypothesis** is falsified if the median mutable state ratio across all 300 repos is below **30%**. A median below 30% would mean the majority of enterprise code is already written in a style that avoids state-space explosion, which would undermine the claim that enterprise code is systematically untestable.

2. **The decision-coverage hypothesis** is falsified if the median decision-space coverage across all 300 repos is above **70%**. A median above 70% would mean enterprise teams are already testing most of their enumerable decision space, which would undermine the claim that standard testing practices leave most decisions unverified.

3. **The cross-sample consistency hypothesis** is falsified if the median L1.18 or L1.19 differs by more than **10 percentage points** between any two of the three independent samples. A large divergence would mean the corpus is too heterogeneous for the survey to produce stable findings, and the sampling methodology needs revision.

4. **The test-determinism hypothesis** is falsified if more than **80%** of repos achieve 5/5 test determinism. This would mean mutable-state test interference is rare in practice, undermining the claim that shared mutable state between tests produces unreliable results.

5. **The paradigm hypothesis** is falsified if the median L1.18 for Tier 3 (FAANG/Big Tech) is more than **20 percentage points lower** than the median for Tier 1 (financial services). A gap of 20+ points would mean elite engineering talent substantially reduces mutable state, which would undermine the claim that the problem is paradigmatic rather than skill-based. A gap under 10 points confirms the prediction. A gap between 10 and 20 points is ambiguous and warrants further investigation.

6. **The overstatement hypothesis** is falsified if decision-space coverage is within **20 percentage points** of reported line coverage for the majority of repos. This would mean line coverage is a reasonable proxy for behavioral verification, undermining the claim that standard metrics give a false sense of security.

5. **The overstatement hypothesis** is falsified if decision-space coverage is within **20 percentage points** of reported line coverage for the majority of repos. This would mean line coverage is a reasonable proxy for behavioral verification, undermining the claim that standard metrics give a false sense of security.

## 5. What this paper explicitly does NOT test

- Whether Honest Code patterns produce better outcomes (that is Paper B, the controlled AI experiment)
- Whether the Slop Audit instrument is reproducible by independent assessors (that is Paper C)
- Whether converting a codebase to Honest Code reduces rework (that is Paper D)
- Whether AI produces better code in one paradigm vs another (that is Paper B)

This paper tests only whether the PROBLEM exists at scale: is enterprise code systematically untestable in the mathematical sense? Everything else in the Open Honest publication program depends on the answer being yes. If the answer is no, the entire argument needs revision.

## 6. Sequence of events

1. **2026-04-12:** predictions and falsification criteria locked in this document
2. **2026-04-12:** this document timestamped via Zenodo DOI
3. **After timestamp:** scripts developed and tested on a small pilot set (5-10 repos, not included in the main samples)
4. **After scripts validated:** GitHub API query executed to define the corpus; corpus size recorded
5. **After corpus defined:** three random seeds published; samples drawn
6. **After samples drawn:** L1.18 and L1.19 computed for all 300 repos; L1.20 computed for all repos whose test suites can be run
7. **After data collected:** analysis performed per the pre-registered predictions and falsification criteria
8. **Manuscript drafted:** reporting both predictions and results, including any falsifications
9. **Submitted:** target venue EMSE or IEEE Software; arXiv preprint posted simultaneously

## 7. What this paper does NOT protect against

- **Selection bias in the corpus filter.** The filter (stars > 100, LOC > 10,000, test directory present) selects for higher-quality-than-average open-source projects. Enterprise proprietary codebases may have WORSE mutable state ratios and decision-space coverage than the public repos in this survey. The findings are therefore likely to be conservative: the real enterprise number is probably worse than what we measure on public repos.
- **Language-specific tooling accuracy.** Static analysis for mutable state detection is imperfect. Some false positives (functions flagged as mutable-state that are actually pure) and false negatives (functions that look pure but depend on global state through indirect references) are expected. The per-language tool implementations are published so others can verify and improve them.
- **Test suite quality variation.** Some repos have comprehensive test suites; others have minimal tests. L1.19 and L1.20 measure what the tests actually cover, not what the developers intended to cover. A repo with poor tests will show low decision-space coverage and possibly low determinism, but this reflects the actual state of verification, not a tool limitation.

## 8. Timestamp anchor

**Timestamp anchor:** [TO ADD: Zenodo DOI or OSF registration ID once minted].

---

## Appendix A: Pilot results (excluded from the formal study)

The following repositories were used to validate the L1.18 and L1.19 scripts before the formal study. They are excluded from all three random samples. They must not appear in the corpus draws. Their results are reported here for transparency and to demonstrate that the scripts produce plausible, interpretable output.

### Pilot L1.18 (mutable state ratio)

| Repository | Domain | Framework | Functions analyzed | Mutable-state functions | Ratio | Classification |
|---|---|---|---|---|---|---|
| `adamzwasserman/aic-coe/tools` | Survey tooling | Pure functions (Honest Code) | 35 | 0 | 0.0% | Healthy |
| `saleor/saleor` | E-commerce | Django (Python) | 7,090 | 2,077 | 29.3% | Not Healthy |
| `posthog/posthog` | Product analytics | Django (Python) | 22,649 | 10,340 | 45.7% | Slop |
| `netbox-community/netbox` | Infrastructure management | Django (Python) | 2,828 | 1,705 | 60.3% | Slop |

**Observations from the pilot:**

1. The three enterprise Django applications range from 29% to 60% mutable state ratio. All three are well-maintained, popular, community-endorsed projects. None is an abandoned or low-quality codebase. The mutable state ratios reflect standard Django/OOP practice, not poor engineering.
2. The Honest Code tooling (our own scripts) scores 0.0% because every function is pure: input in, output out, no `self.`, no global state. This is the target the methodology defines as "Healthy."
3. The range (29% to 60%) is consistent with the pre-registered prediction of a median above 50%. NetBox (60.3%) is a heavily class-based Django application with extensive use of class-based views, model methods, and management commands. Saleor (29.3%) is lower because it has a larger proportion of standalone utility functions and GraphQL resolver functions that take explicit arguments.
4. PostHog (45.7%) is the largest codebase in the pilot at 22,649 functions. The script completed in under 60 seconds on a standard laptop, confirming that the analysis scales to large repositories.

### Pilot L1.19 (decision-space enumeration)

| Repository | Decision points | Total keys/arms | Dict dispatch tables | Match/case | If/elif chains (3+) |
|---|---|---|---|---|---|
| `saleor/saleor` | 237 | 1,137 | 74 | 3 | 160 |

**Observations from the pilot:**

1. Saleor has 74 dict dispatch tables (relatively high for Django). This means 455 of the 1,137 enumerable keys are in dispatch tables, which are the most cleanly testable pattern.
2. The majority of enumerable decision points (160 of 237) are if/elif chains, which are harder to test exhaustively because they often depend on runtime state in addition to the branch condition.
3. Decision-space COVERAGE (the ratio of tested keys to total keys) requires running the test suite with branch tracing, which was not performed in the pilot. The enumeration confirms the script correctly identifies decision points; coverage measurement is the next step.

### Excluded repos list

The following repositories are excluded from all formal study samples:

- `saleor/saleor`
- `posthog/posthog`
- `netbox-community/netbox`
- Any repository under `adamzwasserman/` or `TraileAI/` or `ShawnaRStaff/`

---

## Appendix B: Pre-registration checklist

- [ ] Finalize the GitHub API query and test it against the GitHub API to confirm it produces a corpus of sufficient size (target: at least 500 qualifying repos per language)
- [ ] Write and test the L1.18 static analysis scripts for all 5 languages on a pilot set
- [ ] Write and test the L1.19 decision enumeration scripts for all 5 languages on a pilot set
- [ ] Write and test the L1.20 randomized test runner for all 5 languages on a pilot set
- [ ] Choose three random seeds and publish them in this document
- [ ] Mint Zenodo DOI for this pre-registration
- [ ] Run the experiment
- [ ] Draft the manuscript
- [ ] Submit to EMSE or IEEE Software; post arXiv preprint

## Appendix C: Relationship to the Open Honest project

This paper is the first in a four-paper publication sequence:

| Paper | What it tests | Depends on |
|---|---|---|
| **Paper A (this paper)** | Is enterprise code systematically untestable? | Nothing (standalone) |
| **Paper B** | Does AI produce Honest Code more correctly than class-based code? | Can cite Paper A for the problem statement |
| **Paper C** | Is the Slop Audit instrument reproducible by independent assessors? | Independent of A and B |
| **Paper D** | Does converting to Honest Code reduce rework? | Can cite A and B for context |

Paper A establishes that the problem exists. Papers B, C, and D build on it. If Paper A's findings are falsified, Papers B and D need to be redesigned because their motivation (enterprise code is untestable) would be undermined.

The Open Honest project is an enterprise software quality audit standard. Paper A provides the empirical evidence that the standard addresses a real and measurable problem. The standard exists independently of the paper, but the paper's findings (if confirmed) are the strongest single argument for the standard's existence.
