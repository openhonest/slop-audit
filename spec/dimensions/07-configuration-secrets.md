### 4.7 Configuration and secrets management

**Lifecycle category.** Operational security.

**Definition.** Configuration and secrets management is the application's mechanism for keeping sensitive credentials (database passwords, API keys, signing keys, third-party tokens) and environment-specific configuration (URLs, feature flags, tunable parameters) separate from the source code, injected at deployment time, rotatable without code changes, and protected from unauthorized access by anyone who can read the source repository or the build artifacts. A mature system stores secrets in a dedicated secrets manager, injects them into running processes via environment variables or sidecar mounts, and has zero credentials checked into source control or build artifacts. The opposite is the `config.py` (or `secrets.json`, or `application.properties`) file with hardcoded API keys committed to the repository, sometimes rotated by adding a new key alongside the old one and never removing the old one from git history.

**Industry threshold.** No secrets in source code or build artifacts; secrets stored in a dedicated secrets manager (HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, GCP Secret Manager, or equivalent); injected at runtime via environment variables, mounted files, or runtime API calls; rotatable by updating the secrets manager without code changes or redeployment of every service. Drawn from Akeyless State of Secrets Management 2024 (which found that 96% of organizations are vulnerable to secrets sprawl, 70% have experienced credential leaks, and average remediation takes 36 hours) and Entro Security's NHI & Secrets Risk Report H1 2025 (which found that 91% of former-employee tokens remain active after departure).

**Source citations (per the Wasserman 2026 working analysis, Appendix C).**
- Akeyless State of Secrets Management 2024 — 96% vulnerable, 70% experienced leaks, 36h average remediation — Tier 4 (vendor)
- Entro Security NHI & Secrets Risk Report H1 2025 — 91% of former-employee tokens still active — Tier 4 (vendor)
- CIS Benchmarks — secrets must never appear in code, must be environment-injected, must be rotatable — Tier 1
- Security Boulevard Credential Exposure Analysis (2025) — Tier 3

**Compliance framework mappings.**
- **NIST SP 800-53:** SC-12 (Cryptographic Key Establishment), SC-28 (Protection of Information at Rest), IA-5 (Authenticator Management)
- **SOC 2 Trust Services Criteria:** CC6.1 (Logical and Physical Access Controls), CC6.7 (Restriction of Information Transmission)
- **OSFI B-13:** Section 4.4 (Cyber Security)
- **CIS Benchmarks:** Secrets management controls
- **PCI-DSS:** Requirement 3.5 (Document and implement procedures to protect keys)

#### Layer 2 form (mechanical / artifact-based)

**Layer 2 inspection procedure.** This dimension is heavily mechanical. The Layer 2 form does almost all the work and the Layer 3 form is correspondingly thin (only 3 markers).

1. **Check L1.14 first.** Layer 1 indicator L1.14 has already run `gitleaks` (or `trufflehog`) against the current tree. Any confirmed true positive from L1.14 is an immediate finding and the dimension scores *Absent* without further inspection. Any count at or above the Slop threshold (≥3) is effectively disqualifying unless every hit is demonstrably a false positive on a test fixture. Then fall through to the classical checks below to catch what L1.14 missed.
2. **Grep the source for credential-shaped strings.** Use `grep -ri 'password\|secret\|api_key\|api-key\|token\|private_key' .` filtered to source files. Inspect each match. Look especially for assignments like `API_KEY = "sk_..."`, `PASSWORD = "..."`, `private_key = """-----BEGIN`. L1.14 catches most of these automatically but the grep is a belt-and-braces check for secret shapes that the scanner's ruleset does not recognize (home-grown token formats, internal PKI material, custom cloud vendor keys).
3. **Grep the git history.** Use `git log -p | grep -i 'sk_live\|sk_test\|aws_access_key\|password\|secret'`, or re-run `gitleaks detect` *with* git history enabled (L1.14 uses `--no-git` for speed; the history pass is separate). A credential committed to git history is exposed even if it has been "removed" from the current files; it must be rotated, not just deleted. Found credentials in history without evidence of rotation are also disqualifying.
4. **Inspect environment variable references.** Locate the configuration loading layer. Determine whether secrets are loaded from environment variables, from a secrets manager, or from a file.
5. **Inspect the `.env.example` (or equivalent) file.** Determine whether the example file contains placeholders only, real test credentials, or accidentally committed production credentials. Real credentials in `.env.example` are common and disqualifying.
6. **Inspect Docker images and build artifacts.** If the application builds container images, inspect a built image for embedded credentials. Common failure: secrets baked into the image at build time via `ARG` or `ENV` instructions, captured in the image layers.

#### Layer 3 form (qualitative specified judgment)

