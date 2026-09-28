//! L1.12, the unreachable-code ratio. Ported from the driver of l1_analyzer.dead_code.
//!
//! The canon names a tool per language. Requiring six ecosystems' toolchains at a client site
//! is not realistic, so this computes the same two categories directly: a statement that
//! follows a terminator, which the module next door decides from syntax alone, and a
//! definition whose name occurs nowhere else in the repository, which this one decides from
//! the corpus.
//!
//! WHAT IT CANNOT DO, stated once rather than hidden in the number: it does not resolve
//! types, so it cannot tell two same-named symbols apart; it does not follow dynamic
//! dispatch, reflection, or framework registration. Every definition a language or a
//! framework can reach by such a route is classified undecidable, listed with the reason, and
//! left OUT of the numerator. The published ratio is therefore a LOWER BOUND, and the
//! undecidable share is disclosed beside it. A pass that guesses in this region reports its
//! own blind spot as a defect in somebody's code.

use crate::indicators::dead_code_corpus::{read_corpus, Corpus};
use crate::indicators::dead_code_defs::{collect, Definition, EXCLUDED, UNDECIDABLE};
use crate::indicators::dead_code_facts::repo_facts;
use crate::indicators::dead_code_grammars;
use crate::indicators::unreachable::unreachable_statements;
use crate::{band, py_round2, Indicator};
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

/// How many findings each list shows.
const CAP: usize = 100;
/// The share of production files the grammar must parse before a ratio is publishable.
const MIN_PARSED_SHARE: f64 = 0.8;
/// C builds function names with the preprocessor, and no syntactic scan can follow a pasted
/// name.
const TOKEN_PASTING: &[u8] = b"##";

/// The word buckets that can spare a definition, in the order they are consulted.
const SOFT_REASONS: &[(&str, &str)] = &[
    ("config", "named in a configuration file (an entry point can be wired by name)"),
    ("strings",
     "named in a string literal or comment (a dynamic reference cannot be resolved)"),
    ("docs", "named only in documentation (a documented symbol is a published surface)"),
];

/// One flagged site, as the report names it.
#[derive(Debug, Clone)]
pub struct Site {
    pub file: String,
    pub name: String,
    pub kind: String,
    pub line: usize,
    pub end_line: usize,
    pub reason: String,
}

/// Split every file into production reference sites and test reference sites.
///
/// A definition reached only from the test tree is not dead, because the tests call it, but it
/// is not load-bearing production code either, so it is reported separately rather than
/// folded into either verdict.
fn classify_files(repo: &Path) -> (BTreeSet<String>, BTreeSet<String>) {
    let has_packages = crate::repo_has_packages(repo);
    let disowned = crate::ignored_paths(repo);
    let mut production = BTreeSet::new();
    let mut tests = BTreeSet::new();
    for entry in crate::walk_repo(repo) {
        let path = entry.path();
        if !crate::is_file_entry(&entry) || crate::in_ignored_dir(path) {
            continue;
        }
        let relpath = path.strip_prefix(repo).unwrap_or(path).to_string_lossy().into_owned();
        let reason = crate::bucket_reason(path, repo, has_packages, crate::PRODUCTION,
                                          crate::PRODUCTION_BUCKETS, &disowned);
        if matches!(reason, Some("tests") | Some("test")) {
            tests.insert(relpath);
        } else {
            production.insert(relpath);
        }
    }
    (production, tests)
}

/// The files a dotted string in this repository loads, which nothing imports.
///
/// A framework hook is registered by a name in a string: a plugin on a command line, a task
/// named by its path, a server started from a factory. The module is real and it really runs,
/// and no import statement anywhere leads to it, so the island rule reads it and every
/// function in it as unreachable.
///
/// A SUFFIX match, because an import path is relative to a package root and a package root is
/// not the repository root. An anchored match found a module when the audit ran from inside
/// the package and lost it when the same audit ran from the repository above.
fn modules_named_by_a_dotted_string(corpus: &Corpus,
                                    production_files: &BTreeSet<String>) -> BTreeSet<String> {
    let mut loaded = BTreeSet::new();
    let empty = BTreeSet::new();
    for dotted in corpus.words.get("dotted").unwrap_or(&empty) {
        let tail = format!("{}.py", dotted.replace('.', "/"));
        let suffix = format!("/{tail}");
        loaded.extend(production_files.iter()
            .filter(|f| **f == tail || f.ends_with(&suffix))
            .cloned());
    }
    loaded
}

