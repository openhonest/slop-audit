"""The three clauses about a program's edges: I/O, exceptions and logging.

Split from `honest_code_rules` when that module crossed the god-file threshold, at the seam
the growth follows. Every clause here asks the same question in a different direction: what
crosses the line between this program and the world, and does the code say so. The rest of
that module asks about shape inside the line, which is a different reading with a different
vocabulary.

The three are related in the code as well as in the idea. A boundary declaration is read by
the I/O clause and honoured by nothing else; a handler that only catches is at an edge
because the thing it wraps declared itself one; and a log line is an output the signature
never admitted, which is the same failure as an unstated read.
"""

from __future__ import annotations

from tree_sitter import Node

from l1_analyzer.honest_code_read import (
    Finding,
    Source,
    _finding,
    called_names_in,
    called_spelling,
    declares_a_boundary,
    first_name,
    function_nodes,
    handler_body,
    io_calls_in,
    is_absent_value,
    keys_bound_to_io,
    names_a_table_holds,
    names_handed_on,
    node_text,
    sends_failure_onward,
    subscript_keys_called_in,
    walk,
)
from l1_analyzer.lang_spec import LangSpec

# Calls that record a failure. The vocabulary is small on purpose: a try whose LAST
# statement records a failure is asserting that the call above it raised, so the catch
# below is the success condition rather than a swallow.
_RECORDS_A_FAILURE = frozenset({"append", "add", "extend", "fail", "error", "insert"})

def io_below_the_boundary(source: Source) -> list[Finding] | None:
    """A function that performs I/O and is itself reached by a sibling.

    Read through the language's own node vocabulary. A function nothing in the file reaches
    IS the edge, which is where the I/O belongs. One that a sibling reaches has had the I/O
    pushed inward, and neither it nor its caller can be tested without a mock.

    Reached, not called: a function a dispatch table holds is reached BY the table, and
    building the graph from named calls alone left this reader blind to most of a codebase
    written the way clause 1 asks for. A function that reaches a DECLARED boundary is at an
    edge too, through the thing that made the claim, one step and not transitively.

    A declaration that names no I/O is reported. The decorator says the function is an edge
    and a function reaching nothing outside the process is not one, which is the only case
    where a stamp is computable.

    Not decided: whether an uncalled function is truly an entry point. A module read only
    from outside has every function looking like a boundary.

    Not decided either: a language this reader knows no I/O vocabulary for. Reporting those
    files clean would claim they were checked."""
    spec, raw = source["spec"], source["raw"]
    if not spec["io_calls"] and not spec["io_receivers"]:
        return None
    functions = function_nodes(source["root"], spec)
    named = {}
    for fn in functions:
        named[node_text(fn.child_by_field_name("name"), raw) or first_name(fn, raw)] = fn
    declared = {name for name, fn in named.items() if declares_a_boundary(fn, spec, raw)}
    reached = names_a_table_holds(source["root"], spec, raw)
    for name, fn in named.items():
        reached |= (called_names_in(fn, spec, raw)
                    | names_handed_on(fn, spec, raw)) - {name}

    found: list[Finding] = []
    for name, fn in named.items():
        touched = sorted(io_calls_in(fn, spec, raw))
        # A declaration is false only where the function reaches NOTHING a boundary is for.
        # Another checker in this family requires the marker on a function that reads
        # something non-deterministic, so calling the marker false there would tell an author
        # to delete what a second gate needs. Non-determinism is still not counted as I/O:
        # this half of the clause goes quiet, and the half that reports I/O below a boundary
        # is untouched.
        uncertain = bool(called_names_in(fn, spec, raw) & spec["non_deterministic_calls"])
        # A record can carry a function as a field, which is how some code names its edges:
        # `loader["disable_fk_checks"](conn)` reaches a database and there is no attribute
        # access to read. Reported by an adopter with three such sites, and it is their
        # style rather than an accident.
        through_a_record = bool(subscript_keys_called_in(fn, spec, raw)
                                & keys_bound_to_io(source["root"], spec, raw))
        if (name in declared and not touched and not uncertain and not through_a_record
                and not (called_names_in(fn, spec, raw) & declared)):
            found.append(_finding(
                "L1.21.4", name, fn.start_point[0] + 1,
                "declares itself a boundary and makes no call this reader counts as I/O, "
                "so the declaration states an edge that is not there",
                "take the declaration off, or move the read or the call this function was "
                "meant to be the edge for into it", ""))
            continue
        if name not in reached or not touched:
            continue
        # Emitted and marked, not dropped. A suppression that suppresses nothing is
        # invisible from outside, so a consumer counting declarations had to infer from the
        # presence of a decorator and was wrong three times in four.
        finding = _finding(
            "L1.21.4", name, fn.start_point[0] + 1,
            f"performs I/O ({', '.join(touched)}) and is reached by another function here",
            "take the data as a parameter and let the caller at the edge do the I/O", "")
        finding["withheld_by"] = "declaration" if name in declared else ""
        found.append(finding)
    return found

