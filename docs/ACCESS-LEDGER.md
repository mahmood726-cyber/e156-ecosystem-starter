# What actually blocks access — a measured ledger

**Who this is for.** Anyone doing evidence synthesis without institutional
subscriptions. That is much of the point of this toolkit, and the usual advice —
"you will be limited by paywalls" — turns out to describe the smaller problem.

The method here is simple and worth copying: **every time retrieval failed, we logged
what kind of barrier it was, how many routes were tried, and whether getting through
changed anything.** Nobody keeps that ledger, so nobody knows the rates.

---

## 1. The headline

Of eight retrieval targets in one audit:

| Barrier type | n | Got through |
|---|---|---|
| **Tooling / rendering** (bot-block, JavaScript gating, image retrieval, a tool that stripped reference markers) | 5 | **5/5** — 3 fully, 2 partially |
| **No barrier at all** (open, first try) | 2 | 2/2 |
| **Genuine paywall** | **1** | **0/1** |

So: **of the six targets that presented a barrier, five were our own tooling and one
was a paywall.** Every tooling barrier eventually yielded. The single real paywall did
not, after four routes.

The uncomfortable implication for the finding itself: **the paywall claim has a
denominator of one.** "A workaround is usually available" is well supported for
tooling barriers and essentially untested for paywalls, because only one was
encountered. We are reporting it that way rather than rounding it up.

> **Correction to our own earlier write-up.** The first version of this audit's summary
> said "7 of 8 barriers were tooling". Its own classification table says 5 tooling, 2
> no-barrier, 1 paywall — the summary had folded the two open-access targets into the
> tooling count. The table is right and the sentence was wrong. Corrected here, and
> left visible rather than quietly fixed, because the whole method depends on the
> ledger being trustworthy.

## 2. Was it worth getting through?

The measurement nobody makes: when you do breach a barrier, does it change an
extracted number?

| Metric | Value |
|---|---|
| Breaches achieved | 6 |
| **Changed at least one extracted cell** | **6/6** |
| Yielded the specific number being chased | 5/6 |
| Wasted trips | **0/6** |

So the strong form of "the walled content usually isn't useful" did not survive. Six
for six changed something.

**But the sharp version did, and it is more useful.** In one of two supplement chases,
the number being chased **was not in the supplement at all** — it was in the open main
text, and had been the whole time. What that supplement did contain was the single most
informative thing recovered in the entire session, and nobody was looking for it.

> **The specific number you chase behind a wall is often in the open layer you already
> had. The walled layer is rarely worthless — but its value is usually in cells you
> were not looking for.**

Which reframes the question from *can we get in* to *were we chasing the right object*.

## 3. The layer that actually cannot be recovered

These are different problems and conflating them makes the whole discussion
unfalsifiable:

**Published but paywalled.** The number exists in print. A workaround is plausible in
principle — a regulator's review, an assessment report, an HTA reprint, a registry
posting, a preprint, an author manuscript, a conference slide, a mirrored or
non-English copy. Instances found: **1**, still unresolved after four routes.

**Never published.** The number was never reported by anyone, so there is nothing to
route around. **No amount of access solves this.**

The clean example: one trial's supplementary appendix prints thirty-five subgroup
effect estimates and **no interaction p-values anywhere** — the quantity you would need
to say whether the subgroups actually differ. The main text asserts consistency across
subgroups without testing it. That number is not paywalled and not hidden. It was
either never computed, or computed and not reported.

**In this audit the unpublished layer produced more irrecoverable cells than the
paywalled layer did.** Open access does not touch it. It is a reporting problem, and
the remedy is on the authors' side, not the reader's.

## 4. What not reaching the full text costs, priced in judgements

The ledger above prices access in *cells* — did breaching a barrier change an extracted
number. On **2026-08-26** the same corpus produced a second, sharper price: what not reaching
a paper costs in **risk-of-bias judgements**, and who ends up carrying that cost.

Every stored domain judgement recorded as "no information" was re-derived through the published
RoB 2 algorithm, alongside the original and never in place of it. **191 domains examined:**

| | n |
|---|---:|
| re-derived | **131** |
| **underivable — reported, with nothing proposed** | **60** |
| results touched | 71 |
| topics touched | 22 |

**All 60 underivable domains are the same domain, blocked on the same question.** RoB 2's
Table 10 has no row for signalling question 3.2 = *No information*: every row requires 3.2 to be
answered. The published algorithm therefore defines no output, so none was written down. An
underivable domain is a result, not a gap in the table.

### Reach and conduct are different findings and must not print the same way

This is the part that generalises past risk of bias.

A domain whose signalling responses are **all "no information"** says what *we could reach*. A
domain with at least one substantive response says something about *the trial*. Both are valid
outputs of the same tool, and printing the first as though it were the second **defames a trial
for our missing information**.

| | n |
|---|---:|
| re-derivations from an all-no-information domain — **reach** | **128** |
| re-derivations using at least one substantive response — **conduct** | **3** |
| results with a derivable overall | 24 of 87 |
| …of those, overall **High** | 9 |
| …of those, driven **entirely** by an all-no-information domain | **9 of 9** |

**Every result the algorithm rates High is rated High because of a domain on which we reached
no information at all.** Not one is rated High by anything known about how the trial was run.

