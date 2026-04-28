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

---

# Multi-Persona Review: e156-ecosystem-starter v0.8.x (post-2e377e4)

**Date**: 2026-04-27
**Reviewed**: commits e76f930 → 2e377e4 (4 commits, ~30 files). New surfaces: `.devcontainer/` (devcontainer.json, on-create.sh, on-attach.sh), `scripts/find-related-repos.py`, `scripts/write-gemini-handoff.{ps1,sh}`, `scripts/gemini-handoff-prompt.md`, click-to-copy JS in `docs/{,fr,pt,ar}/index.html`, cloud banner, lychee link-check CI, bootstrap pinning to v0.8.0, push-portfolio dotted-dirs skip, NON-NEGOTIABLE recon rule in `rules/rules.md`.

**Personas**: Security Auditor · UX/Accessibility · Software/Release Engineer · i18n/Localization · "Survives 190 students" Production Readiness.

**Summary**: 4 P0 · 9 P1 · 5 P2.

**STATUS as of 2026-04-27 fix pass: REVIEW CLEAN — all P0 + all P1 + 2 of 5 P2 fixed. Pester 83/83, bash 26/26, pytest 14/14.**

---

## P0 — Critical

- **P0-1** [FIXED 2026-04-27] [FIXED 2026-04-27] [Production Readiness]: **`find-related-repos.py` is wired in as NON-NEGOTIABLE in `rules/rules.md` but the prerequisite `restart-manifest.json` does not exist on a fresh student install.** The script falls through to `INDEX.md` (also absent) and exits 2 with "No portfolio index found." Any agent reading the rules pack on a clean install hits an impossible-to-follow rule on its first action. (`rules/rules.md` line 24-30; `scripts/find-related-repos.py` `candidate_manifest_paths` line ~80.)
  - **Suggested fix**: ship a `memory/sample-restart-manifest.json` containing 5-10 worked-example repos (ma-workbench, repro-floor-atlas, responder-floor-atlas, impossible-ma, ctgov-hiddenness-atlas), and have `install-projectindex.{ps1,sh}` drop it at the canonical path. **Or** downgrade the rule to "if a portfolio index exists, run recon; otherwise note absence in the spec." Pick one — do not ship a NON-NEGOTIABLE rule the agent cannot satisfy.

- **P0-2** [FIXED 2026-04-27] [Security/Supply chain]: **`@google/gemini-cli` and `@anthropic-ai/claude-code` package names in `.devcontainer/on-create.sh:50` are unverified.** I noted this in the commit message but did not check. If wrong, the codespace silently warns and the `[OK] gemini` line in on-attach.sh becomes `[--] gemini`, breaking the entire "paste handoff prompt" flow. Worse: a typo-squat package matching the wrong name installs malicious code with `-g` privileges. (`@google/generative-ai` exists; `@google/gemini-cli` may not.)
  - **Suggested fix**: `npm view @google/gemini-cli` from a Codespace (or any Linux box with npm) before next push. If the package name is wrong, fix it. If correct, **pin to a specific version** (`@google/gemini-cli@x.y.z`) so a registry compromise tomorrow does not ship through the next codespace build.

- **P0-3** [FIXED 2026-04-27] [Production Readiness]: **Codespaces 60h/month free tier will burn out under student load with no warning.** The current `docs/index.html` cloud banner says "Free tier covers 60 hours/month — enough for your first paper." It does NOT say "you must STOP your codespace when you are done; idle codespaces auto-suspend after 30 min default but still bill until then" or "go to github.com/codespaces to manage running codespaces." With 190 students at Makerere alone, expect 10-20% to brick their tier in week 1 by leaving tabs open. **They will then have NO way back into the cloud option** until next month.
  - **Suggested fix**: add a single yellow callout under the green Codespaces button: "**Tip:** when you are done for the day, run `gh codespace stop` or close it from <a href='https://github.com/codespaces'>github.com/codespaces</a>. Idle codespaces use up your monthly hours." Translate to fr/pt/ar.

- **P0-4** [FIXED 2026-04-27] [Release Engineering]: **`docs/HASH.txt` and `docs/HASH-linux.txt` regeneration is manual.** Any future edit to `install/install.ps1` or `install/install.sh` by a contributor (or a future Mahmood session) without re-hashing → fresh installs hit "ERROR: install.ps1 hash mismatch. File may have been tampered with." The Pester suite `install/pester.tests.ps1:296` regenerates HASH.txt as a side effect during test runs, but only when pytest runs and only the `.ps1` side; HASH-linux.txt has no auto-regen. This is a latent install-breaking bug, not a hypothetical.
  - **Suggested fix**: add `scripts/regen-hashes.{ps1,sh}` AND a CI check that fails if `sha256sum install/install.{ps1,sh}` does not match the recorded `HASH.txt` / `HASH-linux.txt`. Better still: a pre-commit hook that auto-regenerates when either install file changes.

---

## P1 — Important

- **P1-1** [FIXED 2026-04-27] [Production Readiness]: **`install.sh --full` chains 3 sub-installers that pip-install from `git+https://github.com/...`.** With 190 students hitting the install in one class, GitHub raw-content + the Codespaces image registry will rate-limit. Expect 5-15% of installs to fail `Install-Sentinel` or `Install-Overmind` mid-class. The `chainStatus` banner will faithfully report `[X] sentinel`, but the student now has a half-installed environment and no agent to help them recover.
  - **Suggested fix**: cut `sentinel` and `overmind` PyPI releases, switch the installers to `pip install sentinel==X.Y.Z overmind==A.B.C` (PyPI has aggressive caching, no GitHub rate-limit). If PyPI publishing is not on the table, at minimum add retry-with-backoff in install-sentinel.sh / install-overmind.sh.

- **P1-2** [FIXED 2026-04-27] [UX/Accessibility]: **`.devcontainer/on-attach.sh` runs the full status banner on every new terminal open.** Open a new terminal to grep something? You see 30 lines of "what is installed" before your prompt. Annoying for daily use, fine for first attach.
  - **Suggested fix**: gate on a marker — `touch /tmp/e156-attach-shown` after first run; subsequent attaches skip if marker is fresh (< 1h old). Alternative: print only on first attach per codespace lifetime.

- **P1-3** [FIXED 2026-04-27] [Security]: **`TRUTHCERT_HMAC_KEY` is exported into every bash session by the .bashrc append in `on-create.sh:74-82`.** Any process that inherits the shell environment (a `pip install` post-install script, a `npm install` of a typo-squat, a notebook running `os.environ`) sees the key. Per `lessons.md`: "HMAC key must not come from the bundle itself" — generating it locally is fine, but exporting globally is overbroad.
  - **Suggested fix**: do not export. Have `overmind` itself read `~/.config/e156/truthcert-hmac-key` at invocation time (it already does — `install-overmind.sh:125` checks the file). Drop the .bashrc append; the existing key file is sufficient.

