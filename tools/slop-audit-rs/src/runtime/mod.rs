//! Running an audited project's own test suite, and reading what came back.
//!
//! THIS BINARY EXECUTES CLIENT CODE. That was a deliberate decision, taken on 2026-09-21,
//! and it reverses the position this crate held from the day it was written. The old
//! refusal said "requires executing the target's own test suite, which this binary does
//! not do", and an auditor could hand the binary to a client's security team on that
//! sentence. They cannot any more, and the documentation says so rather than leaving
//! anybody to find out.
//!
//! What the decision obliges, and what this module owes:
//!
//! A suite runs in a NEW PROCESS GROUP with a hard timeout, and the whole group is killed
//! when the clock runs out. A test that spawns children and hangs must not leave them
//! behind on a machine that is not ours.
//!
//! Every refusal survives. A suite that did not run, timed out, ran no tests or wrote no
//! report is NOT a coverage figure, and a harness that reports zero where it could not
//! measure would be worse here than anywhere else: this number arrives at a client under
//! an auditor's name.
//!
//! Everything a run writes is untrusted input. Output is read for a number and never
//! executed, and no reading of it decides what runs next.

pub mod coverage;
pub mod coverage_runners;
pub mod coverage_rust;
pub mod determinism;
pub mod runners;
pub mod runners_java;
pub mod runners_js;

use std::path::Path;
use std::process::{Command, Stdio};

/// What one finished run of a suite left behind.
///
/// The exit status 124 is a TIMEOUT and not the suite's own code, which is the convention
/// the reference uses and every verdict below reads. A suite that genuinely exits 124 is
/// indistinguishable from one that was killed, and that conflation is the reference's too:
/// recorded here rather than silently inherited.
#[derive(Debug, Clone)]
pub struct Finished {
    pub status: i32,
    pub stdout: String,
    pub stderr: String,
    /// Whether this run was isolated well enough that killing it reached its children.
    /// Read by the timeout refusal, which owes a reader the difference.
    pub isolation: Isolation,
}

impl Finished {
    /// Everything the run said, both streams together. Several readers want one text, and
    /// a tool that writes its summary to stderr is common enough that reading only stdout
    /// loses the answer.
    pub fn output(&self) -> String {
        format!("{}{}", self.stdout, self.stderr)
    }
}

/// The exit status that means the clock ran out rather than the suite deciding anything.
pub const TIMED_OUT: i32 = 124;

/// Run untrusted test code in a new process group, and kill the whole group on timeout.
///
/// A new session, so the kill reaches every child the suite spawned. A suite that starts a
/// database and hangs must not leave it running on a machine this binary was handed to for
/// an afternoon.
///
/// The timeout is the caller's number and is never defaulted here: every refusal that comes
/// of it names the seconds it allowed, and a caller that did not say what it allowed cannot
/// be quoted.
pub fn run_untrusted(command: &[String], cwd: &Path, env: &[(String, String)],
                     timeout_seconds: f64) -> Finished {
    let Some((program, args)) = command.split_first() else {
        return Finished { status: TIMED_OUT, stdout: String::new(),
                          stderr: "no command to run".into(),
                          isolation: Isolation::Grouped };
    };
    let mut cmd = Command::new(program);
    cmd.args(args).current_dir(cwd).stdout(Stdio::piped()).stderr(Stdio::piped());
    for (key, value) in env {
        cmd.env(key, value);
    }
    let isolation = new_process_group(&mut cmd);

    let mut child = match cmd.spawn() {
        Ok(child) => child,
        // A command that will not start is not a suite that failed. The caller's verdict
        // reads this as a run that produced nothing, which is what happened.
        Err(error) => {
            return Finished { status: -1, stdout: String::new(),
                              stderr: error.to_string(), isolation }
        }
    };

    let pid = child.id();
    let deadline = std::time::Instant::now()
        + std::time::Duration::from_secs_f64(timeout_seconds.max(0.0));
    loop {
        match child.try_wait() {
            Ok(Some(status)) => {
                let out = child.wait_with_output().unwrap_or_else(|_| std::process::Output {
                    status,
                    stdout: Vec::new(),
                    stderr: Vec::new(),
                });
                return Finished {
                    status: status.code().unwrap_or(-1),
                    stdout: String::from_utf8_lossy(&out.stdout).into_owned(),
                    stderr: String::from_utf8_lossy(&out.stderr).into_owned(),
                    isolation,
                };
            }
            Ok(None) => {}
            Err(error) => {
                return Finished { status: -1, stdout: String::new(),
                                  stderr: error.to_string(), isolation }
            }
        }
        if std::time::Instant::now() >= deadline {
            let reached = kill_process_group(pid, isolation);
            let out = child.wait_with_output().unwrap_or_else(|_| std::process::Output {
                status: Default::default(),
                stdout: Vec::new(),
                stderr: Vec::new(),
            });
            return Finished {
                status: TIMED_OUT,
                stdout: String::from_utf8_lossy(&out.stdout).into_owned(),
                stderr: String::from_utf8_lossy(&out.stderr).into_owned() + "\ntimed out",
                isolation: reached,
            };
        }
        std::thread::sleep(std::time::Duration::from_millis(50));
    }
}

