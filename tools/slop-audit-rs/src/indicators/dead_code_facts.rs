//! The three repository-level questions a single file cannot answer for itself. Ported from
//! the facts half of l1_analyzer.dead_code_corpus.
//!
//! Each one changes what a definition's STATUS is rather than whether it is found: a public
//! item of a library crate is undecidable and the same item in a binary crate is a candidate,
//! a file named as a package entry point exports names nothing in the tree imports, and a
//! Ruby repository that uses runtime metaprogramming cannot be read for dead code at all.

use std::collections::BTreeSet;
use std::path::Path;

use crate::indicators::dead_code_defs::RepoFacts;

/// The markers that mean a Ruby repository binds names at run time.
///
/// One is enough for the repository-level gate, which decides whether any dead-code reading
/// of Ruby is publishable.
const METAPROGRAMMING: &[&str] = &["define_method", "method_missing", "const_get",
                                   "instance_variable_get", "class_eval", "instance_eval",
                                   "ActiveRecord", "ActiveSupport"];

/// The first metaprogramming marker this Ruby source uses, or nothing.
pub fn metaprogramming_in(text: &str) -> &'static str {
    METAPROGRAMMING.iter().copied().find(|marker| text.contains(marker)).unwrap_or("")
}

/// The manifest keys that name a single entry-point path.
const ENTRY_KEYS: &[&str] = &["main", "module", "browser", "types", "typings"];

/// The entry points one package manifest declares, relative to the repository.
///
/// Five keys name a single path and one names a map of them. A map key whose value is a bare
/// string is legal and is NOT a map, which is why the shape is checked rather than assumed:
/// reading it as one iterates the characters of the string.
///
/// Read with a real JSON parser rather than by scanning for quoted keys. A manifest is
/// somebody else's file, escapes and nesting and all, and a hand-rolled reader of it is a
/// source of quiet wrong answers rather than loud ones.
pub fn entry_paths_in(data: &serde_json::Value, base: &Path, repo: &Path) -> BTreeSet<String> {
    let mut found = BTreeSet::new();
    let mut add = |value: &serde_json::Value| {
        if let Some(path) = value.as_str() {
            let joined = base.join(path);
            if let Ok(rel) = joined.strip_prefix(repo) {
                found.insert(rel.to_string_lossy().into_owned());
            }
        }
    };
    for key in ENTRY_KEYS {
        if let Some(value) = data.get(key) {
            add(value);
        }
    }
    if let Some(map) = data.get("bin").and_then(|b| b.as_object()) {
        for value in map.values() {
            add(value);
        }
    }
    found
}

/// The three facts, read once per repository.
pub fn repo_facts(repo: &Path, lang: &str) -> RepoFacts {
    let mut rust_is_library = repo.join("src").join("lib.rs").exists();
    let mut js_entry_files: BTreeSet<String> = BTreeSet::new();
    let mut ruby_metaprogramming = String::new();

    // SORTED, because the marker named in the refusal is whichever file the walk reaches
    // first, and neither walk yields in a specified order. Two machines could name different
    // markers for the same repository; this port named a third. The refusal itself never
    // moved, only the evidence it cites, which is the kind of number nobody checks because it
    // looks like a detail. The reference sorts here too.
    let mut paths: Vec<std::path::PathBuf> = crate::walk_repo(repo)
        .filter(|entry| crate::is_file_entry(entry) && !crate::in_ignored_dir(entry.path()))
        .map(|entry| entry.path().to_path_buf())
        .collect();
    paths.sort();
    for path in &paths {
        let path = path.as_path();
        let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("");
        if name == "lib.rs" {
            rust_is_library = true;
        } else if name == "package.json" {
            if let Ok(raw) = std::fs::read_to_string(path) {
                if let Ok(data) = serde_json::from_str::<serde_json::Value>(&raw) {
                    let base = path.parent().unwrap_or(repo);
                    js_entry_files.extend(entry_paths_in(&data, base, repo));
                }
            }
        } else if lang == "ruby" && ruby_metaprogramming.is_empty()
            && path.extension().and_then(|e| e.to_str()) == Some("rb") {
            if let Ok(text) = std::fs::read_to_string(path) {
                ruby_metaprogramming = metaprogramming_in(&text).to_string();
            }
        }
    }
    RepoFacts { rust_is_library, js_entry_files, ruby_metaprogramming }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_manifest_names_its_entry_points_and_a_bare_bin_is_not_a_map() {
        // A bin that is a bare string is legal, and reading it as a map iterates the
        // characters of the string.
        let data: serde_json::Value = serde_json::from_str(
            r#"{"main": "dist/index.js", "types": "dist/index.d.ts", "bin": "cli.js"}"#)
            .expect("valid json");
        let found = entry_paths_in(&data, Path::new("/repo"), Path::new("/repo"));
        assert_eq!(found.into_iter().collect::<Vec<_>>(),
                   vec!["dist/index.d.ts", "dist/index.js"]);
    }

    #[test]
    fn a_bin_map_names_every_command_it_declares() {
        let data: serde_json::Value = serde_json::from_str(
            r#"{"bin": {"a": "bin/a.js", "b": "bin/b.js"}}"#).expect("valid json");
        let found = entry_paths_in(&data, Path::new("/repo"), Path::new("/repo"));
        assert_eq!(found.into_iter().collect::<Vec<_>>(), vec!["bin/a.js", "bin/b.js"]);
    }

    #[test]
    fn one_metaprogramming_marker_is_enough_and_the_first_is_named() {
        assert_eq!(metaprogramming_in("class C\n  define_method(:x) {}\nend\n"),
                   "define_method");
        assert_eq!(metaprogramming_in("class C\n  def x; end\nend\n"), "");
    }
}
