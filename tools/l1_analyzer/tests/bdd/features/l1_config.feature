Feature: L1.9-L1.11 Configuration and pipeline discipline
  Presence of pre-commit, CI/CD, and containerization as automated gates
  that intercept AI output.

  Scenario: 5+ active pre-commit hooks is Healthy
    Given a repo with .pre-commit-config.yaml containing 5 hooks
    When I compute L1.9
    Then L1.9 band is Healthy

  Scenario: No .pre-commit-config.yaml is Slop
    Given a repo with no pre-commit config
    When I compute L1.9
    Then L1.9 band is Slop

  Scenario: 5+ CI workflow files is Healthy
    Given a repo with 6 .github/workflows/*.yml files
    When I compute L1.10
    Then L1.10 band is Healthy

  Scenario: Dockerfile + docker-compose is Healthy
    Given a repo with Dockerfile and docker-compose.yml that are parameterized
    When I compute L1.11
    Then L1.11 band is Healthy
