//! The credential patterns L1.14 reads a file with, and the evidence each one needs.
//! Ported from the rule half of l1_analyzer.secret_scan.
//!
//! Two rule families:
//!
//!   PROVIDER rules match a credential by its issuer's own prefix and length (AKIA...,
//!   ghp_..., xoxb-..., a PEM block). They run over raw text, the way gitleaks does, because
//!   such a token is unambiguous wherever it sits, including in a comment.
//!
//!   The GENERIC rule matches a high-entropy literal assigned to a credential-shaped name.
//!   It runs only inside string literals, located with tree-sitter, in all nine supported
//!   languages. A credential-shaped word in an identifier, a type name, or a bare regular
//!   expression is not a committed credential, and charging one is the false positive that
//!   makes an auditor stop believing the number.
//!
//! No offset is converted anywhere here, and that is the difference from the reference. Python
//! counts characters and tree-sitter counts bytes, so the reference carries a `_byte_offset`
//! to keep the string-literal narrowing honest on any file with an accented comment in it.
//! Rust's regular expressions already report byte offsets, which is what the parser reports,
//! so the two units are one unit and there is nothing to convert.

use std::collections::HashSet;
use std::sync::OnceLock;

use regex::Regex;

/// What makes a match evidence.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Mode {
    /// The issuer's own prefix and length are the proof (AKIA..., ghp_...). Nothing else is
    /// needed and nothing else is asked.
    Prefix,
    /// The pattern only locates a slot a credential COULD sit in (the password field of a
    /// connection string). The value must then clear the placeholder screen and the entropy
    /// floor.
    ///
    /// Without the split, `postgresql://postgres:postgres@localhost` counted as a secret. It
    /// fired 30 times across the five repositories this was validated on, which is how an
    /// auditor learns to ignore the number.
    Value,
}

/// One credential pattern. `secret_group` is the capture holding the credential, so a finding
/// can report its shape without ever printing it.
pub struct Rule {
    pub id: &'static str,
    pub pattern: Regex,
    pub secret_group: usize,
    pub mode: Mode,
    /// Whether the match must be bounded by something outside `[A-Z0-9]` on both sides.
    ///
    /// The reference writes this as `(?<![A-Z0-9])...(?![A-Z0-9])` and this engine has no
    /// lookaround, so the same two characters are read by hand in `matches_of`. A flag rather
    /// than a second pattern, because the boundary is a property of the rule and the one rule
    /// that wants it is the only one that may answer yes.
    pub alnum_bounded: bool,
}

fn rule(id: &'static str, pattern: &str, secret_group: usize, mode: Mode) -> Rule {
    Rule { id, pattern: Regex::new(pattern).expect("a valid credential pattern"),
           secret_group, mode, alnum_bounded: false }
}

/// Issuer-prefixed credentials. Each prefix is defined by the provider, so the match is the
/// credential's shape and not a guess about the surrounding code.
pub fn provider_rules() -> &'static [Rule] {
    static RULES: OnceLock<Vec<Rule>> = OnceLock::new();
    RULES.get_or_init(|| vec![
        Rule { alnum_bounded: true,
               ..rule("aws-access-key-id",
                      r"((?:AKIA|ASIA|ABIA|ACCA|A3T[A-Z0-9])[A-Z0-9]{16})", 1, Mode::Prefix) },
        rule("github-token", r"\b(gh[pousr]_[A-Za-z0-9]{30,255})\b", 1, Mode::Prefix),
        rule("github-fine-grained-token", r"\b(github_pat_[A-Za-z0-9_]{40,255})\b", 1, Mode::Prefix),
        rule("gitlab-token", r"\b(glpat-[A-Za-z0-9_-]{20})\b", 1, Mode::Prefix),
        rule("slack-token", r"\b(xox[baprse]-[A-Za-z0-9-]{10,})", 1, Mode::Prefix),
        rule("slack-webhook", r"(https://hooks\.slack\.com/services/T[A-Za-z0-9+/]{8,})", 1, Mode::Prefix),
        rule("stripe-api-key", r"\b((?:sk|rk)_(?:live|test|prod)_[A-Za-z0-9]{10,99})\b", 1, Mode::Prefix),
        rule("google-api-key", r"\b(AIza[0-9A-Za-z_-]{35})\b", 1, Mode::Prefix),
        rule("openai-or-anthropic-key", r"\b(sk-(?:ant-|proj-)?[A-Za-z0-9]{20,})\b", 1, Mode::Prefix),
        rule("sendgrid-api-key", r"\b(SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43})\b", 1, Mode::Prefix),
        rule("npm-token", r"\b(npm_[A-Za-z0-9]{36})\b", 1, Mode::Prefix),
        rule("huggingface-token", r"\b(hf_[A-Za-z0-9]{34})\b", 1, Mode::Prefix),
        rule("twilio-api-key", r"\b(SK[0-9a-fA-F]{32})\b", 1, Mode::Prefix),
        rule("telegram-bot-token", r"\b(\d{8,10}:AA[A-Za-z0-9_-]{33})\b", 1, Mode::Prefix),
        rule("json-web-token",
             r"\b(eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})", 1, Mode::Prefix),
        rule("connection-string-password",
             concat!(r"\b(?:postgres|postgresql|mysql|mongodb\+srv|mongodb|redis|rediss|amqp|ftp)://",
                     "[^\\s:/@\"']+:([^\\s@/\"']{4,})@"), 1, Mode::Value),
    ])
}