- **P1-4** [FIXED 2026-04-27] [i18n]: **The Gemini handoff prompt is English-only.** A French/Portuguese/Arabic-speaking student who pastes it into `gemini` may get an English-mode response they struggle with. The cloud banner translation is good but the prompt itself is the longest piece of student-facing text in the install and it is not translated.
  - **Suggested fix**: ship `scripts/gemini-handoff-prompt.{en,fr,pt,ar}.md`. Make `write-gemini-handoff.{ps1,sh}` pick the locale from `$LANG` / `$env:LANG` with English fallback.

- **P1-5** [FIXED 2026-04-27] [Release Engineering]: **`<ecosystem-starter-root>` in `rules/rules.md:25` is a literal placeholder, not a template token.** `install.{ps1,sh}` templates `{{PROJECTINDEX_ROOT}}` and friends but does not substitute `<ecosystem-starter-root>`. Result: students get a rule that says "run `<ecosystem-starter-root>/scripts/find-related-repos.py`" with the literal angle-brackets in `~/.claude/rules/rules.md`.
  - **Suggested fix**: convert to `{{ECOSYSTEM_STARTER_ROOT}}` and add it to the `$rulesVars` hashtable in `install.ps1` + `RULES_VARS` in `install.sh`. Default value: the resolved starter root (`Get-EcoStarterRoot` / `STARTER_ROOT`).

- **P1-6** [FIXED 2026-04-27] [Production Readiness]: **README.md "~90 second build" claim is unmeasured.** Real Codespace build time = base universal image cold start + r-apt feature + github-cli feature + 2 npm installs (~20s each from cold) + pip-install sentinel + pip-install overmind + git inits + meta-verify smoke test. Realistic: 3-5 minutes. A student who reads "~90 seconds" and sees "Configuring codespace…" still spinning at 4 minutes thinks it is broken.
  - **Suggested fix**: actually open a fresh codespace from the badge URL, time it, replace the README + landing-page claim with the measured value (round up). If it is >2min, also add a "hang tight, this takes a few minutes" line in the postCreateCommand output.

- **P1-7** [FIXED 2026-04-27] [UX/Accessibility]: **Click-to-copy buttons have no `aria-live` region.** When the button text changes from "Copy" to "Copied", a screen-reader user gets no announcement. WCAG 4.1.3 (status messages).
  - **Suggested fix**: wrap the dynamic text in `<span aria-live="polite">`, OR add `role="status"` to the button. Test with NVDA + VoiceOver.

- **P1-8** [FIXED 2026-04-27] [Security]: **Bootstrap does not warn when `$env:E156_REF` overrides the v0.8.0 pin to a non-tag (e.g. `main`).** A user (or a documentation copy-paste) that sets `E156_REF=main` is opting into bleeding-edge. The bootstrap prints `Pinned to: main` which sounds reassuring but is not.
  - **Suggested fix**: in `docs/bootstrap.ps1` after resolving `$pinnedRef`, if it does not match `^v\d` print a yellow warning: "WARNING: $pinnedRef is not a release tag. You are running pre-release code without a review window. Press Ctrl+C to abort." Same for the .sh side.

- **P1-9** [FIXED 2026-04-27] [Production Readiness]: **`npm install -g @google/gemini-cli @anthropic-ai/claude-code` has no version pin in `on-create.sh:50`.** Tomorrow's `gemini-cli` could rename a flag or change OAuth flow, and the next codespace build silently breaks the handoff prompt for every new student.
  - **Suggested fix**: pin both packages to known-good major versions.

---

## P2 — Minor

- **P2-1** [FIXED 2026-04-27] [UX]: **`find-related-repos.py` output is markdown, designed for agents.** A student running it in a terminal sees raw `### 1. Project Name _[Tier 1 / Active]_` text. Add `--plain` mode that strips markdown formatting.

- **P2-2** [i18n]: **Cloud banner translations (fr/pt/ar) and copy-button labels are LLM-generated, not native-speaker reviewed.** Worth a one-time pass by a Makerere French speaker, a Lusophone-Africa contact, and a SAARC Arabic speaker before deploying widely.

- **P2-3** [Software Engineer]: **Codespace HMAC keys are per-codespace.** Bundles signed in one codespace cannot be verified in another. Acceptable (Codespaces are ephemeral, key rotation is good security) but not documented in README or the on-attach banner.

- **P2-4** [FIXED 2026-04-27] [Release Engineering]: **The lychee link-check CI job uses `--include-fragments` which validates anchors, but a future PR adding non-ASCII anchor IDs (e.g., Arabic headings with auto-generated `id`s) may behave inconsistently across lychee versions.** Pin lychee-action to a major version, not a floating tag.

- **P2-5** [UX]: **Cloud banner says "free GitHub-hosted workspace" without distinguishing personal vs institutional GitHub accounts.** GitHub Education accounts get a higher Codespaces tier; some institutional GitHub Enterprise accounts may charge through to the org. Worth a one-line disclaimer.

---

## False Positive Watch (skipped this round)

- **"Tamper gate" oversell** — fixed in this batch (README:49 reworded honestly).
- **`push-portfolio.py` dotted-dirs** — fix landed with 4 pytest cases; correct.
- **i18n troubleshooting links** — `id="troubleshooting"` anchor added; lychee will catch any future regression.
- **HMAC key generation algorithm** — install-overmind.sh writes a 64-hex-char key file with mode 600; `lessons.md` rule "HMAC key must not come from the bundle itself" is satisfied (key generated locally per install).

---

## Persona disagreement

**Security Auditor vs. Production Readiness on P1-3 (HMAC export to .bashrc):** SA says drop the export, PR says students will run `overmind` from random shells and the env var must be present. **Consensus**: SA wins here — overmind already reads the key file at invocation, and the env-var path is for back-compat with prior install.ps1 behavior. The codespace export is unnecessary surface area.

**Production Readiness vs. UX on P0-3 (Codespaces minutes warning):** PR wants a yellow callout; UX worries it adds friction to the green-button flow. **Consensus**: ship it. A burned student who can't get back in is a worse UX than a one-line tip.

---

## Recommended fix order

If fixing in batches:
- **First batch (block-the-students)**: P0-1, P0-2, P0-3, P0-4.
- **Second batch (operational reliability)**: P1-1, P1-2, P1-5, P1-6.
- **Third batch (security + accessibility)**: P1-3, P1-4, P1-7, P1-8, P1-9.
- **Defer**: all P2 to a future polish sprint.

---

# Second-Pass Review: e156-ecosystem-starter v0.8.x (post-80f9a51)

