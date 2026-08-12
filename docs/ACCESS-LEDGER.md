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

## 4. What to do with this

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

## 5. Caveats

- **n = 8 targets, 6 breaches, two clinical areas.** Nothing here is a field rate.
- The breaches were chosen because they looked worth attempting, which biases the
  "changed a cell" rate upward.
- The paywall finding rests on **one** case.
- "No breadth failures confirmed" (see [META-ERROR-LIBRARY.md](META-ERROR-LIBRARY.md))
  means not yet caught, not absent.

## Related

- [`REGISTRY-EXTRACTION-TRAPS.md`](REGISTRY-EXTRACTION-TRAPS.md) — recovering counts, and the traps
- [`SOURCING-METHOD.md`](SOURCING-METHOD.md) — the open-data route to a replacement number