/// The credential-shaped words a binding name may carry, anywhere in the name.
const NAMES: &str = concat!(
    "(?:api[_-]?key|apikey|secret|password|passwd|pwd|token|credential",
    "|access[_-]?key|auth[_-]?key|private[_-]?key)");

/// The four patterns that are not provider rules, compiled once.
///
/// They were four functions, and each was the same five lines around a different string: a
/// lock, an initialiser, a compile and a message. What separated them was words, which is
/// what L1.21.1 counts, and it counted them here.
struct Patterns {
    /// A PEM header alone is prose: this module's own documentation says the words, and a
    /// README that warns against committing one is not a leak. The rule therefore requires
    /// the encoded body to follow, which is what makes it a key rather than a sentence about
    /// keys.
    private_key: Regex,
    /// A value shaped like a UUID is an identifier somebody generated, not a credential
    /// somebody was issued.
    uuid: Regex,
    /// A credential-shaped binding name, then a quoted literal. The name may carry the
    /// keyword anywhere (`API_SECRET`, `dbPassword`, `settings.auth_token`), so the keyword
    /// is not anchored to the start of the identifier.
    ///
    /// NO LEADING CHARACTER CLASS, and its absence is the fix rather than an oversight. The
    /// reference opened with a class over the same characters the alternation itself matches,
    /// so every near-miss made a backtracking engine work through an unbounded prefix; on a
    /// bundled stylesheet whose longest line is 285,769 characters the scan never finished.
    /// The engine here cannot backtrack, so the class would cost nothing, and it is still
    /// absent: the two patterns must match the same text or the two tools report different
    /// numbers.
    ///
    /// The TRAILING class is bounded for the same reason. 64 is well past any real name
    /// suffix, `API_KEY_PROD` uses five.
    generic: Regex,
    /// The same binding, unquoted, in dotenv / shell / CI syntax. A `.env` that is actually
    /// tracked is where real credentials sit, and they are never quoted there.
    ///
    /// Applied ONLY to files whose syntax IS `KEY=value` (see `has_env_syntax`): in source it
    /// would charge `token = someIdentifier`, and in prose it charged seven sentences across
    /// two repositories, because in a paragraph `KEY=value` is a sentence, not a setting.
    generic_env: Regex,
}

fn patterns() -> &'static Patterns {
    static COMPILED: OnceLock<Patterns> = OnceLock::new();
    COMPILED.get_or_init(|| Patterns {
        private_key: compile(
            r"(-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----)\s*\n[A-Za-z0-9+/=]{40,}"),
        uuid: compile(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"),
        generic: compile(&format!("(?i){NAMES}{}",
            "[A-Za-z0-9_.\\[\\]$-]{0,64}\\s*[:=]\\s*[\"']([^\"'\\n]{12,120})[\"']")),
        generic_env: compile(&format!("(?im)^[ \t]*(?:export[ \t]+)?[A-Za-z0-9_.-]*{NAMES}{}",
            "[A-Za-z0-9_.-]*[ \t]*[:=][ \t]*([^\\s\"'#]{12,120})[ \t]*$")),
    })
}

fn compile(source: &str) -> Regex {
    Regex::new(source).expect("a valid credential pattern")
}

pub const GENERIC_RULE_ID: &str = "generic-credential";
const MIN_ENTROPY: f64 = 3.5;

