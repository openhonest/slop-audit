### 4.1 Entitlement system

**Lifecycle category.** Security architecture.

**Definition.** An entitlement system enforces *who* can access *what* in the application, at the level of individual endpoints, resources, or operations. It is the mechanism by which the application converts an authenticated identity into a set of permitted actions. A mature entitlement system supports per-endpoint authorization, role and attribute-based access decisions, deny-by-default behavior, and an audit trail of access decisions. The opposite of an entitlement system is a single coarse "is the user logged in?" check used to gate the entire application, with all users who pass that check having identical access to everything inside.

**Industry threshold.** Per-endpoint authorization with deny-by-default, role-based or attribute-based access decisions, and access logging on both grants and denials. Drawn from Gartner Access Management Magic Quadrant (November 2025), KuppingerCole Leadership Compass for Identity Governance and Administration (2024), and the GigaOm Radar for Cloud Infrastructure Entitlement Management (2026, evaluating 22 vendors). Cloud Infrastructure Entitlement Management is itself a $1.68B market growing at 37.1% CAGR (Grand View Research), reflecting how seriously enterprises treat this dimension.

**Source citations (per the Wasserman 2026 working analysis, Appendix C).**
- Gartner Magic Quadrant for Access Management (November 2025) — Tier 2
- KuppingerCole Leadership Compass for IGA (2024), 20+ vendors — Tier 2
- GigaOm Radar for CIEM (2026), 22 vendors — Tier 2
- Grand View Research CIEM Market Report — Tier 2

**Compliance framework mappings.**
- **SOC 2 Trust Services Criteria:** CC6.1 (Logical and Physical Access Controls), CC6.3 (Authorization)
- **NIST SP 800-53:** AC-2 (Account Management), AC-3 (Access Enforcement), AC-6 (Least Privilege)
- **OSFI B-13:** Section 4.3 (Identity and Access Management)
- **NI 31-103:** Section 11.1 (Compliance and Supervision)

#### Layer 2 form (mechanical / artifact-based)

**Layer 2 inspection procedure.**

1. **Locate the authorization layer.** Look for a middleware, decorator, route guard, or interceptor pattern that runs before each endpoint handler. Common locations: `middleware/`, `decorators/`, `auth/`, `guards/`, route definition files. If no such layer exists, the Layer 2 form scores *Absent*.
2. **Count the enforcement points.** A trained assessor uses `grep` or equivalent to count the number of distinct authorization decoration sites or middleware applications across the codebase. A mature entitlement system typically has at least one enforcement point per endpoint group, often dozens across a mid-size application.
3. **Inspect the default behavior.** Read the authorization layer to determine what happens when no explicit rule matches. Deny-by-default returns 403 or equivalent; allow-by-default lets the request through. If the default is allow-by-default, the Layer 2 form scores at most *Partial* regardless of how sophisticated the explicit rules are.
4. **Inspect the data model.** Look for role tables, permission tables, subscription/tier tables, or attribute schemas that drive the authorization decisions. A hardcoded list of admin user IDs is a sign of an immature system; a structured permission model is the mature pattern.

#### Layer 3 form (qualitative specified judgment)

**Layer 3 inspection procedure.** Four markers, each scored present / partial / absent.

**Marker 1: Granularity matches the actual access pattern.** Determine whether the authorization decisions match the actual access pattern of the application. Specifically: are decisions made at the endpoint level (one rule per route), the operation level (separate rules for read vs write on the same resource), or the resource-instance level (rules that depend on which specific record is being accessed)? The right granularity depends on the application: a public read-mostly site needs less granularity than a multi-tenant SaaS with per-record ownership. Score: present if the granularity matches the access pattern, partial if it is too coarse for the application's needs, absent if there is no granularity at all (one global "is logged in" check).

**Marker 2: The permission model is comprehensible to a developer reading it cold.** A trained assessor reads the permission model definitions (the role tables, permission tables, attribute schemas) and asks whether a new developer joining the team could understand the permissions without help. Named roles and permissions with clear documentation = present. Opaque integer flags or magic strings with no documentation = partial. No permission model at all (just hardcoded checks scattered through code) = absent.

**Marker 3: Access decisions log the reason, not just the fact.** Determine whether the access log records *why* a decision was made, not just *that* it was made. A deny log entry should record which permission was missing, which subscription tier was required, or which role was insufficient — not just "access denied." Without the reason, the log is useless for debugging access issues and for compliance reporting on the user experience. Present = reasons logged; partial = some decisions log reasons, others do not; absent = no reasons logged.

