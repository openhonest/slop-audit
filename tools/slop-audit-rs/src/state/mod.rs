//! The state analysis: how this binary finds the state a repository holds, what it can say
//! about whether that state is bounded, and what it admits it never reached.
//!
//! Ported module by module from l1_analyzer, in the order the analysis depends on. The
//! sequencing is not a preference: L1.18 (mutable state) cannot be computed ahead of
//! L1.18b (finite testability), because the mutable-state count excludes every reference
//! the finite-testability classifier could bound. A port of L1.18 alone would count those
//! and disagree with the reference on every repository, and a binary that disagrees is
//! worse than one declaring a gap, because the gap line is honest.

pub mod census;
pub mod sites;