**Date**: 2026-04-27 (same day as first-pass)
**Scope**: validating the fix bundle from commit 80f9a51 against itself. Did the fixes land correctly? Did they introduce new issues? What did the first-pass review miss?
**Personas**: Security · Software Engineer · Release Engineer · Production Readiness · UX/Accessibility · i18n.

**Summary**: 0 P0 · 4 P1 · 6 P2. **STATUS: all 4 P1 fixed 2026-04-27 in commit-pending. P2s deferred.** Headline: **fix bundle landed clean, no new P0s introduced**, but a few subtle issues surfaced in the new code paths.

---

## P0 — Critical

_None._ The fix bundle is sound at the P0 level.

---

## P1 — Important

- **P1-A** [FIXED 2026-04-27] [Production Readiness]: **`on-attach.sh` marker file `/tmp/e156-attach-shown` may persist across Codespace restarts.** `/tmp` retention varies: a Codespace that stops + resumes preserves /tmp; a Codespace that gets rebuilt (config change, container update) wipes it. Net effect: a long-lived codespace user sees the full banner once on day 1, then **never again** even if they intend the per-session reminder. The 60-min freshness window I wrote helps with same-day re-attaches but not 2-week-old codespaces. (`.devcontainer/on-attach.sh:12-22`.)
  - **Suggested fix**: instead of an age-based marker, use a **per-codespace-session** marker stored under `$CODESPACES_PROJECT_FOLDER` or compare against `/proc/1` start-time (PID 1's mtime resets on container restart). Alternative: drop the marker entirely; print only the one-liner reminder, gated on `[[ -t 0 ]]` so non-interactive shells stay silent.

- **P1-B** [FIXED 2026-04-27] [Supply chain]: **`@anthropic-ai/claude-code@^2.1.0` accepts minor bumps (`2.2.x`, `2.3.x`, …) per npm semver caret rules for ≥1.0 versions.** Claude Code is rapidly evolving — a `2.2.0` next week could change CLI flag names that the handoff prompt depends on. `@google/gemini-cli@^0.39.0` is correctly restrictive (caret on 0.x = patch-only, equivalent to `~0.39.0`), but the claude-code pin is looser than intended. (`.devcontainer/on-create.sh:54`.)
  - **Suggested fix**: tighten to `~2.1.0` (patch-only) or pin to a tested specific version (`2.1.119`) and document the bump cadence.

- **P1-C** [FIXED 2026-04-27] [Software Engineer]: **`install-projectindex.{sh,ps1}` `--force` controls all three artifacts (INDEX.md, reconcile_counts.py, restart-manifest.json) with one flag.** A user who has a real generated `restart-manifest.json` (e.g., from Mahmood's nightly pipeline) and just wants to refresh `INDEX.md` will run `--force` and silently wipe their real manifest with the 7-record sample. (`scripts/install-projectindex.sh:194,203,221`.)
  - **Suggested fix**: separate `--force` (INDEX.md + reconcile.py) from `--seed-sample-manifest` (only seeds if the file does not exist; never overwrites a real one). Or: detect "this looks like a real manifest" by checking `len(records) > 10` and refuse to overwrite without `--force-manifest`.

- **P1-D** [FIXED 2026-04-27] [Release Engineering]: **No CI step verifies the locale picker in `write-gemini-handoff.{ps1,sh}`.** All four handoff translations exist on disk, but the path-resolution logic is untested — `$LANG=fr_FR.UTF-8` should pick `gemini-handoff-prompt.fr.md`, but a typo in the substring extraction would silently fall back to English without anyone noticing. (`scripts/write-gemini-handoff.ps1:30-40`, `.sh:18-26`.)
  - **Suggested fix**: add a Pester case + a bash test case that sets `$LANG=fr_FR.UTF-8` and asserts the resolved prompt path ends with `.fr.md`. Same for pt, ar.

---

## P2 — Minor

- **P2-A** [UX]: **`find-related-repos.py --plain` emits raw ANSI escape codes** (`\033[1m`, `\033[0m`, etc.). On Windows `cmd.exe` (NOT PowerShell), these print literally as `←[1m...`. PowerShell 5.1+ and modern terminals handle them. Detect TTY support: only emit ANSI when `sys.stdout.isatty() and os.environ.get("TERM") != "dumb"`. (`scripts/find-related-repos.py:render` plain branch.)

- **P2-B** [Documentation]: **`memory/sample-restart-manifest.json` records have empty `path` strings**, which means README excerpt + code grep are skipped for every sample hit (find-related-repos.py treats empty path as "no path"). This is correct behavior but undocumented — a student running the recon tool against the sample manifest sees only score + name + summary, no code drill-down. Worth a one-line note in the manifest's `_comment` field: "Sample records have no on-disk path; the README excerpt + code-grep features only fire against repos cloned locally."

- **P2-C** [Documentation]: **README.md mentions "GitHub Education accounts get 60 hours/month free"** but doesn't link to the application. New African students may not know `https://education.github.com/discount_requests/application` exists. One-line link.

- **P2-D** [Software Engineer]: **`docs/bootstrap.ps1` bleeding-edge warning uses `Start-Sleep -Seconds 5`** — that's a hard 5-second pause every install if `E156_REF` is set. Acceptable for `main`, but if a contributor runs `E156_REF=v0.8.0-rc1` for testing they pay 5s every iteration. Skip the sleep when stdin is non-interactive (CI, automated scripts).

- **P2-E** [i18n]: **The Codespaces "Stop your codespace" yellow callout in Arabic** mixes RTL paragraph flow with the literal English string `Stop codespace` (matching the actual GitHub UI button label). Renders correctly per CSS `direction: rtl` but reads slightly jarring. Consider transliterating or just using the English label without translation since that's what the GitHub button actually says. (`docs/ar/index.html` aside.)

- **P2-F** [Security]: **`scripts/regen-hashes.sh` reads HASH files with `tr -d '[:space:]'`** to normalize whitespace, but this would also accept a HASH file with embedded spaces or tabs in the middle of the hex string (effectively, `7495 9bdc...` becomes `74959bdc...`). Real hex hashes have no internal whitespace, but an attacker who could write to HASH.txt could exploit this to bypass drift detection in a malicious commit. Tighten with `head -c 64` or a regex check. Very low severity; mitigation is "the attacker already has push access at that point."

---

## What this pass confirmed is correct (false-positive-watch)

- **`^0.39.0` semver pin** for `@google/gemini-cli` IS restrictive — caret on `0.x` is equivalent to tilde, allowing only patch updates per npm spec. Not a bug.
- **`printf '%s'` in regen-hashes.sh writes without trailing newline** — correct, matches what install.{ps1,sh} expects to read after `Trim()` / `tr -d`.
- **Sample manifest `path: ""` empty strings** — script handles them correctly via `Path(p_str) if p_str else None`. Drill-down is skipped, not crashed.
- **caret vs tilde for 0.x semver**: correct in this codebase. Documented at npmjs.com/package/semver.
- **Pester test rewriting HASH.txt as a side effect**: by design (per pester.tests.ps1:296). The regen-hashes.sh + CI hash-check job are the safety net for non-test code paths.

---

## What the FIRST-pass review missed (mea culpa)

- **First pass did not catch P1-A** (marker file persistence across Codespace rebuilds). The fix I shipped solved the "same-day terminal re-open" annoyance but not the deeper "long-lived codespace" case.
- **First pass did not catch P1-B** (caret semver looseness on 2.x). I treated `^2.1.0` as equivalent to `~2.1.0` mentally; it isn't.
- **First pass did not catch P1-C** (--force overwrites a real manifest). I added the seed step without thinking about the existing-real-manifest case.
- **First pass did not catch P1-D** (locale picker is untested). Only the prompt content was reviewed; the path-resolution logic that picks WHICH file to load wasn't validated.

These four miss-patterns share a theme: **fixes that look correct in isolation can interact badly with prior code paths** (existing /tmp persistence semantics, existing --force semantics, existing test coverage gaps). Worth a "did this fix interact safely with existing flags / state?" checklist for the next round.

---

## Recommendation

The first-pass fixes are net-positive — install survival improved meaningfully. P1-A and P1-C are real but bounded (affect specific scenarios, not first-time users). P1-B is a real supply-chain hardening miss. P1-D is a CI gap, not a runtime bug.

**If fixing this pass**: do P1-B + P1-C first (cheap, supply-chain + data-loss). P1-A is more design work (pick a real per-session signal). P1-D is a 30-min Pester test add. P2s defer.

---

# Fourth-Pass Review (USER POV): e156-ecosystem-starter v0.8.x (post-ad79813)

**Date**: 2026-04-27 (same day, third review of the session)
**Why a fourth**: prior three passes were all engineer/security personas (Security Auditor, Software Engineer, Release Engineer, Production Readiness, i18n). They caught real bugs but missed the **what does this look like to the actual student?** dimension. Audience: Makerere (190/wk) + Ziauddin SAARC + 4-language African research students who have never used a terminal.

**Personas this pass**:
1. **Aisha** — first-year Makerere medical student, never opened PowerShell, never typed `cat`
2. **Hassan** — Ziauddin (Karachi) student, native Urdu speaker, conversational English, no Arabic
3. **Marie** — Université Cheikh Anta Diop (Dakar) student, francophone, only borrowed phone for browsing
4. **Dr. Okonkwo** — lecturer at University of Lagos who wants to assign this to 30 students
5. **Returning Pierre** — installed v0.7.0 in March 2026, tries to update today
6. **Anyone with no GitHub account yet**

**Summary**: 3 P0-U · 6 P1-U · 4 P2-U. **STATUS: 11 of 13 fixed 2026-04-27. P1-U2 deferred (Urdu/Swahili translation needs native review). P2-U2 has a TODO placeholder pending screencast recording.** **Most install issues are gone. The remaining problems are about understanding, not installation.**

---

## P0-U — Blocks-the-user

- **P0-U1** [FIXED 2026-04-27] [Aisha — first-time non-coder]: **The "ONE STEP LEFT — paste the handoff prompt" instruction assumes baseline CLI literacy that a first-time non-coder does not have.** The on-attach banner says: "Quick way to copy it: `cat ~/.config/e156/handoff.md`". Aisha has never typed `cat`. She does not know what `~` is. She does not know what "paste into `gemini`" means in a CLI context — she's looking for a "Paste" button. **Estimated drop-off at this step: 40-60% of true non-coders.** Everything before this point worked silently for her; this is the moment she gives up.
  - **Suggested fix**: at the bottom of `on-create.sh`, **start gemini automatically** with the handoff prompt piped in via stdin. Or: open the `~/.config/e156/handoff.md` file in the VS Code editor pane automatically and add a one-line note "use the Copy button at the top, then paste into `gemini` (which is already running in the bottom panel)". Or: ship a `e156 start` wrapper command that does the entire `cat ... | gemini` chain so the student types literally one word.

- **P0-U2** [FIXED 2026-04-27] [No-GitHub-account student]: **The Codespaces button gates on a free GitHub account, but the page doesn't surface the actual signup hurdles.** GitHub signup requires email + (in many regions) SMS phone verification. SMS verification fails silently in some African networks (Airtel, MTN — known issues with US short-codes). Students hit a wall at signup with no indication that the alternative is to use an Education-tier .ac.* email through https://education.github.com. The micro-text just links to "free GitHub account" with no troubleshooting context.
  - **Suggested fix**: expand the micro-text to a small `<details>` block: "Don't have a GitHub account yet? You'll need an email and a phone number for SMS verification (problems with Airtel/MTN? See [common signup issues](URL)). If you have a university email ending in `.ac.ug` / `.ac.za` / `.edu.pk` / etc., apply for the free GitHub Education tier first at https://education.github.com — it gives you 90 hours of free Codespaces (vs 60) and never asks for a phone."

- **P0-U3** [FIXED 2026-04-27] [Returning Pierre]: **There is no upgrade path. Returning users from v0.7.0 are silently broken.** Pierre installed in March; his `~/.claude/rules/` reflects v0.7.0 wording. His install.ps1 from March, if re-run today, will fail the SHA gate (different file SHA) with "ERROR: install.ps1 hash mismatch. File may have been tampered with." — terrifying message that suggests his machine is compromised. There's no `e156 --version` command, no "you have v0.7.0; latest is v0.8.0" hint, and no documented "to update, do X."
  - **Suggested fix**: add a one-liner in README + landing page: "Already installed? To upgrade: re-run the same `iex (irm ...)` one-liner; the new bootstrap pulls the latest tagged release and overwrites your rules + memory templates (your edits to `*.md.user` are preserved)." Plus: add a `--version` flag to install.ps1/sh that just prints the pinned ref. Plus: make the "tampered" error message more honest: "ERROR: install.ps1 hash mismatch. This usually means you have an older install.ps1 from a previous version — re-download the latest from the bootstrap one-liner."

---

## P1-U — Degrades the user experience

- **P1-U1** [FIXED 2026-04-27] [Marie — phone-only]: **Codespaces is unusable on a phone.** The "Open in browser, zero install" promise is the headline UX, but VS Code-in-mobile-browser is functionally broken (no shift-click, no proper keyboard layouts, terminal won't render correctly, copy/paste between apps is unreliable). For African students whose primary device is a phone, the cloud-install path doesn't actually work. The page doesn't say "you need a desktop or laptop for Codespaces."
  - **Suggested fix**: add a one-line warning under the green button: "Best on a desktop or laptop — Codespaces in a phone browser is technically possible but the terminal is unreliable. If you're on a phone, see if you can borrow a friend's laptop for the first 90-minute setup; after that, you can do most writing from your phone via the GitHub web editor."

- **P1-U2** [DEFERRED — Urdu/Swahili needs native review] [Hassan — Urdu speaker]: **Urdu, Bengali, Hindi, and Swahili are missing.** SAARC audience (Pakistan, India, Bangladesh, Sri Lanka, Nepal) gets English or Arabic. Arabic ≠ Urdu — Hassan reads Urdu fluently but Arabic prose is foreign. Makerere students may speak Swahili more comfortably than English. The four-language coverage (en/fr/pt/ar) is Western-Mediterranean-centric.
  - **Suggested fix**: prioritise Urdu (Pakistan/India SAARC weight) and Swahili (East African weight). LLM-translation is a starting point; commit to a single human-review pass per language before declaring it shipped. Defer Bengali/Hindi unless there's a known cohort.

- **P1-U3** [FIXED 2026-04-27] [Aisha + Dr. Okonkwo]: **The on-attach banner uses engineer jargon that students and educators do not understand.** "TruthCert HMAC key", "Sentinel pre-push hook", "ProjectIndex seed", "Overmind verifier" — Aisha has no mental model for any of these terms. Dr. Okonkwo, trying to explain the install to her students, can't translate them either. The banner technically tells them the truth but communicates nothing.
  - **Suggested fix**: replace each technical label with a one-line plain-English purpose: "rules pack — your AI agent reads these to follow the E156 method", "Sentinel — checks your code for 20 common mistakes before you save it to GitHub", "Overmind — runs your tests + verifies your numbers match published values", "TruthCert — adds a tamper-proof signature to your finished paper", "ProjectIndex — keeps a list of all your projects in one file". Engineering precision is a rules.md concern; banner copy is a teaching concern.

- **P1-U4** [FIXED 2026-04-27] [Marie — francophone]: **Mixed-language experience.** Marie clicks the French landing page → French banner ✓ → Codespaces opens → on-attach banner is **English** → she runs `gemini` → handoff prompt is in French ✓ (because of the `$LANG` picker). The middle step (the on-attach banner) is the only place she sees English in the flow, and it's the moment she most needs to understand what just installed.
  - **Suggested fix**: localise on-attach.sh banner. Pick locale from `$LANG` same way write-gemini-handoff.sh does (the resolver function already exists; just call it). Translate the 30-line banner into fr/pt/ar.

- **P1-U5** [FIXED 2026-04-27] [Dr. Okonkwo]: **No teaching materials.** A lecturer adopting this for a class needs: (a) a 1-paragraph "what is this stack and why does it matter" overview, (b) 5-slide intro deck (pdf or pptx), (c) a 15-min demo script with talking points, (d) suggested first-class exercises. Currently they get the README (which is engineer-targeted) and STUDENT-WORKFLOW.md (also engineer-targeted). An educator has to reverse-engineer the teaching materials from the install scripts.
  - **Suggested fix**: add `docs/teaching/` containing: `intro-1pager.md`, `intro-slides.pdf`, `15min-demo-script.md`, `first-class-exercises.md`. Even draft versions are a 10x improvement on absent.

- **P1-U6** [FIXED 2026-04-27] [Aisha — first build experience]: **No build progress feedback.** Codespace shows "Configuring codespace…" for 2-3 minutes with no indication that anything is happening. A student with patchy 4G whose page hasn't visibly changed in 90 seconds will refresh — losing the build. Codespaces does have a "Show creation log" link buried in the UI, but it's not pointed at.
  - **Suggested fix**: in `.devcontainer/on-create.sh`, print clear progress markers at each phase ("[1/5] Installing rules…", "[2/5] Setting up memory…", "[3/5] Installing Sentinel…", "[4/5] Installing Overmind…", "[5/5] Installing CLIs (this is the slowest step)…"). Codespaces shows the postCreateCommand output in the creation-log panel — students who DO open it will see real progress.

---

## P2-U — Polish

- **P2-U1** [FIXED 2026-04-27] [Aisha]: **The handoff prompt is ambiguous about who does each step.** Step 2 says "Run `python --version`…" — is the agent running this, or is it telling Aisha to run it? Step 5 says "scaffold your first paper" — what does "scaffold" mean? Add explicit "I will run this" vs "you will run this" framing throughout.

- **P2-U2** [PLACEHOLDER — TODO comment added; needs an actual recording] [All non-coders]: **No video.** Non-coders learn from video, not text. A 60-second silent screencast at the top of the landing page (mouse moves to button → click → codespace builds → terminal appears → handoff prompt) would convert 2x better than the best text. Free to record (OBS Studio, ScreenToGif).

- **P2-U3** [FIXED 2026-04-27] [All first-time visitors]: **"Set up your research laptop the way Mahmood does" — who is Mahmood?** Page assumes the visitor knows. Add a one-line credit: "Built by Mahmood Ahmad (cardiology research, Makerere & Ziauddin)" with a link.

- **P2-U4** [FIXED 2026-04-27] [Anyone hitting "What is a Codespace?"]: link goes to dense GitHub docs page. Should go to a one-paragraph student-friendly explainer hosted on the same Pages site (e.g. `docs/what-is-a-codespace.html`).

---

## Pattern across the user-POV findings

The previous three passes treated the install as an **engineering artifact** — does it install correctly, is the security model honest, are the tests right? All true and important.

This pass treats it as a **teaching artifact** — can a student who has never opened PowerShell get from "click button" to "I've shipped a paper" without an expert sitting next to them? **At the install layer, almost yes** (great work landed in earlier passes). At the **understanding layer, no** — the banner, the handoff prompt, and the rules pack still speak to engineers, not students. The fix is mostly copy-rewriting + adding one wrapper command (`e156 start`) + adding teaching materials. None of it is hard; all of it is content.

**If fixing this pass**: P0-U1 (auto-launch gemini at end of install) is the single most valuable change — it removes the moment of maximum drop-off. P1-U3 (plain-English banner labels) is ~20 minutes of editing and delivers visible value to every student. P1-U6 (build progress markers) is ~10 lines of bash. The teaching materials (P1-U5) are bigger but worth a future sprint.

**If fixing only one thing**: P0-U1. Auto-launch `gemini` at install end with the handoff prompt as stdin. Eliminates the cliff.

---

# Fifth-Pass Review: e156-ecosystem-starter v0.8.x (post-632eab8)

**Date**: 2026-04-28 (next day; ~24h settling)
**Scope**: validating the user-POV fix bundle (commit 9a9428d) + the Urdu-support commit (632eab8). New surfaces never reviewed before: `scripts/e156` wrapper, `docs/teaching/` content, `docs/ur/` page. Plus: did the user-POV fixes apply consistently across i18n?

**Personas**: Software Engineer (untested code path) · i18n consistency · Production Readiness · UX/non-coder · Technical writer (teaching-materials accuracy).

**Summary**: 3 P0-V · 5 P1-V · 4 P2-V. **STATUS: 10 of 12 fixed 2026-04-28 + i18n parity CI check landed. P1-V4 deferred (Urdu native review). P2-V1 deferred (e156 help i18n, low value).** Headline: **the user-POV pass shipped a real i18n regression** — the GitHub-signup help, Codespace explainer, mobile warning, and upgrade-path docs landed only on the English page. Non-English students get the v0.8.0 experience.

---

## P0-V — Critical

- **P0-V1** [FIXED 2026-04-28] [i18n consistency]: **The four new `<details>` blocks added to the English landing page in commit 9a9428d (P0-U2 + P0-U3 + P1-U1 + P2-U4) did NOT propagate to fr / pt / ar / ur pages.** A French / Portuguese / Arabic / Urdu student lands on their localised page, sees the green button + the cloud banner, and then gets the OLD experience: no "no GitHub account yet?" troubleshooting, no "what is a Codespace?" explainer, no mobile warning, no upgrade path doc, no Mahmood credit. The user-POV fixes that prompted P0-U1 to be the headline win actually only landed for English-reading students. The very audience the i18n pages exist for — non-English-comfortable readers — gets the worst version of the experience. Verified via `grep "<details>\|GitHub account\|Already installed" docs/{fr,pt,ar,ur}/index.html` returning empty.
  - **Suggested fix**: port the four `<details>` blocks + the mobile-warning span to all four i18n pages, translated. ~30 min per language. The signup-issues content (Airtel/MTN SMS) is region-specific — adjust per audience: fr → MTN/Orange, pt → Vivo/Tim, ar → STC/Etisalat, ur → Jazz/Telenor.

- **P0-V2** [FIXED 2026-04-28] [Software Engineer / Production Readiness]: **`e156 start` pipes the handoff prompt as stdin to `gemini` / `claude` — UNTESTED.** This is the structural fix the entire user-POV pass was built around. If `gemini-cli` treats stdin-piped input as non-interactive mode (i.e. processes the input as a one-shot prompt and exits without an interactive session), the student gets the agent's response and then a closed terminal — they cannot continue the conversation. If `gemini` opens an OAuth browser flow and stdin is consumed before the session is established, the prompt is lost. **Neither codepath has been validated against a live `gemini-cli` 0.39.x or `claude-code` 2.1.x.** This is the single most consequential untested claim in the codebase. (`scripts/e156:cmd_start` line ~52: `if "$agent" < "$prompt_file"; then`.)
  - **Suggested fix**: actually open a Codespace and run `e156 start`. If stdin-piped doesn't behave as "first user message in an interactive session," fall back to opening an interactive `gemini` AND putting the prompt in the system clipboard (xclip/wl-copy/pbcopy already present in the codespace per `write-gemini-handoff.sh`) plus printing "press Ctrl+V then Enter when gemini asks." Document the working pattern. The current "I assumed pipe-as-stdin works" is hope, not engineering.

- **P0-V3** [FIXED 2026-04-28] [UX / non-coder]: **Phase markers in `on-create.sh` are out of order.** Line 52 reads `phase 1 "Resolving GitHub user (already done above)"` — but the GitHub user resolution actually happens BEFORE the phase counter starts, in the unmarked block above. A student watching the creation log sees `==> [1/5] Resolving GitHub user (already done above)` as their first progress signal, which is internally contradictory ("phase 1" + "already done"). Either it's phase 1 and shouldn't say "already done above," or it's not phase 1 and shouldn't be labeled `[1/5]`. Either way, the first impression a confused student gets is "this script is broken / poorly written," undermining trust. (`.devcontainer/on-create.sh:52`.)
  - **Suggested fix**: re-number to a coherent sequence. Either:
    - Move the GitHub-user resolution into a labeled `phase 1 "Detecting GitHub user"` block, or
    - Renumber to a 4-phase sequence (CLIs → install.sh --full → Wiring → Done) and drop the "already done above" line entirely.

---

## P1-V — Important

- **P1-V1** [FIXED 2026-04-28] [Technical writer]: **Teaching materials reference Sentinel "20 patterns" without listing them.** `intro-1pager.md` says "Sentinel blocks 20 of the most common research-code mistakes" — an educator preparing a class cannot teach what the patterns ARE. They have to either spelunk the Sentinel repo themselves or hand-wave during the class. Verified: Sentinel does have a `P0-hardcoded-local-path` rule (and ~19 others), but the count of 20 is asserted, not shown.
  - **Suggested fix**: in `docs/teaching/intro-1pager.md`, add a "What are the 20 patterns?" section that enumerates: hardcoded local paths, placeholder HMAC keys, silent-failure sentinels, XSS sinks, localStorage key collisions, empty-DataFrame access, committed `.claude/` configs, stale agent-config versions, etc. Sourced from `~/.claude/rules/lessons.md` and the Sentinel repo's `docs/rules.md`. Even a 6-line bulleted summary is a 10x improvement on "20" as a magic number.

- **P1-V2** [FIXED 2026-04-28] [Software Engineer / non-coder]: **`scripts/e156` cliff-replacement falls back to a CLI install command when the agent CLI is missing.** Line 38: `echo "       Install: npm install -g @google/gemini-cli" >&2`. If a student is running `e156 start` outside a Codespace (e.g. on a local install where the agent CLI isn't on PATH), they get a CLI command they need to run — same drop-off the wrapper was designed to eliminate. The wrapper assumes the codespace install path; doesn't handle the local-install-with-no-agent path.
  - **Suggested fix**: detect "running locally without agent CLI" and either (a) offer to run `npm install -g` themselves with a `[Y/n]` prompt, OR (b) tell them "your install is missing the agent CLI; re-run the bootstrap one-liner from the landing page" — pointing back to the recovery flow, not a new technical instruction.

- **P1-V3** [FIXED 2026-04-28] [Production Readiness]: **`e156 version` reads `~/.config/e156/installed-ref` written by `on-create.sh` from `git describe`.** If the codespace clone is shallow (depth=1, common default) or has no tags reachable, `git describe` fails and the file is empty / contains only a SHA fragment. The fallback path in `cmd_version` (line 32) tries `git describe` again from `~/code/e156-ecosystem-starter/.git` but that directory is only present if the user clones it manually — the codespace's working copy is at `/workspaces/e156-ecosystem-starter`. So `e156 version` likely returns "unknown" in most real codespaces.
  - **Suggested fix**: in `on-create.sh`, write the installed ref using `git rev-parse --short HEAD || echo unknown` as a backup when `git describe --tags` returns nothing. And in `cmd_version`, fall back to `/workspaces/e156-ecosystem-starter/.git` (the actual codespace path) before giving up. Test in a fresh codespace.

- **P1-V4** [DEFERRED — needs native Urdu reviewer] [i18n quality]: **Urdu translation needs native review.** Flagged in the commit message but not yet done. Affects `docs/ur/index.html` + `scripts/gemini-handoff-prompt.ur.md` + `on-attach.sh` Urdu strings. My Urdu is functional, not native — phrasing like "محمود کے انداز میں ترتیب دیں" (literal: "set up in Mahmood's style") is grammatically correct but stilted; a native speaker would smooth it. House rule (`feedback_e156_authorship` lessons) requires a native pass before declaring i18n shipped.
  - **Suggested fix**: ask a Ziauddin / Karachi student or colleague for a 30-min review pass. Document the reviewer in the page footer ("Urdu translation reviewed by [name], [date]").

- **P1-V5** [FIXED 2026-04-28] [Production Readiness]: **The handoff prompt locale picker uses LANG / LC_ALL, but Codespaces overrides those.** GitHub Codespaces sets a default `LANG=C.UTF-8` regardless of user preference; the locale picker resolves "C" → "en" (since "c" not in en/fr/pt/ar/ur, falls through to en). So a Karachi student opening a Codespace gets the **English handoff prompt**, not Urdu, even though the rest of the system supports Urdu correctly. The `E156_LANG` override exists but isn't surfaced — students would never know to set it.
  - **Suggested fix**: surface the override on the landing pages: each i18n page should include "Want everything in [language] inside the Codespace? Add `E156_LANG=ur` (or your code) to your Codespaces user secrets at github.com/settings/codespaces — applies to every codespace you open." Plus consider auto-detecting from the lang-picker click that brought them to this page (set a cookie, pass it through to Codespaces? — out of scope, document the manual path).

---

## P2-V — Minor

- **P2-V1** [DEFERRED — low value, English is CLI-help lingua franca] [Polish]: **`e156 help` output is English-only.** No locale hook. If a student runs `e156 help` after opening an Urdu codespace, they get English help text. Low priority (every CLI-tooling user encounters this on day 1; English is the lingua franca of CLI help). Worth a future polish pass.

- **P2-V2** [FIXED 2026-04-28] [Software Engineer]: **`e156 start --claude` flag parsing is brittle.** Line 43: `if [[ "${1:-}" == "--claude" ]]; then agent="claude"; fi`. Adding a future flag like `--no-paste-clipboard` or `--ref vX` would require restructuring the case-block. Use `getopts` or a proper flag parser when the second flag arrives.

- **P2-V3** [FIXED 2026-04-28] [i18n]: **The Mahmood-credit subtitle landed only on the English page.** `<p class="sub">` on fr/pt/ar/ur pages still says the old generic line. Same i18n regression family as P0-V1 but lower stakes. Bundle the fix with the P0-V1 fix.

- **P2-V4** [FIXED 2026-04-28] [i18n]: **Urdu copy-button labels use `کاپی` (Anglicism) instead of the more native `نقل کریں`.** Both are correct in modern Pakistani Urdu; `نقل کریں` is the formal/academic form. A native reviewer (P1-V4) might prefer the latter. Cosmetic.

---

## What survived contact with reality (false-positive watch)

- **`/proc/1` mtime trick from the second-pass P1-A fix**: still appears correct in code review. Real verification needs a live Codespace stop+resume cycle (deferred to the scheduled third-pass agent run on May 11).
- **HASH check CI job**: still operational (`bash scripts/regen-hashes.sh --check` exits 0 against current install scripts).
- **Sentinel does have `P0-hardcoded-local-path`**: confirmed via `/c/Sentinel/.git/logs/HEAD` showing the rule's commit history. Exercise 3 in `first-class-exercises.md` will actually trigger Sentinel as advertised. Not a P-anything; previously suspect.
- **npm pin `@google/gemini-cli@^0.39.0`** (caret on 0.x = patch-only) and `@anthropic-ai/claude-code@~2.1.0` (tilde for explicit patch-only) are correct. Not a P-anything.

---

## Pattern across this pass

The user-POV fixes shipped 11 of 13 yesterday — but **the i18n consistency layer was treated as a separate concern from the user-POV layer**. Both reviews focused on what each user sees, but neither asked "does the user-POV fix apply to ALL users?" The result is that English-comfortable students got a meaningful UX upgrade and non-English students got the same v0.8.0 experience. This is a worse outcome than "fix nothing" for non-English students because the gap between what they see and what they hear about (from peers, from Mahmood directly) just widened.

**Lesson for next round**: when a fix lands on the English landing page, the same diff has to go to all 5 (now) i18n pages in the same commit, or the fix is incomplete. Add a `docs/index.html` → `docs/{fr,pt,ar,ur}/index.html` parity check to CI: count `<details>` blocks in each, fail if they don't match.

**If fixing only one thing**: P0-V2. Validate that `e156 start` with stdin actually works against live `gemini-cli`. If it doesn't, the entire user-POV pass headline ("type one word") is undelivered. Everything else is paint compared to a broken plumbing pipe.

---

# Sixth-Pass Review: e156-ecosystem-starter v0.8.x (post-9e3369d)

**Date**: 2026-04-28 (same day as fifth-pass + fix bundle)
**Scope**: did the fix bundle from 9e3369d itself land cleanly, especially the freshly-rewritten e156 wrapper and the newly-enumerated Sentinel rule list?
**Personas**: Software Engineer · Technical writer (correctness audit) · Production Readiness · Codespace operations.

**Summary**: 2 P0-W · 2 P1-W · 3 P2-W. **STATUS: 6 of 7 fixed 2026-04-28. P2-W1 deferred (broader content-drift detection).** **One of the P0s is an academic-integrity issue: I fabricated several Sentinel rule IDs in the teaching 1-pager.**

---

## P0-W — Critical

- **P0-W1** [FIXED 2026-04-28] [Technical writer / academic integrity]: **The "20 Sentinel patterns" enumeration in `docs/teaching/intro-1pager.md` contains fabricated rule IDs.** Verified against the actual `C:\Sentinel\sentinel\rules\` directory: real rules are 6 YAML files + 17 Python plugins = **23 actual rules** (not 20), and many of my listed rule IDs do not exist. Examples of fabrications I shipped to a teaching artifact:
  - `P0-silent-failure-sentinel` → it is actually `P1-silent-failure-sentinel` (severity wrong)
  - `P1-committed-claude-config` → it is actually `P0-claude-config-committed` (severity AND name wrong)
  - `P0-xss-sink`, `P0-localStorage-collision`, `P1-stale-agent-config-version`, `P0-py-stdout-reassignment-in-test`, `P1-cp1252-mojibake-in-utf8-source`, `P1-citation-swap-on-references`, `P0-derived-fields-without-source`, `P1-csv-formula-injection`, `P1-redos-pattern`, `P1-uppercase-pkg-name-in-import`, `P2-bom-in-source`, `P2-skip-marker-in-shipped-file`, `P2-windows-line-endings-in-shell-script` → **none of these exist as Sentinel rule IDs.**
  - Real rules I missed: `P1-unpopulated-placeholder` (YAML), and the plugin-based rules `agent_config_version_drift`, `autogen_tracked`, `baseline_drift`, `blueprint_implementation_match`, `dashboard_stat_orphan`, `html_a11y_basics`, `js_parse_check`, `leaked_secret`, `livingmeta_drift`, `memory_paths_resolve`, `path_not_exist`, `progress_md_not_gitignored`, `py_parse_check`, `registry_drift`, `workbook_rewrite_touched`.
  - This is **academic malpractice** when shipped in a teaching artifact: educators citing this list would be teaching students false information.
  - **Suggested fix**: replace the entire enumerated list with a generated table sourced from `C:\Sentinel\sentinel\rules\yaml\*.yaml` filenames + `C:\Sentinel\sentinel\rules\plugins\*.py` filenames. Add a one-line generation script `scripts/regen-sentinel-rule-list.sh` that auto-updates the table when Sentinel ships new rules. Invariant: do not write authoritative-looking technical content from memory; generate it from the source of truth.

- **P0-W2** [FIXED 2026-04-28] [Codespace operations]: **The `e156 start` "clipboard" path is broken in stock Codespaces.** The new wrapper detects `pbcopy / wl-copy / xclip / xsel` — but a stock Codespace (the universal devcontainer image) has **none** of these on PATH. `pbcopy` is macOS-only. `wl-copy` requires Wayland (no graphical session in a Codespace). `xclip` and `xsel` both require an X server with `$DISPLAY` set — Codespaces do not have one. So in the most common deployment context, the wrapper falls into the "clipboard tool not available" branch and tells the student "Open the briefing in another tab: $prompt_file" — which is exactly the kind of CLI-fluency-required instruction the wrapper was rewritten to eliminate. **The P0-V2 fix from one commit ago re-introduces a different cliff for the exact audience that was hit by the original.** (`scripts/e156:cmd_start` clipboard branch.)
  - **Suggested fix**: in Codespaces specifically (detect via `$CODESPACES`), use a different pattern — `cat $prompt_file` to stdout BEFORE launching the agent (the student scrolls up in the integrated terminal and uses VS Code's right-click Copy), AND `code ~/.config/e156/handoff.md` so the file opens in the editor pane (the `code` command IS on PATH in Codespaces). Both signals are reliable; clipboard tools are not.

---

## P1-W — Important

- **P1-W1** [FIXED 2026-04-28] [Production Readiness]: **`on-create.sh` phase 5 marker prints before the actual final messages.** Phase 5 says `==> [5/5] Done — codespace ready` then the script keeps printing two more lines. Internally consistent (phase 5 IS the done phase) but the "Done" claim with trailing output looks confusing. Same family as P0-V3 ("phase 1 already done above"). (`.devcontainer/on-create.sh:135`.)
  - **Suggested fix**: rename phase 5 to `phase 5 "Wrapping up"` or move the trailing TL;DR lines BEFORE the phase 5 marker.

- **P1-W2** [FIXED 2026-04-28] [Software Engineer]: **`e156 version` codespace path detection is hardcoded to `/workspaces/e156-ecosystem-starter`.** A user who forks the repo and opens a Codespace from their fork gets a working dir at `/workspaces/<fork-name>` — possibly different. The hardcoded path then misses, falls through, returns "unknown". The cleanest signal in a Codespace is `$CODESPACE_VSCODE_FOLDER` or `$CODESPACES_PROJECT_FOLDER`, both set by the runtime to the actual working directory.
  - **Suggested fix**: prepend `${CODESPACE_VSCODE_FOLDER:-${CODESPACES_PROJECT_FOLDER:-}}` to the candidate-path list so forks are auto-detected.

---

## P2-W — Minor

- **P2-W1** [DEFERRED — covers actual regression that just happened; broader rule list is future polish] [i18n parity test brittleness]: `check-i18n-parity.sh` counts only `<details>` blocks. A future contributor could add a `<section class="warning">` block to English without updating i18n, and the check would still pass. Robust version would also count `<section>`, `<aside>`, and the cloud-banner element. Acceptable for now; covers the actual regression that just happened.

- **P2-W2** [FIXED 2026-04-28] [Software Engineer]: `e156 start` Codespace detection uses `[[ -f /.dockerenv ]] || [[ -n "${CODESPACES:-}" ]]`. The `/.dockerenv` check matches **any** Docker container, not specifically Codespaces. Use `$CODESPACES` env var alone (set to `true` only by GitHub Codespaces).

- **P2-W3** [FIXED 2026-04-28] [Software Engineer]: The `xsel` entry in the clipboard-tool list lacks the `--clipboard --input` flags. As written, `xsel < file` writes to PRIMARY selection (middle-click paste), not CLIPBOARD selection (Ctrl+V paste). Should be `"xsel --clipboard --input"`. Low impact because xsel is the LAST candidate. Bundle with the P0-W2 Codespace-clipboard rewrite.

---

## What this pass confirmed IS correct

- **i18n parity check itself works**: `bash scripts/check-i18n-parity.sh` correctly reports 3/3 across all 5 languages.
- **on-create.sh GitHub-user resolution**: phase 1 marker now correctly wraps the resolution code.
- **The new `<details>` blocks on i18n pages**: counted, present, region-specific carrier names per audience.
- **e156 version fallback chain**: in a non-shallow clone or where installed-ref file exists, it does return real version info. The hardcoded codespace path is the only remaining hole (P1-W2).

---

## Pattern across this pass

Two pieces of code rewritten in the prior pass had correctness issues that this pass caught **only because I verified against ground truth** (tested clipboard tool availability vs Codespace defaults; cross-referenced rule list against the actual Sentinel directory).

The second-pass review's lesson reapplied: **fixes that look correct in isolation interact badly with reality.** Cure: when shipping content that asserts external truth (like a rule list), generate it from the source of truth in code, never from memory. When shipping behavioral fixes (like clipboard handling), validate against the actual deployment environment.

---

## Recommended fix order

P0-W1 first (academic-integrity, blocks educator use of teaching materials) → P0-W2 (cliff re-introduction) → P1-W1 + P1-W2 → P2s.

**If fixing only one thing**: P0-W1. The fabricated rule list is the worst single piece of content in this codebase right now and it sits in a teaching artifact.
