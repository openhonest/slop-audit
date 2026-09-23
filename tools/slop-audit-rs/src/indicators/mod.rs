//! Indicator registry. Each submodule is one indicator (or a small group). Ported from
//! the pre-registered Python l1_analyzer and validated equal to it.
pub mod absolute_paths;
pub mod config_presence;
pub mod data_tables;
pub mod dead_code_defs;
pub mod dead_code_facts;
pub mod decision_space;
pub mod duplication;
pub mod git_ratios;
pub mod god_files;
pub mod interleaving;
pub mod mutable_state;
pub mod path_cover;
pub mod thread_scanners;
pub mod thread_surface;
pub mod type_escapes;
pub mod whitespace;
pub mod unreachable;
