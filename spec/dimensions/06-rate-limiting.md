### 4.6 Rate limiting

**Lifecycle category.** Operational security.

**Definition.** Rate limiting is the application's mechanism for capping the number of requests a single client can make in a defined time window, both to prevent abuse (credential stuffing, scraping, denial-of-service) and to protect the application from accidental overload (a misbehaving client, a runaway script, a viral traffic spike). A mature rate limiter applies different limits to different endpoints based on the cost and sensitivity of the operation, returns standardized HTTP 429 responses with `Retry-After` headers, and tracks limits in a shared store so that multiple application instances enforce a unified limit per client. The opposite is the application that has no rate limit at all, or has a single global limit that is too high to prevent abuse and too low to allow legitimate use.

**Industry threshold.** Per-endpoint rate limits with sliding-window enforcement, distributed state for multi-instance deployments, standardized 429 responses with `Retry-After` headers, and stricter limits on authentication endpoints than on read endpoints. Drawn from OWASP API Security Top 10:2023 API4 (Unrestricted Resource Consumption), Cloudflare DDoS Threat Reports 2025 (47.1 million attacks in 2025, a 236% increase from 2023), and Akamai Aggregated Rate Limiting Research (November 2025).

**Source citations (per the Wasserman 2026 working analysis, Appendix C).**
- Cloudflare DDoS Threat Reports (2025) — 47.1M attacks, 236% increase — Tier 4 (vendor) but widely cited
- OWASP API Security Top 10:2023 API4 (Unrestricted Resource Consumption) — Tier 1
- Akamai Aggregated Rate Limiting Research (November 2025) — Tier 4 (vendor)
- Cloudflare WAF Rate Limiting Best Practices — Tier 4 (vendor)

**Compliance framework mappings.**
- **OWASP API Security Top 10:** API4 (Unrestricted Resource Consumption)
- **NIST SP 800-53:** SC-5 (Denial of Service Protection)
- **OSFI B-13:** Section 4.4 (Cyber Security)

#### Layer 2 form (mechanical / artifact-based)

**Layer 2 inspection procedure.**

1. **Locate the rate limiter.** Find the middleware, decorator, or filter that enforces request rate limits. Common locations: `middleware/rate_limit.py`, `RateLimitFilter.java`, `rate-limiter.ts`, or framework-specific (`@RateLimit` annotation, `flask-limiter` extension, `express-rate-limit`). If no rate limiter exists, the Layer 2 form scores *Absent* immediately.
2. **Inspect the algorithm.** Determine whether the rate limiter uses a sliding window, a fixed window, a token bucket, or a leaky bucket. Sliding window and token bucket are the mature patterns. Fixed window is acceptable but allows brief bursts at window boundaries that exceed the intended limit.
3. **Inspect the storage.** Determine whether the rate limiter tracks state in a shared store (Redis, Memcached, distributed cache) or in process memory only. Process memory only fails the Layer 2 form immediately for any deployment with more than one application instance.
4. **Inspect the per-endpoint configuration.** A mature rate limiter applies different limits to different endpoints. A single global limit is *Partial* at best for the Layer 2 form.
5. **Test empirically (the disqualifier check).** If a test environment is available, hammer an authentication endpoint with rapid requests (a 100-request loop is sufficient). The rate limiter should kick in within a small number of requests and return 429. If the limiter never kicks in within 100 requests, the dimension scores *Absent* without further inspection.

#### Layer 3 form (qualitative specified judgment)

**Layer 3 inspection procedure.** Four markers, each scored present / partial / absent.

**Marker 1: Rate limit is applied per identified client, not just per IP address.** Inspect the client identification logic. IP-only rate limiting is bypassed by NAT pooling (a single user behind a corporate NAT shares a limit with hundreds of colleagues, denying legitimate use), by IPv6 rotation, and by residential proxy networks (an attacker rotates through thousands of IPs and effectively has no limit). The mature pattern combines authenticated user identity (for logged-in requests), API key (for service-to-service requests), and IP (as a fallback for unauthenticated requests). Present = composite identification matching the request type; partial = primarily IP-based with some user-based supplements; absent = IP-only.

**Marker 2: Authentication endpoints have stricter limits than read endpoints.** Inspect the rate limit configuration. Verify that login, password reset, token refresh, and similar endpoints have substantially lower limits (a few per minute) than read-only endpoints (hundreds per minute). The asymmetry is the load-bearing defense against credential stuffing attacks. Present = clear differentiation with strict auth limits; partial = some differentiation but auth limits are too permissive (more than 20/min); absent = no differentiation, all endpoints share the same limit.

**Marker 3: The 429 response includes Retry-After in seconds and indicates the actual limit hit.** Inspect the rate limiter's response generation. Verify that exceeded-limit responses include the `Retry-After` header with a value in seconds, and ideally also include a structured response body that names which limit was hit and how long until the client can retry. Without `Retry-After`, well-behaved clients have to guess, which produces retry storms that worsen the underlying problem. Present = `Retry-After` header in seconds plus structured body; partial = `Retry-After` header but no body; absent = neither, or 200/503 instead of 429.

