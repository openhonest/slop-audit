### 4.12 Dependency injection

**Lifecycle category.** Software architecture.

**Definition.** Dependency injection is the application's mechanism for separating *what* a component does from *what it depends on*, by passing dependencies in from outside rather than constructing them internally. A mature dependency injection system uses explicit registration (the application has a single place where service implementations are mapped to interfaces or contracts), supports testability (production dependencies can be replaced with test doubles without modifying the consuming code), manages lifecycles correctly (singletons stay singleton, request-scoped objects stay request-scoped, transient objects are created fresh on each access), and uses contracts (interfaces, protocols, abstract classes, type signatures) rather than concrete classes as the dependency declarations. The opposite is the application that uses `new ConcreteClass()` everywhere, has hidden global state via singletons-as-globals, and cannot be tested without instantiating the entire dependency graph.

**Industry threshold.** Explicit service registration with lifecycle management, contract-based dependencies (interfaces, protocols, type signatures), testability via dependency replacement. Drawn from IEEE research on dependency injection's impact on coupling (Coupling Between Object classes vs Dynamic CBO), MDPI Computers Journal quantitative studies on DI maintainability impact, and industry consensus that DI is a baseline expectation for any application large enough to need automated testing.

**Source citations (per the Wasserman 2026 working analysis, Appendix C).**
- IEEE: DI impact on coupling (CBO vs DCBO metrics) — Tier 3
- MDPI Computers Journal: quantitative DI impact studies — Tier 3
- Keyhole Software Enterprise Technology Adoption Survey 2026 — Tier 4 (vendor)
- Stack Overflow Developer Survey 2025 — Tier 4 (vendor)

**Compliance framework mappings.**
- **NIST SP 800-53:** SA-11 (Developer Security Testing and Evaluation) — DI is required for testability
- **ISO/IEC 25010:** Maintainability characteristics (modularity, reusability, analyzability, modifiability, testability)

#### Layer 2 form (mechanical / artifact-based)

**Layer 2 inspection procedure.**

1. **Locate the dependency graph.** Determine how the application wires its dependencies. Common patterns: an explicit DI container registration file (`container.py`, `ServiceCollection` configuration in ASP.NET, `app.module.ts` in NestJS, `@Configuration` classes in Spring), framework convention (FastAPI dependency injection via `Depends()`, Django settings-based wiring), or no formal mechanism (every class instantiates its own dependencies inline).
2. **Inspect the registration explicitness.** Determine whether services are registered explicitly (the application has a single place where the assessor can read the entire dependency graph) or implicitly (services are constructed wherever they happen to be needed).
3. **Count the `new ConcreteClass()` instances inside method bodies.** Use `grep` or equivalent to find places where one class instantiates another concrete class inside a method body (not in tests, not in factories, not in DI configuration). Mature codebases have very few of these. Codebases without DI have hundreds.

#### Layer 3 form (qualitative specified judgment)

**Layer 3 inspection procedure.** Five markers, each scored present / partial / absent. (DI gets 5 markers because it has more architectural nuance than other dimensions.)

**Marker 1: Dependencies are declared as contracts (interfaces, protocols, type signatures), not concrete classes.** Sample 5 service classes with constructor parameters. For each parameter, check whether the type is an interface/protocol/abstract type or a concrete class. Constructor parameters declared as concrete classes (`public UserService(SqlUserRepository repo)`) prevent substitution; parameters declared as interfaces (`public UserService(IUserRepository repo)`) enable it. Present = 4 or 5 of 5 sampled services use contracts; partial = 2 or 3 do; absent = 0 or 1 do.

**Marker 2: The DI container registration is in a single discoverable location.** A new developer joining the team should be able to find the DI configuration in one place and read it to understand the entire dependency graph. The mature pattern has one or a few module configuration files in a known location. The immature pattern has registrations scattered across many files with no central index, or a "god container" file with 400+ services and no organization. Present = single discoverable location, organized; partial = multiple files but with a clear convention; absent = scattered with no convention, or god container.

**Marker 3: Lifecycles are correctly applied (singletons stateless, scoped per request, transients fresh).** Find singleton services and check whether they hold mutable state. A stateless singleton (a database connection pool, a configuration provider, a logger) is fine. A stateful singleton (a cache that holds per-user data, a request context that persists between requests) is a bug magnet. The mature pattern uses singletons only for stateless or thread-safe-mutable services, scoped for per-request state, and transients for cheap stateless services. Present = lifecycles correctly applied across sampled services; partial = mostly correct with one or two stateful-singleton bugs; absent = stateful singletons everywhere or no clear scope discipline.

**Marker 4: Tests substitute dependencies via constructor injection or container override, not via monkey-patching globals.** Open the test suite. Find a test that exercises a service with dependencies. Determine how the test substitutes those dependencies with test doubles. Constructor injection (the test instantiates the service directly with mock dependencies) and container override (the test reconfigures the DI container to use mocks) are mature patterns that prove DI is actually working. Monkey-patching global state (`@patch('module.GLOBAL_DB', test_db)`) is the antipattern that proves DI is not actually being used in production code. Present = tests use constructor injection or container override; partial = some tests do, others monkey-patch; absent = all tests monkey-patch global state.

**Marker 5: No service-locator antipattern.** Look for code that calls a global method to fetch services on demand from inside method bodies (`ServiceLocator.Get<IUserRepository>()`, `container.resolve("user_repo")`, `app.di.get("user_repo")`). The service locator pattern is DI's antipattern: it provides the appearance of dependency injection while hiding the dependency graph from the consuming code. Mature applications use constructor injection or framework-managed injection, not service locator. Present = no service-locator usage in sampled code; partial = a few legacy uses but no new code uses the pattern; absent = service locator is the dominant pattern.

