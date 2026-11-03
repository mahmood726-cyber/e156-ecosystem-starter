# SciCoQA paired inference status (3 November 2026)

The benchmark preparation and scoring tools are merged into main (PR #73). Seven targeted synthetic tests and the nine required GitHub checks passed. No real SciCoQA prompt-arm inference or independent human adjudication has yet been performed.

Execution is blocked on a configured external model provider and authentic, label-free, version-pinned paper/code text snapshots. GitHub Models inference API retired on 30 July 2026; do not rely on it. The existing paired scorer must not be used to claim source truth from automated labels. Preserve all no-findings, failures and abstentions.

Protocol: [SYNTHESIS-SCICOQA-PAIRED-COMPARISON.md](../../docs/SYNTHESIS-SCICOQA-PAIRED-COMPARISON.md).

## Added experimental runner

The branch now includes `scripts/scicoqa_paired_inference.py`, a standalone CLI adapter for a user-configured external model command. It sends each pre-rendered prompt via stdin and records raw responses, parsed findings, failures and abstentions for both arms. It does not supply model access or prove that external model settings match the declared manifest. Run it against your frozen contexts with a controlled local model command, followed by independent adjudication and the existing `score` step.

Example invocation (the model CLI must already exist and accept stdin):

```bash
python3 scripts/scicoqa_paired_inference.py --prepared /private/scicoqa-pair-001 --output /private/scicoqa-inference-001 -- python3 /private/model_cli.py
```

The additional runner unit tests use simulated text only, never real benchmark observations. No real two-arm model inference or source adjudication has been completed; all scientific accuracy metrics remain unknown.
