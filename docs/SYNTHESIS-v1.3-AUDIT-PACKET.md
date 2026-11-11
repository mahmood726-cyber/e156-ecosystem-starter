# Synthesis v1.3 — auditable evidence packet and response review

**Updated 6 November 2026 · development contract; no private case records in this repository**

## Scope and privacy

This specification supports private scientific-verification records. Keep original manuscripts where licensed, private correspondence, sender/recipient details, sent-message IDs and reviewer identities **in private append-only records**, never in GitHub. Public repository tests use invented synthetic identifiers. This procedure does not authorise contact, override operational holds or set error/email quotas.

A true target item is **one distinct, substantive, independently source-verified error root that has actually been emailed**. A candidate discrepancy, methodological question, withdrawn concern, metadata-only issue, author acknowledgement without an error finding, correction learned after publication, draft, or unverified send does not qualify. Multiple affected cells from one underlying root count once; one consolidated email may document multiple distinct roots.

## Evidence packet fields

The separate [source replay example](SYNTHESIS-REPLAY.md) uses an attributed,
openly licensed public article and a development extraction packet. It contains
no private correspondence or independently adjudicated error allegation.

Every candidate needs an exact and independently checked current report identity (DOI or versioned arXiv identifier), document version and SHA-256, claim locator, original underlying report/registry/protocol identity and hash, source locator, analysis/estimand identity, reconstruction reference, candidate alternative explanation and refutation evidence, severity, source-support status and an explicit trial-family/root ID.

The offline evidence_packet(record) primitive requires these caller fields, plus verified current-claim/correction status and matching statistical estimand. It returns only READY_FOR_INDEPENDENT_REVIEW or HOLD. A structurally complete receipt **does not** authenticate source hashes, scientific disagreement, author confirmation or independence. All status claims require human verification.

For true emailed-root accounting, the private register also needs:

- Independent verifier identity distinct from investigator; dated independent adjudication record and exact evidence reference.
- Maturity INDEPENDENTLY_ADJUDICATED and severity S3–S5; separate author acknowledgment, confirmation and published correction statuses.
- Synthesis discovery record showing this issue was detected before learning from a public correction.
- Recipient and actual Sent-folder Message-ID; an email draft is NOT_SENT. Verify the body specifically includes the relevant root, especially for consolidated emails.
- Actual correction-notice locator if labelled CORRECTION_PUBLISHED; author-confirmation evidence if labelled AUTHOR_CONFIRMED.

reconciliation_summary(records) groups by (root_scope_id, root_cause_id), reports administratively eligible distinct emailed roots and **distinct sent messages** separately, and excludes unverified or non-substantive records. Its labels are supplied by callers and can be mistaken or falsified, so the output is not independent scientific validation or delivery proof.

## Mandatory workflow

1. Check Gmail/Sent and the private error ledger to exclude previously submitted or corrected claims before investigation.
2. Identify the current published version, all relevant correction notices, underlying original report, protocol, SAP, registry and code; record access path and stop point for inaccessible material.
3. Match unique trial populations, outcome/estimand, follow-up, test/statistical model, missingness, censoring, units and rounding precision. Investigate plausible benign explanations; abstain when not comparable.
4. Independently reproduce the exact original source numbers. For NMA/IPD, replay the published model before corrected data, assess shared control and trial-family dependence, RoB 2/RoB NMA and conclusion impact.
5. Record human source verification and distinct root ID. Any external contact needs a separate explicit human decision and source-rights/no-contact checks. Preserve actual send evidence only if a message was sent. A tool must not claim author confirmation or publication correction prematurely.
6. When feedback exists, follow the [response-review procedure](SYNTHESIS-RESPONSE-REVIEW.md): compare each point with the original enquiry, source-check both positions and retain unresolved counterevidence. Record resolved enquiries, false-positive allegations, persistent concerns and version-limited discrepancies separately. Do not schedule automatic reminders.

## Status displays

Keep independently source-verified errors, author-confirmed errors, published corrections, candidates/clarifications, refuted issues, sent emails and actual replies as **separate numbers**. Do not transform a large number of outgoing emails into a count of discovered errors.

Exclude withdrawn allegations and publication-page ingestion metadata problems that do not affect a study claim. Preserve author responses and corrections privately, and amend a record when a version update resolves the issue. An explained clarification request is not an erroneous allegation; a mixed response cannot establish that every point was correct or incorrect.

## Required validation link

These administrative counters are not the prospective scientific benchmark. See [SYNTHESIS-v1.3-BLINDED-VALIDATION-PLAN.md](SYNTHESIS-v1.3-BLINDED-VALIDATION-PLAN.md) and [SYNTHESIS-REPORTING-v0.1.md](SYNTHESIS-REPORTING-v0.1.md). Never optimise on frozen Simo/test data or publish case-specific Gmail material.
