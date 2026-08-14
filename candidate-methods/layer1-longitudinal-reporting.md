# Layer 1 longitudinal reading: what the reader sees (CANDIDATE)

**Status: candidate.** The method behind this is `layer1-longitudinal-method.md` and is not approved. Would become section 6a of `06-slop-report-template.md`. Covers only what a business reader sees.

Written 2026-08-14.

**The rule this section exists to enforce.** The reader is a CIO, a head of engineering, or a board member. They do not see a control chart, a moving range, a baseline, a constant, a limit or the words "common cause". Those live in the method document and in the analyst's working file. If a term from the method document appears on a card, a report page or a screen, that is a defect in this section.

This is the treatment the instrument already gives every indicator: `copy.md` carries a business `label`, a citable `tech` name and a bridging `meaning` for each one. The trend reading gets the same three-layer treatment. Nothing new is invented here.

### 1 The reader's question

A business reader asks one question about any bad number, and it is not the one the panel answers:

> Is this getting worse, or is this just how we work?

The panel answers "how bad is it". This section answers the question actually being asked.

### 2 The three verdicts, in full

Exactly three outcomes. No fourth, and no hedging between them.

---

**"This is your normal."**

> Your delete/add ratio has been at this level for three years. It has not moved. This is what your current way of working produces.

---

**"Something changed in 2024."**

> Your delete/add ratio held steady from 2019 to 2023, then moved in 2024 and has not come back. Something changed in how the work is done that year.

---

**"Not enough history to tell yet."**

> We can see the level, but not the trend. There is not enough history at this size of sample to say whether it is moving. This is a limit of the measurement, not a finding about your code.

---

The third verdict is the one most instruments leave out, and it is the one that earns the other two their credibility. The tool must say it whenever it cannot detect a change, and must never report "this is your normal" in its place. A measurement that cannot see a change reporting no change is a false clean bill.

### 2a The rule that keeps the trend honest

**The trend verdict is never shown on its own.** It is always shown beside the level, because the two answer different questions and the trend alone is dangerous.

A reader who sees "no change detected" and nothing else concludes the number is fine. It may be terrible and steady. Worse, the trend reading can be blind inside the failing range: on one real repository the reading cannot detect a fall until well past the point at which the panel already calls the process failing, so a slide deep into a bad score produces no change at all. That is correct behaviour for the question it answers, and a false clean bill for the question the reader is asking.

So the report never prints a trend sentence without the level sentence next to it, and the word "stable" never appears without the level immediately after. "This is your normal" is not good news until the reader knows what the normal is.

### 3 What the reader should do, which is the point

The verdict is worth nothing without the instruction that follows it. These are the sentences that make the report actionable, and they differ in kind, not in degree.

**"This is your normal", and the level is bad.**

> A cleanup sprint will not hold. This level is what your process produces, so the code will return to it. Changing it means changing how the work is done: what gets reviewed, what the tools are allowed to do unsupervised, what the definition of done is. Budget for a practice change, not a remediation project.

**"Something changed", and the level got worse.**

> Look at what changed in that period. New tool, new team member, a deadline, a new assistant in the workflow. This one has a cause and the cause is findable, which the previous case does not.

**"Something changed", and the level got better.**

> Whatever changed that period is working. Find out what it was before it gets undone. Improvements have causes too, and they are the ones nobody investigates.

**"Not enough history to tell yet."**

> Re-run the audit after more work has landed. No action follows from this reading.

### 4 The sentence a CIO can carry into a meeting

The whole value of the trend reading, in one sentence a non-technical executive can repeat accurately:

> Our delete/add ratio is poor, it has been poor for three years, and it has not changed. Cleaning it up will not stick until we change how we build.

That sentence cannot be produced from the panel alone. It also contains no statistics vocabulary, no chart, and nothing a reader has to take on faith.

### 5 Draft copy strings

For `copy.md`, in the existing `label` / `tech` / `meaning` form.

```
## label.trend
Is this getting worse, or is this just how you work?

## tech.trend
Layer 1 longitudinal reading (methodology §3a)

## meaning.trend
The panel tells you the level. This tells you whether the level is moving. The two have
opposite remedies: a number that has been steady for years is produced by the way you
work, and cleaning it up will not hold; a number that moved has a cause, and the cause
can be found.

## trend.stable
This is your normal. {indicator} has been at this level since {since}, and it has not moved.
The level is {band}.

## trend.stable.bad
A cleanup will not hold. This level is what your current way of working produces, so it
will come back. Changing it means changing the practice, not scheduling a remediation.

## trend.shifted
Something changed in {period}. {indicator} held steady before that and has not returned
to its earlier level.

## trend.shifted.worse
This one has a cause and the cause is findable. Look at what changed in {period}: a new
tool, a new person, a deadline, a change in how the work is reviewed.

## trend.shifted.better
Whatever changed in {period} is working. Find out what it was before it gets undone.

## trend.insufficient
Not enough history to tell yet. We can see the level but not the trend. This is a limit
of the measurement, not a finding about your code.
```

### 6 Where it appears

- **The card**: one line under the indicator, only when the indicator is in a non-healthy band. A green indicator does not need a trend reading and adding one is noise.
- **The Slop Report**: one paragraph per non-healthy indicator, in Part I beside the panel.
- **The hosted page**: nothing. The trend reading needs history and a defined sample; a single static run cannot produce one, and a page that showed a trend it had not computed would be the exact failure §2 exists to prevent.

### 7 What the analyst sees, and does not show

The assessor's working file carries the chart, the limits, the baseline range, the subgroup size and the detection-power calculation, because the finding must be reproducible by another assessor. None of it appears in the client-facing report. If a client asks how the trend was determined, the answer is the method document, not a chart pasted into the deliverable.
