### 4.10 CI/CD

**Lifecycle category.** DevOps.

**Definition.** Continuous Integration and Continuous Delivery (CI/CD) is the automated mechanism by which the application's source code is built, tested, security-scanned, and deployed every time it changes. A mature CI/CD system runs automatically on every commit (no manual triggers required), gates merges and deployments on test and security results (no broken or insecure code reaches the protected branches), produces reproducible builds (the same input commit produces the same output artifact every time), and provides observability into pipeline duration, failure rates, and recovery time. The opposite is the codebase with no automation at all, where builds happen on a developer's laptop, tests are run when someone remembers, security scans never happen, and deployments are manual SSH sessions to a production server.

**Industry threshold.** Automated test, build, deploy, and security scan on every change, with gating that prevents broken or insecure code from reaching protected branches. DORA elite performers (per the 2024 State of DevOps report covering 39,000+ professionals over 10 years) deploy multiple times per day, recover from failures in under one hour, and have a change failure rate under 5%. Puppet's 2024 State of DevOps found that 66% of high-performing organizations have automated CI/CD. The threshold for this dimension is the presence of *real* automation that does *real* work, not the presence of a workflow file that runs `echo "build successful"`.

**Source citations (per the Wasserman 2026 working analysis, Appendix C).**
- DORA Accelerate State of DevOps 2024 — 39,000+ professionals, 10 years — Tier 1
- Puppet State of DevOps 2024 — Tier 2
- CD Foundation DORA 5 Metrics Update — Tier 1
- GitLab DORA Metrics Implementation — Tier 4 (vendor)

**Compliance framework mappings.**
- **NIST SP 800-53:** SA-11 (Developer Security Testing and Evaluation), SA-15 (Development Process, Standards, and Tools), CM-3 (Configuration Change Control)
- **SOC 2 Trust Services Criteria:** CC8.1 (Change Management)
- **OSFI B-13:** Section 4.7 (Technology Operations and Resilience)
- **NIST SSDF (Secure Software Development Framework):** PW.7, PW.8, PS.1

#### Layer 2 form (mechanical / artifact-based)

**Layer 2 inspection procedure.**

1. **Run Layer 1 indicator L1.10 first.** Layer 1's L1.10 (CI/CD pipeline configuration) already counts pipeline definition files. If L1.10 returned **0 pipelines**, this dimension scores *Absent* without further inspection. If L1.10 returned 1–4 pipelines, the Layer 2 form scores *Partial* at best.
2. **Inspect what each pipeline actually does.** Open each pipeline definition file. For each pipeline, identify whether it: (a) compiles or builds the application, (b) runs unit tests, (c) runs integration tests, (d) runs security scans, (e) deploys to an environment, (f) does nothing meaningful (a placeholder pipeline that just runs `echo`).
3. **Inspect the security scanning.** Determine which security scans are configured (Dependabot, Snyk, Trivy, GitGuardian, CodeQL, Semgrep, SonarQube, FOSSA). The presence of scanning configuration is a Layer 2 check; whether the alerts produced are actually monitored is a Layer 3 question.
4. **Inspect the pre-commit hooks.** Look for `.pre-commit-config.yaml`, `husky`, `lefthook`, or equivalent. Pre-commit hooks are the local-machine equivalent of CI gates and catch issues before they reach the pipeline. (Overlaps with L1.9.)

#### Layer 3 form (qualitative specified judgment)

**Layer 3 inspection procedure.** Four markers, each scored present / partial / absent.

**Marker 1: Pipelines run automatically on every push and pull request, not just on manual trigger or tag push.** Inspect the trigger conditions in the pipeline definitions. Pipelines that only run on manual trigger or tag push are not "continuous" anything; they are scripts disguised as automation. The mature pattern runs the full pipeline on every push to every branch and on every pull request, with deployment pipelines additionally gated on branch (only deploy from main/release) or approval (manual gate before production deploy). Present = automatic on push and PR; partial = automatic on PR but not on push, or automatic on push but not on PR; absent = manual trigger only.

**Marker 2: The test suite has real assertions (vacuousness check).** Sample 5 to 10 test files. Read each test and confirm that the assertions are not always true. Common failures: `assert(true)`, `expect(1).toBe(1)`, `assertNotNull(obj)` immediately after `obj = new Foo()` (which is always non-null by construction), tests that catch all exceptions and pass regardless. The mature CI/CD pipeline runs a real test suite that fails when the code is wrong; the immature one runs a vacuous test suite that always passes regardless of code quality. Present = sampled tests are all meaningful; partial = 1-2 vacuous out of 5-10; absent = 3 or more vacuous, or the test suite is mostly skipped/disabled.

**Marker 3: Branch protection requires pipeline success to merge.** Determine whether protected branches (typically `main` and `release`) require pipeline success before merge. Look for branch protection rules in the repository settings or in the pipeline configuration itself. A repository with pipelines but no branch protection is the "pipelines as recommendation, not gate" failure mode: the pipelines correctly fail when the build is broken, but developers merge broken code anyway. Present = protected branches require all required workflows to pass; partial = some workflows are required but not all of the critical ones; absent = no branch protection, anyone can merge anything.

**Marker 4: Security scans produce alerts that someone monitors.** Inspect the security scanning configuration AND the alerting destination. The mature pattern routes findings to a Slack channel, Linear/Jira queue, or other monitored destination, with someone responsible for triaging them. The "scans run, alerts go to /dev/null" failure mode is common: Snyk or Dependabot produces hundreds of findings per month, the email goes to a shared address nobody reads, and the findings are invisible. Present = scans run AND alerts route to a monitored destination AND there is evidence (commit history, ticket queue) of recent triage; partial = scans run and alerts route to a destination but there is no evidence of triage; absent = scans run with no alerting destination, or no scans at all.

**Layer 3 scoring rule for the dimension.** Score Layer 3 *Present* if 3 or 4 markers score Present. *Partial* if 2 markers score Present. *Absent* if 0 or 1 markers score Present.

#### Layer 4 questions (deferred to Phase 1)

- Are the pipelines fast enough to support the team's iteration speed? (Slow pipelines that take hours per change degrade the team's velocity even when they are technically correct.)
- Are there subtle gaps in the test coverage that an experienced engineer would notice but the metrics would not catch?
- Would the CI/CD system survive a coordinated attempt to bypass the gates (a developer who knows where the loopholes are)?

**Combined scoring rubric.**

- ***Present.*** Layer 2 form passes (5+ pipelines, each doing meaningful work, security scanning configured, pre-commit hooks present) AND Layer 3 form scores Present (3 or 4 of 4 markers).
- ***Partial.*** Layer 2 form passes but Layer 3 has gaps (2 markers Present); OR Layer 2 is Partial (1-4 pipelines, partial coverage of build/test/scan/deploy) but Layer 3 scores Present.
- ***Absent.*** Layer 2 form fails (zero pipelines, or pipelines that do nothing meaningful, or all deployments are manual SSH sessions); OR Layer 2 form passes but Layer 3 scores Absent.

**Common failure modes.**

- **Echo-only placeholder pipeline.** A workflow file exists at `.github/workflows/ci.yml` but it just runs `echo "Build successful"` and exits. The pipeline reports green every time but does no actual work. Common in codebases where the team set up CI to satisfy a checklist but never finished the implementation.
- **Tests that always pass.** Test files exist but the assertions are vacuous (`assert(true)`, `expect(1).toBe(1)`, `assertNotNull(obj)` on a fresh constructor). The pipeline runs the tests, the tests always pass, but the tests prove nothing.
- **No branch protection.** Pipelines exist and they correctly fail when the build is broken, but the protected branch has no requirement that pipelines must pass before merge. Developers merge broken code anyway. The pipeline is a recommendation, not a gate.
- **Deploy without test gating.** The deploy pipeline runs every time main is updated, regardless of whether the test pipeline has passed. Broken code reaches production because the test pipeline takes longer than the deploy pipeline.
- **Security scanning that never alerts.** Snyk or Dependabot is configured, but the alerts go to an email address nobody monitors, or a Slack channel with 30,000 unread messages. The scans run; the findings are invisible.
- **Manual deploys only.** A `deploy.sh` script that a human runs from their laptop. Common in early-stage codebases that grew before CI/CD was a priority.
- **Pipeline that only runs on tag push.** The CI workflow is configured with `on: push: tags: ['v*']` and never runs on pull requests or pushes to feature branches. Pre-merge feedback does not exist.
- **Long-failing pipeline ignored.** The main branch has had a failing pipeline for 6 weeks. Nobody is fixing it because nobody is treating the pipeline as authoritative. The test suite has been telling the truth and being ignored.
- **Pipeline credentials hardcoded.** Deploy credentials, registry passwords, or secrets baked into the pipeline YAML instead of being injected via the platform's secrets manager. (Overlaps with 4.7.)

**Example presence (Go / GitHub Actions).** A Go application with 8 GitHub Actions workflows in `.github/workflows/`: `build.yml` (runs `go build` on every push to every branch), `test.yml` (runs `go test ./...` with race detector and coverage reporting), `lint.yml` (runs `golangci-lint run` with a strict configuration), `vet.yml` (runs `go vet` and `staticcheck`), `security.yml` (runs Trivy on the built binary, govulncheck on dependencies, and GitGuardian secret scanning on the diff), `deploy-staging.yml` (deploys to staging on main branch updates after all other workflows pass), `deploy-prod.yml` (deploys to production on tag pushes after manual approval), and `nightly.yml` (runs a full integration test suite against a real database). The `main` branch has branch protection requiring all required workflows to pass before merge. Pre-commit hooks installed via `lefthook` run `gofmt`, `goimports`, `golangci-lint --fast`, and a unit test on changed packages. Pipeline failures notify a `#engineering-alerts` Slack channel and create a Linear ticket if the failure is on main. The team's average time-to-recovery from a broken main is 23 minutes, well within the DORA elite tier.

**Example absence (Java / no CI).** A Java application with no `.github/workflows/`, no `Jenkinsfile`, no `.gitlab-ci.yml`, no `azure-pipelines.yml`. The repository has 14 contributors over 3 years and 2,847 commits. There is a `build.sh` script in the repository root that runs `mvn clean install`, but it is run by developers on their laptops, not by any automation. There are 47 test files in `src/test/java/`, but the assessor confirms by running `mvn test` that 12 of them have been broken for over a year (compilation errors, deleted classes referenced, missing dependencies). The team's deploy process is documented in a Confluence page titled "How to deploy" that begins with "SSH into prod-app-01 as the `appuser` user, then run `cd /opt/app && git pull && mvn package && systemctl restart app`." A failed deploy two months ago resulted in 4 hours of downtime because the developer who knew how to roll back was on vacation.

**Time budget.** Approximately 60 minutes for an experienced assessor: 20 to 30 minutes for the Layer 2 inspection (L1.10 already counted the pipelines), 30 to 40 minutes for the Layer 3 marker assessment.

---

