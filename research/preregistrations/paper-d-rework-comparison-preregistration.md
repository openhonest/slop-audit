# Paper D Pre-Registration

**Working title.** Does Adopting the Honest Code Methodology Reduce Rework? A Within-Codebase Pre/Post Comparison Using Continuous Git-History Metrics.

**Authors.** Adam Z. Wasserman, Shawna Staff.

**Pre-registration date.** 2026-04-12.

**Disclosure of financial interest.** Adam Wasserman and Shawna Staff jointly hold a 2025 provisional patent on key aspects of the IAM codebase. Buckler licenses; Buckler does not own. Both authors have a shared financial interest in the IAM family of codebases being characterized favorably. The idd codebase is Buckler-internal work where Adam is CTO; Shawna operates with approximately 98% autonomy. Shawna's separate non-Buckler repository has zero Adam involvement.

---

## 1. What this paper tests

Papers A and B establish that enterprise code is systematically untestable (Paper A) and that AI produces Honest Code more correctly than class-based code (Paper B). This paper tests the practical consequence: **does adopting Honest Code practices on a real production codebase reduce rework, bug-fix frequency, and maintenance cost?**

The hypothesis: after a developer adopts Honest Code practices on an existing codebase, the continuous maintenance metrics (rework rate, bug-fix frequency, regression count, delete/add ratio, code churn) measurably improve compared to the pre-adoption baseline, even though the codebase was already under a structured SDLC before the adoption.

This is a harder test than "Honest Code vs no process discipline" (which the Zenodo preprint already demonstrated). This paper tests: **Honest Code vs an already-structured SDLC.** The baseline is not chaos. The baseline is a disciplined development process that predates Honest Code. The question is whether Honest Code adds measurable value on top of that discipline.

### 1.1 What is novel about this study

1. **The first pre/post measurement of a coding-paradigm shift on continuous rework metrics.** Prior before/after studies in software engineering have measured process changes (Agile adoption, CI/CD adoption, DevOps transformation). No prior study has measured the effect of a *coding-paradigm shift* (from class-based OOP to pure functions with dispatch tables) on the same codebase with the same developer. The variable is the paradigm, not the process.

2. **L1.18 (mutable state ratio) measured as a time series.** No prior work has plotted mutable state ratio at monthly intervals to show a codebase becoming more or less testable over time. The trajectory is a new kind of data that connects Paper A's cross-sectional finding (enterprise code has high mutable state) to a longitudinal question (does it decrease under Honest Code practices?).

