# SciCoQA paired inference status (3 November 2026)

The benchmark preparation and scoring tools are merged into main (PR #73). Seven targeted synthetic tests and the nine required GitHub checks passed. No real SciCoQA prompt-arm inference or independent human adjudication has yet been performed.

Execution is blocked on a configured external model provider and authentic, label-free, version-pinned paper/code text snapshots. GitHub Models inference API retired on 30 July 2026; do not rely on it. The existing paired scorer must not be used to claim source truth from automated labels. Preserve all no-findings, failures and abstentions.

Protocol: [SYNTHESIS-SCICOQA-PAIRED-COMPARISON.md](../../docs/SYNTHESIS-SCICOQA-PAIRED-COMPARISON.md).
