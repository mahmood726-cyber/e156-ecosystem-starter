# Synthesis — source evidence and private case records

**Experimental software contract, 10 November 2026.** [Author start page](SYNTHESIS-START.md) · [Core prompt](SYNTHESIS-COPY-PASTE-AI-PROMPT.md) · [PMC capture](SYNTHESIS-PREFLIGHT-PMC-COUNTS.md)

Normal `synthesis_preflight.py` intake accepts optional `evidence_checks` on each claim. It captures the requested excerpts from the same permitted PMC snapshot and writes the findings to the normal JSON receipt and Markdown report. Up to 40 checks are supported per packet; checks need unique IDs within a claim. Invalid types, duplicate IDs, unsupported references and excess limits hold the input or scoped comparison.

| Static design | Evidence produced at runtime |
|---|---|
| Bounded schemas, numeric token grammar, explicit scope attestations, synthetic regression fixtures | Captured source identity, snapshot digest, exact quote/locator/offset, parsed lexeme, actual arithmetic and dependency states |
| Method and unit labels, reviewer-selected mappings and declared relationships | Whether the supplied fields satisfy the contract; the software does not independently authenticate their scientific meaning |

No detection-accuracy gain is claimed. Matching inputs, caller attestations or tests do not validate underlying participant records. Public examples are invented fixtures. Correspondence, private case references and evaluation keys are excluded.

## Bind each source before comparing it

Every check requires `id`, `kind` and the article's `snapshot_sha256`. Count references use the existing integer-cell or quoted-count contract. A quoted count has `quote`, `count_text` and optionally the exact indexed `locator`.

A source count record has:

- `count`: the count reference;
- `definition`: a source quote and optional locator for the analysis/population definition;
- `scope_verified: true`: an explicit reviewer attestation;
- `identity`: result, data-version, population, endpoint, time-window, arm/stratum, count and denominator basis, plus the estimator fields defined in [synthesis_preflight_count_identity.py](../scripts/synthesis_preflight_count_identity.py).

Use `not_applicable` only for genuinely absent statistical mechanics, never an unknown population or source identity. The intake derives publication, source version, source hash, numeric value and locator from capture; conflicting caller declarations are refused. Quoting a definition does not prove that the reviewer assigned the right scientific label.

| Kind | Inputs and outcome |
|---|---|
| `MATCHED_COUNTS` | `left` and `right` source count records. The existing identity helper checks same-result/arm/version/estimator metadata. Only comparable counts are tested for equality. Missing or different scope holds the claim. |
| `STRICT_SUBSET` | `relationship: STRICT_SUBSET`, `primary`, `restricted`; optional `exclusions` containing source count records. Verify unchanged arm, outcome, timepoint and counting basis. Exact subtraction requires `exclusions_disjoint_verified` and `exclusions_exhaustive_verified`, both true. A count below its parent without an exclusion ledger holds. A verified excess is a candidate; a wrong smaller count can also be a candidate after accounting. An explicitly exhaustive empty ledger represents no exclusions. |
| `COUNT_PERCENT` | `numerator`, `denominator` source count records and a `percentage` scalar reference. Match analysis identity, use the actual source denominator, and round the computed raw percentage to the printed precision. `rounding` is `HALF_UP` by default or explicitly `HALF_EVEN`. No adjusted, weighted, survival or exposure-rate percentage is inferred from a crude fraction. |
| `INTERVAL` | `estimate`, `lower`, `upper` scalar references; `effect_measure`, `method_context` quote, `scope_verified: true` and `method` (`reported_two_sided` or `conventional_two_sided`). Check printed ordering and containment only. The interval method, uncertainty coverage and P value are not validated. |
| `REVISION_SWEEP` | `expected` scalar reference, `occurrences` and an explicit `dependencies` list. See below. |

Legacy `participant_count_check` arithmetic and correction traces remain available. Their receipts now explicitly retain `scope_status: REVIEWER_ATTESTATION_ONLY` and `decision_status: HOLD`; they cannot clear a decisive claim outcome from attested labels alone. Use `evidence_checks` for source-bound analysis definitions. Legacy v1.1 deterministic calculations remain printed-value diagnostics, not source authentication.

Matching estimator labels alone do not make a crude percentage calculation appropriate. `COUNT_PERCENT` requires `effect_measure: raw count`, `estimand: observed count`, and explicit absence markers (`not_applicable`, `n/a`, `na` or `none`) for model, adjustment and censoring. Missingness must be absent or explicitly `observed`, `complete_case`, `available_case` or `no_imputation`. A supplied denominator unit must equal the counted unit. Non-raw, imputed, weighted, adjusted, censored and person-time estimates hold before any percentage is calculated. Other methods require a separate method-specific check.

## Signed values, units and precision

A scalar reference has `quote`, `number_text`, `role`, `unit`, `scale`, and an optional exact `locator`. Roles are `estimate`, `lower`, `upper`, `percentage`, `value` or `count`. The lexeme is preserved, including its sign, exponent and displayed decimal precision. Partial signed tokens, ambiguous occurrences, numeric ranges and unsupported semantic markup hold. The `count` role still uses the strict integer-count parser.

