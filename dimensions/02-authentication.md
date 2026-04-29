### 4.2 Authentication

**Lifecycle category.** Security architecture.

**Definition.** Authentication is the mechanism by which the application establishes the identity of a user or service, and binds that identity to subsequent requests in a way that resists tampering, replay, and theft. A mature authentication system uses multiple verification factors, binds session credentials to the underlying identity, expires credentials predictably, stores secrets correctly, and survives the loss of any single credential without compromising the user's account.

**Industry threshold.** Authentication Assurance Level 2 (AAL2) per NIST SP 800-63B-4, with session token binding and secure expiry. AAL2 requires multi-factor authentication using at least one phishing-resistant factor. OWASP ASVS 5.0 specifies approximately 350 verification requirements mapped to NIST AALs. The Verizon 2025 Data Breach Investigations Report (22,052 incidents, 12,195 breaches) found that credential abuse accounted for 22% of attack vectors and 88% of web application attacks used stolen credentials, which is what the AAL2 requirement is designed to prevent.

**Source citations (per the Wasserman 2026 working analysis, Appendix C).**
- NIST SP 800-63B-4 (August 2025) — Tier 1
- OWASP ASVS 5.0 (May 2025) — Tier 1
- Verizon DBIR 2025, 22,052 incidents, 12,195 breaches — Tier 1
- OWASP SAMM Benchmark Report (October 2025) — Tier 1
- OWASP Top 10:2025 A07 Authentication Failures — Tier 1

**Compliance framework mappings.**
- **NIST SP 800-63B-4:** Authentication Assurance Levels (AAL1, AAL2, AAL3)
- **SOC 2 Trust Services Criteria:** CC6.1 (Logical and Physical Access Controls)
- **OSFI B-13:** Section 4.3 (Identity and Access Management)
- **SEC Regulation S-P:** Safeguards Rule
- **FINRA Rule 3110:** Supervision

#### Layer 2 form (mechanical / artifact-based)

**Layer 2 inspection procedure.**

1. **Locate the password storage.** Find where user passwords are stored. Inspect the column type, the hashing function, and whether a salt is applied. Plain text storage (passwords in a `password` column readable as the original string) is the single most disqualifying finding in this dimension; it is a guaranteed audit failure regardless of any other authentication property. If found, the Layer 2 form scores *Absent* and the dimension as a whole scores *Absent* without requiring the Layer 3 assessment.
2. **Locate the authentication endpoint.** Find the route or function that exchanges credentials for a session token or equivalent. Inspect what factors it requires. Single-factor (password only) is AAL1 at best. Multi-factor (password plus a second factor such as TOTP, push notification, hardware key, or platform authenticator) is required for AAL2.
3. **Inspect session token issuance.** Determine what kind of credential is issued after successful authentication: a session cookie, a JWT, an OAuth token, an API key. Inspect the token's expiry, its storage on the client (HTTP-only secure cookie versus localStorage), and whether the server can revoke the token before its natural expiry.
4. **Inspect for credential storage in the codebase.** Search for hardcoded API keys, passwords, or tokens in the source code. Check `.env` files, configuration files, and the git history. Hardcoded credentials in the codebase are a parallel disqualifying finding for the Layer 2 form.

#### Layer 3 form (qualitative specified judgment)

**Layer 3 inspection procedure.** Four markers, each scored present / partial / absent.

**Marker 1: Authentication flow handles edge cases without information leakage.** A trained assessor reads the authentication flow code paths for edge cases (expired sessions, concurrent logins from different devices, password reset, account recovery, locked accounts). The marker checks whether error messages and timing differences leak security-relevant information. "Invalid email or password" is correct (does not reveal whether the email exists); "User not found" is incorrect (reveals which emails are registered, enabling account enumeration). Score: present if all sampled error paths are non-leaking, partial if 1–2 leak information, absent if multiple leaks are visible.

**Marker 2: Session management is consistent across client types.** Determine whether the application's web browser, mobile app, and API client paths use consistent session handling. Common failure: web sessions expire after 4 hours, mobile sessions never expire, API tokens are valid for a year. The differential security postures create gaps that attackers exploit. Present = consistent treatment across all client types; partial = minor differences with documented reasoning; absent = significant differences with no documented reasoning.

**Marker 3: Password reset and account recovery do not introduce authentication bypasses.** Read the password reset and account recovery flows. Check whether the recovery mechanism itself can be exploited to log in as another user. Common failures: a recovery link that does not invalidate after use; a recovery flow that does not require possession of the original email address; a recovery flow that uses guessable security questions as the only second factor. Present = recovery flows are as secure as the primary authentication; partial = recovery flows are secure but inconsistent with primary auth; absent = recovery flows are demonstrably weaker than primary auth.