/// Words that mark a value as an instruction to the reader rather than a credential.
const PLACEHOLDER_WORDS: &[&str] = &[
    "example", "changeme", "change_me", "changeit", "placeholder", "your", "here",
    "dummy", "fake", "sample", "redacted", "todo", "insert", "replace", "notreal",
    "xxxx", "test-key", "password", "username", "localhost", "s3cret", "hunter2",
    "abcdef", "letmein",
    // Default service credentials. `postgresql://postgres:postgres@localhost` is a
    // docker-compose default, not a leak, and it was the single most common false positive
    // across the five validation repositories.
    "postgres", "mysql", "mongo", "redis", "root", "admin", "guest", "invalid",
];

const INTERPOLATION: &[&str] = &["${", "{{", "%s", "%(", "os.environ", "process.env",
                                 "getenv", "ENV[", "<", ">", "#{"];

/// Files whose line syntax IS `KEY=value` or `key: value`, which is what the dotenv rule reads.
const ENV_SYNTAX_SUFFIXES: &[&str] = &[
    ".env", ".envrc", ".sh", ".bash", ".zsh", ".ini", ".cfg", ".conf", ".properties",
    ".yml", ".yaml", ".tf", ".tfvars", ".service",
];
const ENV_SYNTAX_PREFIXES: &[&str] = &[".env", "Dockerfile", "Makefile", "docker-compose"];

/// True when this file's lines are settings rather than source or prose.
///
/// `name` is the file NAME, not a path. The suffix is Python's `Path.suffix`: the last dot
/// and what follows it, and nothing at all for a name that only begins with a dot, which is
/// why `.env` is caught by the prefix arm rather than the suffix one.
pub fn has_env_syntax(name: &str) -> bool {
    let suffix = py_suffix(name).to_lowercase();
    ENV_SYNTAX_SUFFIXES.contains(&suffix.as_str())
        || ENV_SYNTAX_PREFIXES.iter().any(|prefix| name.starts_with(prefix))
}

/// Python's `Path(name).suffix`: the last dot and what follows, empty where a name has no
/// dot, ends with one, or carries only a leading one.
pub fn py_suffix(name: &str) -> &str {
    match name.rfind('.') {
        Some(0) => "",
        Some(at) if at + 1 < name.len() => &name[at..],
        _ => "",
    }
}

/// Shannon entropy in bits per character. A generated credential sits near the alphabet's
/// maximum; an English phrase does not.
pub fn entropy(value: &str) -> f64 {
    let mut counts: std::collections::HashMap<char, usize> = std::collections::HashMap::new();
    let mut length = 0usize;
    for ch in value.chars() {
        *counts.entry(ch).or_insert(0) += 1;
        length += 1;
    }
    let total = length as f64;
    -counts.values().map(|n| {
        let share = *n as f64 / total;
        share * share.log2()
    }).sum::<f64>()
}

/// True when the value is an instruction to the reader rather than a credential.
pub fn is_placeholder(value: &str) -> bool {
    let lowered = value.to_lowercase();
    if PLACEHOLDER_WORDS.iter().any(|word| lowered.contains(word)) {
        return true;
    }
    if INTERPOLATION.iter().any(|marker| value.contains(marker)) {
        return true;
    }
    value.chars().collect::<HashSet<char>>().len() <= 2
}

/// The extra evidence the generic rule needs, on top of a credential-shaped name.
pub fn is_generic_secret(value: &str) -> bool {
    if value.contains(' ') || patterns().uuid.is_match(value) {
        return false;
    }
    if is_placeholder(value) {
        return false;
    }
    entropy(value) >= MIN_ENTROPY
}

fn accepts(mode: Mode, value: &str) -> bool {
    match mode {
        Mode::Prefix => !is_placeholder(value),
        Mode::Value => is_generic_secret(value),
    }
}

/// The 1-based line a byte offset sits on.
pub fn line_of(text: &str, offset: usize) -> usize {
    text.as_bytes()[..offset].iter().filter(|byte| **byte == b'\n').count() + 1
}

/// Every (start byte, value) this rule matches, in the order the reference finds them.
///
/// Where the rule wants a boundary the reference states as a lookaround, the two characters
/// either side are read here instead, and a rejected match resumes the search ONE CHARACTER
/// on rather than past the match. That is what a lookaround does: it consumes nothing, so a
/// failure leaves a shorter overlapping match still reachable. Resuming past the match would
/// be a faster scan that finds fewer credentials.
fn matches_of(rule: &Rule, text: &str) -> Vec<(usize, String)> {
    if !rule.alnum_bounded {
        return rule.pattern.captures_iter(text)
            .filter_map(|caps| caps.get(rule.secret_group))
            .map(|m| (m.start(), m.as_str().to_string()))
            .collect();
    }
    let mut found = Vec::new();
    let mut from = 0usize;
    while from <= text.len() {
        let Some(caps) = rule.pattern.captures(&text[from..]) else { break };
        let Some(group) = caps.get(rule.secret_group) else { break };
        let (start, end) = (from + group.start(), from + group.end());
        if !preceded_by_alnum(text, start) && !followed_by_alnum(text, end) {
            found.push((start, group.as_str().to_string()));
            from = end;
        } else {
            from = next_char(text, start);
        }
    }
    found
}

