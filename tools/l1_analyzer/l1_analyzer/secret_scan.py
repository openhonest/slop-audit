"""L1.14 secret-scan hit count, implemented natively.

Canon (03-layer1-indicators.md, L1.14): "Number of secrets detected by
`gitleaks detect --no-git` (or `trufflehog filesystem .`, or `detect-secrets scan`)
run against the current tree with the default ruleset. In a regulated enterprise any
non-zero count is disqualifying." Bands: 0 Healthy, 1-2 Not Healthy (review for false
positives), >=3 or any confirmed true positive Slop.

The Slop band has two arms and this scanner can only evaluate one. The count arm is
mechanical. The confirmation arm needs someone to present the credential to its issuer
and see whether it is live, which this never does: no network call is made and no
credential is validated. `confirmed` therefore reads "not evaluated" and the details
say so. A scanner that silently dropped half a published threshold would be lying by
omission, which is the shape this instrument exists to name.

Two rule families:

  PROVIDER rules match a credential by its issuer's own prefix and length (AKIA..., ghp_...,
  xoxb-..., a PEM block). They run over raw text, the way gitleaks does, because such a
  token is unambiguous wherever it sits, including in a comment.

  The GENERIC rule matches a high-entropy literal assigned to a credential-shaped name.
  It runs only inside string literals, located with tree-sitter, in all nine supported
  languages. A credential-shaped word in an identifier, a type name, or a bare regular
  expression is not a committed credential, and charging one is the false positive that
  makes an auditor stop believing the number.

A scan that opened no file refuses instead of reporting zero. Zero hits over zero files is
the same number as zero hits over a thousand, and `band: Healthy` is the field a reader
looks at, so the count arm read as a clean bill of health on a repository the scanner never
opened. It is reachable: this scanner reads the git index rather than the filesystem, so a
tree whose files are all untracked - a fresh checkout before the first commit, or a
repository whose tracked paths all sit under an ignored directory - excludes every file
before it is read. Of all eighteen indicators this is the worst one to fabricate, because
its whole job is finding live credentials and the answer it fabricates is "none".

`files_scanned` is the denominator and it needs no second reading to check it, which is
where this differs from the thread-safety meter beside it. Every rule here is a regular
expression over the file's decoded text, so a file counted as scanned WAS scanned end to
end: nothing between the count and the match can quietly return empty. The tree-sitter
parse narrows the generic rule to string literals where a grammar is available, and a
grammar that fails only widens that rule, never silences the provider rules that catch a
real AKIA or ghp_ token. Zero is therefore the only bright line needed, and no fraction of
files is set: a partial reading is a different fact from no reading.

The known limits: a repository's own `.gitleaksignore` and any `[allowlist]` in a
`.gitleaks.toml` are NOT honoured, so a repository that has already triaged its findings
will read higher here than under gitleaks; lock files, minified bundles and vendored
trees are skipped; and history is not scanned, matching `--no-git`.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from re import Pattern
from typing import TypedDict

from l1_analyzer.dead_code import _EXT_LANG, _parser
from l1_analyzer.scope import (
    PRODUCTION,
    _bucket_reason,
    _in_ignored_dir,
    _repo_has_packages,
    _rglob_files,
)


class Rule(TypedDict):
    """One credential pattern.

    `secret_group` is the capture holding the credential, so a finding can report its
    shape without ever printing it. `mode` says what makes the match evidence:

      "prefix" - the issuer's own prefix and length are the proof (AKIA..., ghp_...).
                 Nothing else is needed and nothing else is asked.
      "value"  - the pattern only locates a slot a credential COULD sit in (the password
                 field of a connection string, a credential-shaped binding). The value
                 must then clear the placeholder screen and the entropy floor.

    Without the split, `postgresql://postgres:postgres@localhost` counted as a secret.
    It fired 30 times across the five repositories this was validated on, which is how
    an auditor learns to ignore the number.
    """
    id: str
    pattern: Pattern[str]
    secret_group: int
    mode: str


def _rule(rule_id: str, pattern: str, secret_group: int, mode: str) -> Rule:
    return {"id": rule_id, "pattern": re.compile(pattern), "secret_group": secret_group,
            "mode": mode}


# Issuer-prefixed credentials. Each prefix is defined by the provider, so the match is
# the credential's shape and not a guess about the surrounding code.
_PROVIDER_RULES: tuple[Rule, ...] = (
    _rule("aws-access-key-id", r"(?<![A-Z0-9])((?:AKIA|ASIA|ABIA|ACCA|A3T[A-Z0-9])[A-Z0-9]{16})(?![A-Z0-9])", 1, "prefix"),
    _rule("github-token", r"\b(gh[pousr]_[A-Za-z0-9]{30,255})\b", 1, "prefix"),
    _rule("github-fine-grained-token", r"\b(github_pat_[A-Za-z0-9_]{40,255})\b", 1, "prefix"),
    _rule("gitlab-token", r"\b(glpat-[A-Za-z0-9_-]{20})\b", 1, "prefix"),
    _rule("slack-token", r"\b(xox[baprse]-[A-Za-z0-9-]{10,})", 1, "prefix"),
    _rule("slack-webhook", r"(https://hooks\.slack\.com/services/T[A-Za-z0-9+/]{8,})", 1, "prefix"),
    _rule("stripe-api-key", r"\b((?:sk|rk)_(?:live|test|prod)_[A-Za-z0-9]{10,99})\b", 1, "prefix"),
    _rule("google-api-key", r"\b(AIza[0-9A-Za-z_-]{35})\b", 1, "prefix"),
    _rule("openai-or-anthropic-key", r"\b(sk-(?:ant-|proj-)?[A-Za-z0-9]{20,})\b", 1, "prefix"),
    _rule("sendgrid-api-key", r"\b(SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43})\b", 1, "prefix"),
    _rule("npm-token", r"\b(npm_[A-Za-z0-9]{36})\b", 1, "prefix"),
    _rule("huggingface-token", r"\b(hf_[A-Za-z0-9]{34})\b", 1, "prefix"),
    _rule("twilio-api-key", r"\b(SK[0-9a-fA-F]{32})\b", 1, "prefix"),
    _rule("telegram-bot-token", r"\b(\d{8,10}:AA[A-Za-z0-9_-]{33})\b", 1, "prefix"),
    _rule("json-web-token", r"\b(eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})", 1, "prefix"),
    _rule("connection-string-password",
          r"\b(?:postgres|postgresql|mysql|mongodb\+srv|mongodb|redis|rediss|amqp|ftp)://"
          r"[^\s:/@\"']+:([^\s@/\"']{4,})@", 1, "value"),
)

# A PEM header alone is prose: this module's own documentation says the words, and a
# README that warns against committing one is not a leak. The rule therefore requires the
# encoded body to follow, which is what makes it a key rather than a sentence about keys.
_PRIVATE_KEY = re.compile(
    r"(-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----)\s*\n[A-Za-z0-9+/=]{40,}")

# A credential-shaped binding name, then a quoted literal. The name may carry the
# keyword anywhere (`API_SECRET`, `dbPassword`, `settings.auth_token`), so the keyword is
# not anchored to the start of the identifier.
# NO LEADING CHARACTER CLASS, and its absence is the fix rather than an oversight. This
# opened with `[A-Za-z0-9_.\[\]$-]*` before the alternation, over the same characters the
# alternation itself matches, so every near-miss made the engine backtrack through an
# unbounded prefix. On a bundled stylesheet whose longest line is 285,769 characters the scan
# never finished; a run of `a_token_0_x.a_token_1_x.` reproduces it in 250,000.
#
# The prefix never decided whether a match exists, only where one started, and the reported
# value is group 1, which sits after the `[:=]`. `MY_API_KEY = "..."` still matches, because
# `finditer` reaches the keyword from the scan position without needing to consume `MY_`.
#
# The TRAILING class is bounded for the same reason, and removing the leading one alone did
# not fix it. Unbounded, `token` in `a_token_0_x.a_token_1_x.` consumed the whole remaining
# line looking for a `:` or `=`, then gave a character back and tried again, once per start
# position: quadratic in the line length. 64 is well past any real name suffix -
# `API_KEY_PROD` uses five - and turns the inner scan into a constant.
_GENERIC = re.compile(
    r"(?i)"
    r"(?:api[_-]?key|apikey|secret|password|passwd|pwd|token|credential|access[_-]?key|auth[_-]?key|private[_-]?key)"
    r"[A-Za-z0-9_.\[\]$-]{0,64}\s*[:=]\s*[\"']([^\"'\n]{12,120})[\"']")
# The same binding, unquoted, in dotenv / shell / CI syntax. A `.env` that is actually
# tracked is where real credentials sit, and they are never quoted there. cardz commits
# `AUTH0_CLIENT_SECRET=xGLoLZGEXF_...`; gitleaks reports it and the quoted-only rule above
# could not. Applied ONLY to files whose syntax IS `KEY=value` (see _ENV_SYNTAX): in
# source it would charge `token = someIdentifier`, and in prose it charged seven sentences
# across two repositories, because in a paragraph `KEY=value` is a sentence, not a setting.
_GENERIC_ENV = re.compile(
    r"(?im)^[ \t]*(?:export[ \t]+)?[A-Za-z0-9_.-]*"
    r"(?:api[_-]?key|apikey|secret|password|passwd|pwd|token|credential|access[_-]?key|auth[_-]?key)"
    r"[A-Za-z0-9_.-]*[ \t]*[:=][ \t]*([^\s\"'#]{12,120})[ \t]*$")
_GENERIC_RULE_ID = "generic-credential"
_MIN_ENTROPY = 3.5

# Words that mark a value as an instruction to the reader rather than a credential.
_PLACEHOLDER_WORDS = (
    "example", "changeme", "change_me", "changeit", "placeholder", "your", "here",
    "dummy", "fake", "sample", "redacted", "todo", "insert", "replace", "notreal",
    "xxxx", "test-key", "password", "username", "localhost", "s3cret", "hunter2",
    "abcdef", "letmein",
    # Default service credentials. `postgresql://postgres:postgres@localhost` is a
    # docker-compose default, not a leak, and it was the single most common false
    # positive across the five validation repositories.
    "postgres", "mysql", "mongo", "redis", "root", "admin", "guest", "invalid",
)
_INTERPOLATION = ("${", "{{", "%s", "%(", "os.environ", "process.env", "getenv",
                  "ENV[", "<", ">", "#{")
_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

# Files whose content is machine-generated hashes or third-party code. gitleaks allowlists
# the same shapes; without this a lockfile's integrity digests dominate the count.
_SKIP_NAMES = frozenset({
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "Cargo.lock", "poetry.lock",
    "uv.lock", "Gemfile.lock", "composer.lock", "go.sum", "packages.lock.json",
})
_SKIP_SUFFIXES = (".min.js", ".min.css", ".map", ".svg", ".woff", ".woff2")
_MAX_BYTES = 4_194_304

# Files whose line syntax IS `KEY=value` or `key: value`, which is what _GENERIC_ENV reads.
_ENV_SYNTAX_SUFFIXES = frozenset({
    ".env", ".envrc", ".sh", ".bash", ".zsh", ".ini", ".cfg", ".conf", ".properties",
    ".yml", ".yaml", ".tf", ".tfvars", ".service",
})
_ENV_SYNTAX_PREFIXES = (".env", "Dockerfile", "Makefile", "docker-compose")


def _has_env_syntax(name: str) -> bool:
    return (Path(name).suffix.lower() in _ENV_SYNTAX_SUFFIXES
            or name.startswith(_ENV_SYNTAX_PREFIXES))


class Finding(TypedDict):
    """One distinct credential: where it first appears, its shape, and how many times it
    was found. Never its value."""
    rule: str
    file: str
    line: int
    excerpt: str
    in_tests: bool
    occurrences: int


def _entropy(value: str) -> float:
    """Shannon entropy in bits per character. A generated credential sits near the
    alphabet's maximum; an English phrase does not."""
    counts = Counter(value)
    length = len(value)
    return -sum((n / length) * math.log2(n / length) for n in counts.values())


