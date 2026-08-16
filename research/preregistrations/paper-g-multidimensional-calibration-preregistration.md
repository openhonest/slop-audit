# Paper G Pre-Registration

**Working title.** Multidimensional Calibration of Code Health Categories: Clustering Analysis Across All 19 Slop Audit Layer 1 Indicators.

**Author.** Adam Z. Wasserman.

**Pre-registration date.** 2026-04-13.

---

## 1. What this paper tests

The Slop Audit classifies codebases into three categories (Healthy, Not Healthy, Slop) using independent thresholds on each of 19 Layer 1 indicators. Papers A and E calibrate one indicator (L1.18 mutable state ratio) in isolation. This paper tests whether the three-category scheme is supported when all 19 indicators are considered simultaneously as a single feature vector.

The hypothesis: when 19-dimensional indicator vectors are collected for a large corpus and subjected to clustering analysis, the data will exhibit natural groupings that correspond to qualitatively different code health profiles. These emergent clusters may or may not align with the per-indicator threshold scheme currently used.

Three possible outcomes, all informative:

1. **The clusters align with per-indicator thresholds.** The current scheme is validated --- codebases that score "healthy" on individual indicators cluster together in 19-dimensional space.
2. **The clusters reveal correlated indicator groups.** Some indicators move together (e.g., high mutable state correlates with low test determinism and high rework), forming syndrome-like patterns. This would simplify the instrument by identifying redundant indicators.
3. **The clusters do not align with per-indicator thresholds.** A codebase can be "healthy" on 15 indicators and "slop" on 4, yet still cluster with healthy codebases overall. This would mean the current additive counting scheme (11+ slop signals = slop codebase) needs revision.

### 1.1 What is novel about this study

1. **First multidimensional clustering of code health indicators.** Prior tools (SonarQube, CodeClimate) assign letter grades from independent thresholds. No prior study has asked whether codebases naturally cluster in multi-indicator space.

2. **Indicator correlation structure.** The covariance matrix of 19 indicators has never been measured. Knowing which indicators are correlated (and which are independent) is essential for instrument design --- correlated indicators are partially redundant; independent indicators each contribute unique information.

3. **Empirical test of the additive counting scheme.** The current rule "11+ slop signals = slop codebase" assumes each indicator contributes equally and independently. Clustering analysis tests both assumptions.

## 2. Design

**Corpus.** A new corpus of 200+ public repositories, stratified by language (Java, Python, TypeScript, C#). May reuse the Paper A corpus if all 19 indicators can be measured on those repositories; otherwise a new corpus is constructed.

**Measurement.** For each repository, compute all 19 Layer 1 indicators:
- L1.1 through L1.11: git-history metrics (rework ratio, churn, delete/add ratio, etc.)
- L1.12 through L1.17: tooling and configuration metrics (linter compliance, type coverage, dependency freshness, etc.)
- L1.18 through L1.20: finite testability metrics (mutable state ratio, decision-space coverage, test determinism)

Indicators that return n/a for a given repository are handled by imputation (median of the available values for that indicator) or by exclusion (analysis repeated with and without incomplete repositories).

**Analysis 1: Clustering.**
- Standardize all 19 indicators to zero mean, unit variance.
- Fit Gaussian mixture models with k = 2, 3, 4, 5, 6 components.
- Select the best k by BIC.
- Report cluster profiles: the mean indicator vector for each cluster, identifying which indicators most differentiate the clusters.

**Analysis 2: Dimensionality reduction.**
- PCA on the 19-indicator matrix. Report the number of principal components needed to explain 80% and 90% of variance.
- If the effective dimensionality is much less than 19, identify the indicator groups that load on the same components. These are candidates for consolidation in a future version of the instrument.

**Analysis 3: Comparison with per-indicator thresholds.**
- For each repository, compute the current per-indicator classification (Healthy/Not Healthy/Slop on each indicator) and the additive slop count.
- Compare: does the additive slop count predict cluster membership? What is the concordance rate?
- If concordance is low, identify the indicator combinations that cause misclassification.

**Analysis 4: Indicator contribution.**
- Random forest or logistic regression predicting cluster membership from individual indicators.
- Rank indicators by feature importance.
- Identify any indicators that contribute near-zero information given the others (redundancy candidates).

## 3. What counts as confirmation

- BIC selects k >= 2: codebases do not form a single undifferentiated population.
- The clusters have interpretable profiles: at least one cluster has consistently low values on most indicators (a "healthy" profile) and at least one has consistently high values (a "slop" profile).
- PCA effective dimensionality is less than 15: some indicators are correlated, meaning the 19-dimensional space has structure.

## 4. What counts as disconfirmation

- BIC selects k = 1: codebases are uniformly distributed in indicator space, and categorical classification is not supported by the data.
- PCA effective dimensionality is 17+: indicators are mostly independent, and multidimensional clustering adds nothing beyond per-indicator thresholds.
- Concordance between additive slop count and cluster membership exceeds 90%: the simple counting scheme is already optimal and multidimensional analysis is unnecessary.

## 5. Scope and limitations

- Measuring all 19 indicators requires deeper repository access than Paper A (which measured only L1.18). Some indicators (L1.12 linter compliance, L1.15 type coverage) require running language-specific tooling, which limits automation.
- The corpus size must be substantially larger than the number of dimensions (19) to avoid overfitting. A minimum of 200 repositories is required; 500+ is preferred.
- Standardization assumes each indicator is equally important a priori. Sensitivity analysis with domain-weighted standardization will be reported.
- This study calibrates but does not confirm the multidimensional thresholds. Confirmation requires a fresh corpus.

## 6. Relationship to other papers

- **Paper A** provides L1.18 data and the repository corpus (if reusable).
- **Paper E** calibrates L1.18 in isolation; this paper calibrates all 19 indicators jointly. If Paper E's L1.18 cluster boundaries disagree with the boundaries implied by the multidimensional analysis, that disagreement is itself a finding.
- **Paper D** measures rework longitudinally on specific codebases. The rework indicator (likely L1.1 or related) is one of the 19 dimensions here. The multidimensional analysis reveals whether rework is redundant with other indicators or contributes unique information.
- **Paper F** identifies framework paradigm as a confound in TypeScript. If multidimensional clustering separates TypeScript-frontend from TypeScript-backend without explicit framework labeling, that is independent confirmation of Paper F's finding.
