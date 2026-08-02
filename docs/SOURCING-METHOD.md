# Sourcing numbers from open data

How to expand and verify the numbers in a review using only freely-available
sources, and how to record where each one came from so a reader can check you.

This is the method half of the [error library](META-ERROR-LIBRARY.md). The
library tells you what goes wrong; this tells you where to get the number that
puts it right. It was written from a run that repaired 626 generated review
dashboards, and the ordering below is **yield order** — the sources that most
often actually had the missing number, first.

Nothing here needs a subscription, an institutional login, or an API key.

---

## The rule underneath everything

> **Correcting what is wrong is only half the job. A review that is right but
> thin is still thin.**

Most of the effort in that corpus run went not into fixing bad numbers but into
finding numbers that were never there — missing harms, missing denominators,
missing time-to-event estimates. An efficacy-only review is not a neutral
starting point. It is a review with its most consequential layer absent.

---

## The hierarchy

Work down this list. Stop when you have the number *and* a source you can cite.

### 1. Supplements of prior published meta-analyses

The richest source, and the one most often skipped. A previous review on your
topic has usually already done the per-arm extraction you need, and put it in a
supplementary table that nobody reads.

You are not taking their conclusion. You are taking their **extraction**, and
you check it against the primary report before you use it.

### 2. Open-access primary reports (PMC / Europe PMC)

The trial's own paper, plus its appendices. Europe PMC is worth searching
separately from PubMed — its full-text coverage and its links out to registry
records differ.

### 3. Regulatory documents — FDA reviews and EMA EPARs

Underused, and often decisive. The FDA **statistical review** in particular
carries per-arm counts, adjudicated endpoint definitions, and the exact
analysis-population definitions that papers compress into a phrase. EMA EPARs
are strong on harms tables and on populations the FDA did not review.

When a paper and a regulator disagree on a denominator, that disagreement is
itself a finding — record both.

### 4. ClinicalTrials.gov posted results

The registry's posted-results tables give per-arm outcomes and adverse events
for many trials whose papers are paywalled. Reading results straight from the
open registry when the paper is behind a paywall is a legitimate route, not a
workaround.

---

## Every datum carries a provenance line

A number without a source is not evidence, whatever it is next to. Record each
one in the form:

```
class<N>: <field> <old> -> <new> [source, what was taken]
expand:   <field> <- <value>     [source, what was taken]
```

Concretely:

```
class12: SOTATERCEPT n_analysed 163 -> 160 [ctgov posted results NCT04576988, ITT table]
expand:  any-AE control 140/160         [ctgov posted results NCT04811092, AE summary]
```

Two things make this work. The source has to say **which** table or section the
number came from, not just name the document. And the line has to be written at
the moment you change the number — reconstructed provenance is a guess wearing a
citation's clothes.

---

## Add beside, never overwrite

When you correct a published value, **keep the original visible** and put the
corrected value next to it with a link to the source.

| Field | As published | Corrected | Source |
|---|---|---|---|
| Analysed n, arm A | 6,200 | 6,632 | FDA label, §14.1 |

Overwriting destroys the only evidence that a correction happened, and it makes
your review impossible to audit — the reader cannot tell a transcription fix
from a silent re-analysis. It also quietly asserts that you are right, which is
a claim your reader should be allowed to check rather than inherit.

If you disagree with a published number and cannot source a better one, say so
and leave the original standing. A documented disagreement is a contribution. A
substituted guess is not.

---

## Fail closed

- **If you cannot establish a number from an open source, leave the existing
  value** and record it as blocked. Never substitute a plausible guess. A gap
  you documented is a good outcome; a number you could not actually see is not.
- **Never change a trial ID, PMID, DOI or date to make a check pass.** If a gate
  only goes green after you edit an identifier, the gate found something.
- **No firewall circumvention.** If a source is paywalled, login-gated or
  blocked, do not try to get around it. Record it as inaccessible for that field
  and move on.

---

## Missing trials: two tiers, and the honest one is usually B

You will find trials that look eligible and are not in the pool. Adding one
changes the pooled estimate, k, the forest plot, and every statistic downstream.

**Tier A — clearly eligible: add it.** The trial plainly meets the stated PICO
with no judgement call required, *and* you have full per-arm data from an open
source. Update k and the estimate, and record a provenance line per number.

**Tier B — borderline: flag it, do not add it.** If eligibility turns on a
judgement call — an arguable population overlap, an ambiguous comparator, a
surrogate-versus-clinical endpoint question, or data you can only partly source
— then do not touch the pool. Write down the trial, a source link, and why it
looks eligible, and leave the decision to a human with the protocol in front of
them.

**If you are hesitating between tiers, it is Tier B.** "Clearly eligible" means
no reasonable reviewer would disagree.

This is not a hypothetical safeguard. Across 626 dashboards the run escalated
two landmark trials to human review and added **neither** — both had a
time-to-event or median primary endpoint with no 2×2 to extract, and forcing
them in produced `NaN`. The pools were left alone and the finding was written
down.

---

## Retire date-based exclusions

A bare publication-date floor — "we included trials published after 2010" — is
almost never a methodological choice. It is a convenience that survived into the
methods section.

Open sources reach older trials perfectly well: registry records, regulatory
reviews and digitised archives do not stop at an arbitrary year. A date filter
drops eligible evidence and biases the result toward recent, better-funded,
more-published trials — the same direction as publication bias, added on top of
it.

Either state the actual methodological reason for the cut-off (a guideline
change, a licensing date, a change in diagnostic criteria — something that
changes what the trials *mean*), or retire the filter and re-run the search.
`MEL-15` in the self-audit looks for a bare year floor with no stated rationale.

The same applies to a `comparator = placebo` filter, which silently converts
"is X effective?" into "is X better than nothing?" and excludes every
active-comparator trial.

---

## Where this connects

- [`META-ERROR-LIBRARY.md`](META-ERROR-LIBRARY.md) — the defect classes these
  sources are used to repair, and the offline detectors that find them.
- `scripts/meta-self-audit.py` — `MEL-15` (exclusion mis-scoping), `MEL-18`
  (identifiers), `MEL-11` (missing harms) are the three that most often send you
  back to this document.
- **AMSTAR-2 item 4** on search comprehensiveness, and **PRISMA 2020 items 5–6**
  on eligibility criteria and their justification, are the standards a reviewer
  will hold this part of your method against.

MIT-licensed, like the rest of the kit.