/// The stem a Python path defines as a module name.
fn python_stem(relpath: &str) -> &str {
    let name = relpath.rsplit('/').next().unwrap_or(relpath);
    name.strip_suffix(".py").unwrap_or(name)
}

/// The production modules no OTHER production file names.
///
/// A definition was proven alive by a reference from any production file, and the file it is
/// defined in is a production file. So a module whose functions call each other certified its
/// own contents, and the bigger the island the more thoroughly it did so. One 892-line module
/// holding forty functions had its only importer in its own test, and this indicator named two
/// of the forty; the rest were alive because the module called itself.
///
/// Test references deliberately do NOT rescue it: a subsystem certified by its own tests plus
/// itself is the same island one importer wider, and the test-only list already reports that
/// shape honestly. A package initialiser and an entry-point module are never islands, because
/// one re-exports on behalf of a package and the other is invoked rather than imported.
///
/// Python only, because the stem-equals-module-name rule is Python's. Every other language
/// gets the empty set, which under-accuses rather than over-accuses.
fn island_files(corpus: &Corpus, production_files: &BTreeSet<String>) -> BTreeSet<String> {
    let loaded = modules_named_by_a_dotted_string(corpus, production_files);
    let mut islands = BTreeSet::new();
    for relpath in production_files {
        if !relpath.ends_with(".py") {
            continue;
        }
        let stem = python_stem(relpath);
        if stem == "__init__" || stem == "__main__" || loaded.contains(relpath) {
            continue;
        }
        let named_elsewhere = corpus.hard.get(stem).is_some_and(|sites| {
            sites.iter().any(|(site, _o)| production_files.contains(site) && site != relpath)
        });
        if !named_elsewhere {
            islands.insert(relpath.clone());
        }
    }
    islands
}

/// The module names a project file declares as console scripts.
///
/// The last segment only: a script points at a module and a function, and what matters here is
/// which MODULE somebody can run.
pub fn declared_scripts_in(text: &str) -> BTreeSet<String> {
    let mut found = BTreeSet::new();
    let chars: Vec<char> = text.chars().collect();
    let mut i = 0usize;
    while i < chars.len() {
        if chars[i] != '=' {
            i += 1;
            continue;
        }
        let mut j = i + 1;
        while j < chars.len() && chars[j].is_whitespace() {
            j += 1;
        }
        if j >= chars.len() || chars[j] != '"' {
            i += 1;
            continue;
        }
        let start = j + 1;
        let mut k = start;
        while k < chars.len() && (chars[k].is_alphanumeric() || chars[k] == '_' || chars[k] == '.') {
            k += 1;
        }
        if k > start && k < chars.len() && chars[k] == ':' {
            let path: String = chars[start..k].iter().collect();
            found.insert(path.rsplit('.').next().unwrap_or("").to_string());
        }
        i = j + 1;
    }
    found
}

/// Whether the module does work at import time, as opposed to declaring values.
///
/// A bare call at module level is a script running. An assignment whose value happens to be a
/// call is a declaration, and so is a dispatch table naming forty functions. The difference is
/// the statement kind, not whether a call appears.
///
/// The reference asks Python's own parser here, because the clause is Python-only and asking
/// a second parser the same question is how two readers come to disagree about one file. This
/// port has only tree-sitter, so it asks that, and a file it cannot parse is reported runnable,
/// which under-accuses exactly as the reference's own failure path does.
pub fn has_module_level_call(body: &str) -> bool {
    let mut parser = crate::parser_for("python");
    let Some(tree) = parser.parse(body.as_bytes(), None) else { return true };
    let root = tree.root_node();
    if root.has_error() {
        return true;
    }
    crate::nodes::children(root).into_iter()
        .filter(|c| c.is_named() && c.kind() == "expression_statement")
        .any(|stmt| crate::nodes::children(stmt).into_iter()
            .any(|inner| inner.is_named() && inner.kind() == "call"))
}

/// Whether this module's own text says somebody can run it.
///
/// A main guard, which is what a runnable module carries, or a module-level CALL statement,
/// which is a script doing its work at import time. A declaration is neither: without that
/// distinction a module written in the dispatch-table style certified itself, because naming
/// forty functions in a table at module level made all forty roots.
pub fn can_be_run(body: &str) -> bool {
    if has_main_guard(body) {
        return true;
    }
    has_module_level_call(body)
}

