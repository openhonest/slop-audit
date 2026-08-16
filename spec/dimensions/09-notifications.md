### 4.9 Notifications

**Lifecycle category.** Operations.

**Definition.** Notifications are the application's mechanism for communicating events to users (or to other systems) outside of the immediate request/response cycle: emails, SMS messages, push notifications, in-app alerts, server-sent events, webhooks. A mature notification system delivers notifications asynchronously (the originating request returns before the notification is sent), retries failed deliveries with appropriate backoff, has a dead-letter queue for permanently failed notifications, isolates notification failures from the originating request (the request succeeds even if the notification fails), and provides delivery confirmation where the channel supports it. The opposite is the synchronous notification: the application calls the email service inline during a user request, blocks the response until the email is sent, and crashes the request if the email service is unavailable.

**Industry threshold.** Asynchronous delivery via a queue or message bus, retry with exponential backoff, dead-letter queue for permanent failures, isolation between notification failures and originating request failures, observability on delivery rates. Drawn from Gartner Maturity Model for Event-Driven Architecture, Gartner Hype Cycle for Enterprise Architecture 2025, and SSE/WebSocket benchmarks. Note: this dimension is *Not Applicable* for applications that genuinely do not produce notifications of any kind, but it applies to any application that sends emails, SMS, push messages, in-app alerts, or webhooks.

**Source citations (per the Wasserman 2026 working analysis, Appendix C).**
- Gartner Maturity Model for Event-Driven Architecture — Tier 2
- Gartner Hype Cycle for Enterprise Architecture 2025 — Tier 2
- WebSocket.org Protocol Comparison — Tier 4 (vendor)

**Compliance framework mappings.**
- **NIST SP 800-53:** SI-4 (System Monitoring), CP-2 (Contingency Plan)
- **SOC 2 Trust Services Criteria:** CC7.4 (Communication of Internal Control), A1.2 (Availability commitments)
- **OSFI B-13:** Section 4.5 (Resilience)

#### Layer 2 form (mechanical / artifact-based)

**Layer 2 inspection procedure.**

1. **Determine whether the application produces notifications.** Look for email-sending code, SMS-sending code, push notification SDK usage, webhook publishing, in-app notification creation, or SSE/WebSocket streaming. If none of these are present, score *Not Applicable* and document why.
2. **Locate the notification dispatch layer.** Find where notifications are sent. Common patterns: a `NotificationService`, a `mailer.py`, a `notifications/` directory, a job queue producer, a message bus publisher.
3. **Inspect the synchronous-vs-asynchronous boundary (the disqualifier check).** Determine whether the originating request waits for the notification to be sent before returning, or whether the request enqueues the notification and returns immediately. **Synchronous notifications dispatched inline in the request handler are the most disqualifying finding in this dimension** because they block the response, fail the request when the notification fails, and produce cascading failures under provider outages. If notifications are dispatched synchronously, the dimension scores *Absent* without further inspection.
4. **Inspect the queue infrastructure.** If notifications are asynchronous, identify the queue or message bus used (Celery, Sidekiq, BullMQ, AWS SQS, RabbitMQ, Redis pub/sub, etc.) and the worker process that consumes from it.
5. **Inspect the dead-letter queue.** Determine whether permanently failed notifications are routed to a dead-letter queue or equivalent. Without this, failed notifications are silently lost.

#### Layer 3 form (qualitative specified judgment)

**Layer 3 inspection procedure.** Four markers, each scored present / partial / absent.

**Marker 1: Retry strategy uses exponential backoff with a finite retry count.** Inspect the retry configuration. Mature systems use exponential backoff (delays grow on each retry: 5s, 30s, 5min, 30min, 4h) with a finite maximum number of attempts (typically 5–10) before routing to the dead-letter queue. Common failures: no retries at all (any transient failure becomes permanent loss), retries with no backoff (a downstream outage produces a thundering retry storm), retries with no maximum count (failed notifications retry forever, consuming worker resources). Present = exponential backoff with finite count; partial = some backoff but no maximum, or maximum but no backoff; absent = no retries or unbounded retries.

**Marker 2: Notification failures are isolated from the originating request.** Inspect the request handler that dispatches notifications. Verify that a notification failure cannot propagate up to fail the originating request. The mature pattern is complete isolation: the queue enqueue succeeds (which is fast and reliable), the worker handles delivery in the background, and any failure during delivery is logged but never affects the user-facing request. Sample 2-3 dispatch sites; check the error handling. Present = complete isolation in all sampled sites; partial = isolation in most but with one or two paths where failures can propagate; absent = notification failures regularly cause user-facing 500 errors.

**Marker 3: Per-recipient rate limits prevent notification spam from bugs.** Inspect the notification dispatch logic for per-recipient rate limiting. The failure mode is a bug in a job that triggers thousands of notifications to the same user (the price-alert job that sends 1,200 emails to one user in 90 minutes is the canonical example). The mature pattern enforces a per-user maximum (typically 10-50 notifications per hour per user, or per recipient identifier) at the dispatch layer, before the notification reaches the queue. Present = per-recipient rate limits enforced at dispatch; partial = limits exist but are too permissive; absent = no per-recipient limits.