/// Whether a run was isolated in a process group of its own, and so whether killing it
/// reaches the children it spawned.
///
/// A VALUE both halves of the pair return, rather than a side effect one half performs and
/// the other silently skips. On Windows there is no process group in this sense and
/// nothing can be done about it, which is a real limit of a binary that now executes a
/// client's code: a suite that spawns a database and hangs leaves it running. A caller that
/// cannot tell an isolated run from an unisolated one cannot disclose that, and this
/// instrument's whole argument is that an unstated limit is worse than a stated one.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Isolation {
    /// The run has its own process group, so the kill reaches everything it started.
    Grouped,
    /// This platform has no process group to put it in. Children outlive the kill.
    NotAvailable,
}

impl Isolation {
    /// What a reader is owed about a run that timed out, or nothing to add when the kill
    /// reached everything.
    pub fn note(self) -> &'static str {
        match self {
            Isolation::Grouped => "",
            Isolation::NotAvailable =>
                concat!(" This platform has no process group, so any process",
                        " the suite started may still be running."),
        }
    }
}

/// Put the child in a process group of its own, so killing it reaches everything it
/// started.
///
/// The standard library does this, so the crate takes no dependency for it. That matters
/// here more than usual: this binary is one self-contained file an auditor carries to a
/// client site, and its only dependencies are the grammars it must parse with.
#[cfg(unix)]
fn new_process_group(cmd: &mut Command) -> Isolation {
    use std::os::unix::process::CommandExt;
    cmd.process_group(0);
    Isolation::Grouped
}

/// Windows has no process group in this sense, so the child is started as it is.
///
/// It ANSWERS rather than doing nothing quietly. The caller reads the answer and the
/// refusal carries it, so a suite that hangs on Windows tells a reader its children may
/// have survived instead of leaving them to find out.
#[cfg(not(unix))]
fn new_process_group(_cmd: &mut Command) -> Isolation {
    Isolation::NotAvailable
}

/// Kill the whole group the suite ran in, and say whether the kill could reach it.
///
/// Through `kill(1)` with a NEGATIVE pid, which is how POSIX spells a process group.
/// Killing the pid alone leaves every child the suite started, which is the case the group
/// exists for.
///
/// A spawned process rather than a library call, because this runs only on the timeout
/// path, which is already the slow one, and it keeps the crate free of a dependency it
/// would otherwise carry for one line.
#[cfg(unix)]
fn kill_process_group(pid: u32, isolation: Isolation) -> Isolation {
    let _ = Command::new("kill")
        .args(["-9", &format!("-{pid}")])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status();
    isolation
}

/// Nothing to kill the group with, because there is no group. The child itself is already
/// being waited on; what this cannot do is reach its children, and it says so.
#[cfg(not(unix))]
fn kill_process_group(_pid: u32, isolation: Isolation) -> Isolation {
    isolation
}

/// Name the time a run was given and the flag that gives it more.
///
/// Every refusal in this instrument names its repair, and fifteen timeout refusals in the
/// reference once said only that something timed out: not how long it was given, not that
/// the caller chooses that number, not which flag raises it. It is the refusal an adopter
/// is most likely to meet, and it once cost the reference its own two runtime indicators.
///
/// It CLOSES the sentence it is joined to: every refusal it appends to ends without
/// punctuation, so the note supplies the full stop and starts a new sentence rather than
/// running two together.
pub fn timeout_note(seconds: f64) -> String {
    let shown = if seconds.fract() == 0.0 {
        format!("{}", seconds as i64)
    } else {
        format!("{seconds}")
    };
    format!(". It was allowed {shown}s; raise it with --timeout.")
}

