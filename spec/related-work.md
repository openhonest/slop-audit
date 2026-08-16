# Related Work and Prior Art

**Purpose.** A verified prior-art / novelty map for the Slop Audit. It situates the instrument against the closest existing work, names what each does and does *not* do, and flags the few items that partially pre-empt specific claims so they can be cited and distinguished honestly.

**Provenance.** Compiled 2026-06-13 from (1) a multi-agent deep-research sweep (107 agents; 25 claims adversarially verified, 25/25 confirmed) across arXiv, standards bodies, and the SE literature, and (2) a direct Zenodo API backstop (Zenodo carries recent work that arXiv-weighted search misses, given arXiv's current rejection of unaffiliated submissions). **Every arXiv identifier below was individually resolved on 2026-06-13**, none is an unverified ID. Two micro-details remain to confirm (marked *[confirm]*).

---

## Headline finding

**No single existing work or tool combines the full Slop Audit bundle:** open + automated + compliance-framework-mapped *beyond ISO/IEC 25010* + AI-failure-mode-targeted + multi-layer (quantitative indicators + artifact inspection + qualitative trained-assessor judgment + architectural synthesis). The prior art splits along separate axes; each candidate covers only a slice. A March 2026 systematic literature review independently concludes that **no standardized or integrated framework exists for assessing AI-generated code quality** (Geruslu et al. 2026). The novelty is the *bundle*. Two component premises, mutable-state-as-defect-signal, and the concept of finite testability, are independently validated in the prior literature (§D). These are **not** pre-emptions: they confirm the foundations are sound and that the missing piece is exactly the integrated instrument the Slop Audit assembles.

---

## A. Closest standards-grade measurement instruments (situate against)

- **ISO/IEC 5055:2021, CISQ Automated Source Code Quality Measures.** The nearest open, automated, standards-body instrument. Measures four characteristics (security, reliability, performance efficiency, maintainability), a 4-of-8 subset of ISO/IEC 25010, by mechanical static-analysis weakness counting (138 CWE-based patterns). *Does not:* target AI-generated-code failure modes, perform multi-layer or qualitative assessment, or map to SOC 2 / NIST SP 800-53 / OWASP ASVS. The CISQ Automated Technical Debt measure builds on the same four factors with no AI framing. <https://www.it-cisq.org/press-releases/cisq-automated-source-code-quality-measures-now-iso-standard/>
- **SIG / TÜViT (Sigrid) quality models.** ISO/IEC 25010-mapped, automated, with a separate NIST 800-53/OWASP-based security model. Has an "AI Governance" capability, but it only *detects* AI-generated code (stylometry, ~95–99%) and scores generic maintainability/security risk; it does **not** audit the Slop Audit's specific AI-failure markers, and it keeps detection and compliance as separate, uncombined modules. Does not pre-empt the AI-failure-mode-targeted or compliance-mapped-AI-audit claims. <https://docs.sigrid-says.com/reference/sig-quality-models.html>
- **Closest *commercial* positioning: SonarQube / SonarSource.** Now explicitly markets "Fight AI Slop & Verify AI Code" and maps findings to compliance standards (PCI, OWASP, CWE, STIG, CASA). The nearest commercial prior art on the AI-code + compliance angle, but it is **closed-source, single-layer static analysis**, with no qualitative-assessor or architectural layer, no git-history L1 indicators (mutable-state ratio, finite-testability, test determinism), and vendor-defined rather than peer-reviewed metrics. <https://www.sonarsource.com/products/sonarqube/>

## B. Empirical AI-code-failure wave (corroboration, not pre-emption)

These establish that AI-code failure modes are real and measurable at deployment scale. They *ground* the Slop Audit's premise; none is an instrument, none is compliance-mapped, none is multi-layer.

- **Pearce, Ahmad, Tan, Dolan-Gavitt & Karri (2022).** *Asleep at the Keyboard? Assessing the Security of GitHub Copilot's Code Contributions.* IEEE S&P 2022. arXiv:2108.09293. (~40% vulnerable programs across 89 MITRE-Top-25-CWE scenarios.)
- **Wang, Yu, Zhong, Yu, Lian, Lu, Zheng, Zhang & Li (2025).** *AI Code in the Wild: Measuring Security Risks and Ecosystem Shifts of AI-Generated Code in Modern Software.* arXiv:2512.18567 (Dec 2025). (Top-1,000 GitHub repos + 7,000 CVE-linked changes; AI concentrates in glue/test/refactor/doc/boilerplate; review acts as security checkpoint.)
- **Mao, Zhao, Tang, Wang & Zhang (2026).** *A Large-Scale Empirical Study of AI-Generated Code in Real-World Repositories.* arXiv:2603.27130 (Mar 2026). **The duplication-signature source** (see §E note).
- **Geruslu, Aliyeva & Tüzün (2026).** *Factors Influencing the Quality of AI-Generated Code: A Synthesis of Empirical Evidence.* arXiv:2603.25146 (Mar 2026). Systematic literature review, 24 primary studies; the white-space-confirming source.

### B.1 Additional corroboration (OSF + SSRN hardening pass, 2024–2026)

Surfaced 2026-06-13. All corroborate the failure-mode premise; none is an instrument.

- **(ISSRE 2025) *Human-Written vs. AI-Generated Code: A Large-Scale Study of Defects, Vulnerabilities, and Complexity.*** Peer-reviewed, IEEE ISSRE 2025; replication package Zenodo DOI 10.5281/zenodo.15423067; code at <https://github.com/dessertlab/Human_vs_AI_Code_Quality>. The strongest *peer-reviewed* corroboration found.
- ***Assessing the Quality and Security of AI-Generated Code: A Quantitative Analysis.*** arXiv:2508.14727 (2025). Finds **no correlation** between functional Pass@1 and SonarQube-measured quality/security; critical issues (hard-coded passwords, path traversal) recur across models.
- ***A Survey of Bugs in AI-Generated Code.*** arXiv:2512.05239 (2025).
- ***Security Degradation in Iterative AI Code Generation, A Systematic Analysis of the Paradox.*** arXiv:2506.11022 (2025).
- ***Artificial-Intelligence-Generated Code Considered Harmful: A Road Map for Secure and High-Quality Code Generation.*** arXiv:2409.19182 (2024).

## C. "Slop" as a named construct

- **Orlanski, Roy, Yun, Shin, Gu, Ge, Adila, Roberts, Sala & Albarghouthi (2026).** *SlopCodeBench: Benchmarking How Coding Agents Degrade Over Long-Horizon Iterative Tasks.* arXiv:2603.24755 (Mar 2026). Closest named "slop" work, but a **model-capability benchmark** (36 problems, 196 checkpoints; two trajectory metrics: structural erosion + verbosity; agent code 2.3× more verbose, 2.0× more eroded vs 473 OSS repos), **not** an in-the-wild codebase scorer, no compliance mapping, no multi-layer judgment. Does not pre-empt the Slop Audit framing.

## D. Foundational confirmations, components validated in the literature; the integrated instrument is the open contribution

These are **not** pre-emptions. Each independently confirms that a *component premise* of the Slop Audit is real and scholarly-grounded, yet none assembles the components into an operational instrument. They strengthen the case: the signals are sound, and the missing piece is exactly the integration ("the full Monty"). **Novelty scope, stated honestly:** the Slop Audit does *not* claim to have invented mutable-state-as-defect-signal or to have coined "finite testability"; it claims the **integrated, compliance-mapped, AI-failure-targeted, multi-layer instrument**. Cite these as validation, and keep the novelty on the bundle, that is what makes the bundle-novelty claim airtight.

1. **Mutable-state-as-defect-signal, validated.** Marsavina, C. (2020). *Understanding the Impact of Mutable Global State on the Defect Proneness of Object-Oriented Systems.* IEEE SACI 2020 (14th International Symposium on Applied Computational Intelligence and Informatics); IEEE Xplore doc 9118816. Empirically links mutable-global-state usage to defect proneness (detection strategies + bug-fix commit classification + fine-grained change extraction). **What it confirms:** the core L1.18 premise, mutable state is a real, measurable defect signal. The Slop Audit generalizes it to a *finite-testability* ratio, adds decision-space coverage (L1.19) and test determinism (L1.20), and embeds the trio in the full instrument. The component is known; the assembly is the contribution. <https://ieeexplore.ieee.org/document/9118816>
2. **"Finite testability" as a real concept, validated.** Rodríguez, Llana & Rabanal (2014). *A General Testability Theory: Classes, Properties, Complexity, and Testing Reductions.* IEEE Transactions on Software Engineering 40(9): 862–894 (earlier version: Springer 2009). Formalizes finite testability, five testability classes; conditions that enable/disable it. **What it confirms:** finite testability is an established, rigorous notion, not a coinage. The Slop Audit's *Finite Testability* work (Wasserman 2026) operationalizes it as an *empirical measurement* across 200 real codebases, theory grounded; measurement and integration are the contribution. <https://ieeexplore.ieee.org/abstract/document/6839051/>

## E. Adjacent (not pre-emption)

- **Towards Evidence-based Testability Measurements.** ICSE 2021 NIER. arXiv:2102.10877. Operationalizes testability as per-unit test-case hardness via test generation + mutation analysis, not "code provably uncoverable by finite testing," not mutable-state ratio or decision-space coverage, not compliance-mapped or AI-targeted.
- **Lenarduzzi et al. (2019).** *The Technical Debt Dataset.* arXiv:1908.00827 (PROMISE 2019). Composes SonarQube + Ptidej + Refactoring Miner + SZZ over 33 Apache Java projects. Multi-source composition, but no compliance/quality-framework mapping, pre-AI, no qualitative/architectural layer.

> **Duplication-signature refinement (act on this).** Mao et al. (2026, arXiv:2603.27130) find AI code has *lower* total duplicated lines (17.2% vs 24.5%) but *more fragmented* clone instances per file (0.679 vs 0.534 per file) than human code. This complicates the simple "AI bloat/duplication" framing of the L1.13 fuzzy/Type-2-3 clone indicator: the AI signal is **fragmentation, not gross volume**. Recommend recalibrating L1.13 to weight clone-instance count/fragmentation, and citing this nuance proactively.

## F. Zenodo-only 2026 corroboration (structural-distinguishability of AI code)

Surfaced by direct Zenodo querying (missed by the arXiv-weighted sweep). Independent evidence that AI code is structurally distinguishable, useful supporting citations.

- ~~**Bilar, D. Y. (2026).** *Fan-In Distributions in Human-Written vs AI-Generated Python Codebases.*~~ **REMOVED 2026-06-13, UNVERIFIABLE / probable fetch hallucination.** This record was listed in the first Zenodo API summary but could not be relocated by web search, phrase query, or author-name query. Daniel Yaacov Bilar is a real Zenodo author, but his actual deposits are unrelated (Claude Code playbooks); the summarizer distorted his name ("Daniyel") and the Gini statistics could not be confirmed. **Do not cite.** A verify-before-cite catch.
- **Maes, S. (2026).** *Evaluating the Efficacy of Artificial Intelligence in Software Engineering: A Post-February 2026 Analysis.* Zenodo, 2026-03-13. DOI: 10.5281/zenodo.19103819. "Work Slop" / "AI Brain Fry"; cyclomatic complexity + cognitive debt as degradation signals (analysis, not an instrument).
- **Sofience (2026).** *SΔΦ-65, Slop as Externalized Restabilization Cost.* Zenodo, 2026-05-14. DOI: 10.5281/zenodo.20173455. Concept-level formalization of "slop" as cost-externalization across domains (not code-specific).

## Author's own foundational work (context, not prior art)

- **Wasserman, A. Z. (2026).** *Finite Testability of Enterprise Software.* Zenodo. DOI: 10.5281/zenodo.20385346. (The L1.18 mutable-state-ratio measurement across 200 public codebases.)
- **Wasserman, A. Z. (2026).** *Process Discipline as the Key Variable in AI-Assisted Enterprise Software Development.* Zenodo. DOI: 10.5281/zenodo.19355460.

---

## Open items
- All citation details resolved as of 2026-06-13. IEEE 9118816 → Marsavina, SACI 2020. The one item that could not be verified (Bilar, *Fan-In Distributions*) was determined to be a fetch hallucination and removed (§F).

## Search-coverage honesty
- **arXiv/web sweep (deep-research, 107 agents):** strong. *Missed* the Rodríguez 2014 finite-testability term collision and the Zenodo-only items, caught only by the direct Zenodo backstop.
- **Direct Zenodo backstop:** good. Surfaced two real items (Maes, S∆Φ-65, both DOI-confirmed) and one hallucinated one (Bilar, removed), a reminder that fetch-summarized repository results must be verified before citing.
- **OSF + SSRN hardening pass (2026-06-13):** completed. OSF carries AI-code *detection* studies (e.g., robustness of AI-generated-code detection) and unrelated medical quality-assessment tools, but **no competing AI-code-quality AUDIT instrument**; SSRN returned nothing directly competing. White space holds across both. The pass surfaced additional corroboration (§B.1) and the SonarQube commercial "AI slop" positioning (§A).
- **Net:** every arXiv identifier cited here was individually resolved (2026-06-13); the white-space finding is robust across arXiv, Zenodo, OSF, SSRN, and standards bodies. The one remaining place worth a future look is a targeted OSF *Registries* (preregistration) pass.
