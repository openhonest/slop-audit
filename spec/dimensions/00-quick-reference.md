
---

### Section 4 Quick Reference

**Auto-shop-manual style.** This is the look-up sheet for an assessor mid-audit who needs a fast answer about a specific dimension without reading its full entry. Every dimension fits one row. The "Fastest kill check" column names the single inspection that produces the quickest score for that dimension. The "Disqualifier" column names the single failure mode that scores **Absent** regardless of any other finding. When a disqualifier is present, you can stop assessing that dimension immediately.

Lifecycle category abbreviations: **SEC** = Security architecture, **DAT** = Data architecture, **CMP** = Compliance engineering, **OPS** = Operational security, **PRF** = Performance engineering, **OPR** = Operations, **DVO** = DevOps, **INF** = Infrastructure, **ARC** = Software architecture, **GOV** = Governance, **PRC** = Process engineering, **LFC** = Lifecycle management, **DEV** = Software development.

<table>
  <thead>
    <tr>
      <th>#</th>
      <th>Dimension</th>
      <th>Cat</th>
      <th>Threshold (one phrase)</th>
      <th>Fastest kill check (5 min)</th>
      <th>Disqualifier (scores Absent)</th>
      <th>Time</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>4.1</td>
      <td>Entitlement system</td>
      <td>SEC</td>
      <td>Per-endpoint authz, deny-by-default, access logged</td>
      <td>Grep for an authorization decorator/middleware/guard that runs before route handlers</td>
      <td>No authz beyond "is logged in"</td>
      <td>60–90m</td>
    </tr>
    <tr>
      <td>4.2</td>
      <td>Authentication</td>
      <td>SEC</td>
      <td>NIST AAL2 with session token binding, MFA, hashed passwords</td>
      <td>Inspect the password storage column type and contents directly</td>
      <td>Plain text password storage, OR hardcoded credentials in source</td>
      <td>60–90m</td>
    </tr>
    <tr>
      <td>4.3</td>
      <td>Inter-service security</td>
      <td>SEC</td>
      <td>Cryptographic verification of inter-service calls with replay protection (CISA ZT Advanced)</td>
      <td>Inspect one inter-service call site for HMAC, mTLS, or signed JWT</td>
      <td>Plain HTTP between services with shared static API key</td>
      <td>60m / 15m monolith</td>
    </tr>
    <tr>
      <td>4.4</td>
      <td>Multi-tenancy</td>
      <td>DAT</td>
      <td>Tenant context enforced at query layer; no possible cross-tenant code path</td>
      <td>Manual cross-tenant access attempt by ID enumeration in test environment (1 minute test)</td>
      <td>Cross-tenant access succeeds in test environment</td>
      <td>75m / N/A single-tenant</td>
    </tr>
    <tr>
      <td>4.5</td>
      <td>Audit infrastructure</td>
      <td>CMP</td>
      <td>Tamper-evident, structured, queryable who/what/when/where/outcome records</td>
      <td>Locate the audit module; inspect record schema</td>
      <td>No structured audit logging; print statements or app log only</td>
      <td>75–90m</td>
    </tr>
    <tr>
      <td>4.6</td>
      <td>Rate limiting</td>
      <td>OPS</td>
      <td>Per-endpoint sliding-window limits, distributed state, 429 + Retry-After</td>
      <td>Hammer auth endpoint with 100 rapid requests; check for 429</td>
      <td>No rate limiter at all, OR limiter only protects one endpoint</td>
      <td>60m</td>
    </tr>
    <tr>
      <td>4.7</td>
      <td>Configuration &amp; secrets</td>
      <td>OPS</td>
      <td>No secrets in source; environment-injected or vault-stored; rotatable</td>
      <td>Check the L1.14 result first (5 min); grep source and git history for shapes L1.14 missed</td>
      <td>L1.14 Slop (≥3 secrets) or any confirmed hardcoded API key / password / token in source or git history</td>
      <td>30–45m (L1.14 does most of the work)</td>
    </tr>
    <tr>
      <td>4.8</td>
      <td>Caching</td>
      <td>PRF</td>
      <td>Tiered TTLs per data type, invalidation triggers, cache key includes tenant context</td>
      <td>Locate cache layer; inspect TTL configuration and key construction</td>
      <td>Cache key omits tenant or user identifier (cross-context leakage)</td>
      <td>45–60m / N/A no cache</td>
    </tr>
    <tr>
      <td>4.9</td>
      <td>Notifications</td>
      <td>OPR</td>
      <td>Async event-driven delivery with queue coordination, retry, DLQ</td>
      <td>Locate notification dispatch; inspect for sync vs async path</td>
      <td>Synchronous in-request notifications blocking the response</td>
      <td>45m / N/A no notifications</td>
    </tr>
    <tr>
      <td>4.10</td>
      <td>CI/CD</td>
      <td>DVO</td>
      <td>Automated test, build, deploy, security scan, with gating; ≥5 pipelines</td>
      <td>Count CI/CD pipeline definition files</td>
      <td>Zero pipelines; manual deploys only</td>
      <td>45m</td>
    </tr>
    <tr>
      <td>4.11</td>
      <td>Containerization</td>
      <td>INF</td>
      <td>Multi-stage builds, non-root, health checks, dev/prod/test configs</td>
      <td>Locate Dockerfile / Helm chart / K8s manifests</td>
      <td>No containerization at all</td>
      <td>30–45m</td>
    </tr>
    <tr>
      <td>4.12</td>
      <td>Dependency injection</td>
      <td>ARC</td>
      <td>Explicit registration, lifecycle management, swappable contracts</td>
      <td>Locate DI container or service registration; inspect for protocol-based contracts</td>
      <td>Singletons-as-globals; no swappability</td>
      <td>45–60m</td>
    </tr>
    <tr>
      <td>4.13</td>
      <td>Pattern sophistication</td>
      <td>ARC</td>
      <td>Diverse battle-tested patterns chosen for problem fit, not cargo-culted</td>
      <td>Inspect 3 random modules for pattern variety vs uniformity</td>
      <td>One pattern repeated everywhere regardless of context</td>
      <td>60–75m</td>
    </tr>
    <tr>
      <td>4.14</td>
      <td>Architectural philosophy</td>
      <td>ARC</td>
      <td>Coherent articulated philosophy; modules align with the philosophy</td>
      <td>Read 3 random modules; check for stylistic and structural consistency</td>
      <td>No coherent style; every module looks like it was written by a different person</td>
      <td>75m</td>
    </tr>
    <tr>
      <td>4.15</td>
      <td>Live documentation</td>
      <td>GOV</td>
      <td>Docs updated alongside code (mixed commits ≥12% per L1.3); not stale</td>
      <td>Cross-reference: pick 3 recent code commits; check that touched docs were updated</td>
      <td>Documentation references functions/classes that no longer exist</td>
      <td>45–60m</td>
    </tr>
    <tr>
      <td>4.16</td>
      <td>SDLC with AI safeguards</td>
      <td>PRC</td>
      <td>Spec-before-code, BDD-first, real-time review, automated quality gates</td>
      <td>Inspect for .feature files, pre-commit hooks, CI gates</td>
      <td>No spec files, no pre-commit hooks, no quality gates</td>
      <td>60m</td>
    </tr>
    <tr>
      <td>4.17</td>
      <td>Tech debt management</td>
      <td>LFC</td>
      <td>Active deletion (delete/add ratio ≥60% per L1.5); net-negative commits routine; unreachable code &lt;1% (L1.12)</td>
      <td>Run L1.5, L1.6, L1.7, L1.12 indicators (5–10 min)</td>
      <td>L1 indicators show pure accumulation (delete/add &lt;15% OR unreachable code &gt;5%)</td>
      <td>30m (uses L1)</td>
    </tr>
    <tr>
      <td>4.18</td>
      <td>UX from code</td>
      <td>DEV</td>
      <td>Lighthouse / Core Web Vitals pass; accessibility (WCAG 2.2); cognitive load &lt;7 elements per primary view</td>
      <td>Run Lighthouse on the main user-facing route</td>
      <td>Lighthouse score &lt;50, OR no accessibility attributes anywhere</td>
      <td>45m / N/A no UI</td>
    </tr>
  </tbody>
