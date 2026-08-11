//! L1.9-L1.11 config presence (language-agnostic file/dir existence checks). Ported from
//! l1_analyzer.indicators.compute_config_indicators; validated equal.
//!
//! Shape: three independent `pub fn`s, one per indicator, each returning an `Indicator`:
//!   l1_09(repo) -> pre-commit hooks   (present/absent -> Healthy/Slop)
//!   l1_10(repo) -> CI/CD pipelines    (count of .github/workflows/*.yml|*.yaml -> band 5/1)
//!   l1_11(repo) -> containerization   (present and parameterized/absent -> Healthy/Slop)

use crate::{band, Indicator};
use std::path::Path;

/// L1.9 pre-commit hooks: `.pre-commit-config.yaml` file or `.husky` dir at repo root.
pub fn l1_09(repo: &Path) -> Indicator {
    let has_precommit = repo.join(".pre-commit-config.yaml").exists() || repo.join(".husky").exists();
    Indicator {
        code: "L1.9".into(),
        label: "pre-commit hooks".into(),
        value: (if has_precommit { "present" } else { "absent" }).into(),
        band: (if has_precommit { "Healthy" } else { "Slop" }).into(),
        details: String::new(),
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
        details: String::new(),
    }
}

/// L1.11 containerization: `Dockerfile` or `docker-compose.yml` file at repo root.
pub fn l1_11(repo: &Path) -> Indicator {
    let has_docker = repo.join("Dockerfile").exists() || repo.join("docker-compose.yml").exists();
    Indicator {
        code: "L1.11".into(),
        label: "containerization".into(),
        value: (if has_docker { "present and parameterized" } else { "absent" }).into(),
        band: (if has_docker { "Healthy" } else { "Slop" }).into(),
        details: String::new(),
    }
}