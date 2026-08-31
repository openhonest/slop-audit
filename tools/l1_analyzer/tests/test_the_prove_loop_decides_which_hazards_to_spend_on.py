"""What the prove loop decides before it spends anything, held without spending anything.

The loop takes the thread-safety surface, picks which hazards are worth proving, and runs
each one through generate, build, stress and keep. Two of those four cost real money and a
real `cargo build`, so nothing had asked the loop what it picks or how it counts. Its whole
body was one unexercised branch.

The two collaborators are arguments, not defaults, which is what makes this askable: the
generator and the runner are named at this boundary because this is the place that knows a
run is meant to spend money. Standing in for them leaves the loop's own decisions, and
those are the ones that would be wrong quietly.

Four of them. Only review-tier hazards are proven, because the higher tier is already a
finding and a proof adds nothing to it. The cap is a cap on hazards attempted and not on
proofs kept, so a run that caps at two and demonstrates none has still spent twice. Each
proof gets its own directory, because each one writes a crate and stresses it, and two
sharing a directory means one overwrites the other. And a sweep that generated nothing reads the
same at the summary line as a sweep that ran and fired no race, which is written down here
because it is a defect nobody has fixed rather than a decision.
"""

import pytest
from l1_analyzer import cli, prove


def _finding(symbol: str, severity: str) -> dict:
    return {"kind": "shared-mutable", "symbol": symbol, "file": "src/lib.rs", "line": 3,
            "severity": severity, "detail": "", "suggestion": ""}


@pytest.fixture
def spent(tmp_path):
    """Stands in for the generator and the crate builder, and records what the loop asked.

    Handed in as arguments. Nothing here replaces a name inside the module under test, which
    is what this used to do and what the suite refuses: a test that swaps a function the
    code reached for is testing the swap, and this package has hidden three defects that
    way. The refusal is what made the collaborators parameters."""
    asked: list[dict] = []
    built: list[str] = []

    def generate(request) -> str:
        # The real generator writes a Rust test for the located hazard. This writes down
        # which hazard it was asked about, and the answer fires only where the name says a
        # race is expected, so retaining and discarding are both exercised.
        asked.append({"symbol": request["symbol"], "request": request})
        return f"fn t() {{ /* {request['symbol']} */ }}"

    def make_runner(work: str, timeout: float):
        def run(test: str):
            built.append(work)
            fired = "racy" in test
            # The runner's own vocabulary. A word outside it is a run that could not be
            # measured, which is a third answer and not a clean one.
            return {"verdict": "race-observed" if fired else "no-race-in-stress",
                    "detail": "fired" if fired else "quiet"}
        return run

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib.rs").write_text("static mut N: i32 = 0;\n" * 5)
    return {"asked": asked, "built": built,
            "generate": generate, "make_runner": make_runner}


def _run(repo, findings, spent, cap=10, ready=True):
    surface = {"verdict": "review", "findings": findings, "detail": ""}
    return cli._run_prove(repo, "rust", surface, cap, 5.0, repo / "work",
                          ready, spent["generate"], spent["make_runner"])


def test_a_hazard_the_reader_already_calls_a_finding_is_not_proven(tmp_path, spent):
    """The higher tier is a finding on its own, so proving it spends money to learn nothing.
    Review tier is the one where the reader is unsure, which is what a proof settles."""
    _run(tmp_path, [_finding("racy_flag", "flag"), _finding("racy_review", "review")], spent)
    assert [c["symbol"] for c in spent["asked"]] == ["racy_review"]


def test_the_cap_counts_hazards_attempted_and_not_proofs_kept(tmp_path, spent):
    """A run that caps at two and demonstrates none has still spent twice, so the cap has
    to bind before the generator is called and not after the verdict comes back."""
    run = _run(tmp_path, [_finding(f"quiet_{i}", "review") for i in range(5)], spent, cap=2)
    assert len(spent["asked"]) == 2
    assert run["attempted"] == 2
    assert run["demonstrated"] == 0


def test_each_proof_is_built_in_its_own_directory(tmp_path, spent):
    """Each proof writes a crate and stresses it, so two sharing a directory means the
    second one overwrites the first's crate and both verdicts come from whichever won.

    I first wrote this to hold something else, that the directory is bound at the call
    rather than captured from around it. It cannot: the runner is called inside the same
    turn of the loop, so a captured name still reads the right directory, and the test
    passed with the capture put back. What it does hold is that the directory differs per
    proof and is named after the hazard's place in the run, and pointing all of them at one
    directory does fail it."""
    _run(tmp_path, [_finding(f"quiet_{i}", "review") for i in range(3)], spent)
    used = spent["built"]
    assert len(set(used)) == 3, used
    assert all(d.endswith(f"proof-{i}") for i, d in enumerate(used)), used


