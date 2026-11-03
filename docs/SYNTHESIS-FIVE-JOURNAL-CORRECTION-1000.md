# Synthesis v1.3 — 1,000 correction notices from five flagship journals

**Started: 3 November 2026. Development/learning corpus; independent scientific validation NOT performed.**

## Target and actual source progress

Scope is exactly **The Lancet** (main journal), **New England Journal of Medicine**, **Nature** (not Nature Communications/Medicine), **JACC / Journal of the American College of Cardiology** (not JACC Imaging/Asia) and **Circulation** (not Circulation Research/JAHA). Aim for **1,000 distinct complete primary notices**, provisionally 200 per journal across several years. A target is not a result.

| Measure | Actual first-pass total | Interpretation |
|---|---:|---|
| Distinct publisher notice DOI records | 12 | Public sources indexed in pilot |
| Complete primary publisher notice text/PDF examined | **8** | 3 Lancet, 2 Nature, 3 Circulation |
| Publisher-indexed extracts only, not full-credit | **4** | 2 NEJM, 2 JACC; direct page/PDF requests blocked |
| Referenced article entries | 15 | **Not** 15 independently verified scientific errors |
| Notice-described change entries | 28 | **Not** 28 distinct errors or newly detected defects |
| Target remaining after full notices | **992** | Not yet read in full |

The [pilot register](../research/correction_learning/five_journals/20261103/notices-pilot-v1.json) is a source-paraphrased development file with original publisher links, locators, access depth and change mechanisms; no copied article text or private correspondence. The [counting script](../scripts/synthesis_five_journal_corrections.py) checks structural claims, journal identity, DOI duplicates and actual declared source depth. It cannot independently authenticate field truth.

**Notice count is not paper, claim, root or discovery count.** One *Lancet* correction (DOI 10.1016/S0140-6736(21)00398-6) covers four different papers, and other notices amend multiple claims in one paper. A single original article may also receive serial notices. Preserve these many-to-many relations.

## Repeatable research and review process

1. Discover candidates in **original publisher archives**, cross-check PubMed Published Erratum records and ErratumFor/ErratumIn links. For Nature use Author and Publisher Correction filters; for The Lancet use Department of Error; for NEJM use Correction pages; for JACC include Erratum/Corrigendum/Correction; for Circulation use content-type Correction. PubMed misses some online-only corrections.
2. Restrict source journal to the five main journals; do not silently expand to sibling journals. Normalize DOI and official HTTPS URLs. Deduplicate both repeated indexing hits and DOI aliases. Link exact original paper IDs, notices, trial families, altered claim locators and mechanisms.
3. Read **the entire primary publisher notice**, including substantive tables, graphical changes and supplement links where accessible. Record date, DOI, exact source locator, version, original paper, old/new detail and strongest unresolved issue. If access yields only a search extract, partial text or metadata, credit **zero** full reviews.
4. Where useful, retrieve the historical and current paper, figures/data, supplement, protocol, SAP, registry and primary trial data. Verify treatment arms, endpoints, population, estimand, adjustment, precision, timing and units before any numerical comparison. If source-version identity cannot be established, HOLD.
5. Create a correction-derived **development** pair (historical error / amended claim), a valid similar-looking benign control, and a missing-evidence abstention control. Keep both source references and specific locators. Do not use these familiar corrections as untouched test material.
6. Advance in bounded batches, caching official source links and a resumable page/query cursor with honest access status. Respect source rights and publisher access limits; never commit full article text, private mail, credentials or unlicensed figures.

## Source-derived Synthesis improvements

| Primary notice example | Methodological check to develop | False-positive prevention |
|---|---|---|
| JACC 2025 TAVR review, 10.1016/j.jacc.2025.05.001 (index extract only) | Tie every outcome rate to named arm, comparator and contrast direction; test swapped group labels | Table order can legitimately change; cannot accuse the original trial without original data |
| NEJM 2025 enzalutamide correction, 10.1056/NEJMx250003 (index extract only) | Match *grade ≥3* against *serious* against *treatment-related* AE categories; verify time, denominator and supplement version | These AE definitions need not count the same patients |
| Lancet HARMONi-2 correction, 10.1016/S0140-6736(25)02154-3 | Source-matched survival curves, censoring and numbers-at-risk at exact time grid | Staggered entry/censoring/OCR artefacts can explain differences; HOLD on unverified graph data |
| Nature antimalarial correction, 10.1038/s41586-025-09938-4 | Compare historical image and separate corrected image where original article cannot be replaced | Crops and adjacent control panels can be legitimately similar; image resemblance alone insufficient |
| Nature PFAS correction, 10.1038/s41586-025-09871-6 | Version-checked laboratory measurement, chemical identity, potential scale and supporting information | Alternate reference electrodes, measurement methods and chemical species may be noncomparable |
| Circulation rehab correction, 10.1161/CIR.0000000000001338 | Dimensional check for measurement descriptions (minutes-versus-metres) | A six-minute test legitimately contains both time and distance quantities |
| Circulation hypertension correction, 10.1161/CIR.0000000000001396 | Match treatment-specific AE rates by approved/high dose and placebo, then compare guideline text and diagrams | Pooled dose ranges and different estimands cannot be treated as identical safety claims |
| Lancet grouped 2021 notice, 10.1016/S0140-6736(21)00398-6 | Many-to-many notice → article → claim → mechanism, source-attributed denominators and supplements | One notice does not equal one scientific error or four Synthesis discoveries |