def _is_placeholder(value: str) -> bool:
    lowered = value.lower()
    if any(word in lowered for word in _PLACEHOLDER_WORDS):
        return True
    if any(marker in value for marker in _INTERPOLATION):
        return True
    return len(set(value)) <= 2


def _is_generic_secret(value: str) -> bool:
    """The extra evidence the generic rule needs, on top of a credential-shaped name."""
    if " " in value or _UUID.match(value):
        return False
    if _is_placeholder(value):
        return False
    return _entropy(value) >= _MIN_ENTROPY


def _excerpt(value: str) -> str:
    """A finding's shape without its content. An audit artefact that reprints the
    credential has copied the leak into a second file."""
    return f"{value[:4]}... ({len(value)} chars)"


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _byte_offset(text: str, char_offset: int) -> int:
    """A character offset into `text`, expressed in the bytes tree-sitter counts in.

    `re` counts characters and tree-sitter counts bytes, and the two agree only while the file
    is ASCII. One accented word above a credential is one byte of drift, and the drift is
    silent: the string-literal narrowing below then tests the credential's position against the
    wrong span, so the finding is attributed to another literal or - the case that matters -
    dropped without a word. A scanner whose whole job is finding committed credentials failed
    open on any file carrying a comment in French, German or Japanese.

    Exact rather than approximate, because the caller's contract makes it so: `_scan_text` is
    handed the bytes of `text` itself, so re-encoding a prefix reproduces the byte offset the
    parser saw. `str.isascii` is a cached flag on the string, so the common file costs nothing.
    """
    if text.isascii():
        return char_offset
    return len(text[:char_offset].encode("utf8"))