**Marker 4: The authorization layer is the SAME layer for all endpoints.** A common failure is the "almost-uniform" authorization layer: most endpoints go through the standard middleware, but a few are wired up differently (perhaps because they were added before the middleware existed, or because a developer wanted to bypass the middleware for "good reasons"). The exceptions are where the bugs hide. Present = every protected endpoint goes through the same authorization layer; partial = most do, with one or two exceptions; absent = inconsistent application throughout.

**Layer 3 scoring rule for the dimension.** Score Layer 3 *Present* if 3 or 4 markers score Present. *Partial* if 2 markers score Present. *Absent* if 0 or 1 markers score Present.

#### Layer 4 questions (deferred to Phase 1)

- Is the permission model the *right* permission model for this organization's domain? (Requires knowing the domain and seeing how the permissions interact with the actual business workflow.)
- Are there subtle authorization bugs where the granularity is technically correct but the boundaries are drawn in the wrong places? (For example, ownership checks that happen on the wrong field, or role hierarchies that grant unintended permissions through inheritance.)
- Would the permission model survive a regulatory audit by an experienced compliance auditor in this specific industry?

**Combined scoring rubric.**

- ***Present.*** Layer 2 form passes (dedicated authorization layer, multiple enforcement points, deny-by-default, structured data model) AND Layer 3 form scores Present (3 or 4 of 4 markers).
- ***Partial.*** Layer 2 form passes but Layer 3 has gaps (2 markers Present); OR Layer 2 is Partial (allow-by-default, missing audit trail, partial coverage) but Layer 3 scores Present.
- ***Absent.*** Layer 2 form fails (no authorization layer beyond "is logged in"); OR Layer 2 form passes but Layer 3 scores Absent (0 or 1 markers Present).

**Common failure modes.**

- The hardcoded admin list. A literal Python list, JSON file, or database row containing user IDs that get treated as admins, with no extension mechanism for additional roles.
- The "logged in equals authorized" pattern. The application has authentication (login/logout) but no authorization beyond it. Once a user is authenticated, every endpoint is accessible.
- The scattered if-check pattern. Authorization decisions are made inside individual route handlers as ad-hoc if-statements, with no consistent structure, no central place to inspect, and no way to change a permission without editing business logic.
- The orphaned admin endpoint. An endpoint exists in the codebase that an authenticated non-admin user can access but should not be able to, because the developer forgot to add the authorization check. Common in codebases that rely on per-handler if-statements.
- The "privacy by URL" pattern. Resources are protected by being served at unguessable URLs rather than by access control. Common in codebases that grew from unauthenticated prototypes.
- Allow-by-default in the authorization middleware. The middleware exists but lets requests through when no explicit rule matches, which means any new endpoint is unprotected until someone remembers to add a rule.
- No audit trail. Access decisions happen but are not logged, so the application cannot answer the question "who accessed what?" during a post-incident investigation or an audit.

**Example presence (Python / FastAPI).** A FastAPI application using a `requires_subscription("product_a")` decorator on each protected route, backed by a structured `subscriptions` table in the database, with the decorator logging both grants and denials to a dedicated audit table. The decorator returns 403 when the subscription is missing, returns 401 when the user is not authenticated, and is applied to every route in the protected application module as a uniform policy. The decorator implementation is approximately 30 lines of pure-function validation logic with no business-logic coupling. Adding a new subscription tier is a database row plus a one-line update to the permission table; no business logic changes.

**Example absence (TypeScript / Express).** An Express.js application where `app.use((req, res, next) => { if (!req.session.userId) return res.status(401).end(); next(); })` is the only authorization check. Every route mounted after that middleware is accessible to every authenticated user. There is no role table, no permission table, no subscription model. The codebase contains nine hardcoded checks of the form `if (req.session.email === 'admin@example.com')` scattered across four route files, which are the only differentiation between admin and regular users. A `// TODO: real authz` comment dated 14 months ago sits at the top of `routes/admin.ts`.

**Time budget.** Approximately 75 to 105 minutes for an experienced assessor on a mid-size codebase: 30 to 45 minutes for the Layer 2 inspection, 45 to 60 minutes for the Layer 3 marker assessment. Less if the dimension is clearly absent (15 minutes is sufficient to confirm absence at the Layer 2 level alone).

---

