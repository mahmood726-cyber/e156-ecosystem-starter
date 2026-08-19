# The meta-analysis error library

A catalogue of ways a meta-analysis goes wrong, written for someone who is about
to publish one. Every class here was found in a real review or a real generated
dashboard. None of them were invented to make a list look complete.

Most of them are not statistics mistakes. That is the finding worth carrying
away. In a corpus of **626 generated review dashboards**, each audited and
repaired one file at a time with a per-number provenance line, the three
near-universal defects were:

| Defect | Apps repaired | Share |
|---|---|---|
| A **pooling engine that would combine things that do not belong together** | 610 | 97.4% |
| A **provenance claim the artefact was not entitled to make** (a commit timestamp offered as prospective registration) | 540 | 86.3% |
| A **badge that was green because someone wrote it green** | 532 | 85.0% |

Then a long tail: donor-template text describing the wrong drug (63, 10.1%),
and everything else in low single figures.

The pooling arithmetic was almost always right. The framing around it almost
never was. If you take one thing from this document, take that: the defect that
survives review is rarely in the estimator.

You can check your own dashboard against the automated half of this list:

```bash
python scripts/meta-self-audit.py MY_REVIEW.html
```

Offline, standard library only, no API key, no model call. It runs on a weak
laptop in about a second. See [Running the self-audit](#running-the-self-audit).

---

## Where these came from, and what that limits

Three sources, all first-hand:

| Source | What it is | Size |
|---|---|---|
| Corpus fix ledger | Generated meta-analysis dashboards audited and repaired one file at a time, each with a commit and a per-number provenance line | 626 dashboards |
| Fix recipe | The defect classes those repairs were checked against | 19 classes |
| Error-reversal registry | Defects found in the **published** literature during a heart-failure network-meta-analysis audit, plus our own errors recorded by the same standard | 19 published-literature records |
| Working-corpus defect registry | Classes found while building and repairing a live corpus of topic objects and their delivered pages — the source of C10, C11, H7, H8 and M5, and of everything in [`DETECTOR-VERIFICATION.md`](DETECTOR-VERIFICATION.md). **Mostly defects in our own surfaces and our own checking machinery** | 135 topic objects, audited 2026-08-19 |

Three honest limits on that base:

- **It is one corpus and one clinical area for the published-literature half.**
  Frequencies below describe *these* files. Do not quote them as field-wide rates.
- **The counts are a point-in-time snapshot** taken on 2026-08-02, from a ledger
  that was still being written to. They will not reproduce exactly against a
  later copy, and they describe dashboards produced by one generator — a corpus
  with a shared ancestor, which is precisely why three defects reach 85%+.
  A defect that is near-universal *here* may be absent from work built another
  way.
- **Worked examples from the published literature are described structurally,
  not attributed.** The numbers and the mechanism are real and reproducible from
  the cited public sources; the review and its authors are not named here,
  because publishing an audit finding against a named researcher is a separate
  decision from teaching the error class.

The registry that these came from records our **own** errors by the same
standard it applies to anyone else — 37 content-changing errors of our own,
about two-thirds of which ran in the direction that flattered us. That ratio is
the reason this document exists. An error distribution centred on zero is noise;
one skewed toward the author's interest is a bias, and it is the one you are
least able to see in your own work.

---

## A claim of ours that the evidence revised

We started from the position that published syntheses fail on **two** counts:
they do not search widely enough, and they do not check what they find. It is a
natural pairing and we believed both halves equally.

Six syntheses have now been adjudicated in depth. **Three are erroneous. All
three failed at checking. None failed at breadth.**

| Failure mode | Confirmed |
|---|---|
| **Search breadth** — a trial that exists and was never found | **0** |
| **Checking** — a trial found, then entered wrongly | **3** |

And all three checking failures are the *same species*: one trial counted as
several, or characterised as something it is not. Two are the duplicate-identity
case in [C3](#c3--the-same-trial-counted-twice). The third recorded a trial's
comparator as the wrong drug and pooled it into a comparison it does not belong
to. The common root is **matching on the citation string instead of on trial
identity**.

The single most informative case cuts directly against our original claim: the
**worst** of the three had a *broader* search than several of the reviews that
got the right answer — multiple databases, preprints, no date or language
filter, and explicit translation of non-English text — and still produced a badly
wrong pooled result, because it counted the same patients three times. **Breadth
and checking are dissociable, and searching harder would not have caught either
of the errors we found.**

That matters for where anyone spends their effort. The remedies are different:

- Breadth failure → add national indexes, registries beyond ClinicalTrials.gov,
  preprints, non-English sources.
- Checking failure → de-duplicate by **registry identifier**, not by citation
  string; verify comparator and outcome definition at the primary source for
  every included row.

The second is what would have caught all three.

**What this does not license.** Zero confirmed breadth failures means *not yet
caught*, not *absent* — and the sample was selected on triage signals precisely
to find checking problems, so it is biased toward finding them. There is also a
real breadth limitation sitting in plain sight in the same audit: a
Chinese-language trial was invisible to a MEDLINE-only search, because its
journal is not indexed there. It simply did not cause an error in any of the six
— one review found it anyway, another excluded it deliberately and said why.
Breadth remains a plausible failure mode this sample has not caught in the act.

*Denominator: six syntheses, two clinical areas, selected because they looked
worth checking. `3 of 6` is a count, not a field rate, and must never be quoted
as one.*

We are recording this because a claim that survives contact with evidence is
worth more than one that was never tested, and a claim that was revised is worth
recording *as revised*. The registry behind this document applies that rule to
our own errors too — see the note above about which direction our own mistakes
ran in.

---

## Five errors of ours, found on 2026-08-19

These are in the same document, at the same size, as everyone else's. Four of the
five are defects in **our own published surfaces or our own checking machinery**,
and one is a claim from this programme's own reporting that we withdrew the same
day it was made.

The headline is a confirmation, and it needs to come first because it changes how
the rest reads. Across that day's audit of one working corpus of **135 topic
objects**, the **stored quantities held**: six pooled figures survived
independent recomputation, six recorded limitations survived independent test,
and **0 of 47** search records were found resting on a completeness proof that
does not hold. Every substantive correction below is to a *reason*, an
*attribution*, or a *check* — **never to a stored number**.

> **The objects kept being right and the instruments kept being wrong.**

| # | What was wrong | Measured | Now |
|---|---|---|---|
| 1 | A dashboard served pooled estimates the reviews had **withdrawn** | **92** of the 109 checkable rows | fixed by projection; a gate refuses the class |
| 2 | Index cards served an **external benchmark as the review's own result** | 5 of 522 cards; **3 live and unknown** | corrected from their own objects; re-sweep returns 0 |
| 3 | Summing per-topic trial counts **double-counted 19.2%** of the corpus | **68** of 354 summed trials | 53 of 339 after merging; distinct registrations unchanged at 286 |
| 4 | A **case-sensitive lookup** made our own check report a clean result | 1 instance, then 2 more the same day | **open, no detector** |
| 5 | This programme's own claim "**37 of 144** topics carry a templated question" | wrong denominator, one of three forms counted | **withdrawn**; corrected to 80 of 135 |

### 1. A dashboard served 92 estimates the reviews had withdrawn

Surfaced by a cross-family model seat running a different task, and verified here
before being recorded — an outside seat's finding is a lead, not a result.

The dashboard rendered a *Pooled OR (95% CI)* column from a snapshot generated
three months earlier. Of its **711 rows carrying a numeric value**:

| | |
|---:|---|
| **602** | **no underlying object at all — not checkable, so every count below is a floor** |
| 17 | the object has a live pooled estimate (this check does not compare the values) |
| **83** | the object has **withdrawn** its estimate |
| **8** | the review **no longer exists** — retired into another topic |
| 1 | the object carries no pooled value at all |
| **92** | **served where the object does not support it**, of 109 checkable |

> **A withdrawal is the strongest statement a review in this corpus can make.**
> It is what a review says when its trials do not share an endpoint, when its
> comparator is wrong, or when its headline cannot be reproduced from its own
> trials. **Serving the number anyway undoes every one of those decisions at
> once**, for every reader who never opens the page — and the aggregate surface
> is the one most readers actually look at.

**Fixed by projection, not by regenerating the snapshot.** A regenerated snapshot
is correct for a day and wrong again the next time a review withdraws something,
silently and with no symptom. Each row now carries the review's state; a
not-live value is **moved** to a superseded field rather than deleted; and the
snapshot is stamped with a **fingerprint over the underlying states, not a
timestamp** — because a timestamp answers *when was this made*, which is not the
question. *Do the sources still say what this was built from* is the question,
and **a regenerated snapshot with a fresh timestamp and a stale withdrawal passes
a date check and fails a fingerprint check.** A pre-commit gate now refuses on
either half. Exit 1 before, exit 0 after, proven on the case that shipped.

**And an absence must name its own cause.** The empty cell rendered every blank
as `— (k<2 / continuous?)`. **A reader told "k<2" about a withdrawal has been
told something false.** It now renders the real state.

**What this does not do:** it does not compare the *live* rows' numbers against
their objects. A row left live may still be stale by value. See
[C10](#c10--an-aggregate-surface-serving-estimates-the-reviews-withdrew).

### 2. Three live index cards served somebody else's number as their own

See [C11](#c11--an-external-benchmark-served-as-the-reviews-own-result) for the
class and the worked numbers. Two instances had been found by hand; **two found
by hand is not a measurement**, so the shape was swept mechanically over 522
cards. Five instances, three of them live and previously unknown, all three
corrected from their own objects. **The re-run after correction returns zero.**

### 3. Summing per-topic trial counts double-counted 19.2% of the corpus

See [H8](#h8--summing-k-across-reviews-counts-the-same-trial-many-times).

### 4. A case-sensitive lookup that returned nothing looked exactly like a clean result

The verification pass written to *check* the cross-family seat's dashboard
finding — rather than believe it — returned zero. The lookup was `pooled_or`;
**the field is `pooled_OR`**. Every row was skipped and the empty tally read
exactly like a clean corpus, while 92 rows were in fact serving withdrawn values.

> **An outside seat handed over a true finding and our own check said it was
> false.** Had that zero been believed, the finding would have been recorded as
> *"the other seat was wrong"* — the most expensive possible outcome of a correct
> delegation.

It reproduced **twice more the same day**, in the selftests of two instruments
written *after* it was written down, by the author who wrote it down. **Status:
open, no detector.** Full account and the remedies that do work, in
[`DETECTOR-VERIFICATION.md`](DETECTOR-VERIFICATION.md).

### 5. A claim of ours withdrawn the same day it was made

This programme's own session reporting stated that **"37 of 144"** topics carried
a templated question. That number used a denominator including retired
tombstones, and counted only one of the three ways a question field can fail to
state a question. **It is withdrawn.** The measured replacement is **80 of 135
live topics state a question** — 34 templated, 20 an echo of their own title, 1
absent. See [M5](#m5--a-review-question-that-is-a-template).

*Denominator and selection for all five: one corpus, 135 topic objects, audited
by its own maintainers on 2026-08-19. It is **enriched by construction** — this
is a corpus under active repair, so its instruments were under deliberate
scrutiny that day. These are counts in one corpus, not rates for anything.*

---

## How to read a class

Each entry has the same five parts:

- **What it is** — in plain language.
- **A real example** — with the actual numbers.
- **Why it fools a reader** — the specific reason a careful person misses it.
- **How to detect it** — by eye, and the detector ID if the kit automates it.
- **How to correct it** — what to actually do.

Severity means *how much of the paper the defect takes with it*:

- **Critical** — the headline number is wrong or is not entitled to be believed.
- **High** — a reported claim carries more confidence than its evidence supports.
- **Medium** — the framing misleads; the number may survive.

---

# Critical

## C1 — A continuous outcome reported as a ratio

**Detector: `MEL-01`**

**What it is.** The outcome is measured on a scale — mmHg, points on a symptom
score, mL/min, FEV1, blood loss in mL — and the pooled result is presented as a
risk ratio, odds ratio or hazard ratio. Those measures need a countable event.
There isn't one.

**A real example.** A dashboard whose primary outcome was change from baseline
in a continuous score reported a pooled risk ratio, and below it a number needed
to treat, a fragility index, a trial-sequential analysis and a L'Abbé plot — all
four of which require a binary event to exist.

**Why it fools a reader.** A ratio near 1 with a tight interval looks like a
familiar, well-behaved result. Nothing on the page announces that the estimand
and the measure disagree. The downstream machinery makes it look *more*
rigorous, not less: four extra diagnostics is what a thorough review looks like.

**How to detect it.** Read the outcome's units out loud, then read the measure.
If the units are a scale and the measure is a ratio, stop. `MEL-01` looks for a
continuous-unit token in the same neighbourhood as a ratio measure, and names
the ratio-only machinery still on the page.

**How to correct it.** Pool it as a mean difference, or a standardised mean
difference if the trials used different scales. Then **delete** the NNT, the
fragility index, the TSA and the L'Abbé plot. They are not merely inaccurate for
a continuous estimand — they are undefined. Cochrane Handbook ch.6 is the
reference for choosing the measure.

---

## C2 — The effect measure contradicts the data actually extracted

**Detector: `MEL-02`**

**What it is.** The extraction table holds 2×2 event counts but the analysis
reports a mean difference, or it holds mean(SD) columns and the analysis reports
an odds ratio. Somewhere between the table and the model, the data type changed
and nobody said so.

**A real example.** A recurrent-event outcome coerced into a binary 2×2 — every
patient counted once as "had an event or not", discarding the event *rate* the
trial was designed to measure — and then labelled a hazard ratio.

**Why it fools a reader.** Both halves are individually plausible. The table
looks like a table; the forest plot looks like a forest plot. You only catch it
by holding the two side by side, which is exactly what a reader skimming a
dashboard does not do.

**How to correct it.** Re-pool on the measure the data supports. If you
genuinely need to dichotomise a continuous outcome, state the threshold, state
who chose it and when, and show the counts it produced — a threshold picked
after seeing the data is a different study from the one you registered.

---

## C3 — The same trial counted twice

**Detector: `MEL-03`**

**What it is.** One trial enters the pool more than once: once as a pooled
multi-centre report and again as its component sub-studies, or as two papers
from the same cohort, or as separate dose arms treated as separate trials. Its
patients are counted two or three times and its weight rises accordingly.

**A real example.** A well-known 1990s heart-failure programme entered a review
as five rows: the pooled programme at n=1094, plus its four component trials at
345, 278, 366 and 105. Those four sum to **exactly 1094**. Arm-level
denominators reconcile too. 1094 distinct randomisations were counted as 2188 —
and the review's own stated method said to use only the most complete report
when several described one population. In an audit of reviews in that area that
spanned the 1990s and whose trial lists could be fully inspected, this same
double-count was present in **every one**. A separate review in the same set
carried four such duplications totalling roughly 1,709 patients, making its true
trial count about 66 rather than the 69 it claimed.

**Why it fools a reader.** The trial names are all different — that is the whole
problem. "US Carvedilol Program", "MOCHA", "PRECISE" read as four distinct
studies to anyone who does not already know they are the same programme. The
included-studies table is internally consistent. Nothing is misspelled.

**A second example, from a different field and a different decade.** A
cardio-renal review entered five rows for what are in fact two trials plus their
own pooled analysis. Read as arm splits rather than names:

| Row label | Intervention / control | What it is |
|---|---|---|
| first author, 2020 | 2833 / 2841 | trial A |
| a co-author's *forename*, 2021 | 3686 / 3666 | trial B |
| a different co-author, 2021 | 2833 / 2841 | **trial A again** |
| another author, 2022 | 6519 / 6507 | **the pooled analysis of A and B** |
| the same forename, 2022 | 3686 / 3666 | **trial B again** |

The pooled row reconciles against its own neighbours **on both arms
independently**: 2833 + 3686 = 6519, and 2841 + 3666 = 6507. Two exact hits on
the same subset is not coincidence. A second review in the same area repeats the
pattern, and there the duplicate hid behind a one-letter misspelling of the first
author's surname — enough that two rows for one trial sat side by side
undetected.

Both reviews show the same pair of consequences, and the second is the serious
one:

1. Participant total inflated by roughly **half again to four-fifths** over the
   number ever randomised for the question.
2. **Every pooled interval falsely narrow**, because the same events enter the
   variance calculation repeatedly. Both reported I² near 0 across most outcomes
   — which is what pooling data against itself produces.

That conjunction — **N inflated well past the trial universe, together with
I² ≈ 0** — is a cheap screen anyone can run before reading a single method
section. Low heterogeneity *alone* is not suspicious; consistent trials produce
it legitimately. It is the co-occurrence that is diagnostic.

**How to detect it.** Ignore the names and look at the denominators. For every
row, ask whether its n equals the sum of some other rows' n. That is precisely
what `MEL-03` does: subset-sum over the participant-count column, keyed on
denominators, sizes 2–5, up to 60 rows. Bigger tables return `INCONCLUSIVE`
rather than a false all-clear.

For a review you did **not** write — a published paper's Table 1, typed into a
CSV — use the companion screen, which adds arm-level reconciliation,
near-duplicate matching under a transcription tolerance, and the I² co-signature:

```bash
python scripts/trial-identity-screen.py templates/trial-identity/finerenone_table1_example.csv \
    --universe 22000 --i2 0
python scripts/trial-identity-screen.py --selftest
```

The tolerance is not optional decoration: the second review above printed the
same trial's arms as 2840/2833 in one row and 2830/2839 in another, against a
registered split of 2833/2841. Exact matching finds neither. A tolerance buys
that sensitivity at the cost of precision — two genuinely distinct trials of
similar size will collide — so every hit is a prompt to check the registry
identifier, never a verdict.

**How to correct it.** Keep one row — the most complete report of that
population — and re-pool. Also check dose-ranging trials: a trial contributing
three dose arms against one shared control is **one** cohort, and entering the
arms as separate studies double-counts the control group. One review in the
audit set went the other way and *discarded* dose arms, shrinking a 345-patient
trial to 173 with no documented multi-arm method. Neither is acceptable; both
were undocumented.

---

## C4 — A point estimate outside its own interval

**Detector: `MEL-04`**

**What it is.** Exactly what it says. The printed effect does not lie between
the printed bounds.

**A real example.** A published review prints `1.08 (CrI 0.61; 0.91)`. 1.08 is
not in [0.61, 0.91].

**Why it fools a reader.** Nobody checks. The eye reads "1.08, non-significant"
or "0.61–0.91, significant" and moves on; almost nobody reads all three numbers
as a single statement that has to be internally consistent.

**How to detect it.** One line of code, and it costs nothing to run over every
estimate on the page. `MEL-04` does this, and also catches inverted bounds.

**How to correct it.** Recompute all three from the same model on the same data.
A mismatch here usually means the point estimate and the interval came from
different analyses — which is a bigger problem than the typo it looks like.

---

## C5 — An impossible value on the ratio scale

**Detector: `MEL-05`**

**What it is.** A negative or zero risk/odds/hazard ratio. Ratios of positive
quantities are strictly positive.

**Why it fools a reader.** Minus signs are visually quiet, and a reader
half-expecting a difference will read `-0.35` as a reduction rather than as an
impossibility.

**How to correct it.** Usually a sign lost in back-transformation, or a
difference mislabelled as a ratio. Pool on the log scale, back-transform once,
at the end. Never pool ratios on the natural scale — that alone will hand you
Simpson's paradox in a random-effects model.

---

## C6 — The badge is green because someone wrote it green

**Detector: `MEL-06`** — **repaired in 532 of 626 dashboards (85%)**

**What it is.** A status badge — "INTERNAL CHECKS PASSED", "VERIFIED", "100%
integrity" — whose colour is a literal in the HTML rather than a value computed
from the verdict. It was green before any check ran, and it stays green after
one starts failing.

**A real example.** Five hundred and thirty-two dashboards in the corpus. The most
common shape: a green "checks passed" banner at the top of a page that, further
down, reported a numerical witness as skipped for a missing baseline. A skipped
witness is not a pass — but nothing in the page's rendering knew that.

**Why it fools a reader.** It is the single most trusted pixel on the page, and
it is the one with the least behind it. A badge is a claim about the *other*
claims; readers use it to decide how hard to read everything else. This is
exactly why it is worth writing honestly.

**How to detect it.** Search the page for the badge's colour. If it is a literal
in a `style` or `class` attribute and no code anywhere assigns colour from a
verdict object, the badge cannot fail. `MEL-06` checks both that and the
stronger signal: a badge asserting a pass while the page elsewhere states
`FAIL`, `UNVERIFIED` or `insufficient data`.

**How to correct it.** Derive the colour from the verdict, always. Then make the
verdict vocabulary able to express "I could not check this" — separate from both
pass and fail. That third state is the whole point; without it, an unrunnable
check silently becomes a passing one.

---

## C7 — The headline reads a different estimate from the prespecified one

**Detector: `MEL-07`**

**What it is.** The protocol prespecifies a Hartung-Knapp (HKSJ) interval. The
code computes it. The headline, the plain-language summary, the NNT and the
significance colour all read a wider-or-narrower DerSimonian-Laird or Wald
interval instead — usually the one that reaches significance.

**Why it fools a reader.** The methods section is truthful. The prespecified
analysis genuinely was run; it is in the output object. It just is not the
number on the screen. A reader who checks the methods finds nothing wrong.

**How to detect it.** For every displayed number, trace which variable it reads.
Every display surface must read the same one. `MEL-07` flags a headline labelled
with the laxer method, and returns `INCONCLUSIVE` — deliberately not clean —
when both paths exist and the headline is unlabelled.

**How to correct it.** One prespecified estimate, read by every surface. Show
the alternative as a labelled sensitivity analysis. If they disagree in
direction or significance, that disagreement *is* a finding and belongs in the
abstract, not in a supplement.

---

## C8 — Incompatible things pooled into one estimate

**Detector: partly `MEL-02`; needs human judgement — see [What is not
automated](#what-is-not-automated)** — **610 of 626 dashboards (97%) could do this**

**What it is.** Mixed estimands, mixed endpoints or mixed populations combined
into a single pooled number. A pooling engine that can emit an estimate for an
incompatible set will eventually be asked to.

**Why it fools a reader.** The output is a normal-looking forest plot. Nothing
about a pooled diamond announces that two of its inputs measured different
things.

**How to correct it.** Make it structurally impossible rather than merely
discouraged: the engine should **fail closed** — refuse to emit a pooled
estimate at all for an incompatible set, rather than emit one with a warning. A
warning is a thing readers scroll past. In this corpus, 610 of 626 dashboards
would emit the estimate anyway — the single most common defect of the whole run. That is the fix that mattered most and the one
that needed a code change rather than a note.

---

## C9 — Forest-plot rows labelled in a different order from their values

**Detector: `MEL-17`**

**What it is.** The estimates are drawn in one order and the study names in
another. Every row of the plot then attributes a result to the wrong trial. The
common special case is an exact reversal — one list sorted ascending, the other
left in extraction order.

**A real example.** A plot built from two parallel arrays, `labels[]` and
`estimates[]`, where a trial was later removed from one array and not the other.
From that row down, every label sat beside its neighbour's number, and the
totals row — computed from the values, not the labels — stayed correct.

**Why it fools a reader.** The pooled diamond is right. The heterogeneity
statistic is right. Nothing in the summary row is affected, because the summary
never reads the labels. The only way to see it is to check an individual study's
number against its source, which is exactly the check a forest plot is supposed
to save you from.

**How to detect it.** Pick the two or three trials you know best and read their
estimates off the plot. `MEL-17` checks it three ways, all from the file's own
internal consistency: label and value arrays of different lengths; a label array
that is a permutation (or exact reversal) of the extraction table's order; and
both ends of the axis carrying the same "favours" label.

**How to correct it.** Do not re-sort one array to match the other — that fixes
the symptom and leaves the cause. Build the plot from a **single list of
records** (`{label, estimate, lo, hi}`) and sort that list. A label cannot drift
from its estimate if they were never in separate containers.

---

## C10 — An aggregate surface serving estimates the reviews withdrew

**No detector in this kit. Found by a cross-family model seat; verified by hand.**

**What it is.** A summary table, index, dashboard or portfolio page is built from
a snapshot of your reviews. A review then withdraws its pooled estimate — because
its trials do not share an endpoint, because its comparator was wrong, because
the headline could not be reproduced. **The summary keeps serving the old
number**, and nothing about the summary looks stale.

**A real example.** Ours, on 2026-08-19. A dashboard rendering *Pooled OR (95%
CI)* from a snapshot generated three months earlier. Of **711 rows carrying a
numeric value**, 602 had no underlying object and were not checkable; of the
**109 that were**, **92 were serving a value the review does not support** — 83
withdrawn, 8 belonging to reviews that no longer exist, 1 with no pooled value at
all. The uncheckable 602 make 92 a floor, not a total.

**Why it fools a reader.** The withdrawal is *on the review page*, which most
readers never open. The aggregate surface is the one they actually read, and it
is internally consistent: a number, an interval, a k. Nothing about it announces
that it is a copy. **A stale copy of a live value and a live copy of a withdrawn
value look identical.**

And the empty cells lie in the other direction. That dashboard rendered every
blank as `— (k<2 / continuous?)`. **A reader told "k<2" about a withdrawal has
been told something false**, and told it by a tooltip that sounds like a reason.

**How to detect it.** Project, do not regenerate. Regenerating is correct for a
day and wrong again the next time a review withdraws something, silently and with
no symptom:

- Carry each row's **source state** (`live` / `withdrawn` / `retired` /
  `no pool`) into the summary as data, not as formatting.
- **Move** a not-live value to a `superseded` field rather than deleting it. The
  reader can then see that a number was withdrawn, which is more informative than
  a blank.
- Stamp the snapshot with a **fingerprint over the underlying states, not a
  timestamp.** A timestamp answers *when was this made*, which is not the
  question. The question is *do the sources still say what this was built from* —
  and a regenerated snapshot with a fresh timestamp and a stale withdrawal
  **passes a date check and fails a fingerprint check.**
- Wire a gate that refuses on either half: a fingerprint that no longer matches
  *or is absent* (absent is not fresh), or any row serving a value its source
  withdrew.
- Make every empty cell **name its own cause**.

**How to correct it.** Re-derive every row from the current state of the review
it names, and keep the withdrawn value visible beside its withdrawal rather than
blanking it — the same *add beside, never overwrite* rule as everywhere else in
this kit. Then check the fix by **re-running the detector to zero**, not by
reading the diff.

**What this does not cover.** It answers only *does the summary show an estimate
where the review says there is none*. It does **not** compare the live rows'
numbers against their reviews. A row left live may still be stale by value, and
that is a second check.

---

## C11 — An external benchmark served as the review's own result

**No detector in this kit.** Swept mechanically in the source corpus; the sweep
is described below because the shape is reproducible, and its limits are real.

**What it is.** Your review cites a published estimate from someone else's
meta-analysis as a benchmark — a legitimate and useful thing to do. That number
then appears on your index, your summary card or your abstract **in the slot
where your own pooled result goes**, with no marker that it came from elsewhere.
The number is real. It belongs to somebody else.

**A real example.** Ours. Two instances had been found by hand, and **two found
by hand is not a measurement**, so the shape was swept over **522 index cards, 77
benchmark records and 116 page-map entries**. Five instances, **three of them
live and previously unknown**:

| Card served | The review's own pool |
|---|---|
| `RR 0.07 (0.01–0.32), k=2` | **withdrawn, k=0** |
| `HR 0.22 (0.11–0.45), k=2` | `RR 0.2081 (0.0715–0.6057), k=2` |
| `RR 0.21 (0.13–0.33), k=3` | `RR 0.2605 (0.1766–0.3845), **k=2**` |

**The first is the worst and it is a different degree, not a different kind.**
The review has withdrawn its estimate — `k=0` — and the card serves a confident
external `RR 0.07 (0.01–0.32)` at `k=2`. **The review says it cannot answer and
the index says it answered decisively.** The second carries a measure mismatch on
top: the card says `HR`, the review says `RR`. The third claims `k=3` where its
review pools `k=2` — the card is wrong about how many trials the review holds.

**Why it fools a reader.** On *your* index — a list of *your* reviews — a reader
has no reason to suspect that one row means *somebody else computed this*. The
number is correctly transcribed and correctly attributed **in the source record**;
it is the *rendering* that drops the attribution. Every check downstream reads the
card as the review's own output and finds it internally consistent.

**The structural finding is larger than the five.** **42 of the cards were
authored in a `Published:` register** rather than as a projected result of the
review, and a reader cannot tell the two apart. Of those 42, **3** were comparable
against a review at all, **34 had no underlying review object**, and 5 had no
benchmark record. **Thirty-four of forty-two cannot be checked by anything in the
corpus** — which is why "three instances" is a floor, not a count.

**How to detect it.** Project every displayed value from the review object it
belongs to, and let a benchmark appear only in a slot that is *labelled* a
benchmark. Then sweep for the class: for each card, ask whether the value it
shows equals the review's own pooled value, and classify — not into
found/clean, but into `card is the review's`, `card is the benchmark`, `card
withdrawn`, `no review`, `no card`, `no benchmark`.

**One measured caution about that sweep, because it is the more useful half.**
A third limb asked, independently of any card, whether each benchmark reconciles
with the review's own trials. **It first returned eight, and two of the eight
were the instrument's own defect**: it compared a hazard-ratio benchmark against
a **mean difference in a symptom score**, and against a **rate ratio over
recurrent events** — two quantities compared by their **slot** rather than by
their **definition**, with the arithmetic completing without complaint.

> With measure-matching and scope-matching enforced, **all eight collapsed to
> zero.** Done correctly that limb convicts nobody, **and that is the honest
> answer rather than a disappointing one.**

**But read what that zero is over.** The limb returned zero convictions and it
also **assessed zero**: all 172 rows came back `NOT_ASSESSABLE` — 150 with no
benchmark record or no review object, 16 measure mismatches, 3 ambiguous
outcomes, 2 scope differences, 1 with too few intervals. *"Convicts nobody"* and
*"checked everybody and found nothing"* are different statements and only the
first is true. **A large not-assessable folded into one line reads as "nothing to
see here"**, which is why it is broken out here and in the tool's own output.

It also **cannot convict the one case we know is real**: that benchmark is `k=2`
against a review holding three trials, so the limb correctly refuses it as *scope
differs*. That conviction came from testing the benchmark against **its own
declared source** — two named trials with their PMIDs. **A benchmark record
generally does not name the trials it pooled, so that test is not generally
available. That is the gap this sweep measures and does not close.**

**How to correct it.** Re-derive the card from the review. If the review has
withdrawn its estimate, the card says so — it does not fall back to the nearest
available number. Keep the benchmark, in a row that says whose it is. **A
benchmark that reconciles is not thereby correct, and a page serving it is not
thereby innocent** — reconciling is a fact about arithmetic, not about
attribution. An honest declaration that a value comes from elsewhere is not a
defect at all; it is the fix.

---

# High

## H1 — Small-study machinery run below the k it needs

**Detector: `MEL-08`**

**What it is.** Egger's test, a funnel plot, trim-and-fill or a meta-regression
run on a handful of studies. Cochrane Handbook §10.4.3.1 is explicit: do not
test for funnel-plot asymmetry when fewer than 10 studies are pooled. The test
has almost no power there, and its p-value is not interpretable.

**A real example.** A dashboard gating its Egger test at `k >= 3` and reporting
"no evidence of publication bias (p = 0.31)" on 3 studies. Other pages in the
same corpus gated funnel plots and meta-regressions at `k >= 2`.

**Why it fools a reader.** A non-significant Egger test reads as *reassurance* —
"we checked for publication bias and found none". At k=3 it is not evidence of
absence; it is absence of a test. The check makes the review look more careful
while making the reader less accurate.

**How to detect it.** Find k. Compare it against the threshold for every
diagnostic on the page. `MEL-08` does this, and separately greps the code for
the gate bug itself — a `k >= 3` guard in a publication-bias path — because that
is the defect that will regenerate the finding next time. It also flags NNT,
fragility index, TSA and L'Abbé shown for a continuous estimand.

**How to correct it.** Raise the gate to k≥10 and suppress the test, the plot
*and* the p-value below it. If you keep it visible, print the k next to it and
label it "underpowered, not interpretable" in the same font as the result.

---

## H2 — A PRISMA flow whose own numbers do not reconcile

**Detector: `MEL-09`**

**What it is.** Identified minus duplicates does not equal screened; screened
minus excluded does not equal full-text assessed; a stage reads zero; more
studies are included than were ever identified; or the flow's "included" count
disagrees with the k the analysis actually pools.

**Why it fools a reader.** A PRISMA diagram is a compliance object. Readers
check that it is *present*, not that it *adds up*. It is one of the few parts of
a paper almost guaranteed to be skimmed.

**How to correct it.** Reconcile against the real search export and screening
log. A stage reading zero means the diagram was never populated — an empty
PRISMA is worse than no PRISMA, because it claims a process that did not happen.
If "included" and k genuinely differ (studies included but not poolable), say so
explicitly on the diagram.

---

## H3 — "Fragility index = 0, therefore robust"

**Detector: `MEL-10`**

**What it is.** The fragility index is the number of events that would have to
change to overturn statistical significance. Zero is the **weakest** possible
value: it means the result is already non-significant, so nothing has to change.
Reporting it as robustness inverts the meaning completely.

**Why it fools a reader.** "Index = 0" pattern-matches to "zero problems". The
metric's name does not tell you which direction is good, and unlike a p-value
there is no widely-known threshold to anchor against.

**How to correct it.** Delete the robustness claim. And check two further
misuses that travel with it: the fragility index is undefined for a continuous
outcome, and it is a **single-trial** statistic — applying it to a pooled
estimate is a category error, not a conservative approximation.

---

## H4 — Efficacy synthesised, harms not

**Detector: `MEL-11`**

**What it is.** The review pools benefit and says nothing quantitative about
harm, while presenting conclusions in language that implies a practice
recommendation.

**A real example.** Across the core comparator set in one clinical area, **no**
published network meta-analysis pooled any adverse-event outcome. One pooled
all-cause drug discontinuation as a tolerability proxy and explicitly cautioned
against reading it as harm. Four pooled nothing harms-related at all.

**Why it fools a reader.** Absence is invisible. A reader notices a *bad* safety
result; nobody notices a missing section. And an efficacy-only review reads as
positive by construction — every number in it is about benefit.

**How to correct it.** Pool at least one harm outcome. If the trials genuinely
do not report harms comparably, say so in the limitations *and* state that the
benefit estimate therefore cannot support a practice claim. Do not let all-cause
discontinuation stand in for a harms synthesis — it is driven by lack of
efficacy as much as by toxicity. Label it a proxy where you use it. And check
the sign on any NNH: a negative number-needed-to-harm means the convention was
inherited from the benefit outcome.

---

## H5 — Included studies that fall outside the stated search window

**Detector: `MEL-12`**

**What it is.** The methods say the search ran to a given date; the included
studies include trials published after it.

**A real example.** A review stating a search window ending January 2020, whose
included set contains trials published in August 2020, March 2020 and 2021.

**Why it fools a reader.** Nobody cross-references the window against the
reference list. Both statements are true in isolation.

**How to correct it.** Either the window is mis-stated — fix it — or trials were
added outside the search, which must be declared as hand-searching with a
reason. Silently adding a trial after the search is how a sponsor's own trial
gets into a review that never searched for it.

---

## H6 — A registry identifier that cannot be right

**Detector: `MEL-18`**

**What it is.** An NCT number, PMID or DOI that is malformed, or that the page
itself contradicts — the same registry ID attached to two different trials, or
an ID stated against a year before that ID block existed.

**A real example.** In the corpus, three dashboards were repaired for wrong
identifiers or denominators. The mechanism worth learning is the cheapest one:
an ID copied down a column from the row above, so a block of extraction rows all
point at one trial. Nothing about the resulting table looks wrong.

**Why it fools a reader.** Nobody proofreads an eight-digit number. `NCT0158432`
and `NCT01584321` are the same string to a skimming eye, but the second is a
real and different study. Worse, a wrong-but-well-formed ID sends your reader to
a real trial record that is not the one you analysed — so your provenance chain
looks *stronger* than an honest gap would.

**How to detect it.** `MEL-18` checks that every identifier is well formed (an
NCT is `NCT` + exactly 8 digits; a PMID is digits only; a DOI is
`10.<registrant>/<suffix>`), that no single ID is bound to two different trial
names, and that no ID is listed against a year before that block was issued —
ClinicalTrials.gov assigns numbers in registration order, so an `NCT06…` cannot
label a trial that reported in 2005.

It reads those pairings only from **structure** — a table column whose header
says what it holds, or a trial record in the page's own script state. An earlier
version bound each ID to the nearest capitalised word instead and fired on 38 of
40 real dashboards, because one NCT legitimately appears a dozen times per page
and picked up `AUTO`, `TRIALS` and `AACT` as trial names.

**How to correct it.** Re-copy the identifier from the registry record you
actually opened, not from the row above and not from another review's table.
Offline, no tool can tell you an ID points at the right trial — only that the
page contradicts itself. That check is yours.

---

## H7 — A paginated search treated as complete because the cursor came back empty

**What it is.** Your search returns results in pages. You follow the pagination
token until it comes back null, and you record the search as complete. **The null
token is not the proof.** The proof is the sum of records actually returned,
reconciled against the total the API itself reported.

**A real example.** Ours, 2026-08-19. One direction of this had already been
established and enforced: **a live token means the search is incomplete**, and a
gate refused any search record that showed one. The corpus then assumed the
converse for free — **a null token means complete** — and **that half was never
tested**, because on every search until then both proofs agreed. On one topic
they finally disagreed:

> **`100 + 100 + 3 = 203` records returned, with the pagination cursor null,
> against a reported total of `430`.**
>
> **227 records the pagination never returned, while the cursor said it was
> done.**

*Why* the API stopped early is **not diagnosed** — a server-side cap, a
differently-scoped total, something else. The discrepancy is recorded rather than
explained, **because writing down a guessed cause is worse than naming the gap.**

**Why it fools a reader.** It fools the *author*, which is worse. The search log
looks complete, the record count is large, and there is no error. The reconciling
check had existed for months and **had never had an opportunity to fail** —
every search before this one reconciled, so the weaker proof always had the
stronger one standing behind it. A guard whose triggering condition has never
arisen is unproven however green it reads.

**How to detect it.**

- **Reconcile the sum across pages against the reported total.** That is the
  proof. The null cursor is corroboration and never the proof.
- **An absent token field is not a null one.** Reading a *missing*
  `next_page_token` as *"the cursor said done"* convicts a record of a proof it
  never offered. Silence is not a claim.
- Make the verdict its own state: `cursor said done but the sum does not
  reconcile`. It runs even when a record lists no identifiers — page counts and a
  total are enough.

**How to correct it.** Before building anything new on it, **bound the damage on
what already exists.** Ours re-checked every search record in the corpus — **47
rows across 18 objects** — asking which evidence each one actually rests on:

| State | Rows |
|---|---:|
| **Reconciles** — returned equals total, so the proof holds regardless of the cursor | **31** |
| Shortfall declared — legitimate, and already flagged | 8 |
| Not executed — a database the record says was not searched | 6 |
| Not assessable — states neither count | 2 |
| **Resting on a null cursor alone** | **0** |
| **Undeclared shortfall** | **0** |
| **Topics with a delivered page resting on an unproven record** | **0** |

**No delivered page rested on a null cursor alone.** The exposure was confined to
the one topic, which had declared its shortfall and on which nothing had been
built. *Then* the search was re-run by another route.

**And the audit's own first run was wrong, which is the transferable part.** It
reported **five** not-assessable rows. **All five were the audit failing to
look** — two records spell the fields differently, three nest them one level
down. The durable fix is not chasing key names: **a not-assessable verdict now
prints the keys the record actually has beside the keys it looked for.** An
unassessable verdict that does not say what it looked at is not refutable. See
[`DETECTOR-VERIFICATION.md`](DETECTOR-VERIFICATION.md).

---

## H8 — Summing k across reviews counts the same trial many times

**What it is.** You have several reviews. You report the size of your evidence
base by adding up their trial counts. **Trials that appear in more than one
review are counted once per review**, and the total describes no set of patients
that exists.

This is [C3](#c3--the-same-trial-counted-twice) one level up. C3 is a trial
counted twice *inside* one pool, where it inflates the estimate and narrows the
interval. H8 does not touch any estimate — it inflates the **claim about how much
evidence you have**, which is the number that goes in the abstract.

**A real example.** Ours, 2026-08-19, on a corpus of 135 topics. Summing per-topic
trial counts across the **140 topics with a readable trial list** gave **354**.
The **distinct registrations were 286**. **68 of 354 summed trials — 19.2% —
were double counting**, and the corpus had been describing itself with the larger
number.

After merging nine clusters of reviews that turned out to be asking one question:

| | Before | After |
|---|---:|---:|
| Sum of per-topic trial counts | 354 | **339** |
| **Distinct registrations** | **286** | **286** |
| Double-counted by summing | 68 | 53 |
| Topics with a readable trial list | 140 | 131 |

**The distinct count did not move. The merges removed double counting and no
evidence** — which is the check that the merge was a bookkeeping change rather
than a loss. 53 of 339 remain double-counted, and that is not a residual defect:
some of it is legitimate, for the reason below.

**Why it fools a reader.** It is arithmetic on numbers that are each individually
correct. Every review's k is right. Nothing in any single review is wrong, and no
estimate anywhere changes — which is exactly why nobody checks it.

**How to detect it.** De-duplicate on **registry identifier**, never on citation
string or title, and report the distinct count beside the sum whenever you
describe your evidence base. Two lines, always:

```
summed across reviews : 354
distinct registrations: 286   <- the one that describes patients
```

**How to correct it — and the caution matters more than the fix.** **An identical
trial set between two reviews is a question to ask, never a verdict.** Two reviews
holding the same registrations are not necessarily one review: two of ours share
no trial *by construction* because one asks about treatment and the other about
prevention, and two reviews may legitimately hold one trial for different
questions. What an identical set *does* establish is that somebody must look.

**And the remedies are not symmetric.** Splitting one review that asks several
questions **recovers** evidence from readings that would otherwise be lost.
Merging **discards** a review. So a split is a routine build and **a merge is a
decision for a human**, made once, recorded, and reversible. Measure and
recommend; do not let the de-duplicator change anything by itself.

---

# Medium

## M1 — Template contamination

**Detector: `MEL-13`** — **repaired in 63 of 626 dashboards (10%)**

**What it is.** Text from the donor template survives generation and describes
the wrong drug, the wrong disease or the wrong comparator. Or a placeholder
reaches the page: `{{outcome}}`, `None participants`, `NaN`, `[object Object]`,
an internal slug in patient-facing prose.

**A real example.** A COPD review describing its intervention as "a
non-steroidal MRA" and referring to "CKD trials" — both inherited verbatim from
the kidney-disease template it was generated from. Separately, a Python `None`
reaching a JavaScript object literal, which is not a cosmetic issue at all: JS
has no `None`, so the page dies with `ReferenceError` and renders as a stub.

**Why it fools a reader.** A patient or clinician reading the plain-language
summary has no way to know the sentence is about a different drug. It is fluent,
confident and completely wrong.

**How to detect it.** `MEL-13` looks for known donor strings and placeholder
tokens, and is careful about *where*: `NaN` inside a `<script>` is ordinary
JavaScript, and "Conflicts of interest: None declared" is correct English. Only
a rendered `NaN`, or a `None` where a count belongs, is a leak. (Both of those
false positives came from running this detector against real files.)

**How to correct it.** Fix the generator, not the output — map `None` to `null`
or "not reported" at the boundary — then re-render and keep the check in the
build. A leak that reached one page reached all of them.

---

## M2 — A commit timestamp claimed as prospective registration

**Detector: `MEL-14`** — **repaired in 540 of 626 dashboards (86%)**

**What it is.** Wording to the effect that a git commit hash plus timestamp
"constitutes" or "is equivalent to" PROSPERO / ICMJE prospective registration.

**Why it fools a reader.** The underlying fact is true and genuinely valuable —
a signed commit *is* tamper-evident evidence that a protocol existed on a date.
The overclaim rides on that truth. What a commit in your own repository does not
give you is **third-party custody** or **public discoverability**: you can
rewrite the history, and nobody searching PROSPERO will find you.

**How to correct it.** Keep the timestamp. Describe it accurately —
"tamper-evident local record of the protocol date" — and drop the equivalence.
If you want registration, register.

---

## M3 — An eligibility filter that quietly narrows the question

**Detector: `MEL-15`**

**What it is.** Two common shapes. A bare publication-date floor ("we excluded
trials published before 2015") with no methodological reason. And a comparator
filter admitting only placebo or standard care, which silently converts "is X
effective?" into "is X better than nothing?" and excludes every active-
comparator trial — warfarin, aspirin, dalteparin — from a question that was
never scoped that way.

**Why it fools a reader.** Both look like ordinary methodological rigour.
Inclusion criteria are read as evidence of care, not as choices that need
justifying. And a placebo-only pool systematically **overstates** the effect
relative to the question the title asks.

**How to correct it.** Every exclusion needs a stated reason that is about the
science — a guideline change, a licensing date, a transitivity threat — not
about convenience. If active-comparator trials are genuinely out of scope, put
that in the question. Otherwise widen the filter and re-run.

---

## M4 — A stale search presented as current

**Detector: `MEL-16`**

**What it is.** A long gap between the last search and publication, uncaveated —
often alongside a claim to present the most up-to-date evidence.

**A real example.** A review whose search ran in February 2022, published in
November 2024 — a 33-month gap — stating in its own discussion that it "provided
the most up-to-date evidence". The same review's main text and supplement
disagreed with each other about the search date.

**Why it fools a reader.** The publication date is prominent; the search date is
in the methods. Readers date the evidence by the former.

**How to correct it.** AMSTAR-2 item 4 expects a search within 24 months of
publication. Re-run it, or state the gap in the abstract and drop the currency
claim. If your review is "living", the interval between refreshes is part of the
method and belongs next to the result.

---

## M5 — A review question that is a template

**What it is.** The review has a question field. It is filled in. What it
contains is the title with a stock clause appended, or the title repeated, or
nothing. **The field is present and it carries no content**, and every check that
reads it reports as though the question had been examined.

**A real example.** Ours, and we did not go looking for it. A third-party model
family was given twelve clusters of our reviews to read **blind** — no topic
names, no verdicts, no hint that a decision depended on the answer — and asked
whether the reviews in each cluster ask the same question. It returned **UNCLEAR
on ten of the twelve**, and its stated reason every time was that the question
field is auto-generated boilerplate. **The UNCLEARs were the finding.** We then
measured it:

| State | Topics | |
|---|---:|---:|
| **States a question** | **80** | 59.3% |
| Templated — the title plus a stock clause | 34 | 25.2% |
| An echo of its own title | 20 | 14.8% |
| Absent | 1 | 0.7% |

*135 live topics. Ten retired tombstones excluded from the denominator.*

> **A templated question is not a bad question. It is an ABSENT one wearing the
> shape of a present one.**

**Why it fools a reader — and every check you own.** It fools *machinery* first.
A comparison of two templated questions returns "these do not differ" —
**correct as logic, and it reports as though the axis had been checked when it
had not been.** A check that splits a review whose question is ambiguous cannot
find an ambiguity in a title. Any claim you make on the basis of question text
carries this denominator, whether or not you state it.

So the honest consequence was stated plainly rather than left implicit: **the
nine merges we executed rest on identical trial sets, a richer surviving review,
a proven union and reversibility — NOT on a comparison of questions.** For ten of
the twelve clusters there was no question to compare. That is a stronger position
honestly stated than a weaker one asserted.

**How to detect it.** Classify the field rather than testing whether it is
non-empty: does it *state a question*, is it *the title plus a stock clause*, is
it *an echo of the title*, is it *absent*. Four states, not two. Then report the
proportion **beside every claim that reads that field**.

**How to correct it.** Write the question. For a review that has absorbed
another, this is not cosmetic — a review that has taken in a second review and
cannot say what it asks has a real problem, and the template is hiding it.

**What this does not claim.** **Not** that the templated reviews are wrong, and
**not** that their trials or estimates are affected. It claims only that their
question field carries no content a check can read.

**And a correction of ours belongs here.** This programme's own reporting first
stated this as **"37 of 144"**. That denominator included retired tombstones, and
it counted only one of the three ways the field fails. **It is withdrawn**, and
the table above replaces it.

---

# What is not automated

These are real and they were found by hand. A detector for them either does not
exist yet or cannot exist. They are here because knowing what a tool *cannot*
catch is the difference between using it and trusting it.

| Class | Why it resists automation | What to do instead |
|---|---|---|
| **A stratification read as a randomisation split** | A trial entered as "26/26" where 26/26 is a disease-aetiology stratification inside a 52-patient trial, not the arm split. The table is internally consistent, so no table-only check can see it. | Read arm denominators back from the primary source for every trial. There is no substitute. |
| **Inherited trial lists** | A review that runs a narrow de-novo search, retains one record, and imports the rest of its trial list wholesale from an earlier (sometimes sponsor-funded) review. Downstream reviews then "agree" — but they are not independent, so their agreement corroborates nothing. | Ask where each trial in a review's list actually came from. Overlap statistics between reviews help; provenance per trial is the real answer. |
| **A stated rule not applied to the analysed set** | A review states a ≥50% background-therapy rule and its headline rests on a coding that violates it; the rule-compliant coding gives a materially different number, filed as a sensitivity analysis. | Extract the paper's own stated rules, then test the included set against them. The highest-value manual check on this list. |
| **Data taken from design papers or conference abstracts** | Trials cited by a pre-results design paper or an abstract, where the peer-reviewed results paper came years later with different numbers. | Check every included citation resolves to a *results* publication. |
| **Included trials missing from the reference list** | A 32-trial review citing about 10 of its own trials — not reproducible from its own article of record. | Set-difference the included-studies table against the reference list. Automatable, not yet automated here. |
| **A rank that its own analysis does not support** | A treatment ranked #2 by P-score while being absent from the same paper's list of regimens significant in the primary analysis, with the top three P-scores within 0.04 of each other. | Never rank by SUCRA/P-score alone. Show the credible intervals of the relative effects next to the ranking. |
| **A denominator that disagrees with the regulator** | An included trial entered at n=6,200 where the FDA label reconciles to 6,632 analysed. | Reconcile each trial's n against the registry entry or regulatory document. |
| **A search strand querying the wrong population** | A CENTRAL strand contributing a quarter of all records to a reduced-ejection-fraction review, built on *preserved*-EF search terms — and in PubMed syntax that CENTRAL does not use. | Read the executed search string, not the one in the appendix. Diff them. |
| **A flagship review that does not exist** | A frequently-cited "Cochrane review" that never progressed past protocol stage: the record reads "This is the protocol for a review and there is no abstract." | Open every citation you lean on. Distinguish *structurally absent* from *blocked* from *unreachable* — and never let a shortfall be recorded as a zero. |

**A note on missing trials.** If you think an eligible landmark trial is missing
from a pool, **flag it, do not add it**. Adding a trial changes the pooled
estimate, k, the forest plot and every downstream statistic. That is a decision
for a human with the protocol in front of them, not something to slip in during
a cleanup pass.

The corpus run enforced exactly this. Across 626 dashboards, two landmark trials
were escalated to a human review queue — both for the same pulmonary-arterial-
hypertension review — and **neither was added**. Both had a time-to-event or
median primary endpoint with no 2×2 to extract, and adding them drove the render
to `NaN`. The pool was left unchanged and the finding was written down instead.
That is the outcome to copy: a documented gap beats a number you could not
actually source.

---

# Running the self-audit

```bash
# the whole check, offline
python scripts/meta-self-audit.py MY_REVIEW.html

# machine-readable, for a CI step or an agent
python scripts/meta-self-audit.py MY_REVIEW.html --json

# also check your pooling code against invariants any correct
# implementation must satisfy (needs Overmind installed)
python scripts/meta-self-audit.py MY_REVIEW.html \
    --metamorphic templates/meta-self-audit/pooling_probe.py
```

**Verdicts.** There is deliberately no verdict called `PASSED`.

| Verdict | Exit | Meaning |
|---|---|---|
| `CLEAN` | 0 | Every applicable detector ran and found nothing. |
| `DEFECTS-FOUND` | 1 | At least one detector fired. |
| `INCONCLUSIVE` | 2 | A detector could not establish the facts it needs. |

`INCONCLUSIVE` exits non-zero on purpose. "I could not check this" must never
collapse into "this is fine" — that collapse *is* class C6, and a tool that
commits it while detecting it would not deserve to be believed. A detector that
crashes is reported as inconclusive, never as clean.

**The optional pooling witness.** With `--metamorphic`, the audit reuses
Overmind's `MetamorphicWitness` rather than reimplementing it. It does not check
your pooled number against a right answer — there isn't one — but against
relations any correct implementation must satisfy: identical effects pool to
that effect, negated effects pool to the negated result, τ² ≥ 0, I² ∈ [0,100].
A `SKIPPED` witness is reported as skipped and is **not** a pass.

One measured caveat, because it will bite you. The witness's *scale-invariance*
relation doubles every effect while leaving the variances alone. That is not a
change of units — rescale an outcome and its standard errors rescale with it —
and a **correct random-effects estimator fails that relation by construction**,
because τ² absorbs the inflated spread and the weights move. Measured on the
witness's own inputs with this kit's reference probe:

| Transform | Pooled ratio | τ² |
|---|---|---|
| effects ×2, variances unchanged (what the witness does) | 1.862 | 0.021 → 0.150 |
| effects ×2, variances ×4 (a real unit change) | **2.000** | 0.021 → 0.085 |
| fixed-effect, effects ×2 | **2.000** | — |

So relation 1 is meaningful for fixed-effect pooling only. The audit names this
rather than hiding it: if that is the sole violation, the output says so. Run
`POOLING_PROBE_MODE=fixed` to exercise all five relations. Do **not** switch your
probe to fixed-effect while your dashboard reports random-effects — that makes
the gate green by pointing it at code the dashboard does not run.

---

# Blind spots of these detectors

Read this before you trust a `CLEAN`.

- **`CLEAN` means "no detector fired", not "correct".** Eighteen detectors cannot
  cover the failure modes in [What is not automated](#what-is-not-automated),
  and those include the most serious class on the list — a number that is simply
  wrong at the source, in a table that is internally consistent.
- **Everything here is text-pattern matching, not comprehension.** The detectors
  read a rendered page. They do not understand your clinical question, and they
  cannot tell a well-justified decision from a badly-justified one — only
  whether a justification is *present*.
- **They only see one file.** A defect that lives in your extraction
  spreadsheet, your search strategy or your protocol is invisible to a check
  that reads the dashboard. `MEL-12` and `MEL-16` read what the page *claims*
  about the search; they cannot see the search.
- **The double-count search is bounded.** Subsets of size 2–5, tables up to 60
  rows. A six-way split, or a bigger table, returns `INCONCLUSIVE` — which is
  honest, but is not a check.
- **Denominator matching is exact.** `MEL-03` finds sums that match to the
  patient. A double-count where one report drops two patients for missing data
  will not match, and will not be found.
- **The contamination list is a list.** `MEL-13` knows the donor strings from
  *this* corpus. Your template will leak different words, and it will not know
  them. Add your own.
- **`MEL-06` cannot see server-rendered logic.** It checks the HTML and inline
  scripts it is given. A badge coloured by a build step it cannot see will read
  as hardcoded; a badge coloured by a framework it does not recognise may read
  as clean when it is not.
- **k extraction can be wrong.** `MEL-08`'s thresholds are only as good as the k
  it read off the page. If it cannot find k, it says `INCONCLUSIVE`; if the page
  states k misleadingly, the detector inherits that.
- **No detector here checks your arithmetic** unless you pass `--metamorphic`,
  and even then it checks invariants, not correctness. Nothing in this layer
  recomputes your pooled estimate from your raw data.
- **`MEL-17` cannot see a picture.** It reads label and value arrays and table
  order. A forest plot drawn into a `<canvas>`, rendered server-side, or shipped
  as an image is reported `NOT_APPLICABLE` — which is honest, and is not a
  check. It also cannot tell you the order is *wrong* when labels and values
  were mis-paired at extraction time and have been consistently mis-paired ever
  since; it only sees two views of the file disagreeing with each other.
- **`MEL-18` cannot check an identifier against the registry.** It is offline.
  It knows an NCT is well formed, that the page does not contradict itself, and
  that an ID is not older than its own block. A perfectly well-formed NCT that
  belongs to a different trial passes. Confirming an ID points at the study you
  analysed requires opening the registry record, and no offline tool substitutes
  for that.
- **`MEL-18` deliberately does not flag one trial name against several IDs.**
  One publication routinely reports two registered trials — in this corpus
  "Siegal 2015" covers ANNEXA-A and ANNEXA-R. Checking it would report correct
  pages as broken.
- **Quiet on a corpus is not the same as sensitive.** These two detectors were
  run across 431 real dashboards and fired on none of them, after three rounds
  of false positives were traced and removed. That measures *specificity* on
  already-repaired files. Their ability to catch a real defect is evidenced by
  the known-bad fixtures in the test suite, not by that scan.
- **C10, C11, H7, H8 and M5 have no detector in this kit.** They were found by
  hand or by a one-off sweep in the corpus they came from. They are in this
  document because a class you can name and cannot yet catch is worth more to a
  reader than a silence — but nothing in `meta-self-audit.py` looks for them, and
  a `CLEAN` says nothing about any of the five.
- **These detectors read one file, so they cannot see C10 at all.** An aggregate
  surface serving a value its review has withdrawn is a defect in the *relation
  between two artefacts*. Every single-file check reads the summary, finds it
  internally consistent, and is right about that.
- **An empty result and a check that never ran are indistinguishable in the
  output unless you make them distinguishable.** This is the failure mode that
  produced most of the 2026-08-19 findings, including one where our own check
  contradicted a true finding from an outside seat because a key was spelled
  `pooled_or` and the field is `pooled_OR`. The remedies —
  print the denominator, break out `NOT_ASSESSABLE` by reason, print the keys you
  looked at, test in both directions — are in
  [`DETECTOR-VERIFICATION.md`](DETECTOR-VERIFICATION.md), with the measurements.
- **A file named a gate that cannot fail is a trap, not necessarily a defect.**
  Four such files in the source corpus turned out to be correctly-built *advisory*
  tools wearing the wrong name; all four were renamed rather than made to block.
  `scripts/gate-can-fail.py --selftest` ships that check, and its own limit is
  named on the tin: reachability is judged syntactically, so `if False:
  sys.exit(1)` passes it.
- **False positives happen, and several are documented above.** Every one of
  them was found by running the detectors over real files, never by a unit test
  — a suite written by the same person who wrote the detector shares its blind
  spots. When one fires that you believe is wrong, the right response is to
  write down why; that reasoning is what the next version is made of.

---

# Standards these map to

| Class | Standard |
|---|---|
| C1, C2 | **Cochrane Handbook ch.6** — choosing the effect measure for the data type |
| C3 | Cochrane Handbook ch.23 — multi-arm and multi-report studies (unit-of-analysis) |
| C7, C8 | **GRADE** indirectness; the **transitivity** assumption for indirect comparisons |
| C9 | **PRISMA 2020** item 20b — results of individual studies must be presented so each can be identified |
| H6 | **PRISMA 2020** item 13a / **AMSTAR-2** item 8 — studies described, and identified, in adequate detail |
| H1 | **Cochrane Handbook §10.4.3.1** — do not test funnel-plot asymmetry below k=10 |
| H2 | **PRISMA 2020** item 16 / flow diagram |
| H4 | PRISMA 2020 item 13; **GRADE** — harms are part of certainty, not an appendix |
| H5, M4 | **AMSTAR-2** item 4 — search currency and comprehensiveness |
| M2 | **PROSPERO** / ICMJE prospective-registration expectations |
| M3 | PRISMA 2020 items 5–6 — eligibility criteria and their justification |
| H8 | Cochrane Handbook ch.23 — unit of analysis, applied across reviews rather than within one |
| whole layer | **RAISE (2025)** — see [`RAISE-alignment.md`](RAISE-alignment.md) for how the ecosystem maps to the responsible-AI-in-evidence-synthesis principle areas, and where it does not |

**C10, C11, H7 and M5 are deliberately absent from that table.** They are defects
in delivery surfaces, in attribution between artefacts, in search-completeness
proofs and in a metadata field — and the reporting standards do not address any
of them. Claiming a mapping we cannot support would be [C6](#c6--the-badge-is-green-because-someone-wrote-it-green)
committed in a table about standards. H7 is adjacent to AMSTAR-2 item 4 on search
comprehensiveness, but item 4 is about *where* you searched, not about whether
your pagination returned what it said it did.

The mapping above is a self-assessment scaffold. Check the exact wording of any
standard before you cite it in a submission — including this table.

---

# Method notes

Three things we learned building this that generalise beyond it. They are method
notes, not results — offered because they changed how we work, not because we
have measured them.

**An error library is an instrument, not a checklist.** This document started as
a list of things to avoid and turned into something that finds things. Once a
class is written down precisely enough to have a worked example, it usually
becomes precise enough to automate — and once automated, it runs over every file
instead of the ones you remembered to check. Nine of the classes here resisted
that and are honestly filed under [what is not automated](#what-is-not-automated).
The direction of travel matters more than the current count: every class you
write down properly is a candidate detector, and the library gets sharper as you
use it rather than staler.

**Audit yourself before you trust yourself.** The registry these classes came
from records our *own* errors by the same standard it applies to anyone else —
37 content-changing errors, about two-thirds of which ran in the direction that
flattered us. That ratio is the whole argument for this document. An error
distribution centred on zero is noise; one skewed toward the author's interest
is a bias, and it is the one you are least equipped to see in your own work.
Apply the detectors to your own dashboard before you apply the reasoning to
anyone else's.

**Tests written by the detector's author share its blind spots.** Every false
positive in these detectors was found by running them over real files, and none
by the unit tests — the proximity rule that fired on 38 of 40 dashboards, the
sample size read as a year, the trial name split across two encodings. The unit
tests were all passing throughout. Write the tests, keep them in both
directions, and then go run the thing on real data anyway, because the failure
you cannot imagine is exactly the one you did not write a test for.

---

## Adding a class

Found one that is not here? The format is the five parts at the top of this
document, and the bar is a **real example with real numbers**. A class nobody
has actually hit is a hypothesis, not a lesson. If it is deterministic, add a
detector to `scripts/meta-self-audit.py` with a test in **both** directions — a
known-bad that fires and a known-good that does not. A detector with only a
positive test passes CI while matching everything.

And before you trust the detector you just wrote, read
[`DETECTOR-VERIFICATION.md`](DETECTOR-VERIFICATION.md). The most common way a new
check fails is not by missing a defect. It is by **reporting clean because it
never looked** — which is indistinguishable, in the output, from working.

MIT-licensed, like the rest of the kit.
