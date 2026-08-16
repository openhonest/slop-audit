# Paper F Pre-Registration

**Working title.** Framework Paradigm as a Confound in Language-Level Testability Metrics: A Confirmatory Study of Frontend-Functional vs Backend-Class Subpopulations in TypeScript.

**Author.** Adam Z. Wasserman.

**Pre-registration date.** 2026-04-13.

---

## 1. What this paper tests

Paper A measured mutable state ratio (L1.18) across 200 repositories in four languages. Exploratory analysis of the TypeScript results revealed an apparent bimodal distribution: repositories using React and similar frontend frameworks clustered at 0--5% mutable state, while repositories using NestJS and similar backend frameworks clustered at 40--55%. This paper tests whether that observation replicates on a fresh corpus.

The hypothesis: within TypeScript, mutable state ratio is predicted by framework paradigm (functional-frontend vs class-backend) more strongly than by language alone. TypeScript repositories using functional-paradigm frameworks (React, Vue, Svelte, Astro, SolidJS) will have significantly lower L1.18 scores than TypeScript repositories using class-paradigm frameworks (NestJS, Express with classes, TypeORM, Angular services).

If confirmed, this finding means that language-level testability metrics must account for framework paradigm as a confound, and that the Slop Audit should classify TypeScript repositories by framework before applying thresholds.

### 1.1 What is novel about this study

1. **First confirmatory test of framework paradigm as a testability predictor.** The observation originates in Paper A's exploratory analysis. This paper preregisters and tests it on new data.

2. **Quantitative evidence for what practitioners know informally.** The React community's shift from classes to hooks is well-documented anecdotally. This study provides the first cross-project measurement of its effect on a structural code metric.

3. **Implications for instrument design.** If framework paradigm is a strong confound, all language-level code-quality instruments (not just Slop Audit) should account for it. This is a methodological contribution to the empirical software engineering field.

## 2. Design

**Corpus.** A new corpus of 100 TypeScript repositories, independent of the Paper A corpus. 50 classified as frontend-functional, 50 classified as backend-class.

**Classification procedure.** Each repository is classified by inspecting `package.json` dependencies:
- **Frontend-functional:** presence of `react`, `next`, `vue`, `nuxt`, `svelte`, `sveltekit`, `astro`, `solid-js`, `remix` in dependencies or devDependencies.
- **Backend-class:** presence of `@nestjs/core`, `typeorm`, `@angular/core` (in a non-browser context), `socket.io`, `@mikro-orm/core` in dependencies, OR presence of `express`/`fastify` with class-based patterns (detected by `class.*Controller` or `class.*Service` in source).
- **Ambiguous repositories** (both frontend and backend dependencies) are excluded.
- **Classification is performed before L1.18 measurement** to prevent selection bias.

**Measurement.** L1.18 mutable state ratio, using the same script as Paper A (`l1_18_typescript.py`).

**Statistical test.** Two-sample Welch's t-test on L1.18 values between the two groups. Effect size reported as Cohen's d. Mann-Whitney U as a non-parametric backup.

## 3. What counts as confirmation

- Welch's t-test p < 0.01 and Cohen's d > 0.8 (large effect).
- The frontend-functional group mean is below 15% (the provisional Healthy threshold).
- The backend-class group mean is above 30%.

## 4. What counts as disconfirmation

- p > 0.05 or Cohen's d < 0.5: framework paradigm does not strongly predict mutable state ratio within TypeScript.
- Both groups have similar means (both below 20% or both above 35%): the bimodal pattern observed in Paper A was a sampling artifact.

## 5. Scope and limitations

- The classification heuristic (package.json inspection) may misclassify monorepos or full-stack applications.
- Excluding ambiguous repositories reduces ecological validity but increases internal validity.
- This study tests only TypeScript. The same confound may exist in other multi-paradigm languages (Python with Django vs Flask, Java with Spring Boot vs functional libraries) but those are not tested here.
- The corpus is limited to repositories with 100+ stars, which biases toward popular and potentially better-maintained projects.

## 6. Relationship to other papers

- **Paper A** provides the exploratory observation that motivates this confirmatory study.
- **Paper E** may find that TypeScript's bimodal distribution contributes to the overall clustering structure. This paper tests the cause of that bimodality.
- The combined finding (if confirmed) has practical implications: the Slop Audit framework classification step should precede threshold application for TypeScript repositories.
