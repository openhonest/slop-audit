### 4.18 UX from code

**Lifecycle category.** Software development.

**Drafted under the four-layer model.**

**Definition.** UX from code is the discipline that ensures the *end-user experience* of a system is treated as a property of the code that produces it, not as a separate concern handled by a design team after the fact. A mature UX-from-code discipline produces interfaces that are *fast* (Core Web Vitals pass on real devices), *accessible* (WCAG 2.2 AA at minimum), *legible* (cognitive load below the threshold at which users start clicking randomly), *consistent* (the same action produces the same result everywhere), and *forgiving* (errors are recoverable, not destructive). The opposite is the system whose UI is a sequence of design-system components dropped into routes by an AI agent that has never seen a real user, that fails Lighthouse on every dimension, that has no `aria-*` attributes anywhere, and that works correctly only on the developer's MacBook Pro on a fast connection.

This dimension applies only to systems that have a user-facing interface (web app, mobile app, desktop app, CLI tool with significant interaction). Systems that are pure backend services, batch jobs, or library code score this dimension as *Not applicable*, which is recorded distinctly from *Present* / *Partial* / *Absent*.

**Industry threshold.** Lighthouse Performance ≥75 on the main user-facing route on simulated mid-tier mobile; Largest Contentful Paint ≤2.5 seconds; Cumulative Layout Shift ≤0.1; WCAG 2.2 Level AA conformance verified by `axe-core` or equivalent automated check plus manual keyboard-only test pass on the primary flow; primary screens contain ≤7 interactive elements per visual region (Miller's law as adapted by Krug); error states display recoverable messages with explicit next steps. Drawn from Web.dev Core Web Vitals research, the WCAG 2.2 specification, and Krug's *Don't Make Me Think* (3rd ed.).

**Source citations (per the Wasserman 2026 working analysis, Appendix C).**
- Web.dev / Chrome UX Report — Tier 1 (industry standard for performance thresholds)
- WCAG 2.2 (W3C Recommendation, October 2023) — Tier 1
- Krug, *Don't Make Me Think* (2014) — Tier 2
- Nielsen Norman Group usability heuristics (10 principles) — Tier 2

**Compliance framework mappings.**
- **NIST SP 800-53:** AC-8 (System Use Notification, accessibility implications), SI-11 (Error Handling)
- **Section 508 (US Federal):** Revised 508 Standards incorporating WCAG 2.0 AA
- **EN 301 549 (EU):** Accessibility requirements for ICT products and services
- **Accessibility for Ontarians with Disabilities Act (AODA):** WCAG 2.0 AA conformance for designated organizations
- **Loi 25 (Quebec):** does not directly mandate accessibility but interacts with consent UI requirements

---

#### Layer 2 form (mechanical / artifact-based)

**Layer 2 inspection procedure.**

1. **Applicability check.** Confirm the system has a user-facing interface. If not, score *Not applicable* and stop.
2. **Lighthouse run.** Run Lighthouse against the main user-facing route, using the mobile preset and simulated throttling. Record the four scores (Performance, Accessibility, Best Practices, SEO) and the three Core Web Vitals (LCP, CLS, INP or FID).
3. **Accessibility automated scan.** Run `axe-core` (or Pa11y, or the equivalent) against the primary screens. Record the number of violations by severity (critical, serious, moderate, minor).
4. **Keyboard-only navigation pass.** Open the primary user flow in a browser. Disconnect the mouse. Attempt to complete the flow using only Tab, Shift+Tab, Enter, Space, and arrow keys. Record where the flow breaks.
5. **Error-state inspection.** Trigger 3 error conditions (invalid form input, network failure if possible, permission denial). For each, record what the user sees: an error message? A generic "something went wrong"? A blank screen? A stack trace?
6. **Component density check.** On the primary screens, count interactive elements (buttons, links, inputs, dropdowns, toggles) per visual region. A "visual region" is a section the user perceives as a single area of interest. If any region contains more than 7 interactive elements, record the count.

#### Layer 3 form (qualitative specified judgment)

**Layer 3 inspection procedure.** Five markers, each scored present / partial / absent.

**Marker 1: The interface is fast on a real device, not just on the developer's machine.** A Lighthouse score is a starting point but not a guarantee. The marker is *evidence that the team has tested on a representative target device*. Look for: an `.htaccess` or middleware that sets cache headers, a build configuration that produces split bundles, evidence of image optimization (responsive images, modern formats), and ideally a CI step or staging environment that runs Lighthouse against the deployed build. Score: present if Lighthouse Performance ≥75 AND there is evidence of intentional performance work, partial if Lighthouse passes but with no evidence of intentional work (a fluke), absent if Lighthouse fails or if the developer has never seen the app on a phone.

**Marker 2: Accessibility is built in, not bolted on.** Read the source of the primary components. Determine whether `aria-*` attributes, semantic HTML elements (`<button>`, `<nav>`, `<main>`, `<label for=>`), and focus management are *present in the source code as written* — or whether they were added in a "accessibility audit" PR after the fact and are inconsistent across components. Bolted-on accessibility is recognizable: it appears on some screens and not others, the labels are generic ("Click here," "Submit"), and the focus order does not match the visual order. Built-in accessibility is consistent across the codebase and aligns with the visual structure. Score: present if ≥80% of interactive elements have appropriate semantic markup and labels, partial if 40–80%, absent if <40% or if accessibility is conspicuously absent.

**Marker 3: Error states are designed, not generated.** When the user encounters an error, what they see should be the result of a deliberate decision about *what this user needs to know and do next*. The failure mode is the system that displays whatever the framework happens to produce: a stack trace, a JSON blob, a 500 page from the server, a generic toast that says "Error." Sample 3 error paths and read the code that produces the user-facing message. Score: present if all 3 error messages are explicit and actionable ("We couldn't save your changes because the network dropped. Your work is preserved locally — try again or contact support."), partial if 1 or 2 are explicit, absent if all 3 are generic or framework-default.

**Marker 4: The interface is consistent within itself.** Pick the same affordance (a "delete" action, a "save" action, a "back" action) on three different screens. The visual, the label, and the behavior should be the same on all three screens. The failure mode is the system where "Delete" is a red button on one screen, a small trash icon on another, a dropdown menu item on a third, and behaves slightly differently in each location. Score: present if the same affordance is implemented consistently in 3 of 3 sampled locations, partial if 2 of 3, absent if all 3 are different.

**Marker 5: The interface degrades gracefully under realistic constraints.** Throttle the network in DevTools to "Slow 3G." Reload the primary flow. Determine whether the application: (a) shows a loading state, (b) progressively reveals content as it loads, (c) produces an error page only after a deliberate timeout, or (d) hangs forever, displays a blank white screen, or crashes. Repeat with the network offline, with localStorage disabled, and with JavaScript blocked on a single critical script. Score: present if all 4 conditions produce a coherent user experience (even if degraded), partial if 2 or 3, absent if 0 or 1.

**Layer 3 scoring rule for the dimension.** Score Layer 3 *Present* if 4 or 5 markers score Present. *Partial* if 2 or 3 markers score Present. *Absent* if 0 or 1 markers score Present.

#### Layer 4 questions (deferred to Phase 1)

- Is the interface *good* in the deeper sense — does it help users accomplish their actual goals, or does it just expose the data model? (Requires user research to answer.)
- Is the *information architecture* aligned with how users think about the task, or with how the developers think about the data?
- Are the *empty states* (the screens users see before they have any data) designed and helpful, or are they accidental?
- Is the system *internationalized* in a way that survives real translation, or only string-replaced for English variants?
- Does the system have a *design system* and is it being used consistently, or has each developer reinvented basic components?

---

**Combined scoring rubric.**

- ***Present.*** Layer 2 form passes (Lighthouse ≥75, axe-core ≤5 serious violations on primary screens, keyboard-only flow completes, error states explicit, density ≤7) AND Layer 3 form scores Present (4–5 of 5 markers).
- ***Partial.*** Layer 2 passes most checks but Layer 3 has gaps (2–3 markers Present); OR Layer 2 is mixed (Lighthouse 50–75, some accessibility violations, partial keyboard support) but Layer 3 scores Present.
- ***Absent.*** Layer 2 fails (Lighthouse <50 OR ≥10 serious axe-core violations OR keyboard flow does not complete OR error states are framework defaults); OR Layer 2 passes but Layer 3 scores Absent (0–1 markers Present).
- ***Not applicable.*** System has no user-facing interface. This is recorded distinctly so that the dimension is not silently dropped from the audit count.

**Common failure modes.**

- **The MacBook-Pro-only app.** Lighthouse Performance is 92 on the developer's M3 MacBook Pro on gigabit ethernet. On a $200 Android phone on 3G, the page takes 14 seconds to render and Cumulative Layout Shift is 0.8. The team has never tested on a real target device. Layer 3 fails Marker 1.
- **Bolted-on accessibility.** An "accessibility sweep" PR added `aria-label` attributes to half the buttons 8 months ago. New components added since then have no labels. Some labels say "Click here." Layer 3 fails Marker 2.
- **The framework-default error page.** When anything goes wrong, the user sees the React error boundary's default ("Something went wrong"), the Next.js error page, or a JSON dump. Layer 3 fails Marker 3.
- **The inconsistent destructive action.** "Delete user" is a red button at the top right of the user detail page. "Delete project" is a small × icon next to the project name. "Delete file" is a context menu item. Each behaves slightly differently (some confirm, some don't, some are reversible, some aren't). Layer 3 fails Marker 4.
- **The white screen of fetch.** Throttle to Slow 3G, reload, and the user sees a white screen for 12 seconds while the JavaScript bundle downloads, then a flash of unstyled content, then the app appears. No loading state, no progressive reveal. Layer 3 fails Marker 5.
- **The 18-button toolbar.** A primary screen has a toolbar with 18 buttons in a single row. Users learn the 3 they need and never touch the other 15. Layer 2 fails the density check.
- **The accessibility-overlay shortcut.** The team has installed an "accessibility overlay" widget (UserWay, AccessiBe, etc.) instead of fixing the underlying markup. The overlay is visible in the page source. Layer 3 fails Marker 2 with prejudice; this is also a documented anti-pattern that has led to lawsuits in the US under the ADA.

**Example presence (TypeScript / React e-commerce checkout).** A React e-commerce checkout flow built on Next.js. Lighthouse Performance 86, Accessibility 100, Best Practices 95 on the mobile preset with simulated throttling. `axe-core` reports 0 violations on the cart, shipping, and payment screens. The keyboard-only flow completes without breaking. Error states are explicit: "Your card was declined by your bank. The most common cause is an incorrect billing ZIP. Try again, or use a different card." The "Remove from cart" affordance is the same icon, label, and behavior in all three locations where it appears. The CI pipeline runs Lighthouse against the staging deployment on every PR and blocks merge if Performance drops below 80. The team has tested on a Moto G Power as their reference low-end device. Slow 3G throttling produces a coherent skeleton-screen loading state followed by progressive content reveal. Layer 2 passes; all 5 Layer 3 markers score Present.

**Example absence (C# / unsupervised Blazor admin panel).** A Blazor Server admin panel generated largely by an AI agent against a .NET 8 backend. Lighthouse Performance 31 on the mobile preset (the Blazor Server render model ships a large WebSocket-tied SignalR payload on first load and recovers poorly from network loss). `axe-core` reports 47 serious violations on the primary screen, including missing `aria-label` attributes on 23 `<InputText>` components, insufficient contrast on the primary action color, and heading levels that skip from `<h1>` to `<h4>`. The keyboard-only flow breaks at the second screen (a custom `<InputSelect>` component that traps focus inside a modal). Error states display whatever the underlying API returned: `{"error":"validation_failed","details":[...]}` rendered verbatim in a `<pre>` tag. The primary user-list screen has 23 interactive elements per row (every cell is a clickable affordance, plus a context menu, plus inline edit, plus a row-level action menu). Throttling to Slow 3G produces a 22-second white screen followed by the app appearing all at once as the SignalR connection finally establishes. There is no loading state. The team has never run Lighthouse and was not aware that `axe-core` exists. Layer 2 fails on every check; Layer 3 fails on every marker. The dimension scores Absent.

**Time budget.** Approximately 45 to 75 minutes for an experienced assessor on a system with a user-facing interface: 20 minutes for the Layer 2 mechanical inspection (Lighthouse, axe-core, keyboard pass, error triggering, density count), 25 to 55 minutes for the Layer 3 marker assessment (which includes sampling source code for accessibility patterns and reading error-handling code paths). For a system with no user-facing interface, the dimension scores *Not applicable* in approximately 5 minutes.

---

