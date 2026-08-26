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

## A registry title is not an outcome definition

The cheapest way to dispose of a search result is to read its title. It is also the
way to record an exclusion you cannot support.

**A worked case from 2026-08-26.** A prospectively registered search returned five
phase-3 trials of the right drug against the right comparator that the review did
not hold. Each was given a provisional exclusion axis **read from the registry
title returned by the search** — and the record said so, in those words, calling
them *five candidates with provisional axes, not five exclusions.*

Resolved afterwards against each trial's **registered primary outcome measure**,
all five were excluded — and **one axis changed on inspection, the one that
mattered**:

| Trial | Axis from the title | Axis from the registered outcome |
|---|---|---|
| EMPULSE | measure — a win ratio is not a hazard ratio | measure — win ratio over a hierarchical composite |
| EMPERIAL-Reduced / -Preserved | outcome — "exercise ability and symptoms" | outcome — 6-minute walk distance |
| EMPA-VISION | outcome — a mechanistic imaging study | outcome — PCr/ATP ratio by cardiac MRS |
| **EMPACT-MI** | **population** — acute myocardial infarction | **population AND outcome** — its composite is HF hospitalisation or **all-cause** mortality, where the review's is **cardiovascular** death or HF hospitalisation |

The title showed one difference. The outcome module showed a second the title could
not reveal. **Either alone excludes it — but a record citing only the population
axis would have been supportable by less evidence than it appeared to carry**, and
would have been quietly wrong about *why*.

**And one trial had to be recorded as assessed rather than dropped.** EMPULSE does
report the review's outcome concept — first occurrence of CV death or heart-failure
event — but as a **secondary** endpoint and as an **incidence rate per 100
patient-years**, not as a hazard ratio. That is an exclusion on the measure, and it
has to be written down that way so a reader sees the trial was assessed rather than
overlooked. **A silent exclusion and a considered one look identical in a flow
diagram.**

**The rules.**

- **Never let a title carry an exclusion into a published record.** Resolve every
  candidate against the registered outcome measure, the registered population and
  the registered comparator, and name which field decided it.
- **Mark provisional axes as provisional, in the record, before you resolve them.**
  The value of doing so is that the one axis that changed is visible as a change
  rather than absorbed.
- **Say what the exclusion was decided *on*.** "Excluded: population" is not
  auditable. "Excluded: registered primary outcome is a win ratio over a
  hierarchical composite" is.

**What it buys.** After resolution the review's two-trial included set is not a
convenience sample: it is a set that has been searched for and, on these sources,
cannot be improved on. That is a different and defensible claim — and it is only
available because the exclusions were resolved at the source rather than at the
title.

*One topic, five candidates, one search, verified against the registered outcome
modules on 2026-08-26. The mechanism is general; the count is five.*

---

## Anchoring a protocol so the ordering is not your own word

Everything else in this document is about where a *number* comes from. This section is about
where a *time* comes from, because the claim "we wrote the protocol before we ran the search"
is sourced exactly as loosely as any number, and usually worse.