**Layer 3 inspection procedure.** Three markers, each scored present / partial / absent. (Fewer markers than other dimensions because most of this dimension's work is mechanical at Layer 2.)

**Marker 1: Secrets are loaded from a secrets manager, not just environment variables.** Environment variables are the bare minimum; a secrets manager (HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, GCP Secret Manager, or equivalent) is the mature pattern. The secrets manager provides centralized rotation, audit logging, access control, and versioning that environment variables cannot. Inspect the configuration loading layer to determine which mechanism is used. Present = secrets manager with audit logging; partial = environment variables loaded from a deployment system that has its own secrets storage; absent = environment variables loaded from a flat `.env` file or hardcoded in the deployment YAML.

**Marker 2: Secrets can be rotated without redeploying every service that uses them.** Determine whether the rotation procedure requires a coordinated multi-service deployment, or whether secrets can be rotated by updating the secrets manager and having services pick up the new value at runtime (or on the next request). The Entro 91% statistic on former-employee tokens still being active measures the failure mode: when rotation is operationally expensive, it never happens. Present = rotation procedure is a single secrets-manager update with no service redeploy; partial = rotation requires service restart but no code change; absent = rotation requires coordinated deployment of multiple services.

**Marker 3: CI/CD pipelines and container builds do not log or embed secrets.** Inspect CI/CD pipeline configurations and container build processes. Verify that environment variables are not logged for debugging (`echo $API_KEY` or similar), that secrets are not baked into container images at build time, and that secrets used during the build are scrubbed from logs and image layers. Sample 2-3 build logs from CI/CD history if available; check whether any secret-shaped strings appear in plain text. Present = secrets are not logged or embedded; partial = secrets are masked in current logs but historical logs may contain them; absent = secrets are visible in current build logs or embedded in container layers.

**Layer 3 scoring rule for the dimension.** Score Layer 3 *Present* if all 3 markers score Present. *Partial* if 2 markers score Present. *Absent* if 0 or 1 markers score Present.

#### Layer 4 questions (deferred to Phase 1)

- Is the secrets management strategy appropriate for this organization's threat model? (A startup may not need the operational overhead of HashiCorp Vault; a regulated bank may not be able to use anything else.)
- Are there subtle leakage paths through observability tools, error reporting, or third-party SaaS integrations that the trained assessor would not notice?
- Would the secrets management survive an insider threat with access to the deployment system?

**Combined scoring rubric.**

- ***Present.*** Layer 2 form passes (no credentials in source or git history, secrets externalized, clean `.env.example`, no embedded credentials in container images) AND Layer 3 form scores Present (all 3 markers).
- ***Partial.*** Layer 2 form passes but Layer 3 has gaps (2 markers Present); OR Layer 2 is Partial (secrets externalized but no dedicated manager) but Layer 3 scores Present.
- ***Absent.*** Layer 2 form fails (hardcoded credentials in source, committed credentials in git history without rotation, real credentials in `.env.example`, embedded secrets in Docker images); OR Layer 2 form passes but Layer 3 scores Absent.

**Common failure modes.**

- **Hardcoded API keys in source code.** The single most common failure. Stripe keys, AWS keys, Sendgrid keys, OpenAI keys, database passwords. Often "temporarily" added for local development and never removed.
- **Committed `.env` files.** A real `.env` file containing production credentials accidentally committed to the repository. Even if removed in a later commit, it stays in git history forever unless the history is rewritten.
- **Real credentials in `.env.example`.** The example file is intended to be a template with placeholders, but a developer copy-pasted their actual local credentials and committed them.
- **Secrets baked into Docker images.** `Dockerfile` containing `ENV API_KEY=sk_live_...` or `ARG SECRET=...` followed by `ENV SECRET=$SECRET`. The secret is embedded in an image layer and retrievable by anyone with image pull access.
- **Secrets in build logs.** CI/CD pipelines that print environment variables for debugging, capturing the secrets in build logs that may be retained for months.
- **Long-lived service tokens with no rotation.** A static API key for a third-party service that has never been rotated since the application was created. The Entro 91% statistic indicates how common this is.
- **Shared credentials across environments.** The same database password used in dev, staging, and production. A compromise in dev exposes production.
- **Single shared secret for all services.** A single `INTERNAL_SECRET` environment variable used for everything from JWT signing to inter-service auth to data encryption keys. A compromise of any one usage exposes all of them.
- **Secrets stored in environment variables that get logged.** Application logs capture environment variables for diagnostic purposes, including the secrets, leaking them to log aggregation systems.

**Example presence (Java / Spring Boot).** A Spring Boot application using Spring Cloud Config Server backed by HashiCorp Vault. At startup, the application reads its configuration from `https://config.internal/myservice/{profile}`, which proxies to a Vault path scoped to the service identity. Database credentials, third-party API keys, and signing keys are all retrieved from Vault. The application's source code contains zero credential strings; `application.yml` references config keys like `db.password: "${DB_PASSWORD}"` where `DB_PASSWORD` is resolved from Vault, never from a static file. Vault credentials themselves are obtained via Kubernetes service account tokens (no bootstrap credentials needed). Rotation is handled by updating the Vault path and triggering a Spring Cloud Bus refresh event; no redeploy is required. The Docker image contains zero secrets and was last scanned for credential leaks during the most recent CI build.

**Example absence (Python / Flask).** A Flask application with a `config.py` file at the repository root containing:
```
STRIPE_SECRET_KEY = "sk_live_51ABC..."
DATABASE_URL = "postgres://app:hunter2@db.prod.internal:5432/myapp"
JWT_SECRET = "the-quick-brown-fox-jumps-over-the-lazy-dog"
SENDGRID_API_KEY = "SG.xyz..."
```
The file is committed to git and has been since the project's first commit 26 months ago. `git log --all -p config.py` reveals that the Stripe key was rotated once 8 months ago (the new key replaced the old one in a commit), but the old key is still retrievable from history and was never revoked at Stripe. The `.env.example` file in the same repository contains a working OpenAI API key for the team's shared developer account. A Dockerfile in the same repository contains `ENV ADMIN_PASSWORD=changeme` as a default that "would be overridden in production" but isn't, because the Kubernetes deployment YAML omits the override. Five out of nine credentials checked are exposed in the codebase.

**Time budget.** Approximately 60 to 75 minutes for an experienced assessor: 30 to 45 minutes for the Layer 2 inspection (the grep checks are the disqualifier and take 5 minutes), 30 minutes for the Layer 3 marker assessment.

---