def _string_spans(raw: bytes, suffix: str) -> list[tuple[int, int]] | None:
    """Byte spans of every string literal in a source file, or None when the file is not
    one of the nine supported languages. The generic rule fires only inside these, which
    is what keeps a credential-shaped identifier or a bare pattern from counting."""
    entry = _EXT_LANG.get(suffix)
    if entry is None:
        return None
    spans: list[tuple[int, int]] = []

    def walk(node) -> None:
        if "string" in node.type or node.type in ("heredoc_body", "raw_string_literal"):
            spans.append((node.start_byte, node.end_byte))
            return
        for child in node.children:
            walk(child)

    walk(_parser(entry[0]).parse(raw).root_node)
    return spans


_ACCEPTS = {"prefix": lambda value: not _is_placeholder(value), "value": _is_generic_secret}


def _scan_text(text: str, raw: bytes, name: str) -> list[tuple[str, int, str]]:
    """(rule id, line, credential) for one file. Pure: no file system, no network.

    `name` is the file NAME, not a path: it selects the grammar (by suffix) and decides
    whether the file's syntax is `KEY=value`.

    `raw` MUST be `text.encode("utf8")`. Two offset systems meet in this function - `re`
    counts characters and tree-sitter counts bytes - and `_byte_offset` converts between them
    on the strength of that equality. `analyze` guarantees it by handing the parser the bytes
    of the decoded text rather than the bytes it read off disk, so a file with a byte that is
    not valid UTF-8 cannot put the two out of step either."""
    hits: list[tuple[str, int, str]] = []
    claimed: set[tuple[int, str]] = set()

    for rule in _PROVIDER_RULES:
        for match in rule["pattern"].finditer(text):
            value = match.group(rule["secret_group"])
            if not _ACCEPTS[rule["mode"]](value):
                continue
            line = _line_of(text, match.start(rule["secret_group"]))
            if (line, value) in claimed:
                continue
            claimed.add((line, value))
            hits.append((rule["id"], line, value))

    for match in _PRIVATE_KEY.finditer(text):
        # No `claimed.add` here, and it is not an omission. Group 1 is the PEM header, which
        # always contains a space ("BEGIN PRIVATE KEY"), and the only reader of `claimed`
        # below is the generic rule, whose `_is_generic_secret` rejects any value containing a
        # space. The two sets can therefore never intersect, so the de-duplication the add
        # performed could not fire on any input. The provider loop above cannot see it either,
        # having already run.
        hits.append(("private-key", _line_of(text, match.start(1)), match.group(1)))

    spans = _string_spans(raw, Path(name).suffix.lower())
    patterns = (_GENERIC, _GENERIC_ENV) if _has_env_syntax(name) else (_GENERIC,)
    for pattern in patterns:
        for match in pattern.finditer(text):
            value = match.group(1)
            start = match.start(1)
            # The narrowing runs in tree-sitter's units, not the regex module's. Comparing the
            # two directly is how a credential under an accented comment went unreported.
            if spans is not None and not any(
                    lo <= _byte_offset(text, start) < hi for lo, hi in spans):
                continue
            if not _is_generic_secret(value):
                continue
            line = _line_of(text, start)
            if (line, value) in claimed:
                continue
            claimed.add((line, value))
            hits.append((_GENERIC_RULE_ID, line, value))

    return hits