**The problem, stated at full strength.** A protocol committed to a public repository before
its search is a real registration mechanism — the commit hash binds the text, and anyone can
read it. But **the timestamp is author-supplied and forgeable.** Git author and committer
dates are set by whoever makes the commit; an unsigned commit attests nothing further; and a
host stores and displays what it is given. Demonstrated rather than argued in
[`META-ERROR-LIBRARY.md` M2](META-ERROR-LIBRARY.md#m2--a-commit-timestamp-claimed-as-prospective-registration),
where a commit made in 2026 reports both dates as `2019-01-01T00:00:00Z`.

Push history does not rescue it either: a host's public event feed is capped by **count**, not
by time. Measured twice on one repository on 2026-08-26, hours apart: **300 events — the API
cap — spanning 6.50 days, then 6.47 days.** The window is a function of your own push rate, so
it shrinks exactly when you are working hardest.

**The fix is one third-party time at each end.** A public transparency log
([Rekor](https://rekor.sigstore.dev), part of Sigstore) will record a signature over a digest
and stamp it with an `integratedTime` set by the log, not by you.

### The worked example, verified here from the public log

One topic, `finerenone-cv`, anchored on 2026-08-26. Every line below was re-fetched from
Rekor and re-hashed from the committed bytes while writing this section — not copied from the
record that asserts it.

```
protocol commit       3872817c06c92bad152cc4d076ea23b2f611012c
protocol path         ssot/finerenone-cv/PROTOCOL.md         (17,534 bytes)
sha256 recomputed     7220ad588145ee338f936a6799fea6766d4b467f04994dd2198f2ea759fb2633
Rekor logIndex        2604694652   integratedTime 2026-08-26T17:59:41Z
                      logged sha256 MATCHES the recomputed sha256

  first query ATTEMPT      2026-08-26T18:00:30.227Z
  first query executed     2026-08-26T18:00:48.163Z
  second query executed    2026-08-26T18:01:14.013Z

search record commit  fe926bf4f25e4c72a6535bdabc0eab75d4373119
search record path    ssot/finerenone-cv/SEARCH-RECORD.json
sha256 recomputed     ec452d245ebf2a79602d14de321a77be1c6fefd2d58af0ef0f41579520ed9d9e
Rekor logIndex        2604754261   integratedTime 2026-08-26T18:04:45Z
                      logged sha256 MATCHES the recomputed sha256
```

**The bracket: `17:59:41Z < every query time < 18:04:45Z`, both bounds set by the log.**

The ordering test uses the earliest time the record *admits to* — a query **attempt** that
returned nothing at 18:00:30, not the first success at 18:00:48. Using the success would move
the first-query time 18 seconds later and flatter the claim. Always publish the attempt.

### Say exactly what it establishes, and exactly what it does not

This is the part that makes it usable by a referee, and the part most likely to be dropped.

**It establishes.** The protocol text existed **no later than** 17:59:41Z, and the search
record existed no later than 18:04:45Z — both times set by a third party, on an append-only
publicly auditable log. And that whoever holds the signing key signed exactly those bytes.

**It does not establish.** Not when the commit was made. Not that no earlier or parallel
version of the protocol existed elsewhere. Not that the data had not already been seen. Not
anything about the independence of the people who wrote it.

> **The log time is independent of us. The key custody is not.** A stranger can verify the
> text existed by the log time and that we signed it. A stranger cannot verify we did not
> hold an earlier version of the same text. That is weaker than a notary and considerably
> stronger than a git timestamp, and the difference belongs in the same sentence as the claim.

### The recipe, which needs nothing from us

1. **Fetch the log entry:** `curl -s https://rekor.sigstore.dev/api/v1/log/entries/<uuid>`.
   Read `integratedTime` (Unix seconds — the third-party time) and base64-decode `body` for
   `spec.data.hash.value`.
2. **Hash the file at the commit named in the record** — not at `main`, because `main` moves:
   `git show <commit>:<path> | sha256sum`.
3. **Compare.** Identical, or the claim fails.
4. **Check the ordering.** Every query time must fall after the protocol's `integratedTime`
   and before the search record's.

**A recipe nobody has run is a plausible recipe.** Run it against your own anchor before you
publish it, and say in the document that you did.

**Two caveats worth carrying.** Anchoring proves nothing about search *quality* — the same
anchored search is the one whose registry query
[missed a pivotal trial](REGISTRY-EXTRACTION-TRAPS.md#8-two-trials-of-the-same-drug-can-index-their-disease-differently)
and whose PubMed string was
[edited by the service](SEARCH-COMPLETENESS.md#a-second-instance-and-it-settles-the-class-the-service-edits-your-query-and-hands-the-edit-back-as-the-record).
Both are recorded in the anchored record rather than corrected out of it, which is the only
thing that makes anchoring worth doing: **it fixes what a bad result cannot later be quietly
replaced with.** And it is one topic, out of
[155](SEARCH-COMPLETENESS.md#7-what-a-corpus-actually-has--two-denominators-kept-apart-on-purpose).

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
- [`SEARCH-COMPLETENESS.md`](SEARCH-COMPLETENESS.md) — proving a search finished, and
  what a corpus actually holds once you count.
- [`REGISTRY-EXTRACTION-TRAPS.md`](REGISTRY-EXTRACTION-TRAPS.md) — the registry fields
  that answer a different question from the one you asked.

MIT-licensed, like the rest of the kit.
