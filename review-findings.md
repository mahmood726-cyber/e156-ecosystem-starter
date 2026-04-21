# Multi-Persona Review: e156-ecosystem-starter v0.7.0

**Date**: 2026-04-21
**Reviewed**: install/install.ps1, bootstrap/e156-setup.bat, docs/index.html, rules/{rules,e156,advanced-stats,lessons}.md, scripts/install-{sentinel,overmind,projectindex}.ps1 + push-portfolio.py, memory/ scaffold, AGENTS.md + per-agent pointers

**Summary**: 2 P0, 7 P1, 4 P2. **NOT "one of the best in the world" by absolute measure. Defensible rank: top-3 in the narrow niche of "AI-agent quality-stack bootstrap for research students". Not competitive against general dotfile managers (Chezmoi, home-manager).**

---

## P0 — Critical

- **P0-1** [Security Auditor]: Unsigned `.bat` + unsigned `.ps1` installer downloaded from GitHub over HTTPS. SmartScreen is the only gate, and the landing page teaches students to bypass it ("More info → Run anyway"). **This trains students to ignore the exact dialog that protects them from real malware.** Chocolatey and Scoop are unsigned too and have the same problem, but they're not recommending bypass in their install docs. Suggested fix: either (a) get an Azure Trusted Signing cert (~$10/month, not $400/year as assumed), or (b) restructure so students run `powershell -c "iwr … | iex"` where the inner script is SHA-pinned in the landing page itself — then SmartScreen never fires and tampering requires compromising github.com.

- **P0-2** ~~[African-Student Reality Check]: ... pull 200 MB of dependencies ...~~ **DOWNGRADED — finding was wrong about magnitude. Resolved by measurement (2026-04-21).**
  - Actual measured size of Sentinel + Overmind fresh-install: **4.5 MB total** (Overmind 2.0 MB, psutil 844 KB, pyyaml 796 KB, sentinel 541 KB, bin/ 216 KB, dist-info ~140 KB). Method: `pip install --dry-run --ignore-installed --target <scratch>` against both packages on a clean target; then real install + `du -sh`.
  - On a 500 MB monthly cap that's **0.9% of the budget**, not "a week's data". The original P0 framing was a worst-case hypothesis I never measured.
  - **Decision (per AGENTS.md "don't design for hypothetical future requirements"):** ship no preflight code. Tripwire instead: TODO comments in `scripts/install-sentinel.{ps1,sh}` + `scripts/install-overmind.{ps1,sh}` flag that if dependency footprint grows past ~50 MB (e.g. Overmind adds numpy/scipy/torch), the `--estimate-mb` preflight should be added then. Until that happens, the ~5 MB cost is below the threshold where any UX warning helps.

---

## P1 — Important

