# Correction-learning campaign handoff to IPD meta-analysis audit

Checkpoint date: 2026-11-04 (Europe/London). Public, source-limited preservation note.

## Purpose and boundary

The owner requested that the ten correction-learning automation workstreams be paused and replaced by ten individual participant data (IPD) meta-analysis review tasks, but only after ensuring accessible work was on GitHub. This is an inventory of **observably committed** public work, not proof that every automation-run output was committed. Do not silently convert an incomplete run or correction notice into a fully reviewed finding.

## Verified repository inventory at handoff

Repository: `mahmood726-cyber/e156-ecosystem-starter`.

- Preservation branch: `synthesis/correction-learning-10k-20261103`.
- Open, unmerged draft preservation PR: https://github.com/mahmood726-cyber/e156-ecosystem-starter/pull/67
- Pre-handoff branch head inspected: `c1590ff8e3b69223fae22219d3970e740f788a3f`.
- The campaign protocol: `docs/SYNTHESIS-CORRECTION-LEARNING-10K.md`.
- Separate related draft correction-notice regression PR #66: https://github.com/mahmood726-cyber/e156-ecosystem-starter/pull/66
- Existing general medical-journal correction work on `main` is separate; do not treat it as part of the ten shards without source-level reconciliation.

The branch tree showed **21 committed files** under `research/correction_learning/20261103/`, distributed as:

| Shard | Former methodological focus | Committed files | Verification |
| --- | --- | ---: | --- |
| 00 | Event Counts | 2 | Branch files inspected |
| 01 | Numerical | 2 | Branch files inspected |
| 02 | Identity | 3 | Branch files inspected |
| 03 | Methods | 2 | Branch files inspected |
| 04 | Document | 2 | Branch files inspected |
| 05 | Pooled Evidence | 3 | Branch files inspected |
| 06 | Survival | 2 | Branch files inspected |
| 07 | Figure | 2 | Branch files inspected |
| 08 | Source | 3 | Branch files inspected; includes one test file |
| 09 | Correction Watch | **0** | No `shard-09/` directory found |

These are file counts, **not** deduplicated notices, verified cases, completed reviews, errors or validated tests. Individual records include partial/HOLD cases, and batch-level numeric counts have not been centrally reconciled or independently adjudicated.

## Preservation gaps and risk controls

1. No committed `shard-09` evidence was found at this checkpoint. The Correction Watch automation's last recorded result had empty text and required user action; the missing evidence cannot be reconstructed safely from this metadata.
2. Latest run-result text shown by the automation interface was empty for the inspected workstreams. Private/transient conversations, earlier unsaved output, and any write not observed in the current GitHub branch **cannot be certified as preserved**.
3. Prior automation definitions are kept by the task system when disabled. Do **not** publish full prompts, private correspondence, email details, individual clinical data, API tokens or private run transcripts into this public repository.
4. The work remains on the preservation branch and draft PR #67. This handoff **does not merge** unvalidated retrospective evidence to `main` and does not assert the 10,000-notice aspiration was met.
5. The branch should remain available for future reconciliation. Do not delete, reset, rewrite or force-push it. Before merging, reconcile original notices and aliases, confirm provenance, independently review cases, and run required CI and governance checks.

## New IPD lane: transfer principle

Use the newest verified `main` snapshot of Synthesis at each run, beginning with the current repository state. Its v1.3 candidate is **experimental**; `scripts/synthesis_v13_nma_preflight.py` provides limited, source-attested NMA/IPD review/readiness checks, not a general IPD meta-analysis statistical engine or an autonomous scientific-error detector. No findings, code, or correspondence from the correction campaign should be silently relabelled as IPD evidence.

Store public-only IPD study metadata and methodological review notes under a new, separately reviewed branch and folder; use stable DOI/article/version identifiers, deduplicate by review, separate inaccessible/full/partial and independently verified records, record strongest benign alternatives, and keep raw IPD subject to licensing, consent and privacy rules.

## Completion claim boundary

This checkpoint preserves and inventories the **accessible committed material**. It does **not** establish that *all* past task activity, including unsaved run artifacts, is on GitHub. Any subsequent status report must disclose this gap rather than claiming complete preservation.