**Marker 4: Authentication fails closed under failure conditions.** Determine what happens when the authentication service is unavailable, when the session store is unreachable, or when the validation logic encounters an unexpected token format. Mature authentication systems fail closed (reject the request, return 401 or 503). Insecure ones fail open (allow the request through with fallback logic that bypasses the failed component). Sample 2–3 failure paths and check the behavior. Present = fails closed in all sampled paths; partial = fails closed in most paths; absent = fails open in any sampled path.

**Layer 3 scoring rule for the dimension.** Score Layer 3 *Present* if 3 or 4 markers score Present. *Partial* if 2 markers score Present. *Absent* if 0 or 1 markers score Present, or if Marker 4 (fails closed) scores Absent (failing open is severe enough to reduce the dimension regardless of other markers).

#### Layer 4 questions (deferred to Phase 1)

- Is the authentication architecture appropriate for this application's threat model? (Requires understanding the actual threats this specific application faces, not just generic best practices.)
- Are there subtle race conditions in the session management that only manifest under high concurrency?
- Would the authentication system survive a sophisticated adversary with knowledge of the implementation?

**Combined scoring rubric.**

- ***Present.*** Layer 2 form passes (passwords hashed, multi-factor required, server-revocable tokens, no hardcoded credentials) AND Layer 3 form scores Present (3 or 4 of 4 markers, with Marker 4 scoring Present).
- ***Partial.*** Layer 2 form passes but Layer 3 has gaps (2 markers Present); OR Layer 2 is Partial (single-factor only, missing replay protection, etc.) but Layer 3 scores Present.
- ***Absent.*** Layer 2 form fails immediately (plain text passwords, hardcoded credentials, no authentication at all, never-expiring tokens); OR Marker 4 (fails closed) scores Absent at Layer 3; OR Layer 2 form passes but Layer 3 scores Absent.

**Common failure modes.**

- **Plain text password storage.** The most disqualifying finding. Any column containing a string that is the user's actual password fails this dimension immediately. Look for column names like `password`, `pass`, `pwd` and inspect the actual data type and contents.
- **Hardcoded API keys.** API keys, database passwords, or service credentials checked into the source code. Common in `config.py`, `settings.py`, `.env.example` (sometimes containing real credentials by mistake), and especially in old git history that survived a rotation but was never purged.
- **Single-factor authentication.** Password only, with no second factor offered or required. This is AAL1 and fails AAL2.
- **Indefinite session tokens.** Tokens that work forever after issuance, with no expiry mechanism. Common in JWT implementations that omit the `exp` claim.
- **localStorage token storage.** Session tokens stored in browser localStorage rather than HTTP-only cookies, which makes them readable by any JavaScript on the page (including injected XSS payloads).
- **Authentication bypass via header injection.** A development convenience header (`X-Skip-Auth`, `X-Debug-User`) that disables authentication entirely, accidentally left enabled in production builds.
- **Predictable session token format.** Session tokens that are sequential integers, timestamps, or otherwise guessable. Modern implementations use cryptographically random tokens.
- **No password rotation enforcement** for service accounts that have long-lived static credentials.

**Example presence (TypeScript / Node.js).** A Node.js application where users authenticate with email and password, the password is hashed with argon2 (`@node-rs/argon2`) and verified server-side, the second factor is a TOTP code from an authenticator app validated by `otplib`. A successful login issues a JWT signed with a server-side secret with a 4-hour expiry, stored in an HTTP-only secure cookie. Every subsequent API request also carries an `X-Signature` header containing an HMAC-SHA256 signature derived from the request method, path, body, and an `X-Timestamp` header. The server validates the signature and rejects requests where the timestamp is more than 60 seconds old. A captured session cookie is insufficient for an attacker because they would also need the request-signing key. All secrets are loaded from a secrets manager at boot; nothing appears in source code or git history.

**Example absence (Python / Flask).** A Flask application where users authenticate with email and password, the password is stored in a `users.password` column as the original string (confirmed by inspecting the database directly), there is no second factor, and a successful login sets `session['user_id']` in a Flask cookie with no expiry that grants full access until the user clears their browser. The application's `config.py` contains a hardcoded `STRIPE_API_KEY = "sk_live_..."` and `DATABASE_PASSWORD = "..."` checked into git. The session cookie is readable by client-side JavaScript because the `SESSION_COOKIE_HTTPONLY` flag is unset. The codebase fails enterprise audit on multiple counts simultaneously, any one of which is sufficient for disqualification.

**Time budget.** Approximately 75 to 105 minutes for an experienced assessor: 30 to 45 minutes for the Layer 2 inspection (the plain-text-password check takes 5 minutes and can short-circuit the entire dimension), 45 to 60 minutes for the Layer 3 marker assessment.

---

