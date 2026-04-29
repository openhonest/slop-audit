# Slop Audit Methodology

The enterprise software quality audit instrument. Eighteen dimensions mapped to SOC 2, NIST 800-53, OSFI B-13, OWASP ASVS, and other compliance regimes. Four-layer judgment model. Designed to be runnable by a trained assessor working from these documents alone.

## Reading order

| # | File | Contents | Lines |
|---|---|---|---|
| 0 | [Frontmatter](00-frontmatter.md) | Title, status, confidentiality statement | ~14 |
| 1 | [Purpose and scope](01-purpose-and-scope.md) | What the audit produces, who runs it, scope of one audit | ~28 |
| 2 | [Four-layer model](02-four-layer-model.md) | Layer 1 through Layer 4 definitions, composition, why the model exists, Phase 0/Phase 1 boundary | ~135 |
| 3 | [Layer 1 indicators](03-layer1-indicators.md) | Twenty quantitative indicators (seventeen git-history + three finite-testability), reporting format, automation, limitations | ~314 |
| 4 | [Dimensions](dimensions/) | The 18 per-dimension entries (Layer 2 + Layer 3 + Layer 4 for each) | ~1,700 |
| 5 | [Conducting an audit](05-conducting-audit.md) | The 5-day operational walkthrough, prerequisites, common time-budget failures | ~90 |
| 6 | [Slop Report template](06-slop-report-template.md) | Report structure, SOC 2 deliverable extraction, length/tone guidance | ~214 |
| 7 | [Validation](07-validation.md) | Validation set, cross-rater test, "would the auditor agree" test | ~38 |
| 8 | [Training](08-training.md) | Curriculum tracks, certification levels, cross-rater calibration, recertification | ~182 |
| 9 | [TODO and attribution](09-todo-and-attribution.md) | Outstanding work items, source attribution, future extensions backlog | ~95 |

## Dimensions index

Each dimension is a self-contained file in `dimensions/`. An assessor can reference one dimension at a time during an audit.

| # | File | Dimension | Lifecycle category |
|---|---|---|---|
| — | [Quick reference](dimensions/00-quick-reference.md) | The one-row-per-dimension lookup table for mid-audit use | — |
| 4.1 | [01-entitlement.md](dimensions/01-entitlement.md) | Entitlement system | Security architecture |
| 4.2 | [02-authentication.md](dimensions/02-authentication.md) | Authentication | Security architecture |
| 4.3 | [03-inter-service-security.md](dimensions/03-inter-service-security.md) | Inter-service security | Security architecture |
| 4.4 | [04-multi-tenancy.md](dimensions/04-multi-tenancy.md) | Multi-tenancy | Data architecture |
| 4.5 | [05-audit-infrastructure.md](dimensions/05-audit-infrastructure.md) | Audit infrastructure | Compliance engineering |
| 4.6 | [06-rate-limiting.md](dimensions/06-rate-limiting.md) | Rate limiting | Operational security |
| 4.7 | [07-configuration-secrets.md](dimensions/07-configuration-secrets.md) | Configuration and secrets | Operational security |
| 4.8 | [08-caching.md](dimensions/08-caching.md) | Caching | Performance engineering |
| 4.9 | [09-notifications.md](dimensions/09-notifications.md) | Notifications | Operations |
| 4.10 | [10-cicd.md](dimensions/10-cicd.md) | CI/CD | DevOps |
| 4.11 | [11-containerization.md](dimensions/11-containerization.md) | Containerization | Infrastructure |
| 4.12 | [12-dependency-injection.md](dimensions/12-dependency-injection.md) | Dependency injection | Software architecture |
| 4.13 | [13-pattern-sophistication.md](dimensions/13-pattern-sophistication.md) | Pattern sophistication | Software architecture |
| 4.14 | [14-architectural-philosophy.md](dimensions/14-architectural-philosophy.md) | Architectural philosophy | Software architecture |
| 4.15 | [15-live-documentation.md](dimensions/15-live-documentation.md) | Live documentation | Governance |
| 4.16 | [16-sdlc-ai-safeguards.md](dimensions/16-sdlc-ai-safeguards.md) | SDLC with AI safeguards | Process engineering |
| 4.17 | [17-tech-debt-management.md](dimensions/17-tech-debt-management.md) | Tech debt management | Lifecycle management |
| 4.18 | [18-ux-from-code.md](dimensions/18-ux-from-code.md) | UX from code | Software development |

## Other methodology files

| File | Contents |
|---|---|
| [papers/peer-review-strategy.md](papers/peer-review-strategy.md) | Publication program, venue selection, framework extension cadence |
| [papers/paper-2-preregistration.md](papers/paper-2-preregistration.md) | Pre-registration for the independent instrument validation study |
| [validation/protocol.md](validation/protocol.md) | Validation protocol details |

## License

Apache License 2.0. See [LICENSE](LICENSE).
