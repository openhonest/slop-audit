//! Interleaving robustness, which is concurrency anti-coverage. Ported from
//! l1_analyzer.interleaving_robustness.
//!
//! It cross-references the static thread surface, which says WHERE shared concurrency state
//! is, against which of that surface a model checker actually exercises. Surface no model
//! touches is unmodelled: the interleavings its invariants depend on are never forced in
//! testing, so a green suite says nothing about them.
//!
//! Honesty, stated plainly because Rust reviewers will check it. This measures model
//! PRESENCE, not model ADEQUACY: "unmodelled", meaning no model touches this file, is the
//! confident direction, and "modelled" is necessary rather than sufficient, because a model
//! may exist and still not exercise the specific interleaving. It is a static heuristic: a
//! model test in another file can drive a surface file without living in it, so a surface
//! file is called modelled-elsewhere, a weaker signal, when a file carrying a model also
//! names its module, and unmodelled only when nothing does.
//!
//! The verdict is a prioritised audit list, never a bug claim. An unmodelled site reads
//! "force these schedules with a model", not "this races".

use crate::indicators::thread_surface;
use crate::Indicator;
use std::collections::BTreeSet;
use std::path::Path;

/// A verdict, not a band: some of the flagged surface has no model.
pub const UNMODELED: &str = "unmodeled";
pub const MODELED: &str = "modeled";
pub const CLEAN: &str = "clean";

/// The two model checkers this reads for.
const MODELS: &[&str] = &["loom", "shuttle"];

/// Whether `text` carries a concurrency-model marker.
///
/// The reference matches `cfg\((?:loom|shuttle)\)|\b(?:loom|shuttle)::`. The word boundary
/// is the whole of the second arm: `myloom::` names somebody's own module and is not a model,
/// so the character before the name has to be one that cannot continue an identifier.
fn carries_a_model(text: &str) -> bool {
    for model in MODELS {
        if text.contains(&format!("cfg({model})")) {
            return true;
        }
        let path = format!("{model}::");
        let mut from = 0usize;
        while let Some(at) = text[from..].find(&path) {
            let start = from + at;
            let before = text[..start].chars().next_back();
            if !before.is_some_and(|c| c.is_alphanumeric() || c == '_') {
                return true;
            }
            from = start + path.len();
        }
    }
    false
}

/// Whether `text` names `word` as a whole word.
///
/// The reference searches for the module name between word boundaries, so a module called
/// `wal` is not found inside `interval`.
fn names_word(text: &str, word: &str) -> bool {
    if word.is_empty() {
        return false;
    }
    let is_word = |c: char| c.is_alphanumeric() || c == '_';
    let mut from = 0usize;
    while let Some(at) = text[from..].find(word) {
        let start = from + at;
        let end = start + word.len();
        let before = text[..start].chars().next_back();
        let after = text[end..].chars().next();
        if !before.is_some_and(is_word) && !after.is_some_and(is_word) {
            return true;
        }
        from = start + word.len();
    }
    false
}

/// The Rust module name a file defines: a path ending `shared_wal.rs` defines `shared_wal`.
/// That is what a declaration or a use in a model test would name.
fn module_stem(rel_path: &str) -> &str {
    let name = rel_path.rsplit('/').next().unwrap_or(rel_path);
    name.strip_suffix(".rs").unwrap_or(name)
}

/// How the flagged surface splits by whether a model touches it.
pub struct Split {
    pub unmodeled: Vec<String>,
    pub modeled_elsewhere: Vec<String>,
    /// Surface whose OWN file carries a model marker.
    ///
    /// Named apart from the set handed in below, which is every file carrying a marker
    /// whether it holds surface or not. The reference calls both `modeled_in_file`, and two
    /// different facts under one name is how a reader comes to think the split is echoing
    /// its input back.
    pub modeled_in_own_file: Vec<String>,
}

/// Split flagged-surface files by whether a model touches them.
///
/// A surface file is modelled in file when its own file carries a marker; modelled elsewhere
/// when some modelled file names its module, which is a weak signal and not proof the
/// interleaving is exercised; and unmodelled otherwise, which is the confident gap.
pub fn classify(surface_files: &BTreeSet<String>, files_carrying_a_model: &BTreeSet<String>,
                modeled_text: &str) -> Split {
    let mut split = Split { unmodeled: Vec::new(), modeled_elsewhere: Vec::new(),
                            modeled_in_own_file: Vec::new() };
    for path in surface_files {
        if files_carrying_a_model.contains(path) {
            split.modeled_in_own_file.push(path.clone());
        } else if names_word(modeled_text, module_stem(path)) {
            split.modeled_elsewhere.push(path.clone());
        } else {
            split.unmodeled.push(path.clone());
        }
    }
    split
}

fn row(value: String, details: String) -> Indicator {
    Indicator {
        code: "interleaving_robustness".into(), label: "interleaving-robustness".into(),
        value, band: "n/a".into(), details,
    }
}

