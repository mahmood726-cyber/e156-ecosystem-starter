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
| whole layer | **RAISE (2025)** — see [`RAISE-alignment.md`](RAISE-alignment.md) for how the ecosystem maps to the responsible-AI-in-evidence-synthesis principle areas, and where it does not |

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

MIT-licensed, like the rest of the kit.
