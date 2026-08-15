"""L1.14, native: the secret-scan hit count, to the canon's definition.

Canon (03-layer1-indicators.md, L1.14 row): "Number of secrets detected by
`gitleaks detect --no-git` (or `trufflehog filesystem .`, or `detect-secrets scan`)
run against the current tree with the default ruleset. In a regulated enterprise any
non-zero count is disqualifying." Bands: 0 / 1-2 (review for false positives) /
>=3, or any confirmed true positive.

The canon's Slop band has two arms. The count arm is mechanical. The
"confirmed true positive" arm needs a human to confirm the credential is live, and
this scanner never validates a credential against its provider, so it reports the
count arm and discloses that the confirmation arm was not evaluated. Saying so is
the whole point; a scanner that silently drops half a threshold is lying by omission.

Pure assertions against temp repos, no mocks. Every fixture credential below is a
syntactically valid but fabricated value.
"""

import pathlib
import tempfile

from l1_analyzer import secret_scan


def _scan(files: dict[str, str]) -> dict:
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        for name, text in files.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(text)
        return secret_scan.analyze(root, "python")


def _rules(result: dict) -> set[str]:
    return {f["rule"] for f in result["findings"]}


# --- the bands, which are the canon's ------------------------------------------------

def test_zero_hits_is_healthy():
    r = _scan({"app.py": "TOKEN = os.environ['TOKEN']\n"})
    assert r["value"] == 0 and r["band"] == "Healthy"


def test_one_hit_is_not_healthy_and_three_is_slop():
    assert secret_scan._band_for(0) == "Healthy"
    assert secret_scan._band_for(1) == "Not Healthy"
    assert secret_scan._band_for(2) == "Not Healthy"
    assert secret_scan._band_for(3) == "Slop"


def test_the_confirmed_true_positive_arm_is_disclosed_as_not_evaluated():
    r = _scan({"app.py": "x = 1\n"})
    assert r["confirmed"] == "not evaluated"
    assert "not evaluated" in r["details"]


# Planted credentials are assembled from parts so no committed file contains a literal
# that matches a provider pattern. GitHub push protection blocked a push on the Stripe key
# below, which is the correct behaviour of a real secret scanner meeting a test fixture for
# a secret scanner. The value the scanner under test sees is unchanged; only the file on
# disk differs.
AWS_KEY = "AKIA" + "2E0RTQ4KJ7X9WZ1P"
GH_TOKEN = "ghp_" + "q7Rn2Xk9Lm4Pz8Tv1Bd6Hs3Jw5Ny0Cf8Ge2"
SLACK_TOKEN = "xoxb" + "-2847361920-4827361958264-Kj8Nm2Pq7Rt4Vw9Xz1Bc5Df"
STRIPE_KEY = "sk_" + "live_" + "51Hq8Nm2Pq7Rt4Vw9Xz1Bc5Df3Gh"


# --- provider rules -----------------------------------------------------------------

def test_flags_an_aws_access_key_id():
    r = _scan({"conf.py": f'AWS_ACCESS_KEY_ID = "{AWS_KEY}"\n'})
    assert r["value"] == 1 and _rules(r) == {"aws-access-key-id"}
    assert r["findings"][0]["file"] == "conf.py" and r["findings"][0]["line"] == 1


def test_flags_a_github_personal_access_token():
    r = _scan({"deploy.sh": f'export GH_TOKEN={GH_TOKEN}\n'})
    assert _rules(r) == {"github-token"}


def test_flags_a_slack_bot_token_and_a_stripe_live_key():
    r = _scan({"a.py": f'SLACK = "{SLACK_TOKEN}"\n', "b.py": f'STRIPE = "{STRIPE_KEY}"\n'})
    assert _rules(r) == {"slack-token", "stripe-api-key"}


def test_flags_a_private_key_block_only_when_a_body_follows():
    body = "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7VJTUt9Us8cKj"
    r = _scan({"key.pem": f"-----BEGIN RSA PRIVATE KEY-----\n{body}\n-----END RSA PRIVATE KEY-----\n"})
    assert _rules(r) == {"private-key"}


def test_a_private_key_header_mentioned_in_prose_is_not_a_secret():
    # This module's own documentation says the words. A scanner that charges a
    # finding for describing its own rule is measuring itself.
    r = _scan({"README.md": "Never commit a -----BEGIN RSA PRIVATE KEY----- block.\n"})
    assert r["value"] == 0


def test_flags_a_password_inside_a_database_connection_string():
    r = _scan({"settings.py": 'DB = "postgresql://svc:8Kd2Nq7Rt4Vw9Xz1@db.internal:5432/app"\n'})
    assert _rules(r) == {"connection-string-password"}


def test_flags_a_high_entropy_value_assigned_to_a_credential_shaped_name():
    r = _scan({"conf.py": 'API_SECRET = "9Xq4Zt7Lm2Rv8Kd3Nb6Hs1Jw5Yc0Pf"\n'})
    assert _rules(r) == {"generic-credential"}


# --- the cases a naive scanner gets wrong: these must NOT be flagged ----------------

def test_an_environment_lookup_is_not_a_secret():
    r = _scan({"a.py": 'API_KEY = os.environ["API_KEY"]\n',
               "b.js": 'const apiKey = process.env.API_KEY;\n',
               "c.yml": 'api_key: ${API_KEY}\n'})
    assert r["value"] == 0