**Marker 4: The rate limiter fails closed when the backing store is unavailable, OR has a documented circuit breaker.** Inspect the rate limiter's behavior when the Redis (or equivalent) backing store is unreachable. Failing closed means rejecting all requests until the store recovers (slows down the application but maintains protection). Failing open means passing all requests through unchecked (preserves application availability but disables rate limiting entirely, allowing an attacker to disable the rate limiter by attacking the cache). The acceptable middle ground is a documented circuit breaker that fails open temporarily but with strict alerting and a documented recovery procedure. Present = fails closed, or has a documented circuit breaker; partial = fails open with no documentation; absent = fails open with no documentation and no alerting.

**Layer 3 scoring rule for the dimension.** Score Layer 3 *Present* if 3 or 4 markers score Present. *Partial* if 2 markers score Present. *Absent* if 0 or 1 markers score Present.

#### Layer 4 questions (deferred to Phase 1)

- Are the rate limit values calibrated to the actual abuse patterns this application faces? (Generic limits drawn from documentation may be too tight or too loose for the specific threat model.)
- Are there sophisticated bypass paths that an experienced security engineer would notice? (For example, slow-and-low credential stuffing that stays below the per-IP limit but still produces meaningful breach probability over weeks.)
- Would the rate limiting survive a coordinated attack from a botnet with thousands of source IPs?

**Combined scoring rubric.**

- ***Present.*** Layer 2 form passes (rate limiter exists, sliding-window or token-bucket algorithm, distributed state, per-endpoint configuration, empirical test confirms the limiter triggers) AND Layer 3 form scores Present (3 or 4 of 4 markers).
- ***Partial.*** Layer 2 form passes but Layer 3 has gaps (2 markers Present); OR Layer 2 is Partial (process-local state, single global limit, wrong status code) but Layer 3 scores Present.
- ***Absent.*** Layer 2 form fails (no rate limiter, OR empirical test fails to trigger within 100 requests); OR Layer 2 form passes but Layer 3 scores Absent.

**Common failure modes.**

- **No rate limiting at all.** The application accepts unlimited requests from any client. Common in early-stage codebases that haven't yet been targeted by abuse and therefore haven't felt the need.
- **Single global limit.** A single rate limit applied to every endpoint regardless of cost or sensitivity. The login endpoint has the same limit as the homepage, which means either the homepage is too restricted or the login endpoint is too exposed.
- **Process-local state in a multi-instance deployment.** The rate limiter tracks request counts in memory inside each application process. Three application instances behind a load balancer means the effective limit is three times the configured limit per client.
- **IP-only client identification.** The rate limiter identifies clients by IP address, which means a single user behind a corporate NAT shares a limit with hundreds of colleagues, while an attacker rotating through residential proxies effectively has no limit.
- **Wrong status code.** The application returns 200 OK with an error body, or returns 503 Service Unavailable, instead of the standard 429 Too Many Requests. Clients that handle 429 correctly cannot recover gracefully.
- **No `Retry-After` header.** The application returns 429 but does not tell the client when to retry. Clients have to guess, which often produces retry storms.
- **Authentication endpoints with no special protection.** The login endpoint has the same rate limit as the homepage, which means credential stuffing attacks proceed at the speed of the general rate limit (often hundreds per minute), allowing thousands of attempts per hour against any user account.
- **Rate limiter that fails open.** When the Redis backend used by the rate limiter is unavailable, the limiter passes all requests through unchecked instead of failing closed. An attacker can disable the rate limiter by attacking the cache.

**Example presence (Go / gin).** A Go web application built with the `gin` framework and a custom `rate-limit` middleware backed by Redis. The middleware reads a YAML configuration file at startup that defines limits per route group: `/api/auth/*` is limited to 5 requests per 5 minutes per client, `/api/auth/refresh` is limited to 10 requests per 60 seconds, `/api/data/*` is limited to 300 requests per 60 seconds, and `/api/admin/*` is limited to 30 requests per 60 seconds. The algorithm is sliding window using Redis sorted sets with millisecond timestamps. Client identification is composite: authenticated user ID if a JWT is present, API key if present, falling back to IP address. Exceeding a limit returns HTTP 429 with `Retry-After: <seconds>` and a JSON body explaining the limit. When Redis is unavailable, the middleware fails closed (rejects all requests) and emits a critical alert to the observability layer.

**Example absence (TypeScript / Express).** An Express.js application with no rate limiting middleware installed. The login endpoint accepts unlimited requests from any IP. The assessor confirms by writing a 10-line script that submits 1,000 login attempts in 30 seconds; all 1,000 are processed by the application and returned with `{"error": "invalid credentials"}`. There is no rate limiter configuration anywhere in the codebase. The `package.json` has no rate-limiting dependency. A `// TODO: add rate limiting before launch` comment dated 22 months ago sits in `routes/auth.ts`. The application has been in production for 18 months with no rate limiting in place.

**Time budget.** Approximately 75 minutes for an experienced assessor: 30 minutes for the Layer 2 inspection (the empirical test takes 5 minutes and can short-circuit the entire dimension), 45 minutes for the Layer 3 marker assessment.

---