For NEJM and JACC, the quoted mechanism is based on publisher-indexed extracts and remains *provisional* pending full primary-source access. For the eight full notices, the correction itself is publisher-attested; historical data, statistical replay and independently validated corrected values have **not** been established merely by reading the notices.

## State and counting contract

- DISCOVERED: official notice DOI/URL located, no full-content credit.
- INDEXED_EXCERPT_ONLY: search/publisher index excerpt; no full-content credit.
- FULL_PRIMARY_NOTICE: entire substantive publisher notice examined at exact source locator. No claim of independent reanalysis.
- ORIGINAL_HISTORICAL_SOURCE_VERIFIED: independent historical Version of Record or clearly described historical publisher attestation, with provenance.
- CURRENT_EXACT_CLAIM_RECHECKED: exact corrected source span verified, including an authoritative separate figure if original cannot be changed.
- RECONCILED: exact claim corrected and independently checked; unrelated unresolved claims remain open.
- MECHANISM_REGRESSION: source-backed development tests including valid and abstention controls. Not scientific validation.
- INDEPENDENT_MASKED_EVALUATION: separate, preregistered fresh family-disjoint real-paper sample. **Not started.**

Source-verified published corrections are **historical learning examples**, not Synthesis-discovered new errors. Do not mix correction notices, author acknowledgements, published errata, emails, candidate issues, or test-case counts into one headline error total.

## Validation discipline

The 1,000 notices belong entirely to **development**. Preserve Simo v0.10 and existing protected cohorts. Compare structured manual review, v1.2 and candidate v1.3 on a freshly frozen independent sample with unmodified negative controls and unflagged claims. Measure root-level recall, flag precision, false alerts per paper and per claim, evidence-span correctness, abstention, reviewer time and cluster-aware uncertainty. Report the honest null if a new rule does not improve the held-out test.

## Static versus observed

| Static target and design | Observed evidence | Not established |
|---|---|---|
| 1,000 complete notices, 200/journal aspiration, taxonomy and schema | 8 complete publisher notices + 4 source-limited extracts with official URLs | 1,000 read, 200 each, all current articles reconciled |
| Proposed paired tests and code checks | Internal suite outcome only after CI passes | Improved clinical error sensitivity or specificity |
| Published notices document historical corrections | Full/partial source access fields recorded | New unpublished errors or independent scientific confirmation |

## Reuse, non-goals and repository context

Reuse current [Synthesis v1.3](SYNTHESIS-v1.3-CANDIDATE.md), [evidence packet](SYNTHESIS-v1.3-AUDIT-PACKET.md), [blinded validation plan](SYNTHESIS-v1.3-BLINDED-VALIDATION-PLAN.md). Related [PR #66](https://github.com/mahmood726-cyber/e156-ecosystem-starter/pull/66) has four *Nature Medicine* RCT correction cases, explicitly **excluded** from *Nature* here. Related [PR #67](https://github.com/mahmood726-cyber/e156-ecosystem-starter/pull/67) is a separate broad 10,000-notice campaign: do not add its counts without DOI-level reconciliation. This five-journal study does not change that campaign, send correction emails, or alter existing schedules. Portfolio index/workbook were unavailable in this GitHub-only session; no new release/health status is claimed.

Official entry points: [Lancet](https://www.thelancet.com/); [NEJM](https://www.nejm.org/); [Nature Author Correction](https://www.nature.com/nature/articles?type=author-correction) / [Publisher Correction](https://www.nature.com/nature/articles?type=publisher-correction); [JACC correction policy](https://www.jacc.org/policies/editorial-operating-policies); [Circulation correction archive](https://www.ahajournals.org/journal/circ/latest?ContentItemType=correction&pageSize=50&startPage=0).

From repository root:

~~~bash
python3 -B scripts/synthesis_five_journal_corrections.py research/correction_learning/five_journals/20261103/notices-pilot-v1.json --target 1000
python3 -B -m unittest discover -s tests -p 'test_synthesis_five_journal_corrections.py' -v
~~~