**Marker 4: Delivery metrics are observable and monitored.** Inspect the notification system's observability. Mature systems export metrics on dispatch rate, delivery rate, bounce rate, complaint rate, retry rate, and dead-letter rate, and these metrics are monitored with alerting on anomalies. The minimum is per-channel delivery rate; the mature pattern includes per-recipient delivery success and per-template performance. Present = full metric set with monitoring and alerting; partial = some metrics exist but are not monitored; absent = no observability beyond application logs.

**Layer 3 scoring rule for the dimension.** Score Layer 3 *Present* if 3 or 4 markers score Present. *Partial* if 2 markers score Present. *Absent* if 0 or 1 markers score Present.

#### Layer 4 questions (deferred to Phase 1)

- Is the notification architecture appropriate for this application's volume and pattern of notifications? (A simple Celery queue may be adequate at one scale and inadequate at another.)
- Are there subtle bugs in the queue-handling logic that only manifest under specific failure scenarios?
- Would the notification system survive a sustained outage of the primary notification provider, or does it have hidden single points of failure?

**Combined scoring rubric.**

- ***Present.*** Layer 2 form passes (notifications dispatched asynchronously via queue, worker process consumes from queue, dead-letter queue captures permanent failures) AND Layer 3 form scores Present (3 or 4 of 4 markers).
- ***Partial.*** Layer 2 form passes but Layer 3 has gaps (2 markers Present); OR Layer 2 is Partial (asynchronous dispatch but missing dead-letter queue) but Layer 3 scores Present.
- ***Absent.*** Layer 2 form fails (notifications dispatched synchronously inline in the request); OR Layer 2 form passes but Layer 3 scores Absent.
- ***Not Applicable.*** The application does not produce notifications of any kind. Document the reasoning.

**Common failure modes.**

- **Synchronous email send.** The application calls `smtp.send_email()` inline during a user signup request, blocks the response until SMTP returns, and 500-errors the signup if the SMTP server is slow or down.
- **No retry on failure.** A single notification delivery failure is final. Failed emails are silently lost.
- **Retry storm.** Retries are configured but with no backoff and no maximum count, so a downstream provider outage produces a thundering retry storm that exceeds API rate limits and turns a transient failure into a permanent one.
- **No dead-letter queue.** Permanently failed notifications disappear with no record. The operations team cannot tell what was lost.
- **Notification failures crash the originating request.** A failed email send raises an exception that propagates up to the request handler and returns 500 to the user, even though the actual user-facing operation succeeded.
- **No per-recipient rate limit.** A bug in a job that emails users about price changes ends up sending 47 emails to the same user in 4 minutes.
- **Notification queue with no consumer.** Notifications are correctly enqueued but the worker process has been crashed for hours and nobody noticed because there are no health checks or alerts on the queue depth.
- **Hardcoded notification content.** Email templates inlined in source code with no localization, no A/B testing capability, no audit trail of what was sent.
- **No observability.** The application sends 10,000 notifications per day but has no metrics on how many were delivered, how many bounced, or how many produced user complaints.

**Example presence (Python / Django).** A Django application using Celery with Redis as the broker for asynchronous notification dispatch. When a user action requires a notification (signup welcome email, password reset, order confirmation), the request handler calls `send_notification.delay(user_id, template_name, context)` which enqueues the task and returns immediately. A pool of Celery workers processes the queue, retrieves user contact information, renders the template, and dispatches via the appropriate channel (SendGrid for email, Twilio for SMS). Failed deliveries are retried with exponential backoff (5 seconds, 30 seconds, 5 minutes, 30 minutes, 4 hours, then dead-letter). The dead-letter queue is monitored by an operations dashboard. Delivery metrics (sent, delivered, bounced, complained) are exported to Prometheus and visible on a Grafana dashboard. A per-user rate limit (max 10 notifications per hour per user) prevents bug-triggered notification spam. When SendGrid is unavailable, the queue grows but the application's user-facing requests continue to succeed.

**Example absence (Ruby / Rails).** A Rails application where every notification is sent inline during the request. Signing up for a new account triggers `UserMailer.welcome_email(@user).deliver_now` inside the controller action, which blocks the request for 800 milliseconds while the mail server processes the request, and 500-errors the signup if the mail server returns an error. The application has had three production incidents in the last six months where Mailgun outages caused signups to fail. There is no retry: the welcome email is either sent on the first try or never. There is no dead-letter queue. There is no per-recipient rate limit, and a bug in the price-alert job last month sent 1,200 emails to a single user in 90 minutes. The notification system has no observability beyond the application logs. A `# TODO: move emails to a background job` comment dated 19 months ago sits in `app/controllers/users_controller.rb`.

**Time budget.** Approximately 60 to 75 minutes for an experienced assessor: 20 to 30 minutes for the Layer 2 inspection (the synchronous/asynchronous check is the disqualifier and takes 5 minutes), 40 to 45 minutes for the Layer 3 marker assessment.

---

