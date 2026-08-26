# Proving a search finished — a command, and what recall measured

A paginated search that stops with an empty cursor looks finished. On 2026-08-19 one of ours
was not, and the record said it was.

The defect class is written up as
[H7](META-ERROR-LIBRARY.md#h7--a-paginated-search-treated-as-complete-because-the-cursor-came-back-empty)
in the error library. **This page is the runnable half**: the detector, the two real records it
ships with, and the recall figures measured beside it — none of which the class writeup carries.

Everything below is a count with a denominator, taken from our own working records. Nothing here
is a field rate.

---

## 1. The headline is a confirmation

**We re-checked every search record we hold — 47 rows — before building anything further on
them. 31 reconcile, 8 declare their own shortfall, 6 were never executed, 2 cannot be assessed,
and 0 rest on an empty cursor alone. No delivered page rests on an unproven search.** The full
table is in [H7](META-ERROR-LIBRARY.md#h7--a-paginated-search-treated-as-complete-because-the-cursor-came-back-empty).

The one record that failed is the reason the audit was run, and it is one record. The other 46
are the reason it is worth reporting.

> **`100 + 100 + 3 = 203` records returned, cursor null, against a reported total of `430`.**
> **227 records the pagination never returned, while the cursor reported the search complete.**

The proof is not the cursor. It is the arithmetic:

> **The sum across pages, reconciled against the total the database itself reported.**
> The empty cursor is corroboration. It is never the proof.

---

## 2. Run it on your own search

```bash
python scripts/search-record-reconcile.py --selftest                   # 10/10 assertions, exit 0
python scripts/search-record-reconcile.py my_search_record.json
python scripts/search-record-reconcile.py evidence/                    # everything beneath it
```

Standard library only. Offline. No API key, no model call. Exit 1 on any refusal.

It checks four quantities against each other:

    len(list)  ==  len(set(list))  ==  sum of per-page `returned`  ==  the reported total

Each comparison catches a different failure:

| Comparison | What it catches |
|---|---|
| list vs sum across pages | a page transcribed short, or transcribed twice |
| sum vs reported total | **an unexhausted cursor — the search is not finished** |
| list vs distinct | **the same identifier written twice, which inflates a denominator while every other number still reconciles** |

The third is the one a person reading the file would not do. A duplicated identifier keeps the
sum right and the total right, and is invisible to every check but a set comparison.

**An absent `next_page_token` field is not a null one.** A record that never wrote down what the
cursor said has made no claim about completeness, and the check will not convict it of a proof
it never offered. Silence is not a claim, and that limb is asserted in the selftest.

### The can-fire proof, and the measurement on real records

A detector never shown to fire on a known-bad input is not published here as working. This one
is shown twice — once on a fixture, once on the real thing.

`--selftest` asserts **10 of 10**, including that the failing case above is refused **and names
the shortfall of 227**, and that the honest case beside it — `100 + 37 = 137` against a reported
137, cursor also null — **does not fire**. A check that cannot stay quiet is not a check either.

Pointed at our working evidence directory, it finds **7 files carrying a search record**:

| Verdict | Files | Which |
|---|---:|---|
| RECONCILES | 2 | a registry search at 137 = 137, and its PubMed limb at 523 = 523 |
| **refused** | **1** | the record above, naming the shortfall of 227 |
| NOT ASSESSABLE | 4 | records that state a count and name none of the identifiers behind it |

*Denominator: 7 files, which is what this command's own discovery rule reaches — a file carrying
a query, pages, or an identifier list. The 47 in §1 come from a broader instrument that also
reads records nested inside other files. **Two denominators, deliberately not merged**: a count
is only as good as the rule that selected it.*

**A count with no list behind it cannot be checked by anything.** Four of those seven were in
that state — they say how many the search returned and name none of them. Re-running the query
later would silently substitute a different set under the same count, and nothing would notice.
Write the identifiers down.

NOT_ASSESSABLE is counted separately and is never reported as a pass.

### The two records it ships with

Both real, one of each kind, in [`templates/search-record/`](../templates/search-record/README.md):

| File | Verdict |
|---|---|
| `example_reconciles.json` — 137 identifiers named across two pages, reported total 137 | `RECONCILES`, exit 0 |
| `example_cursor_lied.json` — 203 across three pages, cursor null, reported total 430 | refused, exit 1 |

The second is one of **our own** search records, shipped as the known-bad input.

---

## 3. Reconciling is not recall — and recall is the number to publish

The check above compares a record against itself. It says nothing about whether the search found
the trials that exist. That needs a known answer to measure against: the set of trials a review
already includes.

Three topics, searched 2026-08-19, scored against their own reviews' included sets:

| Topic | Search reconciles | Recall against the review's included set |
|---|---|---|
| colchicine, cardiovascular | 137 = 137 | **3 of 3** on ClinicalTrials.gov |
| dabigatran, venous thromboembolism | 38 = 38 | **2 of 4** |
| antiplatelets, acute coronary syndrome | **no** — 203 of 430 | **3 of 4** |

*Denominator: three topics, chosen because they were the ones being built. Included sets of 3, 4
and 4 trials. These are small numbers, reported as counts and not as rates.*

**Every miss turned out to be worth more than the score, and they are not the same kind of
thing.**

- **A miss that is not an error — the search was right and the review is the question.** One of
  the dabigatran review's four trials, `NCT01505881`, is a follow-on from a **mechanical heart
  valve** study. A search filtered on venous thromboembolism *correctly* did not return it. The
  finding is not about the search.
- **A miss that is a real limit, and not uniform.** `NCT00168805` was missed because the query
  term is narrower than the registry's coded field, which reads `Thromboembolism`. Two other
  trials carry that same code and *were* surfaced. The behaviour is inconsistent, which makes it
  a poor thing to reason about and a good thing to measure.
- **A miss caused by how a trial is coded, not by how it was searched.** `NCT02270242` has coded
  conditions `Cardiovascular Disease` and `Interventional Cardiology` — neither of them anything
  a person would query for an acute-coronary-syndrome review.
- **A miss no recall figure can fix.** Two trials in the colchicine review are registered on
  **ANZCTR**, not ClinicalTrials.gov. That search cannot surface them at any recall. The 3 of 3
  is scored against what the database could return, and the honest statement is that a second
  limb is owed on that topic.

The last is the general point. **A recall figure is against a database, not against the
literature.** Ours are against ClinicalTrials.gov, with one PubMed limb, and should not be read
as anything wider.

**None of these misses has been repaired.** They are recorded, and the topics carrying them are
not built on.

---

## 4. A search that reconciles is still not a count of studies

The colchicine record reconciles: 137 listed, 137 distinct, 137 across two pages, 137 reported.
The reconciliation is real, and it is about **registration identifiers**.

Two of those 137 registrations — `NCT04906720` and `NCT06731595` — are one study. Identical
title, sponsor, enrolment of 248, start date, primary completion date and intervention. So **137
distinct registrations is at most 136 distinct studies**, and any screen that dispositions by
identifier counts that study twice, with every downstream count inheriting it.

This is [C3](META-ERROR-LIBRARY.md#c3--the-same-trial-counted-twice) one level further up, at
the registry rather than in the included-studies table — and
[H8](META-ERROR-LIBRARY.md#h8--summing-k-across-reviews-counts-the-same-trial-many-times) is the
same shape one level up again, across reviews. **The reconciliation check cannot see any of
them and does not claim to.** `scripts/trial-identity-screen.py` is the screen for the table
form.

Both registrations were kept and screened together, receiving the same disposition, and the
reading that includes them includes one. **Recorded, not silently deduplicated** — a
deduplication with no record is indistinguishable from a trial that was never found.

Also worth separating from the recall figures above: one of that review's own three included
trials, and the largest of the three, was returned **on page 2 only**. A screen that stopped at
page 1 would have missed it while every number in the record still looked right.

---

## 5. What the checking cost us to get right

The 47-row audit in §1 was written to bound the damage from §2. **Its own first run produced
five false NOT_ASSESSABLE verdicts** — every one of them the audit failing to look rather than
a record failing to say. One record spells its counts differently; two nest theirs a level down.

Five records reported as uncheckable were checkable the whole time. A verdict of "cannot assess"
that is really "did not look" reads exactly like an honest limit — which is why the instrument
now **prints the keys it actually saw** beside every NOT_ASSESSABLE.

That is the general remedy, and it is the same one that has worked every other time this shape
has appeared here: **make the instrument report what it looked at, not only what it found.** A
count printed beside its denominator is refutable. A count alone is not. The seven forms of a
check that finds nothing because it never looked are catalogued in
[`DETECTOR-VERIFICATION.md`](DETECTOR-VERIFICATION.md).

---

## 6. Searching by identifier — two traps, and a claim of ours that did not survive

Looking up a list of registration identifiers in a bibliographic database is the most
mechanical search anyone in evidence synthesis runs. It has two failure modes that a normal
client cannot see, and we got one of them wrong before checking it.

Measured against PubMed's E-utilities on **2026-08-26**, using the `[si]` (secondary source
identifier) field, on **40 distinct NCT identifiers taken in file order from this corpus**.

### The claim we withdrew

We were about to publish that **PubMed silently drops an unindexed identifier from a boolean
query rather than erroring**. Executed, it is wrong, and the correct version is more useful.

**29 of the 40** identifiers return zero records. Queried as one `OR` chain, PubMed returns
**HTTP 200** and a count of **15** — and **names all 29** in a field of the response:

```json
"errorlist": { "phrasesnotfound": ["NCT06833138", "NCT03062241", ... ], "fieldsnotfound": [] }
```

Every one of the 29 zero-yield identifiers appears there, exactly. **The API reports the
omission in full.** What it does not do is put it anywhere a client is looking: the status is
success, `esearchresult.count` is a plain integer, and reading `count` is what essentially
every script does.

> **The drop is not silent. It is loud in a field nobody reads.** That distinction matters,
> because the remedy is different: there is nothing to work around, only a field to read. Parse
> `errorlist.phrasesnotfound` on every identifier query and reconcile it against the list you
> sent. If the two do not account for each other, stop.

It is also the same shape as everything else on this page. A count came back, the count was
correct, and it was about a smaller set than the one asked for — and only the *scope*, printed
beside the verdict, tells you which.

**What this does and does not measure.** One database, one field, 40 identifiers from one
corpus on one day. It says nothing about how many of those 29 trials have a publication:
absence from `[si]` means the record is not indexed against that identifier, not that no paper
exists. Confusing the two is
[H6](META-ERROR-LIBRARY.md#h6--a-registry-identifier-that-cannot-be-right) territory, and the
honest disposition for all 29 is *not found by this route*, never *no publication*.

### Summing per-identifier hit counts double-counts, and by how much depends on the trials

Run the same 40 identifiers individually and add up the counts, and you get **15**. The union
is also **15**, and the boolean `OR` returns a set exactly equal to the union. **0% inflation.**

Now run four large, heavily-published cardiovascular trials the same way:

| | |
|---:|---|
| sum of the four per-identifier counts | **67** |
| distinct records in the union | **46** |
| boolean `OR` count | **46** — set-identical to the union |
| **records indexed against more than one of the four** | **21 of 46** |
| inflation from summing | **45.7%** |

**Same procedure, same database, same day: 0% on one set and 45.7% on the other.** The
difference is entirely a property of the trials — pooled reports, programme-wide analyses and
secondary papers are indexed against every trial they cover, so a set of trials that share
publications inflates and a set that does not, does not.

Which means **you cannot carry an inflation factor between searches**, and a yield reported as a
sum of per-identifier counts is not a number at all. **Take the union, and report the union.**

This is [C3](META-ERROR-LIBRARY.md#c3--the-same-trial-counted-twice) and
[H8](META-ERROR-LIBRARY.md#h8--summing-k-across-reviews-counts-the-same-trial-many-times) one
more level up: not one trial counted twice in a pool, and not one trial counted twice across
reviews, but **one paper counted once per trial it reports**. Every level of this stack has the
same fix — deduplicate on identity, never on the string you searched with.

---

## Blind spots

- **It compares a record against itself.** A record whose stated numbers are both untrue passes.
- **A record that names no identifiers cannot fail this check**, and must never be read as
  having passed it. Four of our seven were in that state.
- **Reconciling identifiers is not counting studies** — §4.
- **Recall is against one database**, and against a known included set that is itself somebody's
  judgement. A trial nobody has ever found scores against nothing.
- **Why the failing search stopped early is not diagnosed** — a server-side cap, a
  differently-scoped total, something else. The discrepancy is recorded rather than explained,
  because writing down a guessed cause is worse than naming the gap.
- **`n = 47` records, `n = 3` recall topics, one programme, mostly cardiovascular, and enriched
  by construction** — this is a corpus under active repair, so its own instruments were under
  deliberate scrutiny. The mechanism generalises. The numbers do not.
- **The identifier findings in §6 are one database, one field, 40 identifiers, one day.** Another database may behave differently, and the 45.7% inflation figure is a property of those four trials, not a constant.
- **Absence from an identifier index is not absence of a publication.** The 29 zero-yield identifiers are *not found by this route* and nothing more.
- **Nothing here checks whether the query was well aimed.** A perfectly reconciling search of
  the wrong condition is clean by every measure on this page.

## Related

- [`META-ERROR-LIBRARY.md`](META-ERROR-LIBRARY.md) — the defect classes in finished syntheses,
  including the ones this programme has committed
- [`DETECTOR-VERIFICATION.md`](DETECTOR-VERIFICATION.md) — proving a detector can fail, and the
  seven ways a check reports clean because it never looked
- [`SOURCING-METHOD.md`](SOURCING-METHOD.md) — where to source a replacement number once the
  search is trustworthy
- [`REGISTRY-EXTRACTION-TRAPS.md`](REGISTRY-EXTRACTION-TRAPS.md) — recovering counts from the
  records a search returns
- [`ACCESS-LEDGER.md`](ACCESS-LEDGER.md) — what actually blocks access, measured
- [`templates/search-record/`](../templates/search-record/README.md) — the two runnable examples

MIT-licensed, like the rest of the kit.