3. **The independence control.** Two codebases undergo the same paradigm shift by the same developer. One has a CTO relationship (idd/Buckler); one has zero supervisory involvement (Shawna's independent repo). If both improve on the same metrics, the cause is the paradigm, not the organizational context. Within-subject designs with an independence control are rare in software engineering empirical research.

4. **The 300k-line conversion event as a characterized data point.** A single documented event in which 300,000 lines of class-based code were removed and replaced by pure-function implementations. The event can be structurally characterized: what patterns were removed, what patterns replaced them, and what happened to the continuous metrics in the months following. No prior study has documented a paradigm-conversion event at this scale with before/after metric data.

## 2. Design

**Within-codebase pre/post comparison.** Same developer, same repository, same tools. The only variable is the coding methodology adopted partway through the codebase's history.

### 2.1 Codebases under measurement

| Codebase | Repository | Developer | Adam involvement | Pre-Honest period | Post-Honest period |
|---|---|---|---|---|---|
| **idd** | `github.com/TraileAI/idd` (`honest-conversion` branch) | Shawna Staff | CTO of Buckler; Shawna operates with ~98% autonomy | Commits before ~March 31, 2026 (pre-Honest Code publication) | Commits on or after Shawna's autonomous adoption of Honest practices (~early April 2026) |
| **Shawna's independent repo** | [TBD: Shawna to confirm repo] | Shawna Staff | **None.** Zero CTO relationship. Zero Buckler involvement. | Commits before adoption | Commits after adoption |

The second codebase is the independence control. If both codebases show the same rework-reduction pattern, the cause is the methodology, not the supervisory relationship. If only idd shows it, the CTO relationship is a confound. If only the independent repo shows it, something else is driving the result.

### 2.2 The adoption boundary

The Honest Code book was published **March 31, 2026**. Shawna autonomously adopted Honest Code practices on or shortly after that date. The exact adoption date is determined by examining the git history for the first commit that reflects Honest Code patterns (pure functions replacing class methods, dispatch tables replacing if/elif chains, explicit I/O boundary separation). The adoption date is recorded per codebase and may differ between the two repositories.

Commits before the adoption date are the **pre** condition. Commits on or after the adoption date are the **post** condition. The adoption date is not a sharp boundary (adoption is gradual), so a transition window of 2 weeks is defined: commits within 2 weeks of the adoption date are excluded from both conditions to avoid contaminating either.

### 2.3 Metrics

All metrics are computed from git history. No subjective judgment. No human scoring. Every metric is reproducible by anyone with access to the repository.

| Metric | Definition | What it measures |
|---|---|---|
| **Rework rate** | Percentage of files touched again within 30 days of their last modification | How often does the developer have to come back and fix something recently built? Lower is better. |
| **Bug-fix commit ratio** | Percentage of commits whose message contains "fix", "bug", "patch", "resolve", "correct", or references an issue tracker | How much of the development effort goes to fixing vs building? Lower is better. |
| **Regression count** | Number of commits that revert or undo a previous commit (detected by `git revert` or commit messages containing "revert", "undo", "rollback") | How often does a change break something that was previously working? Lower is better. |
| **Delete/add ratio** | Lines deleted / lines added per commit, averaged over the measurement period (L1.5) | Is the developer actively pruning dead code and refactoring, or only accumulating? Higher is better (indicates active maintenance). |
| **Net-negative commit ratio** | Percentage of commits where lines deleted > lines added (L1.6) | How often does the developer make the codebase smaller? Higher is better. |
| **LOC trend** | Total lines of production code at monthly intervals | Is the codebase growing monotonically (debt accumulation) or showing a sawtooth pattern (build + prune cycles)? |
| **Churn rate** | Sum of (lines added + lines deleted) per commit, averaged | How volatile is the codebase? High churn with low bug-fix ratio is healthy (active refactoring). High churn with high bug-fix ratio is unhealthy (constant fire-fighting). |
| **L1.18 Mutable state ratio** | Percentage of functions referencing mutable state outside their parameter list, measured at monthly snapshots | Is the codebase becoming more testable over time? Connects directly to Paper A's finding. Lower is better. |

### 2.4 The 300k-line delete

The idd `honest-conversion` branch includes a documented 300,000-line net-negative delete (observed on 2026-04-09). This event is a signature of the Honest Code conversion: the elimination of dead code, redundant implementations, and class-based patterns replaced by pure functions. The paper documents this event as a single data point but does NOT use it to inflate the delete/add ratio for the post period. Instead, the 300k delete is reported separately, and the continuous metrics are computed excluding it, so the improvement (if any) reflects the ongoing practice change, not a one-time cleanup.

## 3. Pre-registered predictions

### 3.1 idd (Buckler-context, CTO relationship present)

| Metric | Pre-Honest prediction | Post-Honest prediction | Direction |
|---|---|---|---|
| Rework rate (30-day) | > 25% | < 15% | Decrease |
| Bug-fix commit ratio | > 20% | < 12% | Decrease |
| Regression count (per month) | > 3 | < 1 | Decrease |
| Delete/add ratio | < 40% | > 60% | Increase |
| Net-negative commit ratio | < 5% | > 12% | Increase |
| L1.18 Mutable state ratio | > 30% | < 15% | Decrease |

### 3.2 Shawna's independent repo (zero Adam involvement)

| Metric | Pre-Honest prediction | Post-Honest prediction | Direction |
|---|---|---|---|
| Rework rate (30-day) | [TO ADD after Shawna confirms repo and baseline metrics are computed] | [TO ADD] | Decrease |
| Bug-fix commit ratio | [TO ADD] | [TO ADD] | Decrease |
| Delete/add ratio | [TO ADD] | [TO ADD] | Increase |

### 3.3 Cross-codebase consistency

| Prediction | Value |
|---|---|
| Both codebases show improvement in at least 3 of 5 metrics | Yes |
| The direction of improvement is the same in both codebases for all metrics | Yes |
| If only one codebase improves, it is the independent repo (not idd) | N/A: both should improve |

## 4. Falsification criteria

1. **The rework-reduction hypothesis** is falsified if the rework rate does NOT decrease in the post-Honest period for BOTH codebases. If rework stays the same or increases, the methodology does not reduce maintenance cost.

2. **The marginal-value hypothesis** is falsified if none of the five metrics improves by more than **5 percentage points** in the post period. A change smaller than 5 points could be noise. The methodology must produce a measurable improvement, not a marginal one.

3. **The independence hypothesis** is falsified if the two codebases show opposite directions on any metric (one improves, the other worsens). Opposite directions would mean the improvement is context-dependent, not methodology-dependent.

4. **The sustainability hypothesis** is falsified if the post-Honest metrics improve for the first month and then regress to pre-Honest levels. This would indicate a Hawthorne effect (temporary improvement from novelty) rather than a durable practice change. The paper measures at least 3 months of post-adoption data to test sustainability.

## 5. Sequence of events

1. **2026-04-12:** predictions and falsification criteria locked (idd predictions filled; independent repo predictions added when Shawna confirms)
2. **After timestamp:** compute pre-Honest baseline metrics for both codebases
3. **Ongoing:** Shawna continues working on both codebases under Honest practices
4. **~July 2026 (3 months post-adoption):** compute post-Honest metrics for both codebases
5. **Compare pre vs post:** apply falsification criteria
6. **Shawna writes her section:** first-person account of the practice change
7. **Manuscript drafted**
8. **Submitted:** target venue EMSE or IEEE Software

## 6. What this paper does NOT test

- Whether enterprise code is systematically untestable (Paper A)
- Whether AI produces Honest Code more correctly (Paper B)
- Whether the Slop Audit instrument is reproducible (Paper C)
- Whether the Honest Code book is the cause of the change vs some other factor (the design cannot fully isolate the book as the causal mechanism; Shawna's practice change coincides with reading the book, but it also coincides with the date she decided to adopt the practices, and the two are not separable)

## 7. What this paper does NOT protect against

- **The CTO confound on idd.** Adam is Shawna's CTO at Buckler. The improvement on idd could be influenced by the CTO relationship. Mitigation: the independent repo has zero Adam involvement. If both repos improve, the CTO relationship is not the driver.
- **The Hawthorne effect.** Shawna knows she is being studied. This could temporarily boost her performance. Mitigation: the sustainability criterion (3+ months of post data) and the independent-repo control.
- **Seasonal effects.** The pre/post boundary coincides with a calendar date (March 31). If the team's workload or priorities changed around the same date for reasons unrelated to Honest Code, the metrics could change for non-methodology reasons. Mitigation: the independent repo is not subject to Buckler's workload cycle.
- **The 300k delete.** A single large cleanup event inflates the delete/add ratio. Mitigation: reported separately and excluded from the continuous metric computation.

## 8. Timestamp anchor

**Timestamp anchor:** [TO ADD: Zenodo DOI or OSF registration ID once minted].

---

## Appendix A: Pre-registration checklist

- [ ] Shawna confirms the independent repository and authorizes its use
- [ ] Compute pre-Honest baseline metrics for idd
- [ ] Compute pre-Honest baseline metrics for Shawna's independent repo
- [ ] Fill in the [TO ADD] predictions for the independent repo in §3.2
- [ ] Identify the exact adoption date per codebase from git history
- [ ] Mint Zenodo DOI for this pre-registration
- [ ] Wait for 3+ months of post-adoption data (~July 2026)
- [ ] Compute post-Honest metrics for both codebases
- [ ] Shawna writes her section
- [ ] Draft the manuscript
- [ ] Submit to EMSE or IEEE Software; post arXiv preprint
