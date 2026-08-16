# Paper E Pre-Registration

**Working title.** Empirical Calibration of Mutable State Thresholds: Clustering Analysis and Rework Correlation on a 200-Repository Corpus.

**Author.** Adam Z. Wasserman.

**Pre-registration date.** 2026-04-13.

---

## 1. What this paper tests

Paper A reports the mutable state ratio (L1.18) across 200 public repositories using provisional thresholds (Healthy: 0--15%, Not Healthy: 15--40%, Slop: 40--100%). Those thresholds were set prior to data collection and are acknowledged as arbitrary. This paper tests whether the data supports those boundaries or suggests different ones, and whether mutable state ratio predicts rework ratio (a separate Slop Audit indicator).

Two hypotheses:

1. **Clustering hypothesis.** The distribution of L1.18 mutable state ratios across the Paper A corpus is not uniform but exhibits natural clusters. Gaussian mixture modeling (GMM) with model selection via BIC will identify the number of clusters and their boundaries.

2. **Rework correlation hypothesis.** Mutable state ratio (L1.18) is positively correlated with rework ratio (measured from git history on the same repositories). The relationship is not linear but exhibits one or more inflection points where rework costs accelerate.

If confirmed, the cluster boundaries and rework inflection points provide empirically grounded thresholds to replace the provisional ones in the Slop Audit methodology.

### 1.1 What is novel about this study

1. **First empirical calibration of code-quality thresholds from cross-language data.** Prior threshold-based tools (SonarQube, CodeClimate) set thresholds by expert judgment or vendor defaults. No prior study has derived code-quality category boundaries from distributional analysis of a multi-language corpus.

2. **First correlation of mutable state ratio with rework.** Mutable state is widely discussed as a testing obstacle but has not been quantitatively linked to maintenance cost in a cross-project study.

3. **Self-validating instrument design.** Both the predictor (L1.18) and the outcome (rework ratio) are measured by the same instrument (Slop Audit Layer 1 indicators). This demonstrates internal coherence of the indicator set.

## 2. Design

**Corpus.** The same 200 repositories used in Paper A (50 each: Java, Python, TypeScript, C#). No new data collection for L1.18 --- the Paper A results are reused.

**New measurement.** For each of the 200 repositories, compute the rework ratio from git history: the proportion of lines changed within 14 days of their initial commit (following the GitClear definition). This is computed from the same shallow clone used in Paper A, extended to sufficient depth for 6 months of history.

**Analysis 1: Clustering.**
- Fit Gaussian mixture models with k = 2, 3, 4, 5 components to the 200 L1.18 values.
- Select the best k by BIC (Bayesian Information Criterion).
- Report the cluster means, standard deviations, and boundaries (the crossover points between adjacent Gaussians).
- Compare the data-driven boundaries to the provisional thresholds (15%, 40%).

**Analysis 2: Rework correlation.**
- Scatter plot of L1.18 (mutable state %) vs rework ratio (%).
- Compute Spearman rank correlation and p-value.
- Fit a piecewise-linear model with 1 and 2 breakpoints (using the `pwlf` package or equivalent).
- Report the breakpoint(s) and their confidence intervals.
- Compare the rework inflection points to the cluster boundaries from Analysis 1.

**Analysis 3: Cross-language comparison.**
- Report whether the clusters are language-homogeneous or language-mixed.
- If TypeScript exhibits bimodal distribution (as suggested by Paper A's exploratory observation of a frontend/backend split), report this as a finding but do not subdivide --- that is Paper F's confirmatory test.

## 3. What counts as confirmation

- **Clustering hypothesis confirmed** if BIC selects k >= 2 (i.e., the distribution is not unimodal) and the cluster boundaries differ from uniform quantile splits by more than 5 percentage points.
- **Rework correlation confirmed** if Spearman rho > 0.3 with p < 0.01.
- **Threshold calibration successful** if the cluster boundaries and rework inflection points agree within 5 percentage points on at least one boundary.

## 4. What counts as disconfirmation

- If the distribution is unimodal (BIC selects k=1), the three-category scheme is not supported by the data.
- If Spearman rho < 0.3 or p > 0.01, mutable state does not predict rework in this corpus.
- If cluster boundaries and rework inflection points diverge by more than 10 percentage points on both boundaries, the thresholds cannot be grounded in both distributional and outcome data simultaneously.

## 5. Scope and limitations

- Rework ratio from shallow git history may undercount rework in repositories with squash-merge workflows.
- The 14-day rework window is one standard definition; sensitivity analysis with 7-day and 30-day windows will be reported.
- This study generates calibrated thresholds but does not confirm them. Confirmation requires testing the new thresholds on a fresh corpus (future work).

## 6. Relationship to other papers

- **Paper A** provides the L1.18 data reused here.
- **Paper D** measures rework longitudinally on two specific codebases; this paper measures rework cross-sectionally on 200 codebases. They are complementary.
- **Paper F** tests the TypeScript frontend/backend subdivision that may emerge from Analysis 3.
