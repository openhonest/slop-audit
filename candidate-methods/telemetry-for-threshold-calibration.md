# Opt-in telemetry for threshold calibration (CANDIDATE)

**Status: candidate. Not canon, not implemented, not a property of the standard.** Written 2026-08-15. Requires Adam's approval before any code is written, and a privacy review before any data is collected. Nothing here should be described publicly as a feature until both happen.

## Why this exists

Every threshold in the twenty-indicator panel is provisional, and `03-layer1-indicators.md` says so. L1.1 through L1.11 are seeded from a single structured-versus-unstructured comparison, one codebase against one condition, with a middle band anchored to industry medians that the canon itself calls "informal, not statistically derived." L1.12 through L1.17 are tool defaults. L1.18 through L1.20 are expert judgment, and L1.18's bounds are additionally stale: they were set against a computation that changed on 2026-08-15, moving measured values by up to 12.7 points.

A tool that reports "Slop" against a number somebody estimated is asserting more than it knows. The honest fix is a distribution measured from real code rather than a better estimate.

Telemetry is one way to get one. It is not a replacement for the corpus study, for the reason in §8.

## 1. What is sent

One record per indicator, per file, per run. Nine fields:

```json
{
  "v": 1,
  "uid": "f3a1c9e0-6b2d-4e77-9c15-8a0d2e4b7f31",
  "day": "2026-08-15",
  "lang": "python",
  "size": "200-500",
  "indicator": "L1.18",
  "value": 66.7,
  "band": "slop",
  "tool": "slop-audit-l1 0.4.2"
}
```

Every field is a number, a value from a fixed vocabulary, or a UID the client generated itself.

`size` is a coarse bucket rather than a line count. A precise size combined with an unusual value is the one residual way a record could be matched back to a codebase by someone who already had a candidate and ran the audit on it. Buckets blunt that at no cost to calibration, because calibration needs the distribution rather than the individual.

## 2. What is never sent

No file path. No directory name. No repository name or remote URL. No function, class or variable name. No source content of any kind. **No hash of any of the above**, because a hash is a fingerprint whenever the input space is guessable, and repository names are easy to guess. No clock time finer than the day, because a sequence of writes with timestamps is itself identifying. No username, no email, no machine name, no IP recorded by the receiving side beyond what GitHub logs for any request.

The client must refuse to send a record containing a field not in §1. Extra fields are a bug, not a feature, and the schema version exists so the receiving side can reject unknown shapes rather than absorb them.

## 3. The UID, and why it is stable

A random UUID generated once on the client, on enable, derived from nothing. It is not a pseudonym. A pseudonym replaces an identifier that already exists; this one stands in for nothing and is never associated with any identity, so there is no link to break.

It is stable for two reasons, and the second is the more important.

**Grouping.** Separating variation within one codebase over time from variation between codebases requires knowing which readings came from the same source. That question is open in this program and cannot be answered from ungrouped readings.

**Audit.** A stable UID is what lets a contributor find their own records. It is the mechanism that makes "public for transparency" true rather than decorative: without it, a user could see everyone's data and not their own.

Rotation is therefore wrong. It would destroy both properties to solve a problem the design does not have.

## 4. Layout, chosen for the user rather than the analyst

```
data/<uid>/<day>.jsonl
```

One folder per install. A contributor pastes their UID into GitHub's search and sees every record ever sent about them, in submission order, in a public repository they do not need permission to read.

A build step concatenates the folders for analysis, so analytical convenience costs nothing in auditability. The reverse layout, one file per day across all installs, would have been easier to analyse and would have made a user's own data effectively unfindable.

Deletion is addressed by the same key. A contributor can ask for `data/<uid>/` to be removed and it is a directory delete, not a search-and-filter through a shared file.

## 5. Consent, including set-and-forget

Three states, and the default is off.

**Off.** No records written, no UID generated, nothing to send. This is the state after installation and it stays that way until the user acts.

**Local only.** Records are written to a local file and never leave the machine. `--dry-run` prints the exact bytes that would be submitted. A user can enable this, look at a week of their own data, and then decide.

**Enabled.** Records are submitted automatically, with no per-submission prompt. This is the set-and-forget state and it is a legitimate thing to want: a contributor who has read the schema once should not be asked again every time.

