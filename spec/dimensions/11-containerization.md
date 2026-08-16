### 4.11 Containerization

**Lifecycle category.** Infrastructure.

**Definition.** Containerization is the application's mechanism for packaging itself and its runtime dependencies into a self-contained image that runs identically in development, testing, staging, and production. A mature containerization system uses multi-stage builds (smaller attack surface, smaller images, faster pulls), runs as a non-root user (defense against container escape), defines health checks (orchestrators can detect and restart unhealthy containers), separates configuration for development, testing, and production (no environmental drift), and produces images that are reproducible from a tagged source commit. The opposite is the application that runs only on the developer's laptop, has no container image, and depends on an undocumented set of system packages that drift between machines.

**Industry threshold.** Multi-stage builds, non-root execution, health checks defined, separate dev/prod/test configurations. Drawn from CNCF Annual Cloud Native Survey 2024 (which found 82% Kubernetes production adoption with an average of 2,341 containers per organization) and CNCF + SlashData State of Cloud Native Development 2025. The threshold reflects industry consensus that containerization is no longer optional for enterprise applications: it is the baseline packaging format that everything else (orchestration, observability, security scanning, deployment automation) builds on.

**Source citations (per the Wasserman 2026 working analysis, Appendix C).**
- CNCF Annual Cloud Native Survey 2024 — 82% K8s adoption, 2,341 containers/org average — Tier 1
- CNCF 2025 Survey (January 2026) — Tier 1
- CNCF + SlashData State of Cloud Native Development 2025 — Tier 1

**Compliance framework mappings.**
- **NIST SP 800-190:** Application Container Security Guide
- **CIS Docker Benchmark:** Container security controls
- **CIS Kubernetes Benchmark:** Orchestration security controls
- **NIST SP 800-53:** SA-11 (Developer Security Testing), SI-7 (Software, Firmware, and Information Integrity)

#### Layer 2 form (mechanical / artifact-based)

**Layer 2 inspection procedure.**

1. **Run Layer 1 indicator L1.11 first.** L1.11 (containerization configuration) already detects the presence and shape of container configuration. If L1.11 returned **Absent**, this dimension scores *Absent* without further inspection. If L1.11 returned **Present and minimal**, the Layer 2 form scores *Partial* at best.
2. **Inspect for embedded secrets.** Use `docker history <image>` or equivalent to inspect a built image's layers. Check for credentials baked into the image at build time. (Overlaps with 4.7.)
3. **Inspect the image build process.** Determine whether images are built as part of CI/CD (mature) or built manually on a developer's laptop and pushed to the registry (immature). Manual builds break reproducibility and introduce drift.
4. **Inspect the image scanning configuration.** Determine whether images are scanned for vulnerabilities before deployment. Look for Trivy, Grype, Clair, or platform-native scanning integrated into the CI/CD pipeline.

#### Layer 3 form (qualitative specified judgment)

**Layer 3 inspection procedure.** Four markers, each scored present / partial / absent.

**Marker 1: The Dockerfile is multi-stage with a minimal runtime base image.** Open the primary Dockerfile. Check for multi-stage construction (one stage builds, another stage runs) and verify that the runtime stage uses a minimal base (Alpine, distroless, scratch, or a slim variant of the language image) rather than a full OS image (Ubuntu, Debian, full Python, full Node). Single-stage builds copy the entire build context and produce 2GB images with 500MB of build tools left over; multi-stage builds copy only what is needed and produce 50-200MB images with no build tooling. Present = multi-stage with minimal runtime base; partial = multi-stage but with a non-minimal base, or single-stage with a minimal base; absent = single-stage with a full OS base.

**Marker 2: The container runs as a non-root user.** Verify that the Dockerfile includes a `USER` directive that switches away from root before the application starts. Running as root inside a container means a vulnerability in the application that allows code execution gives the attacker root inside the container, which is a much larger blast radius than a non-root execution context. Some orchestration platforms (Kubernetes with PodSecurityStandards enforcement) reject root containers entirely; mature codebases prepare for this by running as non-root regardless of the platform. Present = explicit `USER` directive switching to a non-root user; partial = `USER` directive with an unprivileged user but still UID 0 in some namespace mappings; absent = no `USER` directive (defaults to root).

**Marker 3: Health checks are defined and the orchestrator uses them.** Verify that the Dockerfile defines a `HEALTHCHECK` directive AND that the orchestration configuration (Kubernetes liveness/readiness probes, ECS health checks, docker-compose `healthcheck`) actually uses it. A `HEALTHCHECK` in the Dockerfile that the orchestration platform ignores is just decoration. The mature pattern has the orchestrator probing the application's health endpoint and restarting unhealthy containers automatically. Present = `HEALTHCHECK` defined AND orchestrator uses it; partial = one or the other but not both; absent = neither.

