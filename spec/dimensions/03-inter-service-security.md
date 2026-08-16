### 4.3 Inter-service security

**Lifecycle category.** Security architecture.

**Definition.** Inter-service security is the mechanism by which services within an application architecture verify each other's identity and validate the integrity of calls between them. In a microservices or multi-service architecture, every internal call between services is an opportunity for unauthorized access, replay attacks, lateral movement, or man-in-the-middle interception. A mature inter-service security model treats internal calls with the same rigor as external calls: cryptographic verification of the calling service, replay protection, and per-service credential isolation. The opposite is the assumption that internal services trust each other implicitly because they sit inside the same network perimeter.

**Industry threshold.** Cryptographic verification of inter-service calls with replay protection, per the CISA Zero Trust Maturity Model v2.0 "Advanced" tier. The CISA model defines four maturity levels (Traditional, Initial, Advanced, Optimal) across five pillars, and Advanced requires signed, timestamped, replay-protected communication between services. The CNCF Annual Survey 2024 found that 79% of service mesh users rely on mTLS for inter-service trust, and 83% cite automatic mTLS as critical for zero-trust implementation. The threshold reflects a clear industry consensus: services should not trust each other based on network position alone.

**Source citations (per the Wasserman 2026 working analysis, Appendix C).**
- CISA Zero Trust Maturity Model v2.0 — Tier 1
- CNCF Annual Survey 2024 (April 2025), service mesh adoption 42%, mTLS 79% — Tier 1
- Forrester Wave: Zero Trust Platforms Q3 2025 — Tier 2 (Forrester invented the Zero Trust concept)
- arXiv 2024: "Performance Comparison of Service Mesh Frameworks: the mTLS Test Case" — Tier 3
- Research and Markets: Service Mesh Market 2026-2031 — Tier 2

**Compliance framework mappings.**
- **CISA Zero Trust Maturity Model v2.0:** Identity and cross-service trust pillars, Advanced tier
- **NIST SP 800-53:** SC-8 (Transmission Confidentiality and Integrity), SC-23 (Session Authenticity)
- **OSFI B-13:** Section 4.4 (Cyber Security)

#### Layer 2 form (mechanical / artifact-based)

**Layer 2 inspection procedure.**

