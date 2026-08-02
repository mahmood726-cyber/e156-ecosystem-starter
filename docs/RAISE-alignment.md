# RAISE alignment — how this ecosystem maps to Responsible AI in Evidence Synthesis

**RAISE** = *Recommendations for the Responsible use of AI in Evidence Synthesis*
(Cochrane, Campbell, JBI, Collaboration for Environmental Evidence; 2025). This
document maps the E156 ecosystem (AI coding agents + **Sentinel** integrity gate
+ **Overmind/TruthCert** verification + the advanced-stats rule library) to the
RAISE principle areas, so the system's responsible-AI posture is explicit and
auditable — the prerequisite for evidence-synthesis-community adoption.

> **Verify-before-cite:** the principle *areas* below reflect the RAISE framework
> as understood here; the **exact recommendation wording/numbering must be checked
> against the published statement** before any external/compliance claim. Treat
> this as a self-assessment scaffold, not a certified conformance statement.

Legend: ✅ covered · 🟡 partial · ⬜ gap

| RAISE principle area | Ecosystem mechanism | Status |
|---|---|---|
| **Transparency & reporting of AI use** | `AGENTS.md` declares agent roles; TruthCert bundles record method + inputs + `source_hash`; `overmind assess` emits an evidence snapshot; git history + signed bundles are the audit trail | 🟡 — strong provenance, but **no standardized per-output "AI-use disclosure" report** (PRISMA-AI style) |
| **Human oversight & accountability** | Fail-closed defaults; **"memory ≠ evidence"** non-negotiable; Sentinel WARN-vs-BLOCK keeps humans in the loop; review gate before completion; `#4` multi-reviewer signed consensus adds adjudication | 🟡 — designed for oversight; historically **solo workflow** (multi-reviewer layer is new) |
| **Validation & performance evaluation** | `overmind eval-ecosystem` scorecard; `overmind ma-verify` (validated on 850 real Cochrane MAs); Sentinel 17-incident regression corpus + `overmind rule-effectiveness`; meta-verify canary | 🟡 — strong internal validation; **no peer-reviewed external validation yet** (the #1 credibility gap) |
| **Methodological rigor** | `rules/advanced-stats.md` (pooling, heterogeneity, pub-bias, NMA, DTA, Bayesian, survival); `cochrane_v65_invariants` rule (RevMan-2025); `ma-verify` statistical invariants; `rules/e156.md` format contract | ✅ — gold-standard methods encoded as machine-checkable rules |
| **Reproducibility & provenance** | TruthCert **HMAC/Ed25519-signed** certification bundles; numerical-continuity witness; deterministic-by-design; `source_hash`; local-first/offline; cross-machine sync with signed memory | ✅ — **ahead of the field** (no SaaS competitor cryptographically signs outputs) |
| **Data privacy, security & IP** | **OA-only** (no paid/restricted data); local-first/offline (data never leaves the machine); `leaked_secret` + `hmac_compare_eq` + `insecure_deserialization` Sentinel rules; secrets never in git (public/private sync split) | ✅ — strong by design |
| **Bias, fairness & equity** | Multi-witness arbitration reduces single-model bias; lessons on dual-LLM screening bias + LLM citation misattribution; conclusion-instability surfaced (e.g. HKSJ flips in 10% of MAs) | 🟡 — bias *reduction* present; **no explicit equity/representativeness audit** of included evidence |
| **Methodological rigor** *(of the finished synthesis, not the code)* | `scripts/meta-self-audit.py` — 18 deterministic offline detectors over a finished review dashboard, mapped to Cochrane Handbook ch.6 (effect measure vs data type), §10.4.3.1 (no funnel-asymmetry test below k=10), Handbook ch.23 (multi-arm / multi-report unit-of-analysis), PRISMA 2020 (flow arithmetic, eligibility justification, harms reporting), AMSTAR-2 item 4 (search currency), GRADE indirectness. Every class documented with a real worked example in [`META-ERROR-LIBRARY.md`](META-ERROR-LIBRARY.md), derived from a 626-dashboard corpus audit plus a published-literature error registry | 🟡 — evidence-based and machine-checkable, but **text-pattern matching over one rendered page**; the classes it cannot catch are enumerated by name in the library's "What is not automated" table |
| **Transparency about tool limits** | Every detector ships its blind spot beside its feature; `CLEAN` is defined in the tool's own output as "no detector fired", not "correct"; `INCONCLUSIVE` is a first-class verdict that exits non-zero so an unrunnable check can never read as a pass; two known false positives and one known false FAIL (Overmind's scale-invariance relation vs a correct random-effects estimator) are documented with measured numbers | ✅ — limits are in the tool's output, not only in the docs |
| **Error & integrity management** | Sentinel fabrication suite (`fabrication_implausible_precision`, `_orphan_trial`, `_round_number_cluster`, `_temporal_impossibility`, `_self_contradiction`), `citation_cascade`, `denominator_logic`, local "no naked numbers" hallucination heuristic, `ma-verify` | ✅ — **unique**; no competitor has a unified automated fabrication/integrity gate |

## Where this ecosystem leads RAISE expectations
- **Cryptographic output certification** (TruthCert) and **automated fabrication detection** (Sentinel) operationalize "integrity" and "reproducibility" beyond what current evidence-synthesis tools offer — most rely on manual audit + PRISMA reporting.
- **Determinism + provenance + OA-only + local-first** directly satisfy privacy/reproducibility recommendations without trade-offs.

## Gaps to close for full RAISE conformance (priority order)
1. **Peer-reviewed external validation** of Sentinel/Overmind (sensitivity/specificity vs manual review + statcheck/GRIM) — converts "validation" 🟡→✅ and is the top credibility lever.
2. **Standardized AI-use disclosure report** per synthesis output (which agent/model/version did what; PRISMA-AI-aligned) — closes "transparency" 🟡→✅.
3. **Human-oversight workflow** — the multi-reviewer signed-consensus layer (with per-reviewer attestations + adjudication of conflicts) — closes "accountability" 🟡→✅.
4. **Equity/representativeness audit** of the evidence base (geography, population, funding/COI) — closes "bias/fairness" 🟡→✅.
5. **Map to the exact published RAISE items** and produce a line-by-line conformance table for submission to a methods venue (e.g. *Research Synthesis Methods* / Cochrane Methods).

## Reproduce this self-assessment
- Methodological rigor / integrity: `python -m sentinel list-rules`; `overmind ma-verify --csv <results.csv>`
- Validation posture: `overmind eval-ecosystem`; `overmind rule-effectiveness`
- Provenance/signing: `overmind assess --project-id <id>` (evidence snapshot + signature method)