def test_a_placeholder_is_not_a_secret():
    r = _scan({"a.py": 'API_KEY = "your-api-key-here"\n'
                       'PASSWORD = "changeme"\n'
                       'SECRET = "xxxxxxxxxxxxxxxxxxxx"\n'
                       'TOKEN = "<REDACTED>"\n'})
    assert r["value"] == 0


def test_a_low_entropy_english_value_is_not_a_secret():
    r = _scan({"a.py": 'PASSWORD_FIELD_LABEL = "enter your password"\n'})
    assert r["value"] == 0


def test_a_uuid_assigned_to_a_credential_name_is_not_counted_as_a_generic_secret():
    r = _scan({"a.py": 'TENANT_TOKEN = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"\n'})
    assert r["value"] == 0


# --- disclosure ---------------------------------------------------------------------

def test_a_finding_never_prints_the_credential():
    r = _scan({"conf.py": f'AWS_ACCESS_KEY_ID = "{AWS_KEY}"\n'})
    excerpt = r["findings"][0]["excerpt"]
    assert AWS_KEY not in excerpt
    assert excerpt.startswith("AKIA") and "20 chars" in excerpt


def test_hits_in_the_test_tree_are_counted_but_disclosed_separately():
    # gitleaks --no-git scans the whole tree, so the count includes tests. The split
    # is disclosed, because a fixture credential and a production credential are not
    # the same finding to an auditor.
    r = _scan({"tests/test_auth.py": f'KEY = "{AWS_KEY}"\n'})
    assert r["value"] == 1
    assert r["counts"]["in_tests"] == 1
    assert "test" in r["details"]


def test_binary_and_vendored_files_are_skipped_and_disclosed():
    # A clean production file sits beside the vendored one on purpose. Without it the
    # fixture's only file is skipped, the scan reads nothing, and this asserted a zero the
    # scanner had no basis for - the test was demonstrating the false pass it was written
    # to rule out. The zero below is now over a file that was actually read.
    r = _scan({"node_modules/pkg/a.js": f'const k = "{AWS_KEY}";\n',
               "app.py": "KEY = os.environ['KEY']\n"})
    assert r["value"] == 0 and r["band"] == "Healthy"
    assert r["files_scanned"] == 1


def test_a_tree_of_nothing_but_vendored_files_refuses_rather_than_reporting_zero():
    r = _scan({"node_modules/pkg/a.js": f'const k = "{AWS_KEY}";\n'})
    assert r["files_scanned"] == 0
    assert r["value"] == "n/a" and r["band"] == "n/a"


# --- the three defects the real-repository run exposed -------------------------------

def test_a_default_service_password_in_a_connection_string_is_not_a_secret():
    # `postgresql://postgres:postgres@localhost` is a docker-compose default. It was the
    # most common false positive across the five validation repositories, 30 of them.
    r = _scan({"conf.py": 'TEST_DB = "postgresql://postgres:postgres@localhost:5432/app_test"\n',
               "other.py": 'D = "mysql://root:root@127.0.0.1:3306/app"\n'})
    assert r["value"] == 0


def test_one_credential_repeated_is_one_secret_not_seventy_five():
    # The canon bands at 0 / 1-2 / >=3 distinct secrets. One key logged down 75 lines is
    # one leaked key; counting occurrences put a repository three bands away from true.
    line = f'key = "{AWS_KEY}"\n'
    r = _scan({"app.py": line * 75})
    assert r["value"] == 1 and r["band"] == "Not Healthy"
    assert r["findings"][0]["occurrences"] == 75
    assert r["counts"]["occurrences"] == 75


def test_an_unquoted_credential_in_a_tracked_dotenv_is_found():
    """The gap the gitleaks comparison exposed. cardz commits its `.env`, and
    `AUTH0_CLIENT_SECRET=xGLoLZGEXF_...` carries no quotes, so the quoted-literal rule
    could not see it. gitleaks reported it and this did not."""
    r = _scan({".env": "AUTH0_CLIENT_SECRET=xGLoLZGEXF_0oUpHyV9_p0I87sS4JKe1cWbuGLno\n"
                       "PORT=8080\n"
                       "DEBUG=true\n"})
    assert r["value"] == 1 and _rules(r) == {"generic-credential"}


def test_an_unquoted_rule_does_not_fire_inside_source_code():
    # Source goes through the string-literal path, so `token = someIdentifier` is a
    # variable read, not a committed credential.
    r = _scan({"a.py": "auth_token = resolve_token_from_vault_service\n"})
    assert r["value"] == 0


def test_a_gitignored_file_is_not_scanned_because_it_is_not_committed():
    """The canon's antipattern is credentials that "land on the default branch". A
    gitignored `.env` is the auditor's own workstation, not the artifact."""
    import subprocess
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        (root / ".gitignore").write_text(".env\n")
        (root / ".env").write_text(f'AWS = "{AWS_KEY}"\n')
        (root / "app.py").write_text(f'GH = "{GH_TOKEN}"\n')
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        result = secret_scan.analyze(root, "python")
    assert {f["rule"] for f in result["findings"]} == {"github-token"}
    assert "git-tracked files only" in result["details"]


def test_a_non_git_directory_is_scanned_whole_and_says_so():
    r = _scan({"app.py": f'GH = "{GH_TOKEN}"\n'})
    assert r["value"] == 1
    assert "not a git working copy" in r["details"]
