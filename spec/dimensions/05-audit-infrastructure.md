### 4.5 Audit infrastructure

**Lifecycle category.** Compliance engineering.

**Definition.** Audit infrastructure is the mechanism by which the application produces a tamper-evident, queryable record of *who* did *what* to *which resource*, *when*, and *with what outcome*. A mature audit infrastructure produces structured records (not free-form log lines), covers a defined set of auditable events (not arbitrary developer choices), protects sensitive fields from being captured in the audit log (not the log of last resort for personally identifiable information), and stores the records in a way that resists tampering by the application itself (not in a writable database table that can be rewritten by anyone with database access). The opposite is the application that prints "User logged in" to stdout and considers itself audited.

**Industry threshold.** Tamper-evident, timestamped, queryable records with sufficient who/what/when/where/outcome content to satisfy NIST SP 800-53 AU-2 (Audit Events), AU-3 (Content of Audit Records), and AU-10 (Non-Repudiation), and SOC 2 CC7.2. The threshold reflects what a financial services auditor will check: not whether logs exist, but whether the logs are structured, complete, sensitive-field-protected, and resistant to after-the-fact modification.

**Source citations (per the Wasserman 2026 working analysis, Appendix C).**
- AICPA SOC 2 Trust Services Criteria — Tier 1
- NIST SP 800-53 AU family controls (AU-2, AU-3, AU-6, AU-10) — Tier 1
- OWASP SAMM Benchmark Report (October 2025) — real-world maturity data on compliance practices and audit logging — Tier 1
- AWS AICPA SOC 2 Compliance Guide (July 2025) — Tier 4 (vendor)

**Compliance framework mappings.**
- **NIST SP 800-53:** AU-2 (Audit Events), AU-3 (Content of Audit Records), AU-10 (Non-Repudiation)
- **SOC 2 Trust Services Criteria:** CC7.2 (System Operations - monitoring)
- **OSFI B-13:** Section 4.6 (Cyber Security Incident Management)
- **NI 31-103:** Section 11.5 (Recordkeeping)
- **SEC Rule 17a-4:** Records of brokers and dealers (preservation requirements)

#### Layer 2 form (mechanical / artifact-based)

**Layer 2 inspection procedure.**

1. **Locate the audit logging mechanism.** Find where the application records auditable events. Look for a dedicated audit module, a structured logging library configured for audit (separate from application logs), or a database table used for audit records. If audit events are mixed into the same logger as debug and info messages with no separation, the Layer 2 form scores *Partial* at best.
2. **Inspect the structure of audit records.** A mature audit record has a defined schema: at minimum the timestamp, the actor (user ID), the action (verb), the resource (subject), the outcome (success/failure), and an event-specific payload. Free-form log strings ("user 5 did something at 10:00") fail this check.
3. **Count the audit entry points.** Use `grep` for the audit function or class across the codebase. A mature audit infrastructure has dozens to hundreds of entry points. A handful (or just a "user logged in" entry) indicates minimal compliance.
4. **Inspect the storage.** Determine where audit records are written. A mature pattern writes to an append-only store (write-once-read-many storage, immutable database, dedicated audit service) or to a database table protected by row-level security that prevents the application's own service account from updating or deleting rows. Audit records in a writable application database are *Partial* at best.
5. **Inspect the tamper evidence.** Determine whether audit records carry a hash, signature, or other mechanism that allows after-the-fact verification that the record has not been modified. NIST AU-10 (Non-Repudiation) requires this. Hash-chained records, per-record signatures, or external timestamping services all qualify; nothing at all is *Absent* on this aspect.

#### Layer 3 form (qualitative specified judgment)

**Layer 3 inspection procedure.** Four markers, each scored present / partial / absent.

**Marker 1: Audit records cover every state-changing operation, not just some.** Sample 10 state-changing operations across the codebase (create, update, delete on different entities, in different modules). For each one, verify that an audit record is produced. If 8 of 10 are instrumented and 2 are missing, the audit infrastructure is technically present but selectively applied — which is the most common failure mode at this dimension and the one that gets organizations into compliance trouble during real audits. Present = all 10 sampled operations produce audit records; partial = 7-9 do; absent = 6 or fewer.

**Marker 2: Sensitive field redaction happens at write time, not at read time.** Inspect the redaction logic. Write-time redaction is permanent: the sensitive value never reaches the audit store. Read-time redaction is bypassable: a query that reads the audit log without the redaction filter sees the sensitive values. Mature audit infrastructures redact at write time and define the redaction rules in a configuration file separate from the application code so they can be updated as the schema of sensitive data evolves. Present = write-time redaction with configurable rules; partial = write-time redaction with hardcoded rules; absent = read-time redaction or no redaction at all.

**Marker 3: The audit log schema is consistent across event types.** Inspect 5 different event types in the audit log. Verify that they all share a common base schema (timestamp, actor, action, resource, outcome) with optional event-specific fields layered on top, and that the optional fields are clearly distinguished from the required fields. An audit log where every event type has a different shape is impossible to query efficiently and impossible to validate. Present = consistent base schema with structured optional fields; partial = mostly consistent with one or two outliers; absent = each event type has its own ad-hoc shape.