/// The lookbehind: is the byte before `start` one of `[A-Z0-9]`? Nothing before the first
/// byte, so a match at the start of the file is never preceded by one.
fn preceded_by_alnum(text: &str, start: usize) -> bool {
    start > 0 && is_upper_or_digit(text.as_bytes()[start - 1])
}

/// The lookahead: is the byte at `end` one of `[A-Z0-9]`? Nothing after the last byte, so a
/// match at the end of the file is never followed by one.
fn followed_by_alnum(text: &str, end: usize) -> bool {
    end < text.len() && is_upper_or_digit(text.as_bytes()[end])
}

fn is_upper_or_digit(byte: u8) -> bool {
    byte.is_ascii_uppercase() || byte.is_ascii_digit()
}

/// The next character boundary after `at`, or the end of the text.
fn next_char(text: &str, at: usize) -> usize {
    text[at..].char_indices().nth(1).map(|(offset, _)| at + offset).unwrap_or(text.len())
}

/// Byte spans of every string literal in a source file, or None when the file is not one of
/// the nine supported languages. The generic rule fires only inside these, which is what
/// keeps a credential-shaped identifier or a bare pattern from counting.
fn string_spans(raw: &[u8], suffix: &str) -> Option<Vec<(usize, usize)>> {
    let bare = suffix.strip_prefix('.').unwrap_or(suffix);
    let (grammar, _collector) = crate::indicators::dead_code_grammars::for_extension(bare)?;
    let tree = crate::indicators::dead_code_grammars::parser_for_grammar(grammar)
        .parse(raw, None)?;
    // An explicit stack, because this one stops at a string rather than reading every node.
    let mut spans = Vec::new();
    let mut stack = vec![tree.root_node()];
    let mut cursor = tree.walk();
    while let Some(node) = stack.pop() {
        let kind = node.kind();
        if kind.contains("string") || kind == "heredoc_body" || kind == "raw_string_literal" {
            spans.push((node.start_byte(), node.end_byte()));
            continue;
        }
        let children: Vec<_> = node.children(&mut cursor).collect();
        stack.extend(children.into_iter().rev());
    }
    Some(spans)
}