def returns_a_declared_absence(handler, spec: LangSpec, raw: bytes) -> bool:
    """Whether this handler returns the absent case its own function declares it may return.

    A reader at an edge that cannot read something, returning `None` from a function typed
    `dict | None`, has not thrown the error away. The absence is in the contract: every
    caller has to handle it and the type checker says so. That is what the rule on implicit
    defaults asks for, absence as an explicit case of a bounded type.

    This package carried twelve comments telling the swallow rule to allow such sites, which
    was the largest group of exceptions in it by a factor of two, and reading them together
    showed one shape rather than twelve judgments. A rule asking for an exception it should
    never need is the rule's problem.

    The absence has to be DECLARED, and it has to be the one declared. A function returning
    the empty string while typed `-> str` has declared nothing, because no caller can tell an
    absent value from an empty one. A function returning an empty dict where None was
    declared is handing back a value nobody asked for."""
    if not spec["absent_markers"] or not spec["return_type_field"]:
        return False
    holder = handler.parent
    while holder is not None and holder.type not in spec["func_types"]:
        holder = holder.parent
    if holder is None:
        return False
    declared = node_text(holder.child_by_field_name(spec["return_type_field"]), raw)
    if not any(marker in declared for marker in spec["absent_markers"]):
        return False
    returned = [node_text(n, raw).split(maxsplit=1)[1:] for n in walk(handler)
                if n.type in spec["return_types"]]
    given = {parts[0].strip() for parts in returned if parts}
    return bool(given) and given <= set(spec["absent_values"])


def swallowed_exceptions(source: Source) -> list[Finding] | None:
    """A handler whose body throws the error away.

    Read through the language's own node vocabulary. Catch-and-swallow is the purest form
    of a silent failure: it reports success for work that failed. A handler that re-raises,
    or that maps the error to a response, is doing what the rule asks.

    Not decided: whether the enclosing function is a boundary. A route handler catching and
    mapping is right, and nothing in the file says which functions are routes.

    Not decided either: a language with no exception. Go returns an error beside the value
    and Rust returns a Result, and neither is a handler this reads. Reporting those files
    clean would claim they were checked."""
    spec, raw = source["spec"], source["raw"]
    if not spec["handler_types"]:
        return None
    found: list[Finding] = []
    found += _silenced_without_a_handler(source["root"], spec, raw)
    # A handler that catches the test's own failure, or that sorts an exception by its
    # words, is the same principle as swallowing one: what actually happened stops here and
    # never reaches anyone who could act on it. Reported by an adopter whose only test of a
    # constraint could not fail.
    found += self_caught_failures(source) or []
    for node in walk(source["root"]):
        if node.type not in spec["handler_types"]:
            continue
        body = handler_body(node, spec)
        if body is None or not _throws_it_away(body, node, spec, raw):
            continue
        # The catch is the ASSERTION when the guarded body's last statement records a
        # failure: that statement runs only if the call above it did NOT raise, so reaching
        # it is the defect and the handler is the success condition. Keying on the handler
        # alone made both readings look alike.
        if _guarded_body_asserts_a_raise(node, spec, raw):
            continue
        if returns_a_declared_absence(node, spec, raw):
            continue
        caught = _caught_text(node, spec, raw)
        # A signal that carries control flow is not the failure this rule is about. Catching
        # one and returning is how a program stops cleanly.
        if caught and set(caught.split()) <= spec["control_flow_exceptions"]:
            continue
        found.append(_finding(
            "L1.21.8", caught or "everything", node.start_point[0] + 1,
            f"catches {caught or 'everything'} and reports success for work that failed",
            "let it raise and map the type to a response at the boundary", ""))
    return found

