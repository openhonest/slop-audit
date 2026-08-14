"""Reconstruct the saved states of a file from Claude Code transcripts.

The baseline problem for process control at edit tempo: a control chart needs a
population of *candidate* states, and a repository's committed revisions are a population
of *accepted* states. Those differ systematically, because a commit passed review. Limits
computed from accepted states and applied to candidate states are too tight, so the chart
fires on ordinary work in progress.

The unfiltered population exists. Claude Code transcripts under ~/.claude/projects record
every Write with its full content and every Edit with its old and new strings, timestamped.
Replaying them reconstructs the file as it stood after each save, including every state
that was later thrown away.

This tool does the replay and reports how well it is anchored, because a reconstruction
that cannot say how much it guessed is worth nothing. An Edit whose `old_string` is not
found in the current state is a DIVERGENCE: something changed the file outside the
session. Divergences are counted and reported, never silently skipped.

    uv run --no-project python replay.py <path-suffix> [--out DIR] [--verify FILE]

`--verify` checks the final reconstructed state against a known file, which is the only
external check available on the replay's correctness.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    """One transcript tool call that changed a file."""
    ts: str
    kind: str          # "write" | "edit"
    content: str       # full text for a write, "" for an edit
    old: str
    new: str
    replace_all: bool


def _events_for(suffix: str) -> list[Event]:
    """Every Write and Edit against a path ending in `suffix`, oldest first.

    Deduplicated on (timestamp, kind, payload): a transcript can replay the same tool call
    in more than one record, and counting it twice would apply an edit twice."""
    seen: set[tuple] = set()
    out: list[Event] = []
    for path in glob.glob(os.path.expanduser("~/.claude/projects/**/*.jsonl"), recursive=True):
        try:
            handle = open(path, errors="ignore")
        except OSError:
            continue
        with handle:
            for line in handle:
                if suffix not in line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                ts = record.get("timestamp", "")
                message = record.get("message") or {}
                for block in message.get("content") or []:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    name = block.get("name")
                    if name not in ("Write", "Edit"):
                        continue
                    payload = block.get("input") or {}
                    if not str(payload.get("file_path", "")).endswith(suffix):
                        continue
                    if name == "Write":
                        event = Event(ts, "write", payload.get("content") or "", "", "", False)
                    else:
                        event = Event(ts, "edit", "", payload.get("old_string") or "",
                                      payload.get("new_string") or "",
                                      bool(payload.get("replace_all")))
                    key = (event.ts, event.kind, event.content, event.old, event.new)
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(event)
    return sorted(out, key=lambda e: e.ts)


def replay(events: list[Event]) -> tuple[list[tuple[str, str]], dict[str, int]]:
    """The saved states, oldest first, and the counts that say how trustworthy they are.

    A state is emitted after every applied event. Replay cannot begin until the first
    Write, because an Edit against an unknown state has nothing to apply to; edits before
    the first anchor are counted as `unanchored`, not guessed at."""
    states: list[tuple[str, str]] = []
    tally = {"writes": 0, "edits_applied": 0, "divergences": 0, "unanchored": 0}
    current: str | None = None
    for event in events:
        if event.kind == "write":
            current = event.content
            tally["writes"] += 1
            states.append((event.ts, current))
            continue
        if current is None:
            tally["unanchored"] += 1
            continue
        if event.old not in current:
            # Something changed the file outside the session. The chain is broken here and
            # saying so is the whole point; a silent skip would make the rest look sound.
            tally["divergences"] += 1
            continue
        current = (current.replace(event.old, event.new) if event.replace_all
                   else current.replace(event.old, event.new, 1))
        tally["edits_applied"] += 1
        states.append((event.ts, current))
    return states, tally


def anchor_check(events: list[Event]) -> list[tuple[str, bool, int, int]]:
    """The only correctness check the transcripts can perform on themselves.

    Between two Writes of the same file, applying the intervening Edits to the first must
    reproduce the second exactly. Where it does, the replay is verified over that span by
    data rather than by argument. Where it does not, everything after the first failure is
    reconstruction and must be labelled as such."""
    results = []
    anchors = [i for i, e in enumerate(events) if e.kind == "write"]
    for a, b in zip(anchors, anchors[1:]):
        current = events[a].content
        broke = False
        for event in events[a + 1:b]:
            if event.old not in current:
                broke = True
                break
            current = (current.replace(event.old, event.new) if event.replace_all
                       else current.replace(event.old, event.new, 1))
        target = events[b].content
        results.append((events[b].ts, (not broke) and current == target, len(current), len(target)))
    return results


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    suffix = args[0]
    out_dir = next((sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--out"), None)
    verify = next((sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--verify"), None)

    events = _events_for(suffix)
    states, tally = replay(events)

    print(f"events found      : {len(events)}")
    print(f"  writes (anchors): {tally['writes']}")
    print(f"  edits applied   : {tally['edits_applied']}")
    print(f"  divergences     : {tally['divergences']}")
    print(f"  unanchored edits: {tally['unanchored']}")
    print(f"states reconstructed: {len(states)}")
    if states:
        print(f"  first: {states[0][0][:19]}  {len(states[0][1]):>7,} bytes")
        print(f"  last : {states[-1][0][:19]}  {len(states[-1][1]):>7,} bytes")

    checks = anchor_check(events)
    if checks:
        passed = sum(1 for _, ok, _, _ in checks if ok)
        print(f"\nanchor-to-anchor verification: {passed}/{len(checks)} spans reproduce the next Write exactly")
        for ts, ok, got, want in checks:
            mark = "OK  " if ok else "FAIL"
            print(f"  {mark} {ts[:19]}  replayed {got:>7,} vs anchor {want:>7,}")

    if verify:
        want = open(verify, errors="ignore").read()
        got = states[-1][1] if states else ""
        same = hashlib.sha256(want.encode()).hexdigest() == hashlib.sha256(got.encode()).hexdigest()
        print(f"\nverify against {verify}")
        print(f"  final reconstructed state matches on disk: {same}")
        if not same:
            print(f"  reconstructed {len(got):,} bytes, on disk {len(want):,} bytes")

    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        for i, (ts, text) in enumerate(states):
            stamp = ts[:19].replace(":", "").replace("-", "")
            with open(os.path.join(out_dir, f"{i:04d}_{stamp}.py"), "w") as fh:
                fh.write(text)
        print(f"\nwrote {len(states)} states to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