/// (rule id, line, credential) for one file. Pure: no file system, no network.
///
/// `name` is the file NAME, not a path: it selects the grammar (by suffix) and decides whether
/// the file's syntax is `KEY=value`. `raw` MUST be the bytes of `text`.
pub fn scan_text(text: &str, raw: &[u8], name: &str) -> Vec<(&'static str, usize, String)> {
    let mut hits: Vec<(&'static str, usize, String)> = Vec::new();
    let mut claimed: HashSet<(usize, String)> = HashSet::new();

    for rule in provider_rules() {
        for (start, value) in matches_of(rule, text) {
            if !accepts(rule.mode, &value) {
                continue;
            }
            let line = line_of(text, start);
            if !claimed.insert((line, value.clone())) {
                continue;
            }
            hits.push((rule.id, line, value));
        }
    }

    for caps in patterns().private_key.captures_iter(text) {
        // Nothing is claimed here, and it is not an omission. Group 1 is the PEM header, which
        // always contains a space ("BEGIN PRIVATE KEY"), and the only reader of `claimed`
        // below is the generic rule, whose `is_generic_secret` rejects any value containing a
        // space. The two sets can therefore never intersect. The provider loop above cannot
        // see it either, having already run.
        let header = caps.get(1).expect("the PEM header");
        hits.push(("private-key", line_of(text, header.start()), header.as_str().to_string()));
    }

    let spans = string_spans(raw, &py_suffix(name).to_lowercase());
    let mut wanted: Vec<&Regex> = vec![&patterns().generic];
    if has_env_syntax(name) {
        wanted.push(&patterns().generic_env);
    }
    for pattern in wanted {
        for caps in pattern.captures_iter(text) {
            let group = caps.get(1).expect("the credential capture");
            let (start, value) = (group.start(), group.as_str());
            if let Some(spans) = spans.as_ref() {
                if !spans.iter().any(|(lo, hi)| *lo <= start && start < *hi) {
                    continue;
                }
            }
            if !is_generic_secret(value) {
                continue;
            }
            let line = line_of(text, start);
            if !claimed.insert((line, value.to_string())) {
                continue;
            }
            hits.push((GENERIC_RULE_ID, line, value.to_string()));
        }
    }

    hits
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn an_issuer_prefixed_key_is_found_wherever_it_sits() {
        let text = "# left here by mistake\nAKIAQWERTYUIOPASDFGH\n";
        let found = scan_text(text, text.as_bytes(), "notes.txt");
        assert_eq!(found.iter().map(|(id, line, _)| (*id, *line)).collect::<Vec<_>>(),
                   vec![("aws-access-key-id", 2)]);
    }

    #[test]
    fn a_key_welded_to_another_capital_is_not_a_key() {
        // What the reference's two lookarounds say, and the only rule that asks for them.
        let text = "XAKIAQWERTYUIOPASDFGHX\n";
        assert!(scan_text(text, text.as_bytes(), "notes.txt").is_empty());
    }

    #[test]
    fn a_default_service_password_in_a_connection_string_is_not_a_leak() {
        // It fired 30 times across the five repositories the reference was validated on.
        let text = "postgresql://postgres:postgres@localhost:5432/app\n";
        assert!(scan_text(text, text.as_bytes(), "config.txt").is_empty());
    }

    #[test]
    fn a_pem_header_without_a_body_is_a_sentence_about_keys() {
        let prose = "Never commit a -----BEGIN RSA PRIVATE KEY----- to the repository.\n";
        assert!(scan_text(prose, prose.as_bytes(), "README.md").is_empty());
        let real = "-----BEGIN RSA PRIVATE KEY-----\n\
                    MIIEowIBAAKCAQEAxGZlQ0hleUNvbnRlbnRCYXNlNjRFbmNvZGVkQm9keUhlcmU=\n";
        assert_eq!(scan_text(real, real.as_bytes(), "id_rsa").len(), 1);
    }

    #[test]
    fn the_generic_rule_fires_inside_a_literal_and_not_in_an_identifier() {
        let source = "const api_key = \"Zk3qR7vL9wX2mB5nT8yH\";\n";
        assert_eq!(scan_text(source, source.as_bytes(), "app.js").len(), 1);
        let naming = "const api_key = someOtherBinding;\nlet password_field_name;\n";
        assert!(scan_text(naming, naming.as_bytes(), "app.js").is_empty());
    }

    #[test]
    fn the_dotenv_rule_reads_settings_files_and_leaves_prose_alone() {
        let env = "AUTH0_CLIENT_SECRET=Zk3qR7vL9wX2mB5nT8yH\n";
        assert_eq!(scan_text(env, env.as_bytes(), ".env").len(), 1);
        // In a paragraph `KEY=value` is a sentence, not a setting. It charged seven of them
        // across two repositories.
        assert!(scan_text(env, env.as_bytes(), "guide.md").is_empty());
    }

    #[test]
    fn an_accented_comment_above_a_credential_does_not_move_the_literal() {
        // The reference converts character offsets to byte offsets to survive this. Rust
        // counts bytes on both sides, so the two units never had to be reconciled.
        let source = "// clé privée, à ne pas publier\nconst token = \"Zk3qR7vL9wX2mB5nT8yH\";\n";
        let found = scan_text(source, source.as_bytes(), "app.js");
        assert_eq!(found.iter().map(|(id, line, _)| (*id, *line)).collect::<Vec<_>>(),
                   vec![(GENERIC_RULE_ID, 2)]);
    }

    #[test]
    fn a_uuid_and_a_low_entropy_value_are_not_credentials() {
        assert!(!is_generic_secret("123e4567-e89b-12d3-a456-426614174000"));
        assert!(!is_generic_secret("aaaaaaaaaaaaaaaa"));
        assert!(!is_generic_secret("your-api-key-here"));
        assert!(is_generic_secret("Zk3qR7vL9wX2mB5nT8yH"));
    }

    #[test]
    fn a_pathlib_suffix_is_the_last_dot_and_a_leading_dot_is_not_one() {
        assert_eq!(py_suffix(".env"), "");
        assert_eq!(py_suffix("a.tar.gz"), ".gz");
        assert_eq!(py_suffix("Makefile"), "");
        assert_eq!(py_suffix("trailing."), "");
        assert!(has_env_syntax(".env.production"));
        assert!(has_env_syntax("docker-compose.override.yml"));
        assert!(!has_env_syntax("app.js"));
    }
}
