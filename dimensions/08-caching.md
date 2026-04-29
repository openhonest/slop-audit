### 4.8 Caching

**Lifecycle category.** Performance engineering.

**Definition.** Caching is the application's mechanism for storing the result of an expensive operation (a database query, a third-party API call, a computation) so that subsequent requests for the same result can be served from a fast store instead of repeating the work. A mature caching layer applies different time-to-live (TTL) values to different data types based on volatility, has a defined invalidation strategy for when the underlying data changes, includes the relevant security context (tenant, user, role) in the cache key to prevent cross-context leakage, and degrades gracefully when the cache is unavailable. The opposite is the cache that stores everything for an arbitrary duration with no invalidation, no security context in keys, and a hard dependency on the cache being available.

**Industry threshold.** Tiered TTLs per data type, defined invalidation triggers, security context (tenant, user, role) included in cache keys, graceful degradation when the cache is unavailable. Drawn from Redis benchmarks (sub-millisecond latency, enterprise targets 85-95% cache hit ratio), Microsoft Azure Cache for Redis Best Practices, AWS ElastiCache Metrics Documentation, and Cloudflare Edge Network Performance Benchmarks. Note: this dimension is *Not Applicable* if the application has no caching layer at all by design (some applications correctly do not need caching), but for any application with caching the standard applies.

**Source citations (per the Wasserman 2026 working analysis, Appendix C).**
- Redis Official Benchmarks — Tier 4 (vendor)
- Cloudflare Edge Network Performance Benchmarks — Tier 4 (vendor)
- Microsoft Azure Cache for Redis Best Practices — Tier 4 (vendor)
- AWS ElastiCache Metrics Documentation — Tier 4 (vendor)

**Compliance framework mappings.**
- **NIST SP 800-53:** SC-28 (Protection of Information at Rest) — applies to cached sensitive data
- **GDPR Article 32:** Security of processing — applies to cached personal data
- **SOC 2 Trust Services Criteria:** CC6.1 (Logical and Physical Access Controls) — applies to cache access boundaries

#### Layer 2 form (mechanical / artifact-based)

**Layer 2 inspection procedure.**

1. **Determine whether caching is in use.** Look for cache library imports (Redis client, Memcached client, in-memory cache decorators, HTTP cache headers, CDN configuration). If no caching is present, score *Not Applicable* and document why (some applications correctly do not need caching).
2. **Locate the cache key construction.** Find the function or pattern that generates cache keys. Inspect what goes into the key. The key must include the tenant identifier (for multi-tenant applications), the user identifier or role (for user-scoped data), and any other security context that determines what the cached data represents.
3. **Inspect the TTL configuration.** Determine whether different data types have different TTLs based on volatility, or whether a single global TTL is applied to everything.
4. **Inspect the invalidation strategy.** Determine how cached data is invalidated when the underlying data changes. Common patterns: TTL-only, explicit invalidation on write, event-driven invalidation, versioned keys.
5. **Inspect for sensitive data in cache.** Determine what data is being cached. Cached sensitive data (PII, credentials, payment information) requires the same protection as the underlying store.

#### Layer 3 form (qualitative specified judgment)

**Layer 3 inspection procedure.** Four markers, each scored present / partial / absent.

**Marker 1: TTL values match the volatility of the underlying data.** Inspect the TTL configurations. For each cached data type, ask whether the TTL is appropriate for how often the data actually changes. A 24-hour TTL on stock quotes is wrong (data is stale after seconds). A 5-second TTL on user profile data is wrong (data does not change that often, and the cache provides no benefit). The mature pattern uses tiered TTLs that match each data type's volatility: realtime data has short TTLs, stable data has long TTLs, semi-stable data has TTLs in between. Present = TTLs are tiered and match volatility; partial = TTLs are tiered but some are misconfigured; absent = single global TTL or TTLs that mismatch volatility.

**Marker 2: Invalidation strategy is event-driven or version-based for mutable data, not TTL-only.** TTL-only invalidation is acceptable for read-mostly data where staleness for the TTL window is tolerable. For data that changes frequently and where staleness causes correctness bugs, the mature pattern is event-driven invalidation (a message bus broadcasts changes) or versioned keys (the cache key includes a version number that increments on update). Inspect the write paths for cached data; verify that writes trigger invalidation. Present = mutable data has event-driven or versioned invalidation; partial = some mutable data has invalidation, some relies on TTL only; absent = TTL-only for all data including mutable data.

**Marker 3: Cache keys include security context (tenant, user, role) where applicable.** Sample 5 cache key construction sites for data that should be scoped (per-tenant, per-user, per-role). Verify each key includes the relevant scoping. Cross-tenant cache leakage and cross-user cache leakage are the most common subtle failures in this dimension and they overlap with dimension 4.4 (Multi-tenancy). Present = all 5 sampled keys include appropriate scoping; partial = 3 or 4 do; absent = 0, 1, or 2 do.

**Marker 4: The cache fails open with a circuit breaker, OR has documented failure handling.** Inspect what happens when the cache is unavailable. The mature pattern is fail open (serve from database) with a circuit breaker that prevents overwhelming the database under cache failure. Failing open without a circuit breaker is dangerous (a cache failure becomes a database overload). Failing closed (returning errors) is a single point of failure for the application. Present = fails open with a circuit breaker; partial = fails open without a circuit breaker; absent = fails closed (cache becomes single point of failure) or undefined behavior.