def _silenced_without_a_handler(root: Node, spec: LangSpec, raw: bytes) -> list[Finding]:
    """An exception discarded by a call, with no handler body anywhere to read.

    `contextlib.suppress(ValueError)` throws away everything the block raises and returns as
    though it succeeded. It is the purest form of the thing this clause names and it was the
    one the clause could not see, because the reader looked for a handler and there is none:
    no `except`, no body, no statement to judge.

    A control-flow signal is still not the failure this rule is about, the same as anywhere
    else here."""
    found: list[Finding] = []
    if not spec["silencing_calls"]:
        return found
    for node in walk(root):
        if node.type not in spec["call_types"]:
            continue
        called = node.child_by_field_name(spec["call_fn"])
        if called is None or node_text(called, raw).rsplit(".", 1)[-1] not in spec["silencing_calls"]:
            continue
        arguments = node.child_by_field_name(spec["call_args"])
        caught = " ".join(node_text(a, raw) for a in arguments.named_children) if arguments else ""
        if caught and set(caught.split()) <= spec["control_flow_exceptions"]:
            continue
        found.append(_finding(
            "L1.21.8", caught or "everything", node.start_point[0] + 1,
            f"silences {caught or 'everything'} with no handler at all, so the block "
            "returns as though it succeeded",
            "let it raise and map the type to a response at the boundary", ""))
    return found

def _throws_it_away(body: Node, handler: Node, spec: LangSpec, raw: bytes) -> bool:
    """Whether a handler body discards the failure instead of disclosing it.

    Empty, or one statement returning a value a caller cannot tell from success. A body
    that mentions the caught error is disclosing it: a route mapping the message into a
    response hands the caller something that names the failure."""
    if sends_failure_onward(body, spec, raw):
        return False
    statements = [c for c in body.named_children if c.type != "pass_statement"]
    if not statements:
        return True
    if len(statements) > 1:
        return False
    only = statements[0]
    if only.type not in spec["return_types"]:
        return False
    returned = [c for c in only.named_children]
    if not returned:
        return True
    caught_name = _caught_variable(handler, spec, raw)
    if caught_name and caught_name in node_text(returned[0], raw):
        return False
    return is_absent_value(returned[0], spec, raw)

def _guarded_body_asserts_a_raise(handler: Node, spec: LangSpec, raw: bytes) -> bool:
    """Whether the body this handler guards is asserting that its call raised.

    The shape is a call followed by a statement that records a failure. That statement runs
    only when the call did NOT raise, so the handler beneath is the success condition and
    the defect would be reaching the recorder.

    Not decided: whether the recorded failure is the one the author meant. A body ending in
    an unrelated append reads the same way, and separating them would need the meaning of
    the collection rather than its shape."""
    guarded = handler.parent
    if guarded is None or guarded.type not in spec["try_types"]:
        return False
    body = next((c for c in guarded.named_children
                 if c.type in spec["handler_body_types"]), None)
    if body is None:
        return False
    statements = [c for c in body.named_children if c.type != "pass_statement"]
    if len(statements) < 2:
        return False
    last = statements[-1]
    if last.type in spec["assertion_types"]:
        return True
    for call in walk(last):
        if call.type in spec["call_types"]:
            fn = call.child_by_field_name(spec["call_fn"])
            if fn is not None and node_text(fn, raw).split(".")[-1] in _RECORDS_A_FAILURE:
                return True
    return False

def _caught_text(handler: Node, spec: LangSpec, raw: bytes) -> str:
    """What this handler says it catches, or nothing when it catches everything."""
    parts = [node_text(c, raw) for c in handler.named_children
             if c.type not in spec["handler_body_types"]]
    return " ".join(p for p in parts if p).strip()

def _caught_variable(handler: Node, spec: LangSpec, raw: bytes) -> str:
    """The name the handler binds the error to, or nothing if it binds none.

    The last identifier before the body, which is where all five grammars put it whether
    they field it or not."""
    before = [c for c in handler.named_children if c.type not in spec["handler_body_types"]]
    names = [node_text(n, raw) for part in before for n in walk(part)
             if n.type == "identifier"]
    return names[-1] if names else ""