def _band_for(hits: int) -> str:
    """The canon's count arm: 0 Healthy, 1-2 Not Healthy, >=3 Slop."""
    from l1_analyzer.indicators import band
    return band(hits, 1, 3, higher_is_better=False)


# The window the binary test reads. git decides the same way and from the same window, so a
# file that hides its first NUL past this point reads as text here exactly as it does there.
_BINARY_PROBE_BYTES = 8192


def _read_text_bytes(path: Path, max_bytes: int) -> bytes | None:
    """The file's bytes, or None when it is binary, too large, or unreadable.

    THE ORDER IS THE POINT. The binary test used to run after `path.read_bytes()`, so every
    binary file in the tree was read in full and then discarded on the same NUL check. That
    cost is invisible on a source repository and ruinous on one carrying assets: 45,303
    committed PNGs across 1.0 GB did not finish scanning in ten minutes, where two ordinary
    repositories took seconds.

    Deciding from the first chunk is content-based, which is why there is no extension list
    here. A skip-list of `.png`, `.jpg`, `.pdf` is a whitelist that every new format re-opens,
    and the one already in `_SKIP_SUFFIXES` had let images through for exactly that reason.

    Returns None rather than raising on an unreadable path, because a file that vanished
    between the walk and the open is a fact about the tree and not about this function.
    """
    try:
        with path.open("rb") as handle:
            head = handle.read(_BINARY_PROBE_BYTES)
            if b"\0" in head:
                return None
            rest = handle.read(max_bytes - len(head) + 1) if len(head) == _BINARY_PROBE_BYTES else b""
    # honest-code-allow: L1.21.8 - the caller counts these and the result says "N file(s) unreadable or oversized and excluded", so a file this scanner could not read is disclosed rather than counted as carrying no credential
    except OSError:
        return None
    raw = head + rest
    return None if len(raw) > max_bytes else raw