Enabling prints the UID, the schema, and the destination, and requires an explicit confirmation. The UID is printed again on every submission, so the audit path is never more than a scroll away.

## 6. Authorization, and why no secret ships

Automatic submission needs write access to a public repository, and shipping a token that grants it to every installation is not an option.

The mechanism that fits: a GitHub App with a single permission, contents write on the telemetry repository alone, authorized once by the user through the device flow. The token is issued to that user, stored locally, and never travels with the tool.

That has a property worth more than the convenience. **Revocation lives on GitHub's side.** A user who changes their mind revokes the app from their own account settings and submission stops, whatever the tool's configuration says. A consent switch that only exists inside the tool is a switch the tool could ignore.

A manual path must remain for anyone who will not install an app: write locally, submit as a pull request from their own account.

## 7. Bad actors, and why the defence is in the analysis

Open telemetry can be poisoned. Anyone can send fabricated readings to drag a threshold, or flood the set until one source is the distribution. Saying so is cheaper than pretending otherwise, and the controls below are chosen to keep working when someone tries.

**A registry of known UIDs is not one of them.** The obvious guard is to register each UID with a server and purge records from UIDs it has never seen. It stops nobody who tries: registration is free and unlimited, so an attacker registers ten thousand UIDs and submits from all of them. It also introduces a service that has to stay up, which is the dependency §6 exists to avoid.

**The GitHub App is already a better registry.** Installing it requires a real GitHub account, so forging a thousand sources means holding a thousand accounts with history. That cost is real, GitHub bears it, and this project runs no server to collect it.

One detail decides whether that works: **the app commits as itself, never as the user.** GitHub then holds the installation record on its side while the published data stays anonymous. Commits authored by the contributor would put a name beside every record and undo §1 and §2 entirely.

**The load is carried by the analysis rather than by a gate.**

*Aggregate per UID, then pool.* One install contributes one distribution whether it sent ten records or ten million. This defeats flooding, it defeats the enthusiastic honest user who would otherwise dominate by volume, and it forces a poisoner to fabricate individually plausible codebases rather than spam numbers. It is also the answer to the sampling question in §9, so one mechanism settles both.

*Reject the impossible at ingest.* A ratio outside its own range, an unknown indicator code, an unknown language, a size bucket not in the vocabulary. Cheap, and it removes the crudest attacks without judging anyone's data.

*Report medians, not means.* A distribution summarised by a mean is a distribution one outlier can move.

**On cryptography, what it would actually buy.** Signing records binds them to a key so nobody can write into another contributor's folder, which path scoping in the App already prevents. Proof of work raises the cost of flooding crudely. The one genuinely interesting construction is an anonymous credential, where a server certifies that a submission comes from a legitimate install without learning which one, giving Sybil resistance and unlinkability together. That is a project in itself and it is not worth starting before there is data worth poisoning.

**Deletion has to leave a trace.** Purging records edits the public record, and "you can see your own data" stops being true if rows can vanish. Every removal needs a logged reason in the repository, and a contributor whose folder is removed must be able to find out why. A transparency guarantee that a maintainer can silently revoke is not one.

## 8. The limitation that has to be stated wherever this data is used

People who install a code-quality tool, read a telemetry schema, and choose to opt in are not a random sample of software. They are a self-selected sample of developers who care about code quality, which is exactly the population whose code is least likely to look like the median.

Any threshold calibrated on this data describes that population. Paper A states its own equivalent limitation in §6.6 and that section is the model to copy.

This is the reason telemetry does not replace the corpus study. The corpus is a defined, drawn sample. Telemetry is a large convenience sample. They answer different questions and the second one is not a cheaper version of the first.

## 9. Open questions

- How large does the local record file get before submission, and does it need rotating? The volume question itself is settled by per-UID aggregation in §7: one install is one distribution regardless of how many records it sends. What is not settled is the disk cost on the client.
- Is `band` worth sending at all, given it is derivable from `indicator` and `value` under a known tool version? Sending it costs nothing and makes the data readable without the band table, but it also bakes in a threshold the exercise exists to replace.
- What happens to records collected under one tool version when the computation changes, as L1.18's did on 2026-08-15? The `tool` field allows them to be separated. Whether they should be pooled, and under what argument, is a question for whoever writes the calibration paper.
- Should the first release restrict itself to the four indicators that are meaningful at file scope, measured in the MCP work, rather than all twenty?