So a reach-derived domain must never appear as a bare verdict. The wording used here states the
algorithm faithfully and leaves the deficit where it belongs:

> **Domain 2 (deviations from intended intervention): no information reached.** We did not
> retrieve this trial's analysis-population statement, so RoB 2 signalling questions 2.6 and 2.7
> are both "No information", and the published algorithm proposes **High** on that basis. *This
> records what this review could reach, not a finding about how the trial was conducted.*

And the result-level line follows the same rule — *"rated High by the RoB 2 algorithm because no
information was reached on domain 2"*, never *"high risk of bias"* alone.

### "We could not reach it" is only honest while you also say what reaching would take

| domain | what we cannot answer | what would answer it |
|---|---|---|
| D1 | 1.1 sequence generation, 1.2 allocation concealment | the protocol, or the randomisation paragraph of the primary publication. A registry `allocation: RANDOMIZED` field answers neither — RoB 2 guidance says so explicitly |
| D2 | 2.6 appropriate analysis, 2.7 impact of switching | the analysis-population statement (ITT / mITT) in the Methods, the CONSORT flow, or the SAP. For approved drugs an FDA review or an EPAR carries both |
| **D3** | **3.2 evidence the result was not biased by missing data** | **the CONSORT flow diagram and the analysed N per arm.** This one blocks all 60 underivable domains and 63 overall ratings — and 3.1 alone would unblock most of them |
| D5 | 5.1 a pre-specified plan | the SAP or protocol. The registered outcome list, which we already hold, answers 5.2 and 5.3 but not 5.1 |

**Sixty domains and sixty-three overall ratings are blocked on one figure from one paper.** That
is the access argument stated in the only currency that matters to a reader: not "we could not
open it", but *this is the judgement we cannot make, and this is the single object that would
let us make it.*

### One control on the whole exercise

**Every re-derivation moved away from Low. 67 to High, 64 to Some concerns, and 0 toward Low —
the flattering direction.** That asymmetry is not presented as a virtue. It is the check: had
the moves run one-sidedly the *other* way, the finding would have been about the algorithm as we
implemented it rather than about the evidence. A re-derivation that only ever improves your own
position is a bug report about your implementation.

**Nothing was written in place.** Every re-derivation sits beside the original; the stored
judgement is untouched; no reader sees a re-derived value. The tool's own guidance is that its
algorithms *provide proposed judgements* which users should verify — so this is an input to a
person, not an output to a reader, and it is stored as one.

*Denominator: 191 domains across 71 results and 22 topics in one corpus, re-derived on
2026-08-26 against RoB 2 (22 August 2019). An earlier fetch of the tool returned the 20 October
2016 draft, whose tables differ; it was discarded, and the version is named in the module so a
future edit has to say which one it transcribes. The transcription is controlled by one test
case per published table row — 50 of 50 — plus four negative controls, because nothing
downstream can catch a mis-transcribed row: it would yield a plausible judgement with a
plausible citation.*

## 5. What to do with this

1. **Assume a failure is yours until shown otherwise.** Five of six barriers here were
   rendering, bot-blocks, or a tool quietly dropping content. Try a browser before
   concluding anything about access.
2. **Name the obstacle in your data.** "403" and "not reported" are different facts.
   See [REGISTRY-EXTRACTION-TRAPS.md §5](REGISTRY-EXTRACTION-TRAPS.md).
3. **Check the open layer before chasing the walled one.** In half the supplement
   chases here the target was already in the main text.
4. **When something genuinely was never published, say so in the write-up.** "Not
   reported by the trialists" is a finding about the evidence base. Burying it as a
   blank cell hides it.
5. **Keep the ledger.** Barrier type, routes tried, whether it changed a cell. It costs
   a line per retrieval and it is the only way anyone will ever know the real rates.
6. **Price the shortfall in judgements, not only in cells.** "We could not reach it"
   is a complaint. "Sixty domain judgements are blocked on one CONSORT flow diagram" is
   a request someone can act on — see §4.

## 6. Caveats

- **n = 8 targets, 6 breaches, two clinical areas.** Nothing here is a field rate.
- **§4 is a different audit with a different denominator** — 191 domains across 71
  results and 22 topics on 2026-08-26, in a corpus deliberately built from registry
  records without full-text retrieval. That construction is *why* the reach figures are
  so high, and they must not be read as what a full-text-reading review would face.
- The breaches were chosen because they looked worth attempting, which biases the
  "changed a cell" rate upward.
- The paywall finding rests on **one** case.
- "No breadth failures confirmed" (see [META-ERROR-LIBRARY.md](META-ERROR-LIBRARY.md))
  means not yet caught, not absent.

## Related

- [`REGISTRY-EXTRACTION-TRAPS.md`](REGISTRY-EXTRACTION-TRAPS.md) — recovering counts, and the traps
- [`SOURCING-METHOD.md`](SOURCING-METHOD.md) — the open-data route to a replacement number
- [`META-ERROR-LIBRARY.md`](META-ERROR-LIBRARY.md) — the defect classes, including the ones
  this programme has committed
- [`DETECTOR-VERIFICATION.md`](DETECTOR-VERIFICATION.md) — proving a detector can fail
