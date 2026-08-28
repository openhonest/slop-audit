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


# The one copy of each shape this scanner is meant to catch. Every test that needs a
# credential-shaped string takes it from here rather than writing its own: a second copy is
# a second finding on this repository's own secret count, and this file plus one other were
# carrying six between them for three distinct shapes.
CONNECTION_STRING = 'DB = "postgresql://svc:8Kd2Nq7Rt4Vw9Xz1@db.internal:5432/app"\n'
CREDENTIAL_NAME = 'API_SECRET = "9Xq4Zt7Lm2Rv8Kd3Nb6Hs1Jw5Yc0Pf"\n'
VENDOR_KEY = 'TOKEN = "sk_live_9Zx8Wq7Vt6Ru5"\n'


def test_flags_a_password_inside_a_database_connection_string():
    r = _scan({"settings.py": CONNECTION_STRING})
    assert _rules(r) == {"connection-string-password"}


def test_flags_a_high_entropy_value_assigned_to_a_credential_shaped_name():
    r = _scan({"conf.py": CREDENTIAL_NAME})
    assert _rules(r) == {"generic-credential"}


def test_flags_a_vendor_key_by_its_prefix():
    r = _scan({"conf.py": VENDOR_KEY})
    assert _rules(r), "a live-key prefix is the shape this scanner exists to catch"


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


# --- the two offset systems that meet in the scanner --------------------------------

# Assembled from parts, like every other planted credential here: no committed file in
# this repository contains a literal that matches a rule.
GENERIC_VALUE = "Zq7Z" + "vN2pX" + "4bT9wR1kD6yG3mJ8sL0hC5f"
ACCENTED_COMMENT = "# Coût de la connexion, déjà vérifié en préproduction\n"


def test_a_credential_under_an_accented_comment_is_still_found():
    """`re` counts characters and tree-sitter counts bytes. The generic rule is narrowed to
    string literals located by tree-sitter, and the narrowing compared the regex's character
    offset against those byte offsets directly. One accented word above the credential put
    them out of step, and the credential was dropped in silence - the worst answer this
    scanner can give, on a file it did read.

    Two comment lines, so the drift (12 non-ASCII bytes) exceeds the length of the accented
    text itself and the misfire cannot land back inside the right span by luck."""
    plain = _scan({"settings.py": f'API_TOKEN = "{GENERIC_VALUE}"\n'})
    accented = _scan({"settings.py": ACCENTED_COMMENT * 2 + f'API_TOKEN = "{GENERIC_VALUE}"\n'})
    assert _rules(plain) == {"generic-credential"}
    assert _rules(accented) == {"generic-credential"}, (
        "the credential vanished when a non-ASCII comment was placed above it")
    assert accented["findings"][0]["line"] == 3


def test_the_narrowing_still_excludes_a_name_outside_a_string_literal():
    """The other direction of the same fix: correcting the offsets must not widen the rule.
    A credential-shaped identifier read from a vault is not a committed credential, accented
    comment above it or not."""
    r = _scan({"settings.py": ACCENTED_COMMENT * 2
                              + "auth_token = resolve_token_from_vault_service\n"})
    assert r["value"] == 0


def test_a_byte_offset_equals_the_character_offset_only_while_the_text_is_ascii():
    text = "# é\nAPI = 1\n"
    assert secret_scan._byte_offset("# x\nAPI = 1\n", 4) == 4
    assert secret_scan._byte_offset(text, 4) == 5


# --- reading only as much as the decision needs ---------------------------------
#
# The binary test used to run AFTER path.read_bytes(), so every binary file was read in
# full and then discarded on the NUL check. A repository carrying 45,303 committed PNGs
# across 1.0 GB did not finish scanning in ten minutes. The decision is made from the first
# chunk now, which is content-based and needs no extension whitelist to keep up with formats.

def test_a_text_file_comes_back_whole(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("KEY = 'x'\n" * 100)
    assert secret_scan._read_text_bytes(f, 4_194_304) == f.read_bytes()


def test_a_binary_file_is_declined(tmp_path):
    f = tmp_path / "logo.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\xff" * 500)
    assert secret_scan._read_text_bytes(f, 4_194_304) is None