The declared unit must occur in the bound quote, or in an explicit `unit_context` quote/locator, such as a table heading. `percent` can bind a printed percent sign. A percent marker in the captured source suffix still requires the percent unit when the excerpt stops before it; a different unit context cannot override the marker. Explicit percentage-point wording retains its distinct matching unit. Unit labels apply to the selected data block, not an entire spreadsheet. `scale` is reviewer supplied; the software does not infer transformations or convert units. Different interval or revision units/scales hold. A source-backed local reference limit or grading definition still needs specialist interpretation.

If the printed token has `<`, `<=`, `>`, `>=`, `≤` or `≥`, preserve it in `inequality`. It cannot be silently treated as an exact estimate or interval endpoint. Capture retains up to 64 characters before and after an excerpt to detect a cut-off sign, comparison operator or larger numeric token; shortening a quote cannot hide these boundaries. The receipt records source-text offsets, not PDF coordinates. No universal CI/P-value formula, clinical normal range, logarithm base or SE/SD relationship is assumed.

## Revision dependencies

Each occurrence has a stable `id`, `root_id` and scalar `ref`. It is compared with the expected source value using the same role, units, scale and inequality. Repeated aliases of one physical source token are refused.

Each dependency has `id`, `locator`, `status` and optional `depends_on` IDs. Allowed states:

- `MAPPED`: supply `occurrence_id`; its captured locator must match the dependency locator.
- `JUSTIFIED_DIFFERENCE`: supply a reason, `reviewed: true`, and a source-bound `evidence` quote. This remains a reviewer attestation.
- `UNINSPECTED`: retain the missing file, graphic or other dependency explicitly.

Unknown edges, repeated IDs and cycles hold. An empty dependency list is explicit coverage of the agreed scope only. Stale mapped values produce a candidate even when a table matches; uninspected dependencies remain visible. Without a definite stale value, an uninspected dependency holds the sweep. Coverage is always `REVIEWER_SELECTED_ONLY`, never whole-paper certification. The existing root-grouping helper retains affected output IDs under declared source/version/root identities; its counts are administrative, not counts of proven errors. Original and replacement snapshots and published notices still require the separate correction-link procedure.

## Private replies, corrections and contact pauses

Keep the local case file outside the public checkout. The helper never reads an inbox, fetches evidence references or sends messages.

```sh
python scripts/synthesis_case_state.py --state ../private-synthesis-case/state.json --init --identifier YOUR_SOURCE_IDENTIFIER --version YOUR_EXACT_VERSION
python scripts/synthesis_case_state.py --state ../private-synthesis-case/state.json --event ../private-synthesis-case/event.json
python scripts/synthesis_preflight.py --prompt docs/SYNTHESIS-PREFLIGHT-v1.1.md --packet YOUR_PACKET.json --pmc-xml YOUR_PERMITTED_SNAPSHOT.xml --private-case-state ../private-synthesis-case/state.json --output-dir ../private-synthesis-receipt
```

Replace the uppercase arguments with your own verified source and file values. A newly created case directory receives a wildcard `.gitignore`. Existing directories and other output folders must be protected by their owner. These local files are not automatically suitable for public release.

Schema `synthesis-case-state/1` contains `document` (`identifier`, `version`) and an `events` list. Each event needs a unique `event_id`, explicit UTC `recorded_at`, and `type`. Events are appended in timestamp order. The CLI refuses reinitialisation, duplicate IDs and invalid updates, uses an exclusive lock and atomically replaces the validated file. This protects routine updates; the history is not signed or authenticated against external modification.

| Event | Required fields |
|---|---|
| `REPLY_POINT` | `claim_id`, `point_id`, `original_question_reference`, `reply_reference`, `outcome`. Keep point IDs stable. Outcomes: `ACKNOWLEDGED`, `EXPLANATION_UNVERIFIED`, `UNRESOLVED`, `SOURCE_RECHECKED`, `RESOLVED_ENQUIRY`, `METHOD_DISCUSSION`, `CONCERN_PERSISTS`. The last four require private `source_recheck_reference` and `reviewer_reference`. |
| `CORRECTION_STATUS` | `claim_id`, `point_id`, `status`, `evidence_reference`. Status: `NOT_REQUESTED`, `REQUESTED`, `AUTHOR_REPORTED_PUBLISHED`, `PUBLIC_NOTICE_RECORDED`. These are recorded stages; none independently verifies publication or propagation. Use captured public notice evidence separately. |
| `CONTACT_PAUSE` | `pause_id`, `scope` (`DOCUMENT` or claim-ID list), `source_reference`, `reason`, `release_condition`. |
| `CONTACT_RELEASE` | Existing active `pause_id`, `source_reference`, `release_authorised: true`. A release affects only that pause. No deadline or positive reply releases another pause. |

Repeated point assessments preserve history and keep the original question reference fixed. Unknown claim IDs, mismatched document versions, malformed dates and invalid histories hold intake. All sidecar claim IDs must belong to the supplied complete packet. A known pending reply holds a decisive claim disposition. A reviewed point never automatically promotes a claim; existing source/refutation gates still apply. Contact pauses are reported separately from scientific outcomes.

Intake emits only claim IDs, fixed status labels, counts and pause booleans. Private event IDs, question/reply/reviewer references and correspondence text are not copied into the receipt or report. `email_eligible` is always false. Omitting a known reply or pause cannot be detected by this offline helper; supplying the current private record remains the operator's responsibility. Follow the [point-specific source recheck procedure](SYNTHESIS-RESPONSE-REVIEW.md) before treating a reply as resolved.