def undeclared_logging(source: Source) -> list[Finding] | None:
    """A function that writes a log line, and whether it lost a failure doing it.

    A log line written from inside a function is a return value that skipped the type
    system. The function produces an observable output its signature never admits, so no
    caller can see it, no test can assert on it without capturing output, and no caller can
    decline it.

    Two rules, and this reads both. An error is RETURNED, never written: a function that
    logs a failure and carries on has reported it somewhere the caller cannot reach, which
    is how a failure gets lost. And information goes through one logging function of your
    own, declared as a boundary, because reaching a global nobody declared makes every call
    site an independent edge that decides its own format, level and destination.

    One finding per function rather than per call, and the failure reading comes first: a
    function that lost an error has a worse problem than one that opened an edge.

    The count of edges travels with each finding. A reader deciding whether to build one
    logging function needs to know how many there are, and a site at a time never says.

    Not decided: whether the function's return value already names the failure. A caller
    handed something that says what went wrong has not lost it, and no reading of the
    callee alone can tell that from a caller handed nothing.

    Not decided either: a language with no logging convention this reader knows. Rust and C
    have none here, so the clause says it could not decide rather than reporting them clean."""
    spec, raw = source["spec"], source["raw"]
    if not spec["log_receivers"]:
        return None
    writing = [(fn, levels) for fn in function_nodes(source["root"], spec)
               if (levels := _log_levels_in(fn, spec, raw))]
    # An empty list, not None. A file where nothing logs has no violation of a rule about
    # what logging functions do, the same way a file with no handler conforms to the rule
    # about swallowing. Undecided is reserved for a LANGUAGE this reader knows no logging
    # convention for, which is the case above.
    edges = len(writing)
    found: list[Finding] = []
    for fn, levels in writing:
        name = node_text(fn.child_by_field_name("name"), raw) or first_name(fn, raw)
        lost = levels & spec["log_failure_calls"] and not sends_failure_onward(fn, spec, raw)
        detail = (f"logs a failure and carries on, so the caller cannot see it. This file "
                  f"opens {edges} logging edge(s) onto a global nothing declared"
                  if lost else
                  f"writes a log line the signature does not admit. This file opens "
                  f"{edges} logging edge(s) onto a global nothing declared")
        found.append(_finding(
            "L1.21.20", name, fn.start_point[0] + 1, detail,
            "return the failure to the caller, and route what is left through one logging "
            "function of your own that every other function calls",
            _LOGGING_UNDECIDED))
    return found


_LOGGING_UNDECIDED = ("whether the return value already names the failure is not readable "
                      "from the callee alone, and a caller handed something that says what "
                      "went wrong has not lost it")

def _log_levels_in(fn: Node, spec: LangSpec, raw: bytes) -> set[str]:
    """The logging calls this function makes, by level.

    Matched on the receiver AND the call, because both halves are ordinary words on their
    own: `log` names plenty of things that are not a logger, and `info` is a field name."""
    levels: set[str] = set()
    for node in walk(fn):
        if node.type not in spec["call_types"]:
            continue
        called = node.child_by_field_name(spec["call_fn"])
        if called is None or called.type not in spec["member_types"]:
            continue
        receiver = called.child_by_field_name("object") or called.child_by_field_name("value")
        level = node_text(called, raw).rsplit(".", 1)[-1]
        if receiver is None or level not in spec["log_calls"]:
            continue
        if node_text(receiver, raw).rsplit(".", 1)[-1] in spec["log_receivers"]:
            levels.add(level)
    return levels


def _declares_failure(node, spec: LangSpec, raw: bytes) -> bool:
    """Whether this node is a test saying it should not have got this far.

    Four spellings, and they are the same act: a call to the framework's fail, a raised
    assertion error, or a bare `assert False`."""
    text = node_text(node, raw)
    if node.type in spec["assertion_types"]:
        return any(name in text for name in spec["deliberate_failures"]) or "False" in text
    if node.type in spec["call_types"]:
        return called_spelling(node, spec, raw) in spec["deliberate_failures"]
    return False


def _catches_everything(handler, spec: LangSpec, raw: bytes) -> bool:
    """Whether this handler catches a deliberate failure along with everything else.

    A handler naming no type catches all of them. A handler naming one of the language's
    root exception types catches all of them too, which is what puts a test's own failure in
    the same branch as the failure it was watching for."""
    caught = _caught_text(handler, spec, raw)
    if not caught.strip():
        return True
    return any(root in caught for root in spec["catch_all_types"])