/// Whether the text carries a main guard, which the reference matches as a comparison of the
/// module name against the main sentinel with any spacing and either quote.
fn has_main_guard(body: &str) -> bool {
    if !body.contains("__main__") {
        return false;
    }
    let chars: Vec<char> = body.chars().collect();
    let needle: Vec<char> = "__name__".chars().collect();
    let mut i = 0usize;
    while i + needle.len() <= chars.len() {
        if chars[i..i + needle.len()] != needle[..] {
            i += 1;
            continue;
        }
        let mut j = i + needle.len();
        while j < chars.len() && chars[j].is_whitespace() {
            j += 1;
        }
        if j + 1 < chars.len() && chars[j] == '=' && chars[j + 1] == '=' {
            let mut k = j + 2;
            while k < chars.len() && chars[k].is_whitespace() {
                k += 1;
            }
            if k < chars.len() && (chars[k] == '"' || chars[k] == '\'') {
                let quote = chars[k];
                let tail: String = chars[k + 1..].iter().take(9).collect();
                if tail.starts_with("__main__") && tail.chars().nth(8) == Some(quote) {
                    return true;
                }
            }
        }
        i += 1;
    }
    false
}

/// The island modules that can actually be RUN, so their module level executes.
///
/// An island is never imported, so its top level runs only if somebody runs the file. Four
/// pieces of evidence say they can and nothing else counts: a main guard, a declared console
/// script naming the module, a module-level call statement, and being the repository's only
/// production module, which is a one-file program.
fn runnable_islands(repo: &Path, islands: &BTreeSet<String>,
                    production_files: &BTreeSet<String>) -> BTreeSet<String> {
    if production_files.len() == 1 {
        return islands.clone();
    }
    let project = std::fs::read_to_string(repo.join("pyproject.toml")).unwrap_or_default();
    let declared = declared_scripts_in(&project);
    let mut runnable = BTreeSet::new();
    for relpath in islands {
        if declared.contains(python_stem(relpath)) {
            runnable.insert(relpath.clone());
            continue;
        }
        match std::fs::read(repo.join(relpath)) {
            // Unreadable: do not accuse on a file nobody could open.
            Err(_) => {
                runnable.insert(relpath.clone());
            }
            Ok(raw) => {
                if can_be_run(&crate::decode_ignoring_invalid(&raw)) {
                    runnable.insert(relpath.clone());
                }
            }
        }
    }
    runnable
}

/// The innermost definition whose span holds `offset`, or nothing for module level.
///
/// Nothing is the answer that matters: a reference at module level runs when the file runs, so
/// it is a root. A reference inside a definition only runs if that definition does.
fn owner_at<'a>(spans: &'a [(usize, usize, String)], offset: usize) -> Option<&'a str> {
    let mut owner: Option<&str> = None;
    let mut width: Option<usize> = None;
    for (start, end, name) in spans {
        if *start <= offset && offset < *end && width.is_none_or(|w| end - start < w) {
            owner = Some(name.as_str());
            width = Some(end - start);
        }
    }
    owner
}

/// Whether the file at `site` can see the module defined in `home`.
///
/// The corpus maps a bare NAME to its reference sites and knows nothing about which module a
/// reference resolves to, so any identifier anywhere in production kept a definition alive.
/// One module was correctly detected as an island and none of its sixty definitions reported,
/// because its function names are also the names of functions in five unrelated modules. Only
/// names unique in the whole repository survived to be reported.
///
/// A file sees a module when it names that module's stem as a real identifier, which is what
/// every form of import leaves behind, or when it is that module.
///
/// Asked ONLY about islands, where the question is already being put and where a wrong answer
/// decides between reporting a subsystem and reporting nothing. Everywhere else the
/// name-pooled behaviour stands, which under-accuses.
fn sees(site: &str, home: &str, corpus: &Corpus) -> bool {
    if site == home {
        return true;
    }
    let stem = if home.ends_with(".py") { python_stem(home) } else { home };
    corpus.hard.get(stem).is_some_and(|sites| sites.iter().any(|(where_, _o)| where_ == site))
}

