//! Indicator registry. Each submodule is one indicator (or a small group). Ported from
//! the pre-registered Python l1_analyzer and validated equal to it.
pub mod absolute_paths;
pub mod config_presence;
pub mod decision_space;
pub mod git_ratios;
pub mod god_files;
pub mod mutable_state;
pub mod path_cover;
pub mod thread_scanners;
pub mod thread_surface;
pub mod type_escapes;
pub mod whitespace;
