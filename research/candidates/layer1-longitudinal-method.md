# Layer 1 longitudinal reading: method (CANDIDATE)

**Status: candidate. Not canon, not part of the twenty-indicator panel, not citable as a property of the standard.** Pending review by a practitioner of statistical process control. Would become section 3a of `../../spec/03-layer1-indicators.md` if approved.

Written 2026-08-14. The four decisions flagged in §9 are the ones needing a practitioner's signature. No claim here should be published as a property of the Slop Audit until that review happens.

### 1 What is under control

The instrument measures a **process**, not only a product. The process is the team's AI-assisted development practice. The product is the codebase, and each commit is one unit of output.

This is the existing scope of Layer 1, not an extension of it. Three passages already say so:

- §3 of this document: "Layer 1 currently measures *patterns of practice*."
- §2.1 of the four-layer model: the panel signals "the patterns associated with structured or unstructured AI-assisted development".
- §5.1 of the audit walkthrough requires "a written statement from the client identifying the codebase as **representative** of their current AI-assisted development practice". That is a sampling statement: the codebase is the sample, the practice is the population.

What follows adds no new measurement. It adds a second reading of measurements Layer 1 already produces.

### 2 Why a second reading is needed

A single audit returns one value per indicator, compared against a fixed band. The band answers "what level is this?" It cannot answer "is this level changing?", and the two questions have opposite remedies.

A codebase that has sat at the same delete/add ratio for three years and one that arrived there last quarter produce an identical panel today. The first is a property of how the team works and is only movable by changing the practice. The second is an event with a cause that can be found and addressed.

Acting on the first as though it were the second is **tampering** in Deming's sense: intervening on common-cause variation, which increases variation rather than reducing it. The current instrument gives an assessor no way to tell the two apart, and its bands actively invite the error. Worked example in §8.

### 3 Which indicators are chartable

| Indicators | Chartable | Cost |
|---|---|---|
| L1.1 – L1.8 | Yes | None. Each is already computed over a window from `git log` alone. One run per subgroup, no checkout. |
| L1.15 – L1.19 | Yes, second phase | One checkout per subgroup. These describe the tree at a point in time. |
| L1.9 – L1.11 | **No** | Binary presence checks. There is no variation to chart, and this should be stated rather than left for a reader to discover. |
| L1.20 | Marginal | An attribute at n=5 runs. Charting it is possible and probably not worth it. |

### 4 Subgroup definition

**Proposed: a fixed number of commits, not a calendar interval.**

If the commit is the unit of output, the natural subgroup is *n* commits. This gives constant subgroup size, which a calendar window does not: a quiet quarter and a busy quarter differ in commit count by a large factor, and an individuals chart assumes the inherent variation of each point is comparable. Commit-count subgrouping also self-adjusts for activity and removes the need for a minimum-activity floor.

Paper D pre-registers monthly intervals for L1.18, so a calendar reading should still be **reported** for continuity with that study. The proposal is that the chart be computed on commit-count subgroups and the calendar series reported alongside, not that the calendar reading be dropped.

The subgroup size must be fixed by the standard, not chosen per audit. An assessor-chosen window reproduces the inter-rater problem that Layer 1 exists to eliminate.

### 5 Chart type and constants

Each subgroup yields one value, so the chart is an **individuals and moving-range chart (XmR)**.

Limits are computed from the **median** moving range, not the mean:

- Centre line: the mean of the individual values over the baseline
- Natural process limits: centre ± **3.145** × median moving range
- Upper range limit: **3.865** × median moving range

The constants differ from the more commonly quoted 2.660 and 3.268, which apply to the **mean** moving range. Pairing the median with the mean's constant understates the limits, and that error was made and corrected during the drafting of this section.

**Why the median.** A single large step between consecutive subgroups inflates the mean moving range enough to widen the limits past the point where they can detect the very shift that produced them. On the worked example below, mean-based limits ran below zero on two of three indicators, producing charts that could not signal downward at all. The median moving range is Wheeler's standard answer to this and it restored detection power on both.

### 6 Baseline

Limits are computed from a fixed baseline set of subgroups and then **frozen and extended forward**.

This is the decision that determines whether the chart can ever signal. Recomputing limits on every run allows a drifting process to drag its own limits along with it, so the chart reports health indefinitely while the process degrades.

Proposed minimum: **8 baseline subgroups**, with limits treated as provisional until 20. Both figures follow common XmR practice and are among the items needing review.

The baseline range must be recorded in the report. A limit quoted without its baseline is not reproducible, and reproducibility is the entire basis of Layer 1's claim to be non-disputable.

### 7 Signal rules and the detection-power gate

**Three signal rules, and no more.** Each additional rule raises the false-alarm rate, and a false alarm in this instrument costs a remediation sprint.

1. One point outside the natural process limits.
2. Eight consecutive points on one side of the centre line.
3. One moving range above the upper range limit.

Rule 2 cannot fire until eight subgroups exist beyond the baseline, which is at least 16 subgroups in total. The report must say so; otherwise a reader assumes the chart is fully armed from the first run.

**The detection-power gate.** Before any verdict is issued, the computed limits are compared against the range the indicator can actually take:

- If a limit falls outside the metric's own range, the chart is one-sided or dead in that direction.
- If the chart cannot signal in either direction, the output is **"insufficient signal at this window size"**. It is never "stable".

A chart with no detection power reporting no signal is the process-control equivalent of a passing test that never ran, which is the failure this standard exists to name.

**The specification gap.** A one-sided chart is a legitimate object, but it stops being safe the moment a reader takes "no signal" to mean "acceptable". Where a control limit falls beyond a band threshold, the chart cannot signal anywhere inside the failing region, and the report must say so in that direction.

Worked, from the example below: L1.5's lower control limit is 15.1 and its Slop threshold is 30. **Any value from 16 to 29 is Slop and produces no signal.** A repository can fall from 70 to 16, deep into failure, and the chart correctly reports common-cause variation. It is not wrong; it is answering "did something change", and nothing did. But a reader who reads that as "leave it alone" has been misled by an omission. The chart cannot warn about a fall until 14.9 points past the line at which the standard already calls the process failing. Note that the range differs per indicator and must be taken from the definition, not assumed: L1.7 and L1.4 are shares bounded at 0 and 100, while **L1.5 is a ratio of deleted to added lines and is unbounded above** (a real value of 347.3 appears in the worked example). Two reviewers of this draft independently assumed L1.5 was bounded at 100.

### 7a The two limits answer different questions

The bands and the limits are not competing answers. They are different analyses and an operator needs both.

- **Specification limits** are the Healthy / Not Healthy / Slop thresholds, and Paper E's corpus calibration of them. They say what output is **acceptable**.
- **Control limits** are computed from one repository's own variation. They say what that process **actually does**.

Combining them is standard process-capability analysis and gives four readings rather than a contradiction:

| | Within specification | Outside specification |
|---|---|---|
| **In control** | Stable and good. Leave it alone. | **Stable and bad.** A common-cause problem: change the practice, do not react to individual points. |
| **Out of control** | Passing by luck; it will drift out. | Both. Start with the special cause. |

This dissolves an apparent conflict with Paper E, *Empirical Calibration of Mutable State Thresholds*. That paper computes thresholds from a 200-repository corpus, which are specification limits. Nothing here competes with it. The two disagreeing on a repository whose practice differs from the corpus median is the expected and useful result: **that difference is the capability gap**, and it is the number a CIO actually wants. Paper E can proceed unchanged.

This framing came out of review rather than from the drafting, and it needs the same practitioner confirmation as the rest.

### 8 Worked example

libuv (`github.com/libuv/libuv`), 14 annual subgroups, 2012 through 2025, computed with the existing tool via `--since` and `--until`. Median moving range, constant 3.145, all 14 points as baseline.

| Indicator | Centre | Limits | Detection power | Signals |
|---|---|---|---|---|
| L1.5 delete/add ratio | 70.4 | 15.1 to 125.8 | two-sided | **2012 (347.3)** |
| L1.7 high-delete commits | 51.4 | 36.3 to 66.4 | two-sided | none |
| L1.4 doc-line ratio | 7.3 | −1.2 to 15.8 | one-sided (floor) | **2014 (18.8), 2017 (19.3)** |

**The tampering case.** libuv's 2019 L1.5 is 17.8. The fixed band calls that **Slop**, below the 30 threshold. On the chart it sits inside the limits: common cause, no signal, no intervention warranted. The same number yields opposite instructions, and the chart is the reading that prevents a cleanup sprint against a stable process. Note that 17.8 sits close to the lower limit of 15.1; the case is real but not comfortable, and a reviewer should test it against other repositories before it is used as the standard's illustration.

### 9 The four decisions needing a practitioner's review

1. **Median versus mean moving range**, and the constants 3.145 and 3.865 that follow from that choice.
2. **The frozen baseline rule** and its minimum size of 8, provisional to 20.
3. **The subgroup definition**: commit-count against calendar interval, and the fixed size.
4. **The detection-power gate**: whether "insufficient signal at this window size" is stated correctly, and whether one-sided charts should be reported as usable in the direction that works or suppressed entirely.

Everything else in this section is standard XmR practice and needs confirmation rather than judgment.

### 10 What must not be claimed before that review

The Slop Audit should not be described as statistical process control in any public material until §9 is signed off and this section is canon. The defensible statement today is the one this document already makes: **Layer 1 measures patterns of practice.**

The provenance is worth recording. The SPC framing was not present in the Slop Audit canon before 2026-08-14; a search of the tree at that date returned zero occurrences of "statistical process control", "control chart", "control limit", "special cause", "Shewhart" and "Deming". It arose in discussion, not from the standard.

### 11 References

- Shewhart, W. A. *Economic Control of Quality of Manufactured Product*, 1931. The distinction between control limits, computed from the process, and specification limits, imposed from outside. The Slop Audit's Healthy / Not Healthy / Slop bands are specification limits.
- Deming, W. E. *Out of the Crisis*, 1982. Common and assignable cause; the funnel experiment and tampering.
- Wheeler, D. J. and Chambers, D. S. *Understanding Statistical Process Control*. XmR charts, the median moving range and its constants.

Page numbers are deliberately omitted. They should be taken from physical copies before this section is cited, not reproduced from memory.