def _scannable(path: Path) -> bool:
    return path.name not in _SKIP_NAMES and not path.name.endswith(_SKIP_SUFFIXES)


def _tracked_files(repo: Path) -> frozenset[str] | None:
    """The paths git tracks, or None when `repo` is not a git working tree.

    The audit question is which credentials are COMMITTED - the canon's antipattern says
    they "land on the default branch". A gitignored file is not on the branch; it is the
    auditor's own workstation. Scanning the tree instead of the index charged 92 findings
    to one repository from `.env` and a gitignored browser-console log, none of which any
    consumer of that repository can ever see. This is a deliberate deviation from
    `gitleaks --no-git`, which scans the filesystem, and it is disclosed in `details`.
    """
    from l1_analyzer.indicators import _run_external
    run = _run_external(["git", "ls-files", "-z"], repo)
    if not run["ran"] or run["status"] != 0:
        return None
    return frozenset(p for p in run["output"].split("\0") if p)


_DOC_SUFFIXES = frozenset({".md", ".markdown", ".rst", ".txt", ".adoc"})


def analyze(repo: Path, lang: str) -> dict[str, object]:
    """L1.14 for one repository, over the current tree (never git history), which is what
    `gitleaks detect --no-git` means. `lang` is accepted for a uniform indicator
    signature; a committed credential is the same finding in any language and the
    provider rules are language-independent.

    The published number counts DISTINCT credentials, not occurrences. One key repeated
    down 75 lines of a log is one leaked key, and the canon's bands (0 / 1-2 / >=3) only
    make sense read that way. Occurrences are reported beside each finding."""
    has_packages = _repo_has_packages(repo)
    tracked = _tracked_files(repo)
    raw_hits: list[tuple[str, str, str, int, bool]] = []   # rule, value, file, line, in_tests
    scanned = skipped = 0
    for path in _rglob_files(repo, "*"):
        if _in_ignored_dir(path, ()) or not _scannable(path):
            continue
        relpath = str(path.relative_to(repo)) if repo in path.parents else path.name
        if tracked is not None and relpath not in tracked:
            continue
        raw = _read_text_bytes(path, _MAX_BYTES)
        if raw is None:
            skipped += 1
            continue
        scanned += 1
        bucket = _bucket_reason(path, repo, has_packages, PRODUCTION)
        in_tests = bucket in ("tests", "test")
        # A specification, a README or a design note is not production code. The scope
        # helper has a docs bucket but it fires only on a directory literally named
        # `docs`, and this repository's specification lives in `spec/`, so a credential in
        # a fenced block showing an ANTIPATTERN was reported as being in production code.
        # Decided on the extension rather than the directory: prose is prose wherever it
        # is filed, and this is the only indicator that scans files which are not code.
        in_docs = not in_tests and (bucket == "docs" or path.suffix.lower() in _DOC_SUFFIXES)
        text = raw.decode("utf8", errors="ignore")
        # The parser is handed the bytes of the decoded text, not the bytes read off disk.
        # The two differ only for a file carrying something that is not valid UTF-8, where the
        # decode drops it - and then every span tree-sitter returned would be shifted by the
        # dropped bytes against the offsets the regexes below report. Re-encoding costs one
        # pass and makes `_byte_offset` exact by construction rather than by assumption.
        raw_hits.extend((rule_id, value, relpath, line, in_tests, in_docs)
                        for rule_id, line, value in _scan_text(text, text.encode("utf8"), path.name))

    grouped: dict[tuple[str, str], list[tuple[str, int, bool, bool]]] = {}
    for rule_id, value, relpath, line, in_tests, in_docs in raw_hits:
        grouped.setdefault((rule_id, value), []).append((relpath, line, in_tests, in_docs))
    findings: list[Finding] = [
        {"rule": rule_id, "file": sites[0][0], "line": sites[0][1], "excerpt": _excerpt(value),
         # A credential that appears anywhere outside the test tree is a production
         # finding, however many fixtures also carry it.
         "in_tests": all(site[2] for site in sites),
         # Documentation only when EVERY site is documentation, for the same reason as
         # tests: one production copy makes it a production finding however many pages
         # also print it.
         "in_docs": all(site[3] for site in sites) and not all(site[2] for site in sites),
         "occurrences": len(sites)}
        for (rule_id, value), sites in grouped.items()
    ]

    total = len(findings)
    in_tests = sum(1 for f in findings if f["in_tests"])
    in_docs = sum(1 for f in findings if f["in_docs"])
    counts = {"total": total, "in_tests": in_tests, "in_docs": in_docs,
              "in_production": total - in_tests - in_docs,
              "occurrences": len(raw_hits),
              "by_rule": dict(sorted(Counter(f["rule"] for f in findings).items()))}
    scope_note = ("git-tracked files only" if tracked is not None
                  else "the whole tree: not a git working copy, so gitignored files cannot be excluded")
    # "distinct secret(s) ... in production code" counts FINDINGS, not files, and reading it
    # as a file count is how a one-file reading and a no-file reading looked alike in prose.
    # The file counts are now named as file counts and stand on their own.
    details = (
        f"{total} distinct secret(s) in {len(raw_hits)} occurrence(s) across {scanned} scanned "
        f"file(s); {total - in_tests - in_docs} of the secret(s) are in production code, "
        f"{in_docs} only in documentation and {in_tests} only in the test tree; "
        f"scope: {scope_note}; "
        "the canon's second Slop arm, a confirmed true positive, is not evaluated: "
        "no credential is validated against its issuer"
    )
    if skipped:
        details += f"; {skipped} file(s) unreadable or oversized and excluded"
    if scanned == 0:
        # The refusal, in value and band rather than in the prose beneath them. The counts,
        # findings and confirmed keys stay on the result so a consumer reading them does not
        # have to special-case the shape; they are all empty, which is the point.
        details = (
            f"not measured: no file was read. Scope: {scope_note}, and every candidate file "
            "was excluded before it was opened. A count of zero here would be a clean bill of "
            "health on a repository this scanner never read, which for a credential scanner "
            "is the worst answer it could fabricate"
        )
        if skipped:
            details += f"; {skipped} file(s) unreadable or oversized and excluded"
    return {
        "value": "n/a" if scanned == 0 else total,
        "band": "n/a" if scanned == 0 else _band_for(total),
        "details": details,
        "findings": sorted(findings, key=lambda f: (f["file"], f["line"], f["rule"])),
        "counts": counts,
        "confirmed": "not evaluated",
        "files_scanned": scanned,
    }