**Layer 3 scoring rule for the dimension.** Score Layer 3 *Present* if 3 or 4 markers score Present. *Partial* if 2 markers score Present. *Absent* if 0 or 1 markers score Present. **However, if Marker 3 (security context in cache keys) scores Absent, the entire dimension scores at most *Partial* regardless of the other markers, because cross-context leakage is a severe security failure.**

#### Layer 4 questions (deferred to Phase 1)

- Are the TTL values calibrated to the actual access patterns this application sees? (Generic TTLs may be too long or too short for the specific traffic patterns.)
- Are there subtle race conditions in the cache invalidation logic that only manifest under specific load patterns?
- Would the caching strategy survive a 10x traffic spike, or does it have hidden bottlenecks (like cache stampedes during popular-key expiration) that an experienced architect would notice?

**Combined scoring rubric.**

- ***Present.*** Layer 2 form passes (caching is in use, key construction is sound, TTL configuration exists, invalidation strategy exists, sensitive data handling is appropriate) AND Layer 3 form scores Present (3 or 4 of 4 markers).
- ***Partial.*** Layer 2 form passes but Layer 3 has gaps (2 markers Present); OR Layer 2 is Partial (caching exists but with significant gaps) but Layer 3 scores Present; OR Marker 3 of Layer 3 scores Absent (cross-context leakage).
- ***Absent.*** Layer 2 form fails (no caching despite clear need, OR cross-context leakage in cache keys, OR no invalidation strategy and stale data routinely returned); OR Layer 2 form passes but Layer 3 scores Absent.
- ***Not Applicable.*** The application correctly does not need caching. Document the reasoning.

**Common failure modes.**

- **Cache key omits tenant.** The cache key for a query that returns tenant-scoped data does not include the tenant identifier, so tenant A and tenant B share cached results. Cross-tenant data leakage via cache.
- **Cache key omits user.** Similar to above but for per-user data. User A sees user B's cached profile.
- **No invalidation on write.** The application writes to the database but does not clear the cache. Subsequent reads return the stale value until the TTL expires.
- **Single global TTL.** Every cached value has the same expiry regardless of volatility. Either real-time data is too stale or stable data is being recomputed pointlessly.
- **TTL of zero or "forever".** The cache stores values indefinitely, never refreshing. Common in caches added "to fix a slow query" without thought about the consequences.
- **Cache stampede.** When a popular cache key expires, every concurrent request for that key triggers a fresh database query. The "thundering herd" pattern. Mature caches use locking, pre-warming, or stale-while-revalidate to prevent this.
- **No fallback when cache is down.** The application errors out completely when Redis is unavailable, instead of falling back to direct database queries. Cache becomes a single point of failure.
- **Cache contains secrets.** The cache stores authentication tokens, password hashes, or other credentials, in a Redis instance with no access control because "it's just a cache."
- **Caching writes instead of reads.** The application caches the *write* of a value (returns success immediately, queues the write for later) without correctly handling the case where the queued write fails. Data loss disguised as performance.

**Example presence (TypeScript / Node.js).** A Node.js application using `ioredis` for caching against an AWS ElastiCache cluster. The cache layer is wrapped in a `CacheService` class that exposes `get<T>(key: TenantScopedKey<T>): Promise<T | null>` and `set<T>(key: TenantScopedKey<T>, value: T, ttl: TTLPolicy): Promise<void>`. The `TenantScopedKey` type is constructed via `tenantId:resourceType:resourceId:version` and the type system prevents construction of a key without a tenant ID. The `TTLPolicy` is one of seven named policies (`REALTIME_SECONDS`, `SHORT_MINUTES`, `MEDIUM_HOURS`, `LONG_HOURS`, `STABLE_DAYS`, `NEVER_EXPIRE_VERSIONED`, `EPHEMERAL_REQUEST`) selected by the calling code based on data volatility. Invalidation is event-driven: every database write publishes an event to a Redis pub/sub channel, and a subscriber clears matching cache keys. When the cache layer is unavailable, the `get` method returns `null` (cache miss) instead of throwing, and the application falls back to the database. A circuit breaker limits database load to prevent cache-failure-induced overload. Hit ratio is 91% in production.

**Example absence (C# / .NET).** A .NET application using `IMemoryCache` for caching. The cache is process-local (not distributed), which means three application instances behind a load balancer have three independent caches. Cache keys are constructed as `string.Format("user_{0}", userId)` for some queries and `"all_products"` for others; the `all_products` key returns the same cached list regardless of which tenant's user is requesting it, and the assessor confirms cross-tenant leakage by logging in as tenant A, observing the cached list, then logging in as tenant B and seeing the same list. There is no invalidation: when a product is updated, the cache continues returning the stale value for 1 hour (the global TTL applied to every cache key). When the cache is unavailable, the application errors out. There is no observability on cache hit ratio. The cache was added 14 months ago to "fix slow product queries" and has not been touched since.

**Time budget.** Approximately 75 to 90 minutes for an experienced assessor: 30 minutes for the Layer 2 inspection, 45 to 60 minutes for the Layer 3 marker assessment. Less if no caching is present.

---