/// Which definitions in the island modules are actually reachable.
///
/// Reference is not reachability, and the difference is the whole defect. Two functions in a
/// module nothing imports prove each other alive under a reference test, and a subsystem of
/// forty prove each other alive forty times over. The roots are what RUNS: module-level code
/// in a runnable island file, which executes when the file does, and any reference from a
/// production file that is not an island. From those roots this closes over references sitting
/// inside a live definition's span, so a helper called by a live function stays live and a
/// helper called only by a dead one does not.
///
/// Names are global rather than per file because the corpus's reference map is keyed by name,
/// as every other rule here reads it. Two island modules holding a same-named function
/// therefore rescue each other, which over-EXCUSES and is the direction this takes when it
/// cannot tell.
fn island_live_names(definitions: &[(String, Definition)], corpus: &Corpus,
                     production_files: &BTreeSet<String>, islands: &BTreeSet<String>,
                     runnable: &BTreeSet<String>) -> BTreeSet<String> {
    let mut spans: BTreeMap<&str, Vec<(usize, usize, String)>> = BTreeMap::new();
    for (relpath, d) in definitions {
        if islands.contains(relpath) {
            spans.entry(relpath.as_str()).or_default()
                .push((d.start_byte, d.end_byte, d.name.clone()));
        }
    }
    let no_spans: Vec<(usize, usize, String)> = Vec::new();
    let sites = |d: &Definition, relpath: &str| -> Vec<(String, usize)> {
        corpus.hard.get(&d.name).map(|uses| uses.iter()
            .filter(|(site, offset)| {
                if !production_files.contains(site) {
                    return false;
                }
                // The definition's own name token, or its recursion.
                if site == relpath && d.start_byte <= *offset && *offset < d.end_byte {
                    return false;
                }
                // A same-named symbol in a module that cannot see this one.
                sees(site, relpath, corpus)
            })
            .cloned()
            .collect())
            .unwrap_or_default()
    };

    let mut live: BTreeSet<String> = BTreeSet::new();
    for (relpath, d) in definitions {
        if !islands.contains(relpath) {
            continue;
        }
        for (site, offset) in sites(d, relpath) {
            let rooted = !islands.contains(&site)
                || (runnable.contains(&site)
                    && owner_at(spans.get(site.as_str()).unwrap_or(&no_spans), offset).is_none());
            if rooted {
                live.insert(d.name.clone());
                break;
            }
        }
    }

    let mut changed = true;
    while changed {
        changed = false;
        for (relpath, d) in definitions {
            if !islands.contains(relpath) || live.contains(&d.name) {
                continue;
            }
            for (site, offset) in sites(d, relpath) {
                if !islands.contains(&site) {
                    continue;
                }
                let owner = owner_at(spans.get(site.as_str()).unwrap_or(&no_spans), offset);
                if owner.is_some_and(|o| live.contains(o)) {
                    live.insert(d.name.clone());
                    changed = true;
                    break;
                }
            }
        }
    }
    live
}

/// Why a definition in a module loaded by name cannot be called dead.
///
/// The reader knows the module runs, because something in the tree names its path in a string
/// and hands that to a framework. What it cannot know is which of its functions the framework
/// calls, and none of those calls is written down anywhere the parser can read. Undecidable,
/// which is the same answer this gives everywhere it can see that something is happening
/// without seeing what.
fn loaded_reason(relpath: &str, loaded: &BTreeSet<String>) -> &'static str {
    if loaded.contains(relpath) {
        "in a module loaded by name from a string (a framework calls into it without an import)"
    } else {
        ""
    }
}

/// True when the name has a real identifier use in one of `files`, outside the definition's
/// own span. Excluding its own span is what stops a self-recursive call, or the name token
/// itself, from proving the definition alive.
fn referenced_from(d: &Definition, relpath: &str, corpus: &Corpus,
                   files: &BTreeSet<String>) -> bool {
    corpus.hard.get(&d.name).is_some_and(|uses| uses.iter().any(|(site, offset)| {
        if !files.contains(site) {
            return false;
        }
        !(site == relpath && d.start_byte <= *offset && *offset < d.end_byte)
    }))
}

fn soft_reason(name: &str, corpus: &Corpus) -> &'static str {
    let empty = BTreeSet::new();
    for (bucket, reason) in SOFT_REASONS {
        if corpus.words.get(bucket).unwrap_or(&empty).contains(name) {
            return reason;
        }
    }
    ""
}

/// Name a finding list that was cut, so it stops disagreeing with the count beside it.
fn listed_note(shown: usize, total: usize) -> String {
    if total <= shown { String::new() } else { format!("; {shown} of them listed below") }
}

/// The whole reading, so a caller that wants the lists can have them.
pub struct DeadCode {
    pub row: Indicator,
    pub findings: Vec<Site>,
    pub undecidable: Vec<Site>,
    pub test_only: Vec<Site>,
}