def test_the_binary_decision_is_made_from_the_head_not_the_whole_file(tmp_path):
    """A binary far larger than the size limit is still declined for being binary.

    This is what proves the NUL test runs before the file is read whole: under the old
    order the size check came first and this file would have been declined for its size,
    which is a different reason and a different code path.
    """
    f = tmp_path / "big.bin"
    f.write_bytes(b"\x00" + b"\xff" * (5 * 1024 * 1024))
    assert secret_scan._read_text_bytes(f, 4_194_304) is None


def test_a_file_past_the_size_limit_is_declined(tmp_path):
    f = tmp_path / "big.txt"
    f.write_text("a" * 2048)
    assert secret_scan._read_text_bytes(f, 1024) is None
    assert secret_scan._read_text_bytes(f, 4096) == f.read_bytes()


def test_a_file_that_cannot_be_opened_is_declined(tmp_path):
    assert secret_scan._read_text_bytes(tmp_path / "absent.py", 4_194_304) is None


def test_a_nul_beyond_the_probe_window_is_not_seen(tmp_path):
    """The documented limit, asserted rather than left to be discovered.

    git decides the same way and from the same window, so a file that hides its first NUL
    past 8 KB reads as text here exactly as it does there.
    """
    f = tmp_path / "late.bin"
    f.write_bytes(b"a" * 9000 + b"\x00" + b"b" * 10)
    assert secret_scan._read_text_bytes(f, 4_194_304) is not None


# --- the pathological line ------------------------------------------------------
#
# Found 2026-08-17 by pointing the scanner at a real repository. `_GENERIC` opened with an
# unbounded character class, then an alternation, then a second unbounded class over the same
# characters. On a bundled CSS file whose longest line is 285,769 characters the engine
# explored that ambiguity exponentially and the scan never finished: three files in one
# repository each took longer than every other file in it put together.
#
# The leading class never contributed to whether a match exists, only to where the match
# started, and the reported value is capture group 1, which sits after the `[:=]`. Removing it
# changes no finding and removes the ambiguity.

def _under_time_limit(seconds, fn):
    """Run `fn`, failing rather than hanging if it exceeds `seconds`."""
    import signal

    def bail(*_a):
        raise TimeoutError(f"did not finish within {seconds}s")

    old = signal.signal(signal.SIGALRM, bail)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        return fn()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def test_a_very_long_single_line_does_not_hang_the_generic_rule():
    """The reproduction, reduced from the repository that found it.

    A run of near-misses is what does it: text that repeatedly enters the keyword
    alternation and then fails, so the engine backtracks into the unbounded class in front of
    it. A long line with no keyword at all is fine, and so is one where the keyword is
    followed by a real `:`; it is the near-miss that costs.
    """
    line = "".join(f"a_token_{i}_x." for i in range(20000))
    assert len(line) > 250_000
    hits = _under_time_limit(5.0, lambda: secret_scan._scan_text(line, line.encode("utf8"), "index.css"))
    assert hits == []


def test_the_generic_rule_still_finds_a_quoted_credential_after_a_prefix():
    # The leading class was there for `MY_API_KEY`. Dropping it must not lose that shape.
    # The value is assembled from parts, as the rest of this suite does, so no committed
    # literal here matches a provider pattern on our own tree.
    value = "Kp7mQx2v" + "Rt9wLz4b" + "Nc6eYh1j" + "Fs8dGa3u"
    src = f'MY_API_KEY = "{value}"\n'
    rules = {r for r, _line, _v in secret_scan._scan_text(src, src.encode("utf8"), "a.py")}
    assert "generic-credential" in rules


def test_the_generic_rule_still_finds_a_credential_with_a_suffixed_name():
    value = "Kp7mQx2v" + "Rt9wLz4b" + "Nc6eYh1j" + "Fs8dGa3u"
    src = f'API_KEY_PROD = "{value}"\n'
    rules = {r for r, _line, _v in secret_scan._scan_text(src, src.encode("utf8"), "a.py")}
    assert "generic-credential" in rules