def test_a_proof_that_fired_is_counted_and_the_test_that_fired_is_kept(tmp_path, spent):
    """The verdict alone is not the evidence. A demonstrated proof is a runnable test the
    reader can adopt, and dropping it would leave a claim with nothing behind it."""
    run = _run(tmp_path, [_finding("racy_one", "review"), _finding("quiet_two", "review")], spent)
    assert run["demonstrated"] == 1
    assert run["verdict"] == "demonstrated"
    kept = next(o for o in run["outcomes"] if o["symbol"] == "racy_one")
    assert kept["generated_test"]


def test_every_hazard_attempted_is_reported_whether_it_fired_or_not(tmp_path, spent):
    """Listing only the ones that fired would report the hit rate as perfect."""
    run = _run(tmp_path, [_finding("racy_one", "review"), _finding("quiet_two", "review")], spent)
    assert {o["symbol"] for o in run["outcomes"]} == {"racy_one", "quiet_two"}


def test_a_sweep_that_proved_nothing_does_not_read_like_one_that_generated_nothing(
        tmp_path, spent):
    """This test was written the other way round, recording the defect, and it is kept
    facing forward so the defect cannot come back.

    The summary word was "demonstrated" or "none," and "none" covered a surface with nothing
    worth proving as well as a surface where proofs ran and came back quiet. The counts were
    the only place the two stayed apart, so a reader looking at the verdict could not tell
    them apart at all. Filed as slop-audit-nn6 and fixed the same day."""
    nothing = _run(tmp_path, [_finding("racy_flag", "flag")], spent)
    tried = _run(tmp_path, [_finding("quiet_one", "review")], spent)
    assert nothing["verdict"] != tried["verdict"]
    assert nothing["attempted"] == 0
    assert tried["attempted"] == 1



def test_a_language_that_is_not_rust_attempts_nothing_and_says_why(tmp_path, spent):
    run = _run(tmp_path, [_finding("racy_one", "review")], spent)
    assert run["attempted"] == 1
    surface = {"verdict": "review", "findings": [_finding("racy_one", "review")], "detail": ""}
    other = cli._run_prove(tmp_path, "python", surface, 10, 5.0, tmp_path / "w",
                           True, spent["generate"], spent["make_runner"])
    assert other["verdict"] == "n/a"
    assert "python" in other["detail"]
    assert len(spent["asked"]) == 1, "the Python run must not have asked for anything"


def test_no_key_attempts_nothing_and_says_which_key(tmp_path, spent):
    """The reason has to name the key. A run that says only "not applicable" sends a reader
    looking at their code for a reason that is in their environment.

    Whether a key is present is handed in rather than read here, so this asks the loop what
    it does with a no and never touches the environment the suite is running in."""
    run = _run(tmp_path, [_finding("racy_one", "review")], spent, ready=False)
    assert run["verdict"] == "n/a"
    assert "ANTHROPIC_API_KEY" in run["detail"]
    assert spent["asked"] == []


def test_a_run_that_could_not_be_measured_is_not_counted_as_clean(tmp_path, spent):
    """Three answers, not two. A crate that would not build has told you nothing about the
    hazard, and folding it in with the runs that finished clean turns "we could not check"
    into "we checked and it is fine", which is the claim this whole tool exists to refuse."""
    def broken(work, timeout):
        return lambda test: {"verdict": "n/a", "detail": "no cargo toolchain"}

    surface = {"verdict": "review", "findings": [_finding("racy_one", "review")], "detail": ""}
    run = cli._run_prove(tmp_path, "rust", surface, 10, 5.0, tmp_path / "w",
                         True, spent["generate"], broken)
    assert run["attempted"] == 1
    assert run["demonstrated"] == 0
    assert run["outcomes"][0]["verdict"] == prove.NOT_RUN
    assert "no cargo toolchain" in run["outcomes"][0]["detail"]