**Marker 4: The audit log is queryable for compliance reporting in minutes, not hours.** Test or estimate a representative compliance query against the audit storage: "show me every action user X took in the last 90 days," "show me every modification to resource Y in the last 30 days," "show me every grant of admin privilege to any user in the last year." If the storage architecture supports these queries efficiently (indexed columns, queryable structured fields, dedicated query interface), the response time is in minutes. If the only query path is grep on log files or full-table scans of an unindexed audit table, the response time is in hours and the audit log is effectively unusable for compliance reporting. Present = queries return in minutes; partial = queries return in 30-60 minutes; absent = queries take hours or are impractical.

**Layer 3 scoring rule for the dimension.** Score Layer 3 *Present* if 3 or 4 markers score Present. *Partial* if 2 markers score Present. *Absent* if 0 or 1 markers score Present.

#### Layer 4 questions (deferred to Phase 1)

- Are the audit categories sufficient for the specific regulatory regime this organization operates under? (Different regulators expect different categories of events to be audited; an experienced compliance auditor knows what is missing.)
- Are there subtle integrity vulnerabilities in the tamper evidence mechanism that only a security architect would notice?
- Would the audit log survive scrutiny by a regulator who knows what they are looking for?

**Combined scoring rubric.**

- ***Present.*** Layer 2 form passes (dedicated audit mechanism, structured records, dozens of entry points, append-only storage, tamper evidence) AND Layer 3 form scores Present (3 or 4 of 4 markers).
- ***Partial.*** Layer 2 form passes but Layer 3 has gaps (2 markers Present); OR Layer 2 is Partial (some elements missing) but Layer 3 scores Present.
- ***Absent.*** Layer 2 form fails (no dedicated audit infrastructure, free-form log strings only, no tamper evidence, application logs and audit logs are the same stream, auditable events recorded as arbitrary print statements); OR Layer 2 form passes but Layer 3 scores Absent. The published natural experiment's unstructured condition exhibited "no structured audit logging" as one of its named failure modes.

**Common failure modes.**

- **Print statements as audit.** `print(f"user {user.id} created order {order.id}")` written to stdout, captured by container logging, and considered audited. The "log" is unstructured text; the "audit" is whatever the developer happened to type that day.
- **Audit table that the application can write and rewrite.** Audit records stored in a regular database table that the application's own service account can `UPDATE` or `DELETE`. An attacker who compromises the application can rewrite history, which defeats the purpose of an audit log.
- **Free-form audit messages.** Audit records exist as a single text field per event ("User 5 changed something on order 123 at 2026-04-07T10:23:00Z") with no structured schema. Querying these for compliance reporting requires regex parsing of the text, which is error-prone.
- **Sensitive data captured in audit.** The audit record includes the full request body, which contains the user's password during a password change, or the user's full credit card number during a payment update. The audit log becomes a parallel security failure surface.
- **Selective audit instrumentation.** Some operations are audited and others are not, with no consistent rule. The assessor finds an audited "create user" event but no corresponding "delete user" event, or vice versa.
- **Audit logs that disappear.** Logs are written to a container's local filesystem with no shipping to a durable store. When the container restarts, the audit history for that container is gone.
- **No actor identification.** Audit records show that "something happened" but cannot identify which user did it. Common in systems that treat the audit log as a debugging tool rather than as a compliance instrument.

**Example presence (Python / FastAPI).** A FastAPI application with a dedicated `audit/` module that exposes a single `record_event(actor, action, resource, outcome, metadata)` function. Every state-changing service method calls this function as a decorator (`@audit_event(action="invoice.create")`) or as an explicit call. The function writes to a dedicated `audit_events` table with a defined schema, computes a SHA-256 hash of the record body chained to the previous record's hash, and stores the hash as the row's primary key. A separate background worker copies new audit records to S3 in append-only mode. PII fields are redacted at write time via a `RedactionRules` configuration that covers email, phone, SSN, and payment card data. The codebase has 142 audit entry points across 18 service modules, covering every state-changing operation. Compliance reports are generated by querying the `audit_events` table directly with structured filters.

**Example absence (Java / servlet).** A Java servlet application that uses `log.info("User " + userId + " did something")` for what the developer calls "audit logging." The logs are written to the same `application.log` file as debug, error, and info messages from the rest of the application. There is no defined schema, no structured filtering, no sensitive-field redaction (the assessor finds `log.info("Login attempt: " + email + ":" + password)` in the authentication module, capturing plaintext passwords on every login). There is no tamper evidence because the logs are flat text files. The "audit query interface" is `grep` on the log files. The application has 11 logging statements that the developer considers audit-relevant, scattered across 47 service classes that perform state-changing operations.

**Time budget.** Approximately 90 to 105 minutes for an experienced assessor on a mid-size codebase: 30 to 45 minutes for the Layer 2 inspection, 60 minutes for the Layer 3 marker assessment.

---

