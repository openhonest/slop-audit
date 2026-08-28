//! L1.9-L1.11 config presence (language-agnostic file/dir existence checks). Ported from
//! l1_analyzer.indicators.compute_config_indicators; validated equal.
//!
//! Shape: L1.9 and L1.11 ask the same question of different paths, so they are one
//! function and a table of two rows. Written as two functions they were two bodies with one
//! shape, differing only in the filenames and the words, which this project's own
//! conformity check reported the first time it was pointed at a Rust file.
//!   present_at(repo, PRECOMMIT) -> pre-commit hooks   (present/absent -> Healthy/Slop)
//!   l1_10(repo)                 -> CI/CD pipelines    (count of workflows -> band 5/1)
//!   present_at(repo, CONTAINER) -> containerization   (present/absent -> Healthy/Slop)

use crate::{band, Indicator};
use std::path::Path;


/// One indicator that asks whether any of a set of paths exists at the repository root.
pub struct Presence {
    pub code: &'static str,
    pub label: &'static str,
    pub paths: &'static [&'static str],
    pub present_value: &'static str,
    pub present_details: &'static str,
    pub absent_details: &'static str,
}

/// L1.9 pre-commit hooks: a `.pre-commit-config.yaml` file or a `.husky` dir at the root.
pub const PRECOMMIT: Presence = Presence {
    code: "L1.9",
    label: "pre-commit hooks",
    paths: &[".pre-commit-config.yaml", ".husky"],
    present_value: "present",
    present_details: "a pre-commit hook config is present",
    absent_details: "no .pre-commit-config.yaml and no .husky directory at the repository root",
};

/// L1.11 containerization: a `Dockerfile` or `docker-compose.yml` file at the root.
pub const CONTAINER: Presence = Presence {
    code: "L1.11",
    label: "containerization",
    paths: &["Dockerfile", "docker-compose.yml"],
    present_value: "present and parameterized",
    present_details: "a Dockerfile or docker-compose.yml is present at the repository root",
    absent_details: "no Dockerfile and no docker-compose.yml at the repository root",
};

/// Both rows read by one body. These shipped a band and a value with no sentence, in both
/// tools, until the reference's result type was made total on 2026-08-19. A reader got Slop
/// with nothing saying what was looked for or where.
pub fn present_at(repo: &Path, what: &Presence) -> Indicator {
    let found = what.paths.iter().any(|p| repo.join(p).exists());
    Indicator {
        code: what.code.into(),
        label: what.label.into(),
        value: (if found { what.present_value } else { "absent" }).into(),
        band: (if found { "Healthy" } else { "Slop" }).into(),
        details: (if found { what.present_details } else { what.absent_details }).into(),
    }
}

/// L1.10 CI/CD pipelines: count of `.github/workflows/*.yml` + `*.yaml` entries. Mirrors
/// Python's non-recursive `Path.glob`, which yields nothing when the directory is absent
/// and matches any entry (file or directory) whose name ends in the suffix.
pub fn l1_10(repo: &Path) -> Indicator {
    let workflows = repo.join(".github").join("workflows");
    let ci_count = match std::fs::read_dir(&workflows) {
        Ok(entries) => entries
            .filter_map(Result::ok)
            .filter(|e| {
                e.file_name()
                    .to_str()
                    .map(|n| n.ends_with(".yml") || n.ends_with(".yaml"))
                    .unwrap_or(false)
            })
            .count(),
        Err(_) => 0,
    };
    Indicator {
        code: "L1.10".into(),
        label: "CI/CD pipelines".into(),
        value: ci_count.to_string(),
        band: band(ci_count as f64, 5.0, 1.0, true).into(),
        details: if ci_count > 0 {
            format!("{ci_count} workflow file(s) in .github/workflows")
        } else {
            "no .yml or .yaml workflow files in .github/workflows".into()
        },
    }
}