- **P1-1** [Dotfiles Veteran]: **16 hardcoded Mahmood-specific paths** in `rules/*.md` + `AGENTS.md` (`C:\E156\`, `C:\ProjectIndex\`, `C:\Sentinel\`, `C:\overmind\`, `mahmood726-cyber`). Students either replicate the exact layout or mentally substitute. Chezmoi solves this with templating (`{{ .chezmoi.homeDir }}`). Fix: template the rules with `{{USER_GITHUB}}`, `{{PROJECTINDEX_ROOT}}`, etc., rendered by `install.ps1`.

- **P1-2** [Windows DevX]: **No auto-update.** Scoop has `scoop update`. Chocolatey has `choco upgrade`. Here the student runs `e156-setup.bat` once and is frozen at v0.7.0; new rules / new Sentinel rules / new Overmind versions never reach them. Fix: ship `scripts/update-ecosystem.ps1` that re-downloads latest release and re-runs install with `-Force -NonInteractive`.

- **P1-3** [Windows DevX]: **Windows-only.** Half the target audience may use Linux (shared lab machines often are). `install.sh` + `install-*.sh` parity is a 2-day port that ~doubles addressable students. Not shipping it is the single biggest scope choice.

- **P1-4** [Software Engineer]: **No `.bat` tests.** 121 lines of shell orchestration with 4 failure modes (no Python, download fail, extract fail, install.ps1 fail) and zero automated coverage. Pester covers install.ps1; nothing exercises the bat. Fix: a BATS (bash-like) test or a PowerShell Pester harness that invokes `cmd /c e156-setup.bat` with mocked network layer.

- **P1-5** [Software Engineer]: **No rollback in install.ps1.** If Sentinel chain fails mid-pip-install, the student is left with half-installed pip packages and a warning. `install/install.ps1` for `e156-student-starter` has `Invoke-Rollback`; this one does not. Grep: `grep -c "rollback" install.ps1` returns 0.

- **P1-6** [AI-Agent Ecosystem Reviewer]: **Rules quality vs. alternatives.** The curated rules (rules.md, lessons.md, advanced-stats.md) ARE the standout. Compared to `awesome-cursorrules` or vanilla Cursor community `.cursorrules` files, these are tighter, incident-backed, with *why*-lines. But: `AGENTS.md` line "Anti-simulation: no hardcoded research outputs" is a principle Cursor/Claude rules libraries don't articulate. **This is the genuine contribution.** If anything ships separately, it's the rules. Consider a standalone `agent-rules-research-science` repo.

- **P1-7** [Product Manager]: **No install telemetry or success signal.** You will never know whether 5 or 500 African students succeeded. No `install-completed` ping (even anonymous), no crash-report URL, no feedback form on the landing page. Fix: a tiny opt-in `student doctor --report` that posts a redacted success+error summary to a GitHub Issues-backed endpoint.

---

## P2 — Minor

- **P2-1** [UX/Accessibility]: Landing page is clean but not mobile-audited; `pre` blocks overflow on narrow screens (no `word-wrap`). Students on low-end phones browse GitHub pages daily.
- **P2-2** [Software Engineer]: `install-projectindex.ps1` writes template files as UTF-8-no-BOM via `System.Text.UTF8Encoding $false` (correct), but `docs/HASH.txt` is written by the ecosystem repo's `sha256sum | awk` pipeline which emits LF; CRLF-drift on git warnings each commit. Not a bug, cosmetic.
- **P2-3** [Windows DevX]: `-Full` flag doesn't also imply `-NonInteractive`. A CI run with `-Full` still has the sub-installers' own prompts live. Fix: `-Full` should `-NonInteractive` the sub-installers.
- **P2-4** [AI-Agent Ecosystem Reviewer]: No `.cursorrules` or `.continuerc` generated. Cursor and Continue users are a real chunk of the student population; they can read AGENTS.md but Cursor specifically looks for `.cursorrules`.

---

## Persona pushback (where they disagreed)

**Dotfiles Veteran vs. Product Manager:** DV: "This is a dotfiles-replacement and loses to Chezmoi on every axis — templating, cross-platform, encrypted secrets, diff/apply loop." PM: "Chezmoi doesn't target AI-agent rules + Sentinel + Overmind as a stack. The integration is the product. Wrong benchmark."
**Consensus:** Both right. Against Chezmoi for "my personal env": loses. Against Chezmoi + Cursor rules + Sentinel setup docs + Overmind quickstart — all installed separately: wins on integration.

**Security Auditor vs. African-Student Reality:** SA: "Teaching students to bypass SmartScreen is negligent." ASRC: "The realistic alternative is they DON'T install at all. SmartScreen bypass is the smallest harm." **Consensus:** Ship Azure Trusted Signing ($10/mo is within any research budget); this is P0 precisely because it's cheap to fix.

---

## Final consensus verdict

**"One of the best in the world"? No — qualified.**

- **In the niche of "AI-agent quality-stack bootstrap for research students on Windows"**: plausibly top-3. The integrated fail-closed Sentinel→Overmind→TruthCert chain is genuinely novel as a package. I cannot name another starter that does this.
- **Against general dotfile managers (Chezmoi, home-manager, yadm)**: not competitive. Windows-only, no templating, no sync loop.
- **Against community rule collections (awesome-cursorrules, Continue rule packs)**: the *content* of `rules/*.md` is above-median — incident-backed, specific, actionable. The *packaging* (installable bootstrap) is above-median. Together: competitive.
- **World-class bar**: requires Linux parity, code signing, templated paths, auto-update, opt-in telemetry, and the P0-2 bandwidth fix. All are 1-2 day tasks individually. A week of focused work moves this from "top-3 in niche" to "defensible world-class in niche".

**Honest one-liner**: the *rules content* is the durable artifact and deserves to ship as a standalone repo. The *installer* is good engineering for a first-year research student on Windows but would need a week's polish to be pointed at by someone like Simon Willison or Harper Reed without caveats.