**Marker 4: Per-environment configuration is parameterized, not hardcoded in the image.** Verify that the same image can be deployed to dev, staging, and production by changing environment variables or configuration files passed at runtime, rather than rebuilding the image. The mature pattern has one image per source commit, deployed to multiple environments via runtime configuration. The immature pattern has separate `Dockerfile.dev`, `Dockerfile.staging`, `Dockerfile.prod` files (or one Dockerfile with hardcoded environment-specific values), which breaks reproducibility because the image deployed to production is not the same image that was tested in staging. Present = one image per commit, runtime configuration; partial = one image per commit but with significant environment-specific build args; absent = separate images per environment.

**Layer 3 scoring rule for the dimension.** Score Layer 3 *Present* if 3 or 4 markers score Present. *Partial* if 2 markers score Present. *Absent* if 0 or 1 markers score Present.

#### Layer 4 questions (deferred to Phase 1)

- Is the container orchestration appropriate for this application's scale and operational maturity? (Kubernetes is overkill for some applications; ECS or simple docker-compose may be the right choice.)
- Are there subtle resource exhaustion scenarios (memory leaks, file descriptor leaks, thread pool exhaustion) that the container limits would not catch?
- Would the containerization survive a sophisticated attacker who has compromised the host or the orchestrator?

**Combined scoring rubric.**

- ***Present.*** Layer 2 form passes (containerization configured, no embedded secrets, images built in CI/CD, image scanning integrated) AND Layer 3 form scores Present (3 or 4 of 4 markers).
- ***Partial.*** Layer 2 form passes but Layer 3 has gaps (2 markers Present); OR Layer 2 is Partial (containerization minimal, manual builds, missing scanning) but Layer 3 scores Present.
- ***Absent.*** Layer 2 form fails (no containerization, OR a Dockerfile exists but is fundamentally broken and unused); OR Layer 2 form passes but Layer 3 scores Absent.

**Common failure modes.**

- **Single-stage build copying the entire build context.** A Dockerfile that uses a full Ubuntu base image, copies the entire repository including `node_modules`, and runs as root. The resulting image is 2GB, contains the source code and build tools, and has every system package installed. Attack surface is enormous.
- **Root execution.** The Dockerfile does not include a `USER` directive, so the container runs as root. A vulnerability in the application that allows code execution gives the attacker root inside the container, which is a much larger blast radius than a non-root execution context.
- **No health check.** The Dockerfile has no `HEALTHCHECK` directive and the orchestration platform has no application-level health probe. When the application hangs or crashes, the orchestrator does not detect it and continues routing traffic to the broken container.
- **Configuration hardcoded in the image.** Database URLs, API endpoints, feature flags, and environment-specific values baked into the image at build time. The same image cannot be promoted from staging to production; a separate build is required for each environment, breaking reproducibility.
- **Secrets in environment variables visible in `docker inspect`.** Secrets passed as environment variables instead of mounted files. Anyone with `docker inspect` access can read them from the running container's metadata.
- **No resource limits.** Containers without CPU or memory limits. A bug that allocates unbounded memory takes down the entire host instead of just the affected container.
- **Image built on a developer's laptop and pushed.** The image in the registry is whatever the developer's local environment produced, not what the source code at a specific commit produces. Reproducibility is gone.
- **No image scanning.** Images are pulled into production without ever being scanned for vulnerabilities. The first time anyone notices a CVE in a base image is when an external auditor runs a scan during a compliance review.

**Example presence (Python / multi-stage Dockerfile).** A Python application with a multi-stage Dockerfile: the build stage uses `python:3.12-slim` as the base, installs build dependencies, runs `pip install --user -r requirements.txt`, and compiles any C extensions. The runtime stage uses `python:3.12-alpine` as the base, copies only the installed packages from the build stage's `~/.local`, copies the application code, creates a non-root user `app`, switches to that user, defines `HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1` with a 30-second interval, and exposes port 8000. The resulting image is 87MB. Three compose files (`docker-compose.yml`, `docker-compose.dev.yml`, `docker-compose.prod.yml`) define environment-specific configuration via overrides. Resource limits (`mem_limit: 512m`, `cpus: 1.0`) are defined in production. Images are built in GitHub Actions on every commit, scanned with Trivy for vulnerabilities, and pushed to a private ECR registry only if the scan passes. Secrets are mounted as files via Docker secrets in production.

**Example absence (C# / no containerization).** A .NET application deployed directly to a Windows Server VM in Azure. There is no Dockerfile in the repository. The deployment process is a PowerShell script that copies the build output to a network share, an administrator RDPs into the production server, copies the files from the share to `C:\inetpub\wwwroot\app\`, and restarts IIS. The development environment requires installing .NET SDK 6.0, SQL Server LocalDB, and 14 specific NuGet packages on the developer's laptop, with installation instructions documented in a 2,400-word Confluence page that has been edited 47 times in the last 18 months. Onboarding a new developer takes approximately 2 days because of environmental drift between machines. There is no concept of "the application image" — there is only "what is currently installed on this server."

**Time budget.** Approximately 60 to 75 minutes for an experienced assessor: 20 to 30 minutes for the Layer 2 inspection (L1.11 already characterized the configuration), 40 to 45 minutes for the Layer 3 marker assessment.

---