1. **Identify the services.** Look for service boundaries in the codebase. Common signals: separate Docker images, separate `services/` directories, separate deployment manifests, separate ports in `docker-compose.yml`, distinct API client modules. If the application is a monolith with no internal service boundaries, this dimension scores either *Not Applicable* (if the architecture is genuinely single-service by design) or *Absent* (if the architecture should have services but doesn't).
2. **Locate the inter-service call sites.** Find the points where one service calls another. Common patterns: HTTP client modules named after the called service (`iam_client.py`, `billing_client.py`), gRPC stubs, message queue producers and consumers, RPC frameworks.
3. **Inspect the call signing.** Determine whether each inter-service call carries a cryptographic signature derived from the request content and a service-specific key. Look for HMAC signing functions, mTLS client certificates, signed JWT bearer tokens, or service mesh sidecar configuration. Calls that go out as plain HTTP with no signature score the Layer 2 form *Absent* on this aspect regardless of any network-level controls.
4. **Inspect the credential storage.** Determine whether each calling service uses a distinct credential or whether all services share a single static API key. Per-service credential isolation is the mature pattern; shared credentials are an accumulation of risk because a compromise of any one service gives the attacker the credential for all of them.

#### Layer 3 form (qualitative specified judgment)

**Layer 3 inspection procedure.** Four markers, each scored present / partial / absent.

**Marker 1: Signing is applied consistently to ALL inter-service calls, not just some.** Sample 5 distinct inter-service call sites from different parts of the codebase. Verify that each one applies the signing logic. The most common failure is the "almost-uniform" application: 80% of inter-service calls are signed correctly, but 20% bypass the signing layer because they were added before the signing was introduced or because a developer wrote a one-off helper that did not go through the standard client. The exceptions are where the bugs hide. Present = all 5 sampled call sites apply the signing; partial = 3 or 4 do; absent = 0, 1, or 2 do.

**Marker 2: The signature includes enough request content to make replay attacks detectable.** Inspect the signing function to determine what is included in the signature input. Just signing the URL and method is insufficient (the same URL+method can carry different bodies). Just signing the URL+method+timestamp is better but still incomplete. The mature pattern signs URL+method+body+timestamp+nonce. Present = signature input includes body and timestamp at minimum; partial = signature input includes timestamp but not body, or vice versa; absent = signature input is just URL+method.

**Marker 3: Timestamp validation rejects stale requests with appropriate clock-skew tolerance.** Inspect the receiving-side validation logic. Determine the tolerance window for clock skew between services. Mature systems allow a small window (30-60 seconds) and reject anything outside it. Common failures: no tolerance window at all (rejects requests that arrive even seconds late, breaking under normal network latency); excessive tolerance (10+ minutes, which makes replay protection meaningless); no validation at all even though the timestamp is in the signature input. Present = appropriate window with rejection enforced; partial = window exists but is too wide or too narrow; absent = no validation despite timestamp being in the signature.

**Marker 4: Credentials are rotated on a defined schedule and rotation is documented.** Determine whether inter-service credentials have a documented rotation schedule and a documented rotation procedure that does not require service downtime. Look for: a rotation schedule in operations runbooks, evidence in commit history of past rotations, automation that handles rotation, secret manager integration that supports rotation. Present = documented schedule, automated or near-automated process, evidence of past rotations; partial = manual rotation process documented but without an active schedule; absent = no rotation has ever happened, or the credentials cannot be rotated without coordinated deployment.

**Layer 3 scoring rule for the dimension.** Score Layer 3 *Present* if 3 or 4 markers score Present. *Partial* if 2 markers score Present. *Absent* if 0 or 1 markers score Present.

#### Layer 4 questions (deferred to Phase 1)

- Is the inter-service trust model the right model for this organization's deployment topology? (Service mesh with mTLS may be overkill for a 3-service system; a custom signing approach may be insufficient for a 30-service system.)
- Are there subtle protocol vulnerabilities in the specific signing implementation that only an experienced security architect would notice?
- Would the inter-service security model survive a determined attacker who has compromised one service and is trying to pivot laterally?

**Combined scoring rubric.**

- ***Present.*** Layer 2 form passes (cryptographic signing on all calls, per-service credentials) AND Layer 3 form scores Present (3 or 4 of 4 markers).
- ***Partial.*** Layer 2 form passes but Layer 3 has gaps (2 markers Present); OR Layer 2 is Partial (TLS but no application-layer signing, shared keys, partial coverage) but Layer 3 scores Present.
- ***Absent.*** Layer 2 form fails (plain HTTP, no signing, shared static API keys); OR Layer 2 form passes but Layer 3 scores Absent.

**Common failure modes.**

- **The "internal network is trusted" assumption.** Services authenticate external users but trust each other implicitly because they're behind a firewall. The Forrester Zero Trust thesis explicitly rejects this pattern; CISA Zero Trust v2.0 documents it as the "Traditional" tier that the Maturity Model is designed to move organizations away from.
- **Shared API key for all internal services.** A single `INTERNAL_API_KEY` environment variable used by every service to call every other service. A compromise of any one service exposes the key to all of them.
- **TLS without authentication.** Services use HTTPS to encrypt traffic but do not verify the calling service's identity. The encryption is correct; the authentication is missing.
- **No replay protection.** Inter-service calls are signed but the signature does not include a timestamp, so a captured call can be replayed indefinitely.
- **Long-lived service tokens with no rotation path.** The architecture supports inter-service authentication but the credential is hardcoded in the deployment configuration and rotating it requires a coordinated multi-service deploy. In practice, this means rotation never happens.
- **Service mesh sidecar configured but not enforced.** Istio, Linkerd, or another service mesh is deployed, but the mesh is in observation-only mode and does not actually require mTLS between services.
- **Inter-service credentials in source code.** API keys for internal service calls hardcoded in client modules, often committed and rotated repeatedly through the git history without ever being properly purged.

**Example presence (Java / Spring Boot).** A Spring Boot multi-service application where the public-facing API service calls an identity service, a billing service, and a notification service. Each outbound call goes through a `SignedHttpClient` wrapper that derives an HMAC-SHA256 signature from the HTTP method, path, body, and a millisecond timestamp, then attaches `X-Signature` and `X-Timestamp` headers. Each receiving service has a `@SignatureValidationFilter` that recomputes the signature using a service-specific key from Spring Cloud Config / HashiCorp Vault, rejects requests where the timestamp is more than 60 seconds old, and rejects requests where the signature does not match. Keys are rotated quarterly via the Vault secrets engine without service redeployment. A captured inter-service call cannot be replayed and cannot be made by any service that does not possess the specific calling key.

**Example absence (Python / Django).** A Django multi-service application where the public-facing API service calls the identity service via `requests.post(IDENTITY_URL, headers={"X-API-Key": INTERNAL_API_KEY})` over plain HTTP. The `INTERNAL_API_KEY` is the same string in every service's `settings.py`, loaded from `os.environ["INTERNAL_API_KEY"]`, and the same string also appears in the deployment YAML for every service. The receiving identity service has a middleware that checks `request.META.get("HTTP_X_API_KEY") == settings.INTERNAL_API_KEY` and processes the request if it matches. There is no signature, no timestamp, no replay protection, no per-service isolation. Anyone with access to any service's environment configuration can make calls as any other service. The codebase contains a `# TODO: replace with proper inter-service auth (see ticket INFRA-247)` comment dated 18 months ago.

**Time budget.** Approximately 75 minutes for an experienced assessor on a multi-service codebase: 30 minutes for the Layer 2 inspection, 45 minutes for the Layer 3 marker assessment. Approximately 15 minutes for a monolith (just to confirm the architecture is single-service by design).

---