/// The published coverage band: strictly above 90 is Healthy, at or above 60 is Not
/// Healthy, below that is Slop.
///
/// ONE rule for every language, because comparing languages is what the meter claims to do,
/// and eight copies of a threshold is eight places for one language to start grading the
/// same evidence differently from the rest.
pub fn coverage_band(pct: f64) -> &'static str {
    if pct > 90.0 {
        "Healthy"
    } else if pct >= 60.0 {
        "Not Healthy"
    } else {
        "Slop"
    }
}

/// The published determinism band: every run clean is Healthy, exactly one short is Not
/// Healthy, worse is Slop.
///
/// The caller refuses a zero denominator BEFORE it reaches here, since zero clean out of
/// zero satisfies "every run passed" and would band Healthy.
pub fn determinism_band(passing: usize, runs: usize) -> &'static str {
    if passing == runs {
        "Healthy"
    } else if runs > 0 && passing == runs - 1 {
        "Not Healthy"
    } else {
        "Slop"
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_suite_that_finishes_hands_back_what_it_said() {
        let run = run_untrusted(
            &["sh".into(), "-c".into(), "echo out; echo err >&2; exit 3".into()],
            Path::new("."), &[], 30.0);
        assert_eq!(run.status, 3);
        assert!(run.stdout.contains("out"));
        assert!(run.stderr.contains("err"));
        assert!(run.output().contains("out") && run.output().contains("err"));
    }

    #[test]
    fn a_suite_that_hangs_is_killed_and_reports_the_timeout_status() {
        let run = run_untrusted(
            &["sh".into(), "-c".into(), "sleep 30".into()], Path::new("."), &[], 0.5);
        assert_eq!(run.status, TIMED_OUT);
        assert!(run.stderr.contains("timed out"));
    }

    #[test]
    fn the_whole_process_group_dies_with_the_suite() {
        // A suite that starts a child and hangs must not leave it behind on a machine this
        // binary was handed to for an afternoon. The child writes to a file after the
        // timeout would have passed; if the group died, the file never appears.
        let dir = std::env::temp_dir().join(format!("slop-group-{}", std::process::id()));
        let _ = std::fs::create_dir_all(&dir);
        let marker = dir.join("survivor");
        let _ = std::fs::remove_file(&marker);
        let script = format!("(sleep 2; touch {}) & sleep 30", marker.display());
        let run = run_untrusted(&["sh".into(), "-c".into(), script], &dir, &[], 0.5);
        assert_eq!(run.status, TIMED_OUT);
        std::thread::sleep(std::time::Duration::from_millis(3000));
        assert!(!marker.exists(), "a child outlived the group it was killed with");
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn a_command_that_will_not_start_is_not_a_suite_that_failed() {
        let run = run_untrusted(
            &["there-is-no-such-program-here".into()], Path::new("."), &[], 30.0);
        assert_ne!(run.status, 0);
        assert!(!run.stderr.is_empty(), "the reason must survive");
    }

    #[test]
    fn the_environment_the_caller_names_reaches_the_suite() {
        let run = run_untrusted(
            &["sh".into(), "-c".into(), "echo $SLOP_AUDIT_PROBE".into()],
            Path::new("."), &[("SLOP_AUDIT_PROBE".into(), "reached".into())], 30.0);
        assert!(run.stdout.contains("reached"));
    }

    #[test]
    fn the_timeout_note_names_the_seconds_and_the_flag_that_raises_them() {
        // The refusal an adopter is most likely to meet. Saying only that something timed
        // out once cost the reference its own two runtime indicators.
        assert_eq!(timeout_note(300.0), ". It was allowed 300s; raise it with --timeout.");
        assert_eq!(timeout_note(0.5), ". It was allowed 0.5s; raise it with --timeout.");
    }

    #[test]
    fn one_band_rule_serves_every_language() {
        assert_eq!(coverage_band(90.1), "Healthy");
        assert_eq!(coverage_band(90.0), "Not Healthy", "strictly above 90 is Healthy");
        assert_eq!(coverage_band(60.0), "Not Healthy");
        assert_eq!(coverage_band(59.9), "Slop");
    }

    #[test]
    fn every_run_clean_is_healthy_and_one_short_is_not() {
        assert_eq!(determinism_band(5, 5), "Healthy");
        assert_eq!(determinism_band(4, 5), "Not Healthy");
        assert_eq!(determinism_band(3, 5), "Slop");
    }

    #[test]
    fn a_zero_denominator_never_reaches_a_band_as_healthy() {
        // Zero clean out of zero satisfies "every run passed". The caller refuses it before
        // it gets here, and this records what would happen if one ever did not.
        assert_eq!(determinism_band(0, 0), "Healthy",
                   "which is exactly why the caller must refuse it first");
    }
}