/// Of the flagged concurrency surface, which files no model checker touches.
pub fn analyze(repo: &Path, language: &str) -> Indicator {
    if language != "rust" {
        return row("n/a".into(), format!(
            "interleaving-robustness meter is Rust/loom/shuttle only; {language} not \
             supported yet"));
    }
    let surface = thread_surface::scan(repo, "rust");
    // An unread surface scan makes "no exposed surface to model" a claim about nothing, and
    // inheriting it would put the fabricated clean back one module downstream, which is
    // where a fixed defect returns. The input's own refusal is passed through rather than
    // reworded: this meter has no independent reading of the source to fall back on.
    if surface.verdict == thread_surface::UNREAD {
        return row("n/a".into(), format!(
            "the thread-safety surface meter read no source, so there is no surface to \
             compare against the model checkers: {}", surface.details));
    }
    let surface_files: BTreeSet<String> = surface.findings.iter()
        .filter(|f| f.severity == thread_surface::EXPOSED)
        .map(|f| f.file.clone())
        .collect();
    if surface_files.is_empty() {
        return Indicator {
            code: "interleaving_robustness".into(), label: "interleaving-robustness".into(),
            value: "no exposed surface".into(), band: "n/a".into(),
            details: "no hand-overridden concurrency surface to model".into(),
        };
    }

    // The WHOLE repository, tests included: a model checker lives in the test tree by
    // design, so scoping it out would report every modelled file as unmodelled.
    let mut files_carrying_a_model: BTreeSet<String> = BTreeSet::new();
    let mut modeled_chunks: Vec<String> = Vec::new();
    for (path, text) in crate::source_files(repo, &["rs"]) {
        if !carries_a_model(&text) {
            continue;
        }
        let rel = path.strip_prefix(repo).unwrap_or(&path).to_string_lossy().into_owned();
        files_carrying_a_model.insert(rel);
        modeled_chunks.push(text);
    }

    let split = classify(&surface_files, &files_carrying_a_model, &modeled_chunks.join("\n"));
    let details = format!(
        "{} flagged-surface file(s) no loom/shuttle model touches, {} named by a model \
         (unproven), {} modelled in-file, across {} exposed-surface files",
        split.unmodeled.len(), split.modeled_elsewhere.len(), split.modeled_in_own_file.len(),
        surface_files.len());
    // The verdict is computed by `verdict_of` where a caller needs it. Computing it here
    // and dropping it would be a value nothing reads, which this instrument counts against
    // other people's code.
    row(format!("{} of {} exposed-surface files unmodeled",
                split.unmodeled.len(), surface_files.len()), details)
}

/// Whether this reading reached a verdict about surface it actually read.
pub fn verdict_of(split: &Split) -> &'static str {
    if split.unmodeled.is_empty() { MODELED } else { UNMODELED }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_model_marker_is_the_checker_and_not_a_module_that_ends_in_its_name() {
        assert!(carries_a_model("#[cfg(loom)]\nfn f() {}"));
        assert!(carries_a_model("use shuttle::sync::Mutex;"));
        assert!(carries_a_model("    loom::model(|| {});"));
        // A word boundary is the whole of the second arm.
        assert!(!carries_a_model("use myloom::thing;"));
        assert!(!carries_a_model("let looms = 3;"));
    }

    #[test]
    fn a_module_name_is_matched_whole_and_not_inside_another_word() {
        assert!(names_word("mod wal;\nuse crate::wal::Coord;", "wal"));
        assert!(!names_word("let interval = 3;", "wal"));
    }

    #[test]
    fn the_module_a_file_defines_is_its_own_name() {
        assert_eq!(module_stem("src/storage/shared_wal_coordination.rs"),
                   "shared_wal_coordination");
        assert_eq!(module_stem("lib.rs"), "lib");
    }

    #[test]
    fn surface_splits_three_ways_and_only_the_last_is_a_finding() {
        let surface: BTreeSet<String> =
            ["a.rs", "b.rs", "c.rs"].iter().map(|s| s.to_string()).collect();
        let in_file: BTreeSet<String> = ["a.rs"].iter().map(|s| s.to_string()).collect();
        let split = classify(&surface, &in_file, "mod b;\nloom::model(|| {});");
        assert_eq!(split.modeled_in_own_file, vec!["a.rs"]);
        assert_eq!(split.modeled_elsewhere, vec!["b.rs"]);
        assert_eq!(split.unmodeled, vec!["c.rs"]);
        assert_eq!(verdict_of(&split), UNMODELED);
    }

    #[test]
    fn a_language_this_meter_does_not_serve_says_so_rather_than_reading_clean() {
        let got = analyze(Path::new("."), "python");
        assert_eq!(got.value, "n/a");
        assert!(got.details.contains("Rust/loom/shuttle only"), "{}", got.details);
    }
}