**Layer 3 scoring rule for the dimension.** Score Layer 3 *Present* if 4 or 5 markers score Present. *Partial* if 2 or 3 markers score Present. *Absent* if 0 or 1 markers score Present.

#### Layer 4 questions (deferred to Phase 1)

- Are the abstractions at the right level? (A DI container can use interfaces correctly but still have interfaces at the wrong granularity, producing "interface explosion" with 200 interfaces that each have one implementation.)
- Are the dependencies pointing in the right direction (high-level depending on low-level vs. inverted), as the Dependency Inversion Principle describes?
- Are the contracts well-shaped, or do they leak implementation details that defeat the abstraction?
- Would the dependency graph survive a major architectural change (replacing the database, changing the deployment topology) without breaking widely?

**Combined scoring rubric.**

- ***Present.*** Layer 2 form passes (DI mechanism exists, explicit registration, few `new ConcreteClass()` inside method bodies) AND Layer 3 form scores Present (4 or 5 of 5 markers).
- ***Partial.*** Layer 2 form passes but Layer 3 has gaps (2 or 3 markers Present); OR Layer 2 is Partial (DI exists but with significant scattering) but Layer 3 scores Present.
- ***Absent.*** Layer 2 form fails (no DI mechanism, every class instantiates its own dependencies inline, dependency graph is invisible); OR Layer 2 form passes but Layer 3 scores Absent.

**Common failure modes.**

- **`new` everywhere.** The application constructs concrete dependencies inline at every usage site. Changing an implementation requires editing every usage site.
- **Singleton-as-global with mutable state.** A `ConfigManager` class with a static `Instance` property and mutable per-user fields. Two concurrent requests can read each other's state. The class is not actually a singleton in the architectural sense; it is a global variable wearing a singleton's clothes.
- **Service locator antipattern.** Code that calls `ServiceLocator.Get<IUserRepository>()` inside a method body instead of receiving the dependency through the constructor. The dependency is hidden from the consuming code's interface, which makes the consuming code untestable in isolation.
- **Concrete-class dependencies.** Constructor parameters declared as concrete classes (`public UserService(SqlUserRepository repo)`) instead of interfaces (`public UserService(IUserRepository repo)`). The dependency cannot be substituted without modifying the service's signature.
- **God container.** A single DI container registration file with 400+ services, no organization, no grouping, no comments. The container exists but reading it is impossible.
- **Tests that monkey-patch globals.** Tests that don't use DI to substitute dependencies but instead modify global state via `import unittest.mock; mock.patch('module.GLOBAL_DB', test_db)`. The tests work but they reveal that DI is not actually being used in production code.
- **Deep class hierarchies as DI substitute.** Inheritance used to provide "default" implementations of dependencies, with subclasses overriding methods to substitute for testing. The application has an `AbstractUserService` with 14 protected methods, each subclassed for testing. This is DI implemented via inheritance, which produces all the brittleness of inheritance plus none of the benefits of injection.
- **Container that is itself a global.** A DI container that exists as a module-level global, with services fetched from it via `container.get(...)` calls scattered throughout the codebase. The container provides registration but the consumption pattern is service locator, not injection.

**Example presence (TypeScript / NestJS).** A NestJS application with explicit module configuration. Each feature module (`UserModule`, `OrderModule`, `BillingModule`) has a `@Module()` decorator that lists its providers, controllers, and imports. Services are declared as classes with `@Injectable()` decorators and constructor-injected dependencies. Interfaces define the contracts: `interface UserRepository { findById(id: string): Promise<User>; save(user: User): Promise<void>; }`. The module binds the interface to a concrete implementation via `{ provide: 'UserRepository', useClass: PostgresUserRepository }`. Tests use `Test.createTestingModule()` to substitute implementations: `.overrideProvider('UserRepository').useClass(InMemoryUserRepository)`. Singletons (database connection pool, configuration service, logger) are explicitly scoped via `@Injectable({ scope: Scope.DEFAULT })`. Per-request services (the current user context, the current tenant context) are scoped via `@Injectable({ scope: Scope.REQUEST })`. The application has 47 services across 12 modules and the entire dependency graph is discoverable by reading the module files in 30 minutes.

**Example absence (Java / no DI).** A Java application that predates Spring (or any other DI framework) and was never refactored. Every class instantiates its own dependencies in the constructor: `public UserService() { this.repo = new MysqlUserRepository(new MysqlConnectionPool(...)); this.email = new SmtpEmailSender("smtp.gmail.com", 587); }`. The `MysqlConnectionPool` is a singleton-as-global accessed via `MysqlConnectionPool.getInstance()` which lazily creates the pool the first time it is called. Tests cannot run in CI because the test code instantiates `UserService` which instantiates `MysqlUserRepository` which calls `MysqlConnectionPool.getInstance()` which tries to connect to a real MySQL database, which is not available in the CI environment. The team's workaround is to skip 80% of the test suite in CI and run it manually on developer laptops. The codebase has 312 places where `new ConcreteClass()` is called inside another class's method, each one a barrier to testability and substitution.

**Time budget.** Approximately 75 to 90 minutes for an experienced assessor: 20 to 30 minutes for the Layer 2 inspection, 50 to 60 minutes for the Layer 3 marker assessment (5 markers, slightly more time per marker because the architectural judgment is more nuanced).

---

