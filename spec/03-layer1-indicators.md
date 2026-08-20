## 3. Layer 1. Quantitative git-history assessment

### 3.1 Inputs and prerequisites

- Read access to the full git history of the target repository (clone is sufficient; remote access is not required after the initial clone)
- A defined assessment date range (typically the most recent 12 months of activity, or the period since AI assistance was introduced if known)
- A working git installation
- Optionally: a script that runs the indicators in batch (a reference implementation lives in `research/slop-audit-layer1.sh` — TBD)
- No source code reading is required at this layer

### 3.2 The twenty indicators

Each indicator is a single number derived from one of five mechanical sources: `git log` output filtered by file extension and date range (L1.1 through L1.8), static repository inspection for presence and shape of configuration files (L1.9 through L1.11), a language-appropriate dead-code analyzer run on the current tree (L1.12), a fuzzy clone detector with identifier and literal normalization (L1.13), and additional static analyzers or shell-level counts (L1.14 through L1.20). The threshold values for L1.1 through L1.11 are calibrated against the structured and unstructured conditions documented in Wasserman 2026 Section 4.8. L1.12 through L1.17 are calibrated against the GitClear 2024 analysis of AI-assisted code accumulation patterns (for L1.13 in particular, which formalizes GitClear's 8x copy-paste finding into a fuzzy-clone metric), against industry tool defaults, and against the observed trailing-whitespace and god-file patterns recorded in the author's working analysis.

Each indicator is presented as two rows: a full-width lay-description row that explains in plain language why the indicator matters, followed by a data row with the operational definition and the threshold bands. The lay-description row spans all six columns. The format below uses inline HTML rather than pure Markdown because Markdown tables do not natively support row-spanning cells.

<table>
  <thead>
    <tr>
      <th>#</th>
      <th>Indicator</th>
      <th>Definition</th>
      <th>Healthy</th>
      <th>Not Healthy</th>
      <th>Slop</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>L1.1</td>
      <td>Doc-only commit ratio</td>
      <td>Percentage of commits touching only documentation files (<code>.md</code>, <code>.feature</code>, <code>.txt</code>, <code>.rst</code>, <code>.adoc</code>)</td>
      <td>≥10%</td>
      <td>1–10%</td>
      <td>&lt;1%</td>
    </tr>
    <tr style="background-color: #e6f4ea;">
      <td colspan="6">✓ <b>Good pattern:</b> Teams that write specifications in their own commits are giving AI coding assistants the context they need to produce auditable code. The spec is the constraint that keeps generation aligned with intent.</td>
    </tr>
    <tr style="background-color: #fce8e6;">
      <td colspan="6">✗ <b>Antipattern:</b> Teams with no spec commits are letting AI generate from one-off prompts alone, with nothing constraining what comes out. The published research associates this condition with audit failure across 16 of 18 enterprise dimensions.</td>
    </tr>
    <tr>
      <td>L1.2</td>
      <td>Code-only commit ratio</td>
      <td>Percentage of commits touching only code files (<code>.py</code>, <code>.js</code>, <code>.ts</code>, <code>.html</code>, <code>.css</code>, <code>.yaml</code>, <code>Dockerfile</code>)</td>
      <td>&lt;70%</td>
      <td>70–85%</td>
      <td>&gt;85%</td>
    </tr>
    <tr style="background-color: #e6f4ea;">
      <td colspan="6">✓ <b>Good pattern:</b> When code commits routinely arrive alongside or after documentation updates, the codebase accumulates AI output at a rate the team can record, explain, and review. Auditors and future developers have something to read against the code that is shipping.</td>
    </tr>
    <tr style="background-color: #fce8e6;">
      <td colspan="6">✗ <b>Antipattern:</b> When every commit is code with no documentation update, AI output accumulates faster than anyone can record what it does or why. The system's explanation drifts out of sync with reality immediately, leaving auditors and future developers nothing to read against the code that is actually shipping.</td>
    </tr>
    <tr>
      <td>L1.3</td>
      <td>Mixed (doc+code) commit ratio</td>
      <td>Percentage of commits touching both documentation and code in the same commit</td>
      <td>≥12%</td>
      <td>3–12%</td>
      <td>&lt;3%</td>
    </tr>
    <tr style="background-color: #e6f4ea;">
      <td colspan="6">✓ <b>Good pattern:</b> Updating documentation alongside code in the same commit keeps the spec the AI is reading aligned with the code the AI is producing. Mixed commits are the visible signature of a team treating documentation as an active constraint on the AI rather than as deferred paperwork.</td>
    </tr>
    <tr style="background-color: #fce8e6;">
      <td colspan="6">✗ <b>Antipattern:</b> When documentation and code never change together, the spec the AI reads diverges from the code it produces. Each subsequent generation drifts further from intent, and the codebase moves toward the gradient-mean failure mode the published research documents.</td>
    </tr>
    <tr>
      <td>L1.4</td>
      <td>Doc lines as % of total lines added</td>
      <td>Documentation line additions divided by total line additions across all commits in range</td>
      <td>≥25%</td>
      <td>5–25%</td>
      <td>&lt;5%</td>
    </tr>
    <tr style="background-color: #e6f4ea;">
      <td colspan="6">✓ <b>Good pattern:</b> Under structured AI-assisted development the architect spends a quarter or more of all writing on specifications, BDD scenarios, and architecture documents that constrain what the AI generates next. The published natural experiment measured 41.6% documentation lines under the structured condition.</td>
    </tr>
    <tr style="background-color: #fce8e6;">
      <td colspan="6">✗ <b>Antipattern:</b> Under unstructured AI-assisted development almost no writing is non-code, and the AI generates with nothing constraining it but the prompt of the moment. The published natural experiment measured 3.1% documentation lines under the unstructured condition.</td>
    </tr>
    <tr>
      <td>L1.5</td>
      <td>Code delete/add ratio</td>
      <td>Lines deleted divided by lines added across code files. A high value indicates sustained refactoring; a low value indicates accumulation without cleanup.</td>
      <td>≥60%</td>
      <td>30–60%</td>
      <td>&lt;30%</td>
    </tr>
    <tr style="background-color: #e6f4ea;">
      <td colspan="6">✓ <b>Good pattern:</b> A high delete-to-add ratio is the signature of a team continuously eliminating AI-generated code that fails review. The team is keeping pace with AI output velocity by pruning aggressively, retaining only the portion that meets standards.</td>
    </tr>
    <tr style="background-color: #fce8e6;">
      <td colspan="6">✗ <b>Antipattern:</b> AI coding assistants generate code roughly four times faster than humans by volume. A low delete-to-add ratio means that output is being kept regardless of quality, accumulating into a codebase nobody can review or audit, including the portions the published research found would be eliminated under structured oversight.</td>
    </tr>
    <tr>
      <td>L1.6</td>
      <td>Net-negative commit ratio</td>
      <td>Percentage of commits that delete more lines than they add</td>
      <td>≥15%</td>
      <td>5–15%</td>
      <td>&lt;5%</td>
    </tr>
    <tr style="background-color: #e6f4ea;">
      <td colspan="6">✓ <b>Good pattern:</b> Net-negative commits are the visible signature of architectural review actively removing AI-generated code that does not meet standards. They appear regularly in codebases where the team treats AI output as a draft to be filtered, not as a finished product.</td>
    </tr>
    <tr style="background-color: #fce8e6;">
      <td colspan="6">✗ <b>Antipattern:</b> Their absence means the team is keeping everything the AI produces, including the 90% that the published research shows would be eliminated under structured review. The natural experiment retained roughly 250,000 of 2.6 million AI-generated lines; everything else was deleted in net-negative commits.</td>
    </tr>
    <tr>
      <td>L1.7</td>
      <td>High-delete-ratio commit ratio</td>
      <td>Percentage of commits with delete/add ratio &gt;40%</td>
      <td>≥20%</td>
      <td>5–20%</td>
      <td>&lt;5%</td>
    </tr>
    <tr style="background-color: #e6f4ea;">
      <td colspan="6">✓ <b>Good pattern:</b> Deep cleanup commits where deletions dominate are how a structured AI-assisted team eliminates bloat the AI produced in earlier passes. The published research documents 175,881 lines of AI-generated bloat eliminated in 9 commits during a single month after the structured AI SDLC was introduced on a single codebase.</td>
    </tr>
    <tr style="background-color: #fce8e6;">
      <td colspan="6">✗ <b>Antipattern:</b> Their absence means the AI is producing code and nothing is removing it. Bloat from earlier generations stays in the codebase, compounds with each subsequent generation, and eventually contaminates the context the AI reads when generating new code.</td>
    </tr>
    <tr>
      <td>L1.8</td>
      <td>Test-to-production code ratio</td>
      <td>Lines of code in test files divided by lines of code in production files</td>
      <td>≥0.4</td>
      <td>0.1–0.4</td>
      <td>&lt;0.1</td>
    </tr>
    <tr style="background-color: #e6f4ea;">
      <td colspan="6">✓ <b>Good pattern:</b> Teams that ask the AI to generate tests alongside production code end up with substantial test coverage at no additional cost. The published natural experiment's structured condition produced 68 test files with 100% coverage, generated by the same AI that produced the production code.</td>
    </tr>
    <tr style="background-color: #fce8e6;">
      <td colspan="6">✗ <b>Antipattern:</b> Teams that ask the AI for production code without explicitly asking for tests end up with no tests at all. AI coding assistants skip tests by default. The published natural experiment's unstructured condition produced zero test files.</td>
    </tr>
    <tr>
      <td>L1.9</td>
      <td>Pre-commit hook configuration</td>
      <td>Presence and non-triviality of <code>.pre-commit-config.yaml</code>, <code>husky</code> config, or equivalent</td>
      <td>≥3 hooks active</td>
      <td>&lt;3 hooks</td>
      <td>Absent</td>
    </tr>
    <tr style="background-color: #e6f4ea;">
      <td colspan="6">✓ <b>Good pattern:</b> Pre-commit hooks intercept AI-generated code before it enters the repository, catching the AI's most common failure modes (formatting violations, type errors, exposed secrets, test failures) at the earliest possible point and before they compound through subsequent generations.</td>
    </tr>
    <tr style="background-color: #fce8e6;">
      <td colspan="6">✗ <b>Antipattern:</b> Without pre-commit hooks, every line the AI produces lands in the codebase regardless of formatting, type safety, secret exposure, or test status. The repository becomes the place where AI failure modes accumulate instead of the place where they are filtered out.</td>
    </tr>
    <tr>
      <td>L1.10</td>
      <td>CI/CD pipeline configuration</td>
      <td>Count of CI/CD pipeline definition files (<code>.github/workflows/*.yml</code>, <code>.gitlab-ci.yml</code>, <code>Jenkinsfile</code>, etc.)</td>
      <td>≥5</td>
      <td>1–4</td>
      <td>0</td>
    </tr>
    <tr style="background-color: #e6f4ea;">
      <td colspan="6">✓ <b>Good pattern:</b> CI/CD pipelines apply automated quality gates (testing, security scanning, integration validation) to every change, including changes generated by AI. The structured AI condition in the published natural experiment used 13 automated quality pipelines.</td>
    </tr>
    <tr style="background-color: #fce8e6;">
      <td colspan="6">✗ <b>Antipattern:</b> Without CI/CD pipelines, AI-generated code reaches production without the automated testing, security scanning, or integration validation that would catch the failure modes the published research documents. The unstructured AI condition used zero quality pipelines.</td>
    </tr>
    <tr>
      <td>L1.11</td>
      <td>Containerization configuration</td>
      <td>Presence of <code>Dockerfile</code>, <code>docker-compose.yml</code>, Helm charts, or Kubernetes manifests</td>
      <td>Present and parameterized</td>
      <td>Present and minimal</td>
      <td>Absent</td>
    </tr>
    <tr style="background-color: #e6f4ea;">
      <td colspan="6">✓ <b>Good pattern:</b> Containers ensure that AI-generated code runs identically in development, testing, and production, regardless of which environmental assumptions the AI absorbed from its training data. The container is the constraint that makes the AI's environment-coupling tendency harmless.</td>
    </tr>
    <tr style="background-color: #fce8e6;">
      <td colspan="6">✗ <b>Antipattern:</b> Without containers, AI generates against assumptions about the local environment that may not hold elsewhere. AI is particularly prone to this because its training data conflates many environments into a single statistical mean. The bugs that result surface only after deployment in places nobody can debug.</td>
    </tr>
    <tr>
      <td>L1.12</td>
      <td>Unreachable code ratio</td>
      <td>Lines of production code that nothing reaches, divided by total production lines of code. A line is flagged when it belongs to a definition no production or test file references by name, or to a statement no path can reach (after a <code>return</code>, <code>raise</code>, <code>break</code> or <code>continue</code> in the same block). A definition the analyzer cannot decide - reached only through reflection, a dynamic dispatch, or a name assembled at runtime - is excluded from the numerator and disclosed alongside the ratio, so the number reads as a lower bound rather than a verdict. Cross-check with a language-appropriate dead-code analyzer where one is available (<code>vulture</code>, <code>ts-prune</code>/<code>knip</code>, <code>staticcheck</code>, <code>error-prone</code>, Rust's <code>dead_code</code> lint, RuboCop's dead-code cops); the definition above is the measure, and the tool is a second opinion on it.</td>
      <td>&lt;1%</td>
      <td>1–5%</td>
      <td>&gt;5%</td>
    </tr>
    <tr style="background-color: #e6f4ea;">
      <td colspan="6">✓ <b>Good pattern:</b> A codebase with almost no unreachable code is a codebase where someone is continuously removing the functions, imports, branches, and exports that the AI generated and the team never called. Dead-code analyzers are cheap to run and cheap to act on, and a team that acts on them keeps the reviewable surface area of the codebase bounded to what is actually in use.</td>
    </tr>
    <tr style="background-color: #fce8e6;">
      <td colspan="6">✗ <b>Antipattern:</b> Unreachable code is the visible sediment of unsupervised AI generation. AI coding assistants routinely produce helper functions that are never called, imports that are never referenced, branches that are never taken, and exports that nothing consumes, because the AI optimizes for producing plausible code in the immediate vicinity of the prompt rather than for integrating with what already exists. When the team keeps all of it, the codebase fills with code that looks alive but is not, every reviewer wastes attention deciding whether each unreferenced symbol is a bug or a vestige, and the AI itself reads this sediment on the next generation and compounds the drift. Unreachable code above 5% is a high-confidence signal of pure-accumulation AI-assisted development.</td>
    </tr>
    <tr>
      <td>L1.13</td>
      <td>Near-duplicate code block ratio (fuzzy)</td>
      <td>Percentage of production LOC participating in a Type-2 or Type-3 clone class of ≥50 tokens. Reduce each file to the leaf tokens of its parse tree; replace every identifier with one symbol and every literal with one symbol, so a copy renamed throughout still matches; keep keywords, operators and punctuation as written, so the SHAPE of the code is what is compared. Any run of 50 consecutive symbols occurring at two or more distinct places is a clone, and every line those runs touch is a duplicated line. Comments are dropped, and a container literal spanning 12 lines or more is skipped as a data table, on the same ground L1.17 discounts one: a table with a row per case is not a pile of logic. Cross-check with <code>pmd cpd --ignore-identifiers --ignore-literals --minimum-tokens 50</code> or <code>jscpd --mode weak</code>; NiCad and SourcererCC go further into gapped Type-3 clones than this definition does.</td>
      <td>&lt;3%</td>
      <td>3–10%</td>
      <td>&gt;10%</td>
    </tr>
    <tr style="background-color: #e6f4ea;">
      <td colspan="6">✓ <b>Good pattern:</b> A codebase with near-zero fuzzy duplication is one where a reviewer has extracted recurring shapes into shared components and utility functions before merge. When the AI produces near-identical code across three screens, the reviewer collapses it into one component. The resulting codebase has one way to render an admin table, one way to validate a form, one way to paginate a list.</td>
    </tr>
    <tr style="background-color: #fce8e6;">
      <td colspan="6">✗ <b>Antipattern:</b> AI coding assistants generate near-duplicate blocks across different files because each generation is local to the prompt context and does not see what already exists elsewhere. The same admin-table shape appears on the Users screen, the Products screen, and the Orders screen, each with renamed identifiers, slightly different field sets, and slightly modified handlers. A human would extract one <code>&lt;AdminTable/&gt;</code> component; unsupervised AI accumulates three parallel near-copies. GitClear 2024 documented an 8x increase in copy-pasted code blocks under AI assistance without safeguards. Exact-match clone detectors miss this pattern entirely because the blocks are not byte-identical; fuzzy Type-2 detection (identifier and literal normalization) catches it, and Type-3 detection catches it even when the AI added or removed a few lines between the duplicates.</td>
    </tr>
    <tr>
      <td>L1.14</td>
      <td>Secret scan hit count</td>
      <td>Number of distinct credential-shaped strings in the current tree: a value matching a known provider's key format, a password inside a connection string, a private-key block, or a high-entropy assignment to a name that reads as a credential. Placeholder values and environment-variable references are excluded, and each distinct secret counts once however many times it occurs. Report the count split by where it sits - production code, test tree, documentation - because a fixture credential and a production credential are not the same finding, and report whether any was validated against its issuer, because the Slop band's second arm turns on a confirmed true positive. In a regulated enterprise any non-zero count is disqualifying. Cross-check with <code>gitleaks detect --no-git</code>, <code>trufflehog filesystem .</code> or <code>detect-secrets scan</code>.</td>
      <td>0</td>
      <td>1–2 (review for false positives)</td>
      <td>≥3, or any confirmed true positive</td>
    </tr>
    <tr style="background-color: #e6f4ea;">
      <td colspan="6">✓ <b>Good pattern:</b> Zero secrets committed. The team uses environment variables, a secrets manager, or a parameter store for all credentials. A secret scanner runs in CI and blocks merges that introduce credential-shaped strings. Pre-commit hooks catch the rest before they reach the remote.</td>
    </tr>
    <tr style="background-color: #fce8e6;">
      <td colspan="6">✗ <b>Antipattern:</b> AI coding assistants embed API keys, database passwords, and service-account tokens directly in example code, test fixtures, and configuration files without recognizing them as sensitive. Without a secret scanner in CI, the credentials land on the default branch and eventually leak publicly when the repository is cloned, shared, or exposed. The cost of a single leaked production credential in a regulated enterprise typically exceeds the cost of the entire audit. L1.14 is a Layer 1 indicator precisely because the check is fast and the consequence of missing it is severe.</td>
    </tr>
    <tr>
      <td>L1.15</td>
      <td>Type-escape density</td>
      <td>Count of type-system escape hatches per thousand lines of production code in statically-typed files. Escapes include: <code>any</code> in TypeScript (excluding declaration files), <code># type: ignore</code> in Python under mypy/pyright, <code>interface{}</code> and <code>any</code> in Go, <code>dynamic</code> in C#, raw types and <code>@SuppressWarnings("unchecked")</code> in Java, <code>Any</code> in Kotlin and Swift. For codebases with no statically-typed files, this indicator is recorded as <b>n/a</b> and does not contribute to the slop signal count.</td>
      <td>&lt;1 per KLOC</td>
      <td>1–5 per KLOC</td>
      <td>&gt;5 per KLOC</td>
    </tr>
    <tr style="background-color: #e6f4ea;">
      <td colspan="6">✓ <b>Good pattern:</b> In a statically-typed codebase the team resolves the real types rather than escaping the type system. When the AI produces code with <code>any</code> or <code>interface{}</code>, a reviewer replaces it with the actual type before merge. The type system remains a constraint that catches errors at compile time instead of at runtime.</td>
    </tr>
    <tr style="background-color: #fce8e6;">
      <td colspan="6">✗ <b>Antipattern:</b> AI coding assistants default to type-system escape hatches when they cannot figure out what the real types should be. The code compiles, the tests pass on happy paths, and the type errors surface at runtime in production instead of at compile time where they could be caught. A codebase with a high <code>any</code> density is a codebase where the team has silently abandoned the type system as a constraint and is now running a dynamically-typed program wearing a statically-typed costume.</td>
    </tr>
    <tr>
      <td>L1.16</td>
      <td>Trailing-whitespace density</td>
      <td>Percentage of lines in production files that contain trailing whitespace, computed by <code>grep -rEn ' +$' --include=*.{py,js,ts,tsx,jsx,go,java,rb,rs,cs,kt,swift,php} . | wc -l</code> divided by total production LOC. <b>This is not a code-quality indicator.</b> Trailing whitespace does not affect program behavior. What it signals is that AI output has been committed without passing through any human editor or any formatter.</td>
      <td>&lt;0.5%</td>
      <td>0.5–3%</td>
      <td>&gt;3%</td>
    </tr>
    <tr style="background-color: #e6f4ea;">
      <td colspan="6">✓ <b>Good pattern:</b> Near-zero trailing whitespace means every file has been touched by a human editor or by a formatter between generation and commit. Every modern editor (VS Code, JetBrains, Vim, Emacs) strips trailing whitespace on save by default, and every formatter (Prettier, Black, gofmt, rustfmt, rubocop) strips it as part of its standard rewrite. The file arriving on the default branch has been seen by at least one tool that cared enough to clean it up.</td>
    </tr>
    <tr style="background-color: #fce8e6;">
      <td colspan="6">✗ <b>Antipattern:</b> AI coding assistants routinely emit trailing whitespace on a significant fraction of the lines they generate. A codebase with high trailing-whitespace density is a codebase where the AI's raw output is being written directly to disk and committed without a human editor or a formatter ever touching the file. The trailing whitespace itself is harmless — it is the <i>staleness signal</i> that matters. A codebase where nobody has opened the file in an editor between "AI wrote it" and "commit lands on main" is a codebase where nobody has reviewed the AI output either, regardless of what PR comments claim. Treat high L1.16 as an unreviewed-AI-output marker, not as a whitespace complaint.</td>
    </tr>
    <tr>
      <td>L1.17</td>
      <td>God-file count (large-file concentration)</td>
      <td>Percentage of production files exceeding 1000 lines of code. Computed by <code>find . -type f \( -name '*.py' -o -name '*.js' -o ... \) -exec wc -l {} +</code> filtered to the production tree. Excludes generated files (parsers, schema bindings, lockfiles, migration archives). <strong>Counts LOGIC lines.</strong> A large data literal is discounted, because a god-file is a pile of logic: nobody hand-piles into a lookup table and it carries no merge-conflict surface. A large block of TYPE DECLARATIONS is not discounted, and is not meant to be. The remedy for it is the remedy for a large data table: separate data from code and import it. Mixing the two is fine in a 400-line file, and this rule only bites at god-file scale, which is exactly the scale at which separating them is the standard answer. So a file whose LOGIC exceeds a thousand lines is a god-file however much declaration sits beside it, and a file that crosses the line only because its type shapes live inline should move them to a sibling module rather than ask for a discount.</td>
      <td>&lt;0.5% of files</td>
      <td>0.5–2% of files</td>
      <td>&gt;2% of files, OR any file &gt;4000 lines</td>
    </tr>
    <tr style="background-color: #e6f4ea;">
      <td colspan="6">✓ <b>Good pattern:</b> A codebase with no god files is a codebase where every responsibility has a home proportional to its scope. When a file approaches 1000 lines the team splits it into smaller files before it becomes a hotspot that every feature touches. The file structure reflects the architecture; the architecture is visible from the file tree.</td>
    </tr>
    <tr style="background-color: #fce8e6;">
      <td colspan="6">✗ <b>Antipattern:</b> AI coding assistants add new code to the largest file they can find, because the largest file offers the most context for the next generation. Without a reviewer insisting on a split, the file grows indefinitely and every feature PR touches it, producing merge conflicts and making incremental refactoring impossible. A 4000-line file that receives edits in every other PR is the signature of a codebase where nobody has the authority or the time to refactor, and the AI is actively reinforcing the pattern by feeding the god file into its own next prompt.</td>
    </tr>
    <!-- L1.18 Mutable state ratio -->
    <tr style="background-color: #f5f5f5;">
      <td colspan="6"><b>L1.18 Mutable state ratio.</b> What percentage of the codebase's functions depend on state that lives outside their parameter list? This indicator measures the proportion of code that is subject to state-space explosion: the mathematical property that makes exhaustive testing of mutable-state systems impossible. A pure function's behavior is determined entirely by its inputs; a method on a mutable class depends on instance variables, inherited state, global state, and the order of prior method calls. The higher the mutable state ratio, the larger the portion of the codebase that is mathematically untestable regardless of test budget.</td>
    </tr>
    <tr>
      <td>L1.18</td>
      <td>Mutable state ratio</td>
      <td>Percentage of functions/methods in the production tree that reference <b>unbounded</b> mutable state outside their parameter list. Computed by static analysis: count functions whose body reads or writes variables not declared in the function's parameter list or local scope (instance variables, class variables, global variables, module-level mutable state). Language-specific: Python (<code>self.</code> references in method bodies), TypeScript/JavaScript (<code>this.</code> references and module-level <code>let</code>/<code>var</code>), Java/C# (field access, with or without <code>this.</code>, for every field not declared <code>final</code>, <code>readonly</code> or <code>const</code>), Go (receiver mutation), Rust (<code>self.</code> and <code>static mut</code>), Ruby (<code>@ivar</code> and <code>$global</code>). <b>Bound-aware:</b> a reference does not count when the finite-testability classifier (L1.18b) could bound the state it reaches, because a read keyed by a literal against a closed set is exhaustively testable and an unbounded accumulator is not. <b>No exclusion for I/O boundary functions</b> — route handlers, database adapters and CLI entry points are counted like any other function; see the note below.</td>
      <td>&lt;15% of functions</td>
      <td>15–40% of functions</td>
      <td>&gt;40% of functions</td>
    </tr>
    <tr style="background-color: #fff3cd;">
      <td colspan="6">⚠ <b>Withdrawn 2026-08-15: L1.18 does not exclude I/O boundary functions, and never did.</b> This row promised to exclude route handlers, database adapters and CLI entry points. What was implemented was a comment marker a function had to carry, which fired on no repository that had not adopted this project's private marker. Doing it by analysis was investigated on 2026-08-15 across seven trees (5,210 files, 77,576 functions) and the six pinned corpus repositories, and it cannot be done credibly. A route-handler decorator list reaches <b>7.2%</b> of production functions locally and <b>0%</b> of the corpus, and its match keys are variable names the developer invents (<code>router.get</code>, <code>app.get</code> and <code>test_app.get</code> all appear; <code>.patch</code> cannot separate <code>@router.patch</code> from <code>@mock.patch</code>). "Database adapter" has no syntactic signature at all: one measured module holds 53 adapters and 6 pure functions with nothing distinguishing them. "CLI entry point" had no marker whatsoever; every one was an undecorated <code>main()</code>. The framework-agnostic alternative, "the function calls an I/O primitive", measured <b>45% false positives</b> at usable recall and <b>0% recall</b> on that adapter module at usable precision, and it reads dict-lookup dispatch as I/O. Seven repositories belonging to one person use roughly <b>20 distinct web, ORM, HTTP and CLI frameworks</b>, one of them in-house; an enumeration that misses one moves a score by an amount decided by which framework the authors chose. The marker was deleted with the claim, because an exclusion a subject opts into is a lever a subject controls. <b>Consequence for the reader: L1.18 is inflated by the whole I/O layer of every codebase it measures. It is not "how much of the pure core is impure."</b> Full evidence in <code>research/amendments/amendment-2026-08-15-l1-18-corrected-ratio.md</code>.</td>
    </tr>
    <tr style="background-color: #e6f4ea;">
      <td colspan="6">✓ <b>Good pattern:</b> A codebase where the vast majority of functions are pure: input in, output out, no side effects. Mutable state is confined to a thin I/O boundary layer (route handlers, database adapters, message queue consumers) that is small, visible, and separately tested. The pure core is exhaustively testable. The I/O boundary is integration-tested. The two are clearly separated.</td>
    </tr>
    <tr style="background-color: #fce8e6;">
      <td colspan="6">✗ <b>Antipattern:</b> Methods that read and write instance variables, call other methods that mutate shared state, inherit behavior from parent classes that also mutate state, and produce different results depending on the order they are called. The number of possible states is combinatorially explosive. No finite test suite can cover the state space. The code is not "hard to test." It is mathematically untestable. The test coverage number on the dashboard measures line execution, not state-space coverage, and gives a false sense of security.</td>
    </tr>
    <tr style="background-color: #fff3cd;">
      <td colspan="6">⚡ <b>What low L1.18 structurally eliminates.</b> When L1.18 approaches zero, the following defect categories become structurally impossible — not merely unlikely, but mathematically ruled out by the absence of shared mutable state: <b>race conditions</b> (no shared state to race on), <b>order-dependent test failures</b> (pure functions are evaluation-order-independent), <b>stale-cache bugs</b> (no mutable cache to go stale), <b>side-effect interference</b> (no implicit writes for other functions to read), <b>null-from-uninitialized-state</b> (no dependence on initialization order), and <b>state-space explosion in testing</b> (behavior domains are finite products of parameter domains). L1.18 is therefore not only a structural metric but a <i>defect-category predictor</i>: an assessor who observes L1.18 = 5% can report that these defect categories are confined to at most 5% of the codebase's functions. This framing also explains the cognitive dimension: humans systematically fail at the conditional logic that mutable-state code demands (Wason 1966; fewer than 10% correct on first attempt), and low L1.18 eliminates the "escape hatches from formal reasoning" that enable those cognitive failures.</td>
    </tr>
    <!-- L1.19 Decision-space coverage -->
    <tr style="background-color: #f5f5f5;">
      <td colspan="6"><b>L1.19 Decision-space coverage.</b> Of the decisions in the codebase that ARE finitely enumerable (dispatch table keys, match/case arms, explicit enum branches, configuration flag values), what percentage are actually exercised by at least one test? This is the "honest" version of test coverage: not "what percentage of lines were executed" but "what percentage of the enumerable decision space has been verified." A dispatch table with 12 keys where tests exercise 12 of 12 has 100% decision-space coverage. An if/elif/else chain with 12 branches where tests exercise 8 of 12 has 67%. Standard line-coverage tools do not report this metric; it requires counting decision points and matching them against test invocations.</td>
    </tr>
    <tr>
      <td>L1.19</td>
      <td>Decision-space coverage</td>
      <td>Percentage of finitely enumerable decision points (dispatch table keys, match/case arms, enum variants used in branching, explicit configuration flag values) that are exercised by at least one test case. Computed by: (a) enumerate all dispatch tables, match statements, and enum-driven branches in the production tree; (b) count the total number of distinct keys/arms/variants; (c) run the test suite with branch-level tracing; (d) count how many of those keys/arms/variants were exercised. The ratio (d)/(b) is the decision-space coverage percentage.</td>
      <td>&gt;90%</td>
      <td>60–90%</td>
      <td>&lt;60%</td>
    </tr>
    <tr style="background-color: #e6f4ea;">
      <td colspan="6">✓ <b>Good pattern:</b> Every key in every dispatch table has a corresponding test. Every branch of every match/case statement is exercised. The team can state with confidence: "every decision this code can make has been tested." This is only achievable when the decision space is finite and enumerable, which is why Honest Code uses dispatch tables instead of open-ended conditional chains.</td>
    </tr>
    <tr style="background-color: #fce8e6;">
      <td colspan="6">✗ <b>Antipattern:</b> Line coverage is 85% but decision-space coverage is 40%. The test suite executes most lines of code but only exercises a fraction of the actual decisions the code can make. The remaining 60% of decision space is untested: the code will make those decisions in production, but nobody has verified what happens when it does. The team believes the code is well-tested because the coverage number is high. The coverage number is measuring the wrong thing.</td>
    </tr>
    <!-- L1.20 Test determinism -->
    <tr style="background-color: #f5f5f5;">
      <td colspan="6"><b>L1.20 Test determinism.</b> Do the tests produce the same results regardless of execution order? Pure-function tests are inherently order-independent because they share no mutable state. Tests that depend on mutable state (database fixtures, in-memory singletons, class-level setup/teardown) often produce different results when run in different orders, which means the test suite is not a reliable verification instrument. Test determinism is measurable by running the full test suite in randomized order multiple times and counting failures that appear only in some runs.</td>
    </tr>
    <tr>
      <td>L1.20</td>
      <td>Test determinism</td>
      <td>Run the full test suite 5 times with randomized execution order (e.g., <code>pytest --randomly-seed=random -x</code> for Python, <code>jest --randomize</code> for JS/TS, <code>mvn test -Dsurefire.runOrder=random</code> for Java). Count the number of runs where all tests pass. Test determinism = (passing runs) / 5. A suite where all 5 runs pass is fully deterministic. A suite where 3 of 5 runs pass has 60% determinism, indicating order-dependent tests.</td>
      <td>5/5 (100%)</td>
      <td>4/5 (80%)</td>
      <td>&lt;4/5 (&lt;80%)</td>
    </tr>
    <tr style="background-color: #e6f4ea;">
      <td colspan="6">✓ <b>Good pattern:</b> Every test passes regardless of execution order. Tests share no mutable state. Each test sets up its own context, runs a pure assertion, and tears down cleanly. The test suite is a reliable instrument: if it passes, the code is verified. If it fails, something is actually broken.</td>
    </tr>
    <tr style="background-color: #fce8e6;">
      <td colspan="6">✗ <b>Antipattern:</b> Tests pass when run in the default order but fail when randomized. Test A creates a database record that test B depends on. Test C sets a singleton value that test D reads. The test suite is not verifying the code; it is verifying one specific execution path through a shared mutable state space. A "passing" test suite that is order-dependent is not a passing test suite. It is a suite that has not yet been run in the order that reveals the failure.</td>
    </tr>
  </tbody>
</table>

**Calibration note.** All thresholds in this table are provisional and subject to empirical calibration (see Paper E). The initial values for L1.1 through L1.11 are seeded from a single structured-vs-unstructured comparison (the IDD codebase under structured AI SDLC vs the unstructured condition in the same paper). The "not healthy" middle band is anchored to industry-median codebases per GitClear 2025 (211M lines across Google, Microsoft, and Meta repositories), but this anchoring is informal, not statistically derived. L1.12 through L1.17 are seeded from industry tool defaults and GitClear 2024. L1.18 through L1.20 are the "Honest dimension" indicators measuring finite testability: mutable state ratio, decision-space coverage, and test determinism. Their initial thresholds are set by expert judgment based on Honest Code principles and will be replaced by empirically derived boundaries through the Paper A/Paper E validation cycle (clustering analysis and rework correlation on a 200-repository corpus). L1.18's 15/40 thresholds were set against the pre-2026-08-15 computation and have not been recalibrated since the four corrections of that date, which moved measured values by −4.9 to +12.7 points in a direction decided by the language and moved one corpus repository's band. Recalibration needs a corpus containing TypeScript, Go, Ruby and Rust repositories, which the current six-repository parity corpus does not. A codebase scoring in the slop column on eleven or more of the twenty indicators is considered to exhibit the unstructured-condition pattern with high confidence. Indicators that return **n/a** (typically L1.15 in a purely dynamically-typed codebase) are excluded from both the numerator and the denominator of the slop signal count.

### 3.3 Reporting format for Layer 1

The Layer 1 panel appears as page 1 of the Slop Report with this structure:

```
LAYER 1: QUANTITATIVE GIT-HISTORY PANEL
Repository: [name]
Branch: [branch]
Date range: [start] to [end]
Total commits in range: [count]
Total lines added in range: [count]
Total lines deleted in range: [count]

Indicator                              Value      Threshold band
L1.1  Doc-only commit ratio            X.X%       [Healthy / Not Healthy / Slop]
L1.2  Code-only commit ratio           X.X%       [Healthy / Not Healthy / Slop]
[...]
L1.11 Containerization                 [present]  [Healthy / Not Healthy / Slop]
L1.12 Unreachable code ratio           X.X%       [Healthy / Not Healthy / Slop]
L1.13 Fuzzy duplication ratio          X.X%       [Healthy / Not Healthy / Slop]
L1.14 Secret scan hits                 X          [Healthy / Not Healthy / Slop]
L1.15 Type-escape density              X.X/KLOC   [Healthy / Not Healthy / Slop / n/a]
L1.16 Trailing-whitespace density      X.X%       [Healthy / Not Healthy / Slop]
L1.17 God-file concentration           X.X%       [Healthy / Not Healthy / Slop]
L1.18 Mutable state ratio              X.X%       [Healthy / Not Healthy / Slop]
L1.19 Decision-space coverage          X.X%       [Healthy / Not Healthy / Slop]
L1.20 Test determinism                 X/5        [Healthy / Not Healthy / Slop]

Slop signal count: X of 20 indicators (or X of 19 if L1.15 is n/a)
Overall pattern: [Structured / Mixed / Unstructured]
```

The pattern classification at the bottom uses a simple rule: 0–4 slop signals = Structured, 5–10 = Mixed, 11+ = Unstructured. When L1.15 is recorded as n/a, the thresholds scale down proportionally to the denominator of nineteen. This classification appears in the Slop Report executive summary and is the single number a CPC member is most likely to remember.

### 3.4 Automation

## Note on L1.12, L1.13 and L1.14, revised 2026-08-19

These three used to be defined by naming a tool: run gitleaks, run a fuzzy clone detector, run a language-appropriate dead-code analyzer. That is not a definition, and it cost the instrument a whole indicator.

An assessor without the tool has nothing to run, so the indicator returns n/a, and n/a is excluded from both halves of the slop-signal fraction. L1.13 reported n/a on every repository this methodology has ever measured, both validation controls included, because jscpd was installed on none of the machines that ran it. A panel that says twenty indicators and measures nineteen is not a lenient panel; it is a panel with a column nobody has read.

Each row now states the algorithm precisely enough to reimplement, and names the tools as a cross-check on the result rather than as the source of it. The thresholds are unchanged, and so is what the indicators are for. A tool is still worth running where one is installed: two independent implementations disagreeing is a finding, and that is exactly what a cross-check is for.

A reference Bash script implementing the twenty indicators is intended to live at `research/slop-audit-layer1.sh`. The script takes a repo path and a date range and emits the panel as plain text. L1.1 through L1.8 are pure `git log` queries. L1.9 through L1.11 are file-existence and content checks. L1.12, L1.13 and L1.14 are parse-tree analyses over the production tree, each defined by its own row above and none of them shelling out. They used to name a tool instead of an algorithm, which is why L1.13 reported n/a on every repository this methodology had measured; see the note on those three below. L1.15 is a grep-and-count over the production tree with per-language patterns. L1.16 is a single `grep -rEn ' +$'` pipe to `wc -l`. L1.17 is a `find` and `wc -l` pipeline. L1.18 requires a language-specific static analysis pass counting functions that reference mutable state outside their parameter list. L1.19 requires enumerating dispatch table keys, match/case arms, and enum-driven branches, then cross-referencing against test-suite execution traces. L1.20 requires running the test suite 5 times with randomized order and counting passing runs. Building the script is on the TODO list at the end of this document. Automation is not required for the methodology to be runnable; an assessor can produce the full panel manually in approximately 60 to 90 minutes per repo. Automation reduces this to under fifteen minutes and eliminates transcription errors.

### 3.5 Limitations of Layer 1

Layer 1 currently measures *patterns of practice*. A codebase can have a healthy doc-to-code ratio and still produce inferior output if the documentation is wrong, the tests are vacuous, or the CI pipelines do nothing meaningful. Layer 1 is necessary but not sufficient: it identifies whether the *practice* of structured AI-assisted development is happening. It does not by itself prove the *outcome* is enterprise-ready. Layer 2 is what proves the outcome.

However, the relationship between Layer 1 indicators and quality outcomes is under active empirical investigation. Paper E tests whether L1.18 (mutable state ratio) predicts rework ratio across a 200-repository corpus. Paper G tests whether the full 19-indicator vector clusters into naturally occurring code health profiles that predict maintenance cost. If those correlations are confirmed, Layer 1 indicators become quantitative predictors of code quality --- not merely proxies for practice discipline --- and the boundary between Layer 1 (practice patterns) and Layer 2 (outcome evidence) narrows. Until that evidence is in, the conservative interpretation applies: Layer 1 measures practice, Layer 2 measures outcome.

This is why a Slop Report cannot consist of Layer 1 alone. The Layer 1 panel is the entry point. The Layer 2 scorecard is the body.

---

