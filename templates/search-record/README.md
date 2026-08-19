# Search records that can be checked

Two real search records, and one command that reads them.

```bash
python scripts/search-record-reconcile.py --selftest                              # 10/10, exit 0
python scripts/search-record-reconcile.py templates/search-record/example_reconciles.json   # exit 0
python scripts/search-record-reconcile.py templates/search-record/example_cursor_lied.json  # exit 1
python scripts/search-record-reconcile.py templates/search-record/                 # both, exit 1
```

Standard library only, offline, no API key, no model call.

## The two files

| File | What it is | Verdict |
|---|---|---|
| `example_reconciles.json` | A ClinicalTrials.gov search for a colchicine cardiovascular review, 2026-08-19. Two pages, 100 + 37 = 137, reported total 137, all 137 identifiers named. | `RECONCILES`, exit 0 |
| `example_cursor_lied.json` | A ClinicalTrials.gov search for an acute-coronary-syndrome antiplatelet review, 2026-08-19. Three pages, 100 + 100 + 3 = 203, **reported total 430**, cursor null. | `CURSOR_SAID_DONE_BUT_THE_SUM_DOES_NOT_RECONCILE`, exit 1 |

The second is one of **our own** search records. It is shipped as the known-bad input the
detector is proved to fire on, because a detector never shown to fire is not a detector.

## What each file is worth reading for, beyond the exit code

**`example_reconciles.json`.** One of that review's own three included trials —
`NCT03048825`, and the largest of the three — was returned on **page 2 only**. A screen that
stopped at page 1 would have missed it while every number in the record still looked right.

It also carries the limit of its own clean verdict: two of the 137 registrations,
`NCT04906720` and `NCT06731595`, are the same study — identical title, sponsor, enrolment,
start date, primary completion date and intervention. **137 distinct registrations is at most
136 distinct studies.** The check reconciles identifiers and cannot see that. Recorded, not
silently deduplicated.

**`example_cursor_lied.json`.** Beside the 227 missing records sits a second finding of a
different kind: the query's condition filter did not surface `NCT02270242` (TWILIGHT), one of
the review's four trials, because its coded conditions are `Cardiovascular Disease` and
`Interventional Cardiology` rather than any of the terms queried. Recall 3 of 4. That is a
recall failure of the query, not of the pagination, and the two are worth separating.

## The record format

Every key is optional except that you need either an identifier list or per-page counts:

```json
{
  "query_as_executed": "intervention=colchicine; condition=...; page_size=100",
  "nct_ids": ["NCT02551094", "NCT03048825"],
  "pages": [
    {"returned": 100, "total_reported": 137, "next_page_token": "NF0g5i..."},
    {"returned":  37,                        "next_page_token": "null -- exhausted"}
  ]
}
```

- The identifier list may be `pmids`, `nct_ids`, `identifiers`, `records`, or split across
  `page_1` / `page_2` / … keys.
- The total may be `total_reported`, `total_count`, `totalCount` or `total`, on a page or at
  the top level.
- **Write down what the cursor said.** An absent `next_page_token` field is not a null one; a
  record that never wrote it has made no claim about completeness, and the check will not
  convict it of a proof it never offered.

## Related

- [`docs/SEARCH-COMPLETENESS.md`](../../docs/SEARCH-COMPLETENESS.md) — why the null cursor is
  not the proof, the audit of every record we hold, and what recall was measured at
- [`docs/META-ERROR-LIBRARY.md`](../../docs/META-ERROR-LIBRARY.md) — defect classes in finished
  syntheses, including the ones this programme has committed
- [`templates/trial-identity/`](../trial-identity/) — the screen for one trial entered twice,
  which is what the duplicate registration above becomes if it reaches a pooled analysis

MIT-licensed, like the rest of the kit.
