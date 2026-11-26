# Synthesis — reviewing explanations and preventing false positives

**12 November 2026 · review procedure, not a measured accuracy claim**

Use this with the [human checklist](SYNTHESIS-HUMAN-CHECKLIST.md) and
[optional prompt](SYNTHESIS-COPY-PASTE-AI-PROMPT.md). Review each original
point separately. A respondent's authority, agreement, disagreement or tone
does not decide whether a scientific claim is correct.

## Recheck before changing a verdict

1. Register every original point, including unanswered ones, then read the exact original question, response and relevant attachments. Unavailable attachments remain unresolved. Identify whether the original
   item alleged an error or asked for clarification. Verify every quotation
   against the correct document and section. Separate invented/misattributed
   quotations from genuine source passages.
2. State the response's proposed explanation in a testable form. Locate its
   supporting source: current article, footnote, supplement, protocol/SAP,
   registry version, code/configuration or official software documentation.
   A source quotation inside an email is not an independent source inspection.
3. Recompute only the same estimand, population and method. Save input data,
   formulas and working; for code, save the script, environment, command and
   raw output. A plausible formula or unexecuted script is not reproduction.
4. Actively seek counterevidence to both positions. Check whether the proposed
   explanation resolves the original point completely or merely a different
   point. Preserve remaining contradictions and inaccessible requirements.
5. Record the point outcome below, reviewer, date, sources, calculation trail
   and limits. Retain the original record and append the revised assessment.
   Do not overwrite a mixed thread with a blanket correct/incorrect label. Do not call all points confirmed when only one was accepted, or resolved when the reply did not address them.

| Point outcome | Evidence required | Treatment |
|---|---|---|
| CONCERN_PERSISTS | Source recheck addresses the reply but supports the original specific concern | At most a flag candidate, subject to all existing evidence gates and review |
| RESOLVED_ENQUIRY | Source-supported explanation answers a clarification request | Reconciled; do not count as an erroneous allegation |
| FALSE_POSITIVE_ALLEGATION | Source recheck refutes an actual error allegation | Withdraw that point and retain the reason; exclude it from confirmed errors |
| VERSION_LIMITED | Verified discrepancy belongs to an earlier edition and is resolved in the current edition | Preserve version history; exclude from new current-article errors |
| METHOD_DISCUSSION | Source-supported methodological preference or interpretation without an objective contradiction | Discussion; do not count as established error |
| UNRESOLVED | Explanation, original claim or required source cannot be established | HOLD; do not count as correct or false positive |

An author-confirmed typo, an explained denominator and an unresolved model
question in one email have three separate outcomes. Agreement to clarify
wording is not necessarily an admission that the numerical analysis was wrong.
Equally, correct numerical output does not resolve an incorrect method label,
wrong comparator attribution or inconsistent presentation.

## Specific alternatives to test

| Apparent mismatch | Check before alleging an error |
|---|---|
| Coefficient versus HR/OR | Predictor coding, reference group, contrast size and units; exp(beta × contrast), including -1/+1 effect coding |
| Interim/final or repeated same-result values differ | Exact analysis version, data cutoff, population, contrast and endpoint definition; a stale result needs its own source comparison |
| Count divided by headline sample size | Item respondents, skip logic, missingness, eligible risk set, treated versus randomised population and exposure time |
| P value versus a crude two-group calculation | Null hypothesis, superiority/non-inferiority margin, sidedness, permutation method, model and multiplicity |
| CI has zero width or unusual geometry | Actual interval construction, zero-event boundary, censoring and source precision; method limitations may require discussion rather than an arithmetic verdict |
| Non-zero weighted value with no observed cases | Observed counts versus weighting and marginal standardisation, plus the actual code and model |
| Composite and component counts/rates differ | First versus recurrent events, overlapping components and endpoint-specific follow-up |
| Different trial counts or dates | Unique trial families, outcome-specific contributions, registration activation, first recruitment, closure and dated amendments |
| Trial inclusion/exclusion alleged from a title | Full Methods, allocation evidence and actual contribution to each pooled outcome; distinguish unclear design from proved non-random allocation |
| Wrong numbers inferred from a figure | Row, arm, orientation, legend and analysis version; distinguish presentation from fitted-model errors |
| Value exceeds a scale or differs only at a rounding tie | Source-defined limits and their applicability; printed precision and stated rounding convention |
| Citation fails to support a claim | Citation error versus false factual statement; unsupported citation is not automatically contradiction |

## Software contract and limits

For persistent point, correction-stage and contact-pause metadata, use the optional [private case sidecar](SYNTHESIS-INTAKE-EVIDENCE.md#private-replies-corrections-and-contact-pauses). Normal intake holds known unresolved points and emits only a redacted summary. The sidecar does not fetch messages, authenticate explanations or verify a claimed published correction; those require the source rechecks above. A contact release never authorises outreach. Registered points without replies hold intake. `SOURCE_RECHECKED` alone does not close a registered point; record the supported point outcome. `FALSE_POSITIVE_ALLEGATION` requires an original error allegation, and `VERSION_LIMITED` requires a source recheck. `DECLINED_OR_UNAVAILABLE` records an editorial stage independently of scientific resolution. Legacy logs without a point inventory remain labelled `REPLY_EVENTS_ONLY`; they cannot establish complete thread coverage.

`feedback_recheck(record)` in `scripts/synthesis_v13_checks.py` validates
single-claim review declarations, original/reply references, source-recheck
fields and calculation artifacts. It does not read emails, authenticate
sources or adjudicate scientific truth. Records and real correspondence stay
private; public tests use synthetic examples only.

`gate(record)` requires a documented feedback review for AUTHOR_DISAGREED
records. A supplied review must match the candidate's claim ID. Supported
explanations return RECONCILED, method discussions return DISCUSSION, and
incomplete or unresolved reviews return HOLD. CONCERN_PERSISTS must still
pass the existing version, source, comparability and refutation gates. Callers
must attach known feedback; these offline functions cannot discover omitted
messages or enforce an inbox-wide policy. The helper's FALSE_POSITIVE_RECORDED
label records a reviewer's assessment, not independently established truth.

## Evaluation limits

Keep private names, quotes, addresses, identifiers and correspondence out of
public fixtures and documentation. Any examples used to revise a prompt must
be excluded from held-out accuracy testing, including linked trial families.
Use the same underlying model, source
access and time budget when comparing prompts; preserve all flags, no-flags,
abstentions and adjudication outcomes. A resolved enquiry is not automatically
a false positive, and an unanswered query is not a true positive. These changes
have no independently measured real-world performance result.

Keep private channel preferences and requested submission formats with the case. A later summary must accurately identify the point, reviewer role, evidence and method; a proposed clarification is not an admission of analytical error.

Reviewing feedback does not authorise new contact or override any source-rights,
no-contact or operational hold.
