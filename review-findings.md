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