def test_a_hazard_nobody_could_write_a_test_for_is_reported_as_not_generated(tmp_path, spent):
    """The generator can decline. Reporting that as a clean run would claim a proof was
    attempted against the code when nothing ever reached the code."""
    surface = {"verdict": "review", "findings": [_finding("racy_one", "review")], "detail": ""}
    run = cli._run_prove(tmp_path, "rust", surface, 10, 5.0, tmp_path / "w",
                         True, lambda request: None, spent["make_runner"])
    assert run["outcomes"][0]["verdict"] == prove.NOT_GENERATED
    assert spent["built"] == [], "nothing should have been built for a test that was never written"


def test_neither_collaborator_has_a_default():
    """The rule that made this file possible, asserted so it cannot quietly come back.

    A default here would put the real generator and a real `cargo build` one forgotten
    argument away from any test, and the test would look like it was testing the loop. The
    module below this one learned that in August and this one had not."""
    import inspect

    parameters = inspect.signature(cli._run_prove).parameters
    for name in ("model_ready", "generate", "make_runner"):
        assert parameters[name].default is inspect.Parameter.empty, name


# --------------------------------------------------------------------------
# The summary line, which had two words for four situations (slop-audit-nn6)
# --------------------------------------------------------------------------

def _run_with(tmp_path, spent, findings, runner=None, generator=None):
    surface = {"verdict": "review", "findings": findings, "detail": ""}
    return cli._run_prove(tmp_path, "rust", surface, 10, 5.0, tmp_path / "w", True,
                          generator or spent["generate"], runner or spent["make_runner"])


def test_a_surface_with_no_hazard_worth_proving_says_it_located_nothing(tmp_path, spent):
    """Not "none". Nothing was generated, nothing was built and nothing was run, so the
    summary must not read as a stage that ran and came back empty. That is the vacuous
    affirmative this instrument reports against other people's code."""
    run = _run_with(tmp_path, spent, [_finding("racy_flag", "flag")])
    assert run["verdict"] == "nothing-located"
    assert run["attempted"] == 0


def test_proofs_that_ran_and_fired_nothing_say_so_in_their_own_words(tmp_path, spent):
    """The real negative result, and the only one of the four that is evidence. The tests
    were written, built and stressed, and no race appeared. It is bounded rather than a
    proof of safety, and the word has to be different from the three that measured nothing."""
    run = _run_with(tmp_path, spent, [_finding("quiet_one", "review"),
                                      _finding("quiet_two", "review")])
    assert run["verdict"] == "no-race-fired"
    assert run["attempted"] == 2


def test_a_run_with_no_toolchain_says_nothing_was_measured(tmp_path, spent):
    """Two proofs attempted and neither crate built. Saying no race fired here would report
    a clean result from a stage that never executed a line of the generated code."""
    def broken(work, timeout):
        return lambda test: {"verdict": "n/a", "detail": "no cargo toolchain"}

    run = _run_with(tmp_path, spent, [_finding("racy_one", "review"),
                                      _finding("racy_two", "review")], runner=broken)
    assert run["verdict"] == "not-measured"
    assert run["attempted"] == 2
    assert run["demonstrated"] == 0


def test_a_generator_that_declined_every_hazard_says_nothing_was_measured(tmp_path, spent):
    """The same reading from the other end. No test was written, so no code ran, and the
    two failures are one situation for a reader: this stage produced no evidence."""
    run = _run_with(tmp_path, spent, [_finding("racy_one", "review")],
                    generator=lambda request: None)
    assert run["verdict"] == "not-measured"


def test_one_proof_that_fired_beats_any_number_that_did_not(tmp_path, spent):
    """A demonstrated race is a fact about the code, and the runs that came back quiet do
    not weigh against it. One firing settles the run."""
    run = _run_with(tmp_path, spent, [_finding("quiet_one", "review"),
                                      _finding("racy_two", "review"),
                                      _finding("quiet_three", "review")])
    assert run["verdict"] == "demonstrated"
    assert run["demonstrated"] == 1


def test_a_run_that_measured_some_and_could_not_measure_others_reports_what_it_measured(
        tmp_path, spent):
    """A partial toolchain failure is not a total one. Two crates built and came back quiet,
    one would not build, and calling the whole run unmeasured would throw away two real
    negative results."""
    calls = {"n": 0}

    def flaky(work, timeout):
        def run(test):
            calls["n"] += 1
            if calls["n"] == 1:
                return {"verdict": "n/a", "detail": "build failed"}
            return {"verdict": "no-race-in-stress", "detail": "quiet"}
        return run

    run = _run_with(tmp_path, spent, [_finding(f"quiet_{i}", "review") for i in range(3)],
                    runner=flaky)
    assert run["verdict"] == "no-race-fired"
    assert run["attempted"] == 3