def _sorts_by_text(handler, spec: LangSpec, raw: bytes) -> bool:
    """Whether this handler decides what happened by reading the exception as words.

    The wider rule, and it holds outside a test. This package hit the same shape in a
    different room: a contention check retried a KeyError because the word matched, and the
    cause was ours."""
    bound = _bound_name(handler, spec, raw)
    if not bound:
        return False
    # Inside a CONDITION. A handler putting the exception's text in a response is doing what
    # the rule asks: it caught by type and is telling the caller what happened. Firing there
    # reported a route handler as sorting by words when it was only quoting them.
    for branch in walk(handler):
        if branch.type not in spec["branch_types"]:
            continue
        condition = branch.child_by_field_name(spec["branch_cond"])
        if condition is None:
            continue
        for node in walk(condition):
            if node.type not in spec["call_types"]:
                continue
            if called_spelling(node, spec, raw) not in spec["exception_text_calls"]:
                continue
            if bound in [node_text(c, raw) for c in walk(node) if c.type == "identifier"]:
                return True
    return False


def _bound_name(handler, spec: LangSpec, raw: bytes) -> str:
    """The name a handler binds the caught exception to, or the empty string.

    Not the type it caught, which is what `_caught_variable` reports and is a different
    question. This one is the local name the body reads, and it is the only thing that tells
    `str(e)` from any other call to `str`."""
    where = handler.child_by_field_name("value") or handler
    named = [c for c in walk(where) if c.type == "identifier"]
    if not named:
        return ""
    # The LAST in source order, which is the alias: `except KeyError as e` names the type
    # first and the local name second. The walk returns nodes in its own order, so taking
    # the last one it happened to yield picked the type and matched nothing.
    named.sort(key=lambda c: c.start_byte)
    return node_text(named[-1], raw)


def self_caught_failures(source: Source) -> list[Finding] | None:
    """A test that catches its own failure, or a handler that sorts an exception by its words.

    Reported by an adopter, from the only test in their suite of a constraint surviving a
    database rebuild. A deliberate failure raises, so a handler for every exception catches
    it alongside the failure the test was watching for, and the two could then only be told
    apart by asking whether the exception's text carried the message the test itself had
    written. Reword that message and the test passes while the thing it tests is broken.

    It is worse than one wrong branch. Every other exception lands in the same handler and
    reads as success: a typo in the query, a closed connection, a bug in the package.

    Two findings, and both are exact. A deliberate failure inside a try whose handler can
    catch it is wrong whatever the handler does next. A handler branching on the exception's
    text rather than its type is the wider rule and holds outside a test entirely.

    Not decided: whether the text being matched is one the same function wrote, which is what
    makes that instance circular. In general the string can come from anywhere, so nothing
    here tries to tell those apart.

    Not decided for a language with no exception. Go returns an error beside the value and
    Rust returns a Result, and neither is a handler this reads."""
    spec, raw = source["spec"], source["raw"]
    if not spec["handler_types"] or not spec["deliberate_failures"]:
        return None
    found: list[Finding] = []
    for node in walk(source["root"]):
        if node.type not in spec["try_types"]:
            continue
        guarded = [c for c in node.named_children if c.type not in spec["handler_types"]]
        handlers = [c for c in walk(node) if c.type in spec["handler_types"]]
        declares = any(_declares_failure(inner, spec, raw)
                       for part in guarded for inner in walk(part))
        for handler in handlers:
            if declares and _catches_everything(handler, spec, raw):
                found.append(_finding(
                    "L1.21.8", node_text(node, raw).strip().split("\n")[0][:50],
                    handler.start_point[0] + 1,
                    "this catches its own failure: the body above declares the test should "
                    "not have got this far, and that declaration raises like anything else, "
                    "so both land here and only the words tell them apart",
                    "assert the failure you expect with the construct that expects it, so "
                    "the test's own failure is never a case this handler sees", ""))
            if _sorts_by_text(handler, spec, raw):
                found.append(_finding(
                    "L1.21.8", node_text(handler, raw).strip().split("\n")[0][:50],
                    handler.start_point[0] + 1,
                    "this decides what happened by reading the exception as text, so "
                    "rewording a message anywhere changes which branch runs",
                    "read the failure's type, which is the thing that does not change when "
                    "somebody edits a sentence", ""))
    return found