fn na(reason: String) -> DeadCode {
    DeadCode {
        row: Indicator { code: "L1.12".into(), label: "dead-code".into(), value: "n/a".into(),
                         band: "n/a".into(), details: reason },
        findings: Vec::new(), undecidable: Vec::new(), test_only: Vec::new(),
    }
}

/// L1.12 for one repository.
pub fn read(repo: &Path, lang: &str) -> DeadCode {
    let extensions = dead_code_grammars::extensions_for(lang);
    if extensions.is_empty() {
        return na(format!(
            "no native dead-code analysis for {lang}; the canon's tool for it is not wired"));
    }
    let (sources, _skipped) = dead_code_grammars::parsed_files(repo, lang);
    if sources.is_empty() {
        return na(format!("no production {lang} source in scope"));
    }
    let facts = repo_facts(repo, lang);
    if !facts.ruby_metaprogramming.is_empty() {
        return na(format!(
            "not measured for ruby: the repository uses runtime metaprogramming ({}), so an \
             unreferenced name is not evidence of dead code", facts.ruby_metaprogramming));
    }

    let (production_files, test_files) = classify_files(repo);
    let corpus = read_corpus(repo);

    let mut production_loc = 0usize;
    let mut analyzed_loc = 0usize;
    let mut definitions: Vec<(String, Definition)> = Vec::new();
    let mut unreachable: Vec<Site> = Vec::new();
    let mut unparsed = 0usize;
    let mut pasted = 0usize;
    for (rel, tree, src, test_lines) in &sources {
        // Minus this file's test region, which the reader above replaced with spaces rather
        // than deleting, so that every line number stays the one the author would see.
        // `splitlines` counts those spaces back in. A Rust unit test lives in the file it
        // tests, so counting them here took a crate's tests out of the numerator and left them
        // under it: 2,532 of uuid-rs/uuid's 9,821 lines are test module, and its dead-code
        // ratio was a quarter of what it should have read.
        let lines = crate::py_splitlines(&crate::decode_ignoring_invalid(src)).len() - test_lines;
        production_loc += lines;
        analyzed_loc += lines;
        // A tree the grammar could not parse cannot support a claim about what it contains:
        // one large file parses with error nodes and the statements around them read as
        // unreachable, sixteen of them. Its identifiers are still harvested as references by
        // the corpus, which can only spare a symbol, never condemn one.
        if tree.root_node().has_error() {
            unparsed += 1;
            analyzed_loc -= lines;
            continue;
        }
        // C builds function names with the preprocessor, so a function is called at a site
        // where its name never appears. No syntactic scan can follow a pasted name, so a file
        // that pastes has its definitions disclosed as undecidable instead.
        if lang == "c" && src.windows(TOKEN_PASTING.len()).any(|w| w == TOKEN_PASTING) {
            pasted += 1;
            if let Some(found) = collect(tree.root_node(), lang, rel, &facts, src) {
                definitions.extend(found.into_iter().map(|d| (rel.clone(), Definition {
                    status: UNDECIDABLE,
                    reason: "the file builds identifiers with preprocessor token pasting (##), \
                             so a call site need not spell this name".into(),
                    ..d
                })));
            }
            continue;
        }
        if let Some(found) = collect(tree.root_node(), lang, rel, &facts, src) {
            definitions.extend(found.into_iter().map(|d| (rel.clone(), d)));
        }
        if let Some(found) = unreachable_statements(tree.root_node(), lang) {
            unreachable.extend(found.into_iter().map(|u| Site {
                file: rel.clone(), name: String::new(), kind: "statement".into(),
                line: u.line, end_line: u.end_line, reason: String::new(),
            }));
        }
    }

    let parsed_share = (sources.len() - unparsed) as f64 / sources.len() as f64;
    if parsed_share < MIN_PARSED_SHARE {
        return na(format!(
            "not measured for {lang}: the grammar parsed only {:.0}% of the {} production \
             file(s) ({unparsed} failed), which is below the {:.0}% floor this indicator \
             needs. tree-sitter does not run a preprocessor, so macro-decorated declarations \
             and #if regions do not parse; a ratio computed over the remainder would describe \
             a different codebase",
            parsed_share * 100.0, sources.len(), MIN_PARSED_SHARE * 100.0));
    }

    let loaded = modules_named_by_a_dotted_string(&corpus, &production_files);
    let islands = if lang == "python" {
        island_files(&corpus, &production_files)
    } else {
        BTreeSet::new()
    };
    let runnable = runnable_islands(repo, &islands, &production_files);
    let island_live = island_live_names(&definitions, &corpus, &production_files, &islands,
                                        &runnable);

    let mut dead: Vec<Site> = Vec::new();
    let mut undecidable: Vec<Site> = Vec::new();
    let mut test_only: Vec<Site> = Vec::new();
    let mut excluded = 0usize;
    for (relpath, d) in &definitions {
        let entry = |reason: &str| Site {
            file: relpath.clone(), name: d.name.clone(), kind: d.kind.to_string(),
            line: d.line, end_line: d.end_line, reason: reason.to_string(),
        };
        if d.status == EXCLUDED {
            excluded += 1;
        } else if d.status == UNDECIDABLE {
            undecidable.push(entry(&d.reason));
        } else if (!islands.contains(relpath) || island_live.contains(&d.name))
            && referenced_from(d, relpath, &corpus, &production_files) {
            // An island definition nothing reaches has no production reference worth
            // consulting: the references it has are its neighbours', and its neighbours are
            // unreachable too. It falls through to the same tail as any other unreferenced
            // definition, so a test consumer still reports test-only and a configuration
            // entry point still reports undecidable.
            continue;
        } else if referenced_from(d, relpath, &corpus, &test_files) {
            test_only.push(entry("referenced only from the test tree"));
        } else {
            let reason = match loaded_reason(relpath, &loaded) {
                "" => soft_reason(&d.name, &corpus),
                loaded => loaded,
            };
            if reason.is_empty() {
                dead.push(entry(""));
            } else {
                undecidable.push(entry(reason));
            }
        }
    }

    let mut flagged: BTreeSet<(String, usize)> = BTreeSet::new();
    for f in dead.iter().chain(unreachable.iter()) {
        for line in f.line..=f.end_line {
            flagged.insert((f.file.clone(), line));
        }
    }
    if production_loc == 0 {
        // Nought here bands healthy, so a tree with no lines to measure published "no dead
        // code" over a measurement that never happened.
        return na(format!(
            "no production {lang} lines to measure: {} definition(s) were read but the files \
             carry no countable code", definitions.len()));
    }
    let percent = (flagged.len() as f64 / production_loc as f64 * 100.0 * 100.0).round() / 100.0;
    let mut details = format!(
        "{} flagged line(s) of {production_loc} production {lang} LOC ({analyzed_loc} of them \
         analyzed) ({} unreferenced definition(s), {} unreachable statement(s)); {} \
         definition(s) undecidable and excluded from the numerator, {} referenced only by \
         tests, {excluded} runtime entry point(s); lower bound - dynamic dispatch, reflection \
         and framework registration are not resolved",
        flagged.len(), dead.len(), unreachable.len(), undecidable.len(), test_only.len());
    if unparsed != 0 {
        details.push_str(&format!(
            "; {unparsed} file(s) the grammar could not parse, not analyzed"));
    }
    if pasted != 0 {
        details.push_str(&format!(
            "; {pasted} file(s) use preprocessor token pasting, definitions undecidable"));
    }
    if corpus.unreadable != 0 {
        details.push_str(&format!(
            "; {} file(s) unreadable or oversized and excluded", corpus.unreadable));
    }
    // Three lists share one cap, so the note names the largest of them: a reader told the
    // findings were cut knows to check the others rather than trust their lengths.
    details.push_str(&listed_note(CAP, (dead.len() + unreachable.len())
        .max(undecidable.len()).max(test_only.len())));

    let by_place = |a: &Site, b: &Site| a.file.cmp(&b.file).then(a.line.cmp(&b.line));
    let mut findings: Vec<Site> = dead.into_iter().chain(unreachable).collect();
    findings.sort_by(by_place);
    undecidable.sort_by(by_place);
    test_only.sort_by(by_place);
    findings.truncate(CAP);
    undecidable.truncate(CAP);
    test_only.truncate(CAP);

    DeadCode {
        row: Indicator {
            code: "L1.12".into(), label: "dead-code".into(),
            value: py_round2(percent), band: band(percent, 1.0, 5.0, false).into(), details,
        },
        findings, undecidable, test_only,
    }
}

/// The panel row for this indicator.
pub fn analyze(repo: &Path, language: &str) -> Indicator {
    read(repo, language).row
}