</table>

**How to use this table during an audit.**

1. **Before starting Day 2** of the audit walkthrough, scan this table to identify which dimensions have the fastest kill checks and run those first. This builds early confidence in the overall pattern (Structured / Mixed / Unstructured) before committing time to the slower per-dimension inspections.
2. **When the time budget is tight**, prioritize dimensions where the disqualifier is concrete and unambiguous (4.2 plain text passwords, 4.4 cross-tenant access, 4.7 hardcoded credentials, 4.10 zero pipelines, 4.17 pure accumulation). These produce defensible *Absent* scores in minutes.
3. **When a dimension scores at Not Healthy or Slop on Layer 1**, look up the corresponding Layer 2 dimensions in this table that are most likely to confirm the pattern (e.g., L1.10 zero pipelines → 4.10 CI/CD; L1.5 low delete ratio, L1.12 high unreachable code, or L1.17 god-file concentration → 4.17 tech debt management; L1.4 low doc lines → 4.15 live documentation; L1.14 secret scan hits → 4.7 configuration and secrets; L1.13 high fuzzy duplication → 4.14 architectural philosophy; L1.15 high type-escape density → 4.5 type safety and 4.12 dependency injection; L1.16 high trailing whitespace → the entire AI-supervision chain, since it indicates no human editor has touched the files).
4. **Disqualifier rows save time.** If the disqualifier is present, the dimension scores *Absent* without further inspection. Note the disqualifier evidence and move on. The full per-dimension entry in the catalog below explains *why* the disqualifier is sufficient; you do not need to re-derive that during the audit.
5. **The "Fastest kill check (5 min)" column is not a substitute for the full inspection procedure when the dimension is non-disqualifying.** A clean kill check tells you the dimension is *not Absent*; it does not tell you whether it is *Present* or *Partial*. For that, you need the full procedure.
6. **The *Not applicable* score.** Dimension 4.18 (UX from code) introduces a fourth score level, *Not applicable*, for systems with no user-facing interface. When a dimension scores *Not applicable*, it is removed from the denominator of the present/partial/absent counts in the executive summary; see Section 6.1 for the report treatment. The kill check for 4.18 is "is there a user-facing interface at all," which takes under a minute.

**Status of dimension entries below.** All 18 dimensions are drafted in the four-layer form. Each entry contains: header block (lifecycle, definition, industry threshold, source citations, compliance mappings), a Layer 2 mechanical inspection procedure, a Layer 3 qualitative-marker form (typically 4 or 5 markers with present/partial/absent scoring and an aggregation rule), a Layer 4 deferred-to-Phase-1 question list, a combined scoring rubric, common failure modes, two cross-language examples (Present and Absent in different languages), and a time budget. Section 4 is v0 — substantive review, tightening of marker wording, and calibration against the validation set (Section 7) are the next work items, not drafting.

---

