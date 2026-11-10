# Start with Synthesis

Synthesis is a free, experimental research-checking checklist. Start with one open-access paper or one claim. Record its version and the material you actually checked. A result covers the selected check; it does not certify a paper. Detection accuracy has not been independently established.

## Choose how to work

| Route | What you do | Where it runs |
|---|---|---|
| Manual | Follow the [six core checks](SYNTHESIS-HUMAN-CHECKLIST.md#start-with-six-core-checks), keeping your evidence and calculations | Your own permitted workflow; no AI service required |
| Optional AI prompt | Copy the [short core](SYNTHESIS-COPY-PASTE-AI-PROMPT.md#copy-the-short-core) into an assistant approved for the material | The assistant you select, under its applicable institutional and service arrangements |
| Optional evidence capture | Supply a packet and permitted PMC XML, or explicitly enable live PMC retrieval | Local Python scripts; source retrieval uses PMC EFetch when enabled |

**The prompt does not provide a model or an AI hosting service.** Synthesis does not choose an assistant, grant upload permission or establish its privacy protections. If your institution requires an internal service, use its approved environment. Use the manual route when AI processing is not permitted. Do not upload correspondence, identifiable participant data or confidential manuscripts to an unapproved service.

The Python intake does not call an LLM or send emails. Its local receipts can contain source excerpts and claim records: keep them private unless each item is suitable for release. A file hash identifies the captured bytes; scientific correctness requires separate review.

## Check one claim

1. Find the exact claim in the correct paper version. Save its locator and verify corrections.
2. Match the source and analysis. Establish population, arm, outcome, timepoint, units and denominator before comparing numbers. Use the [participant worksheet](SYNTHESIS-PARTICIPANT-WORKSHEET.md).
3. Save the calculation and strongest tested explanation. Preserve matching results and missing evidence. Mark calculations you did not run as `NOT_RUN`.
4. After revisions, check affected text, tables, captions and supporting files. Keep uninspected locations visible and record nearby unaffected results.

For statistical and source-specific checks, add the detailed prompt module and [methods guide](SYNTHESIS-METHODS.md). Read the [public worked examples](SYNTHESIS-WORKED-EXAMPLES.md) as teaching material, not measured validation.

## Try the local workflow

Python 3.10 or later is required by the intake scripts. From the repository root, the following commands replay an explicitly synthetic example without network access:

```sh
python scripts/synthesis_preflight.py --prompt docs/SYNTHESIS-PREFLIGHT-v1.1.md --packet examples/synthesis_intake_demo/packet.json --pmc-xml examples/synthesis_intake_demo/article.xml --output-dir ../private-synthesis-demo
```

Read `receipt.json` and `report.md` in the output directory. The example contains source-bound count agreement, strict-subset accounting, a count/percentage comparison, a signed interval and a revision with stale text and an uninspected dependency. The stale revision is a review candidate and its claim remains on hold. The numbers and document identifiers are invented software fixtures, not research findings.

For a real permitted PMC paper, first run capture to obtain its exact snapshot digest and quote locations. Then map the relevant sources in a packet; do not reuse the example digest, identifiers or assumed analysis labels. See the [intake evidence contract](SYNTHESIS-INTAKE-EVIDENCE.md) and [PMC capture guide](SYNTHESIS-PREFLIGHT-PMC-COUNTS.md). `--pmc-live` explicitly enables retrieval. Figures and external supplements can still require manual inspection.

## Keep replies and contact pauses private

Use the [private case record](SYNTHESIS-INTAKE-EVIDENCE.md#private-replies-corrections-and-contact-pauses) to track each reply point, correction stage and contact pause. Store it outside the public checkout and pass it with `--private-case-state` when reviewing that packet. Intake emits only a redacted status summary; it does not fetch correspondence or discover omitted replies. A validated record never authorises an email.

To report a checking problem, use an authorised public or synthetic example with the command, source version, expected behavior and actual receipt. Do not put emails, private worksheets or answer keys in an issue or pull request.
