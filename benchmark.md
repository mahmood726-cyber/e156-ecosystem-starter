# Benchmark: e156-ecosystem-starter v0.8.0 vs the field

> 2026-04-21. Honest comparison against real-world tools that occupy
> overlapping (not identical) niches. Where competitors win, the table
> says so plainly.

## The four niches this tool sits in

`e156-ecosystem-starter` doesn't have a clean single competitor because it
spans four distinct categories. We benchmark against the leader in each.

| Niche | What we ship | Competitor leader |
|---|---|---|
| Dotfile / dev-env bootstrap | rules + memory + AGENTS.md propagation | Chezmoi |
| AI agent rule pack | curated `rules/*.md` | awesome-cursorrules |
| Pre-push quality gate | Sentinel hook installer | pre-commit / lefthook |
| Reproducible dev env | install scripts + verifier | devcontainers / Nix home-manager |

---

## 1. Dotfile / dev-env bootstrap

| Feature | Chezmoi | yadm | dotbot | Nix home-manager | **e156-eco** |
|---|---|---|---|---|---|
| Cross-platform (Win/Linux/macOS) | yes | Linux/macOS | Linux/macOS | Linux/macOS | Win + Linux/macOS |
| Templating | Go templates (rich) | git filters | YAML interpolation | Nix lang | `{{NAME}}` literal |
| Encrypted secrets | age, gpg, vault | gpg | no | sops | no |
| Auto-update | `chezmoi update` | `yadm pull` | `dotbot -c install.conf.yaml` | `home-manager switch` | `update-ecosystem.ps1` |
| Rollback | git-backed | git-backed | no | atomic generations | manifest-based |
| Sync across machines | yes (git remote) | yes | no (one-way) | yes (flake) | no |
| Maturity | 7+ yrs, 12k stars | 8+ yrs, 4k stars | 9+ yrs, 7k stars | 10+ yrs, 8k stars | 1 day old |
| Learning curve | medium | low | low | high | low |

**Verdict:** **Loses to Chezmoi on every general-purpose dotfile axis.** Templating
is shallower (literal `{{NAME}}` vs Chezmoi's full Go template engine), no
encrypted secrets, no multi-machine sync. **Wins only** on the integrated
AI-agent + Sentinel + Overmind story, which Chezmoi doesn't try to do.
Anyone who wants a real dotfile manager should use Chezmoi.

---

## 2. AI agent rule pack

| Feature | awesome-cursorrules | awesome-copilot-instructions | Continue rule packs | Anthropic CLAUDE.md examples | **e156-eco** |
|---|---|---|---|---|---|
| Number of curated rules | 200+ community-contrib | 50+ | 20-30 | <10 official | 4 (deep) |
| Incident-backed (with *Why*) | rare | rare | rare | yes | **yes (every entry)** |
| Cross-agent (Claude+Gemini+Codex) | Cursor only | Copilot only | Continue only | Claude only | **yes** |
| Installable (not copy-paste) | no | no | partial | no | **yes (install.ps1/sh)** |
| Templated paths | no | no | no | no | **yes** |
| Memory scaffolding | no | no | no | no | **yes** |
| Quality of individual rules | mixed (community PRs) | mixed | curated | high | high (curated 1-author) |

**Verdict:** **Genuinely competitive here.** Most rule packs are copy-paste
markdown with no install logic and single-agent. The combination of
(a) install automation, (b) cross-agent context files, (c) every rule
incident-backed with a *Why* line, and (d) memory scaffold is unusual.
Loses on rule volume — 200 community-contributed Cursor rules vs our 4
curated files. Wins on signal-to-noise per rule.

---

## 3. Pre-push quality gate

| Feature | pre-commit | lefthook | husky | gitleaks | **e156-eco (Sentinel)** |
|---|---|---|---|---|---|
| Hook framework | yes | yes | yes (JS) | hook adapter | bundles Sentinel |
| Built-in rule library | 1000+ via repos | minimal | none | secret-detection only | 53 rules |
| AI-agent-defect focus | no | no | no | no | **yes (XSS, hardcoded paths, placeholder HMAC, empty-DF, etc.)** |
| Cross-language | yes | yes | JS-leaning | secret-only | Python + JS + HTML |
| Bypass logging | no | no | no | no | **yes (audit trail)** |
| Maturity | 8+ yrs | 4+ yrs | 7+ yrs | 6+ yrs | new |
| Setup friction | medium (.pre-commit-config.yaml) | low | npm-only | low | low |

**Verdict:** **Sentinel is genuinely novel in the AI-agent-defect category** —
no other pre-push tool I know of specifically targets the "Claude/Cursor/
Copilot will write XSS / hardcoded paths / placeholder HMAC" failure modes.
Loses to pre-commit on rule volume + ecosystem maturity. Wins on the niche
(post-LLM code review). For students who want the BROADEST gate, layer
Sentinel ON TOP of pre-commit — they don't compete.

---

## 4. Reproducible dev env

| Feature | devcontainers | Gitpod | DevPod | Nix home-manager | **e156-eco** |
|---|---|---|---|---|---|
| Reproducibility | high (Docker) | high (Docker) | high | absolute (Nix) | low (depends on host) |
| Cross-platform | needs Docker | cloud | needs Docker | Linux/macOS | yes (Win/Linux/macOS) |
| Cloud option | yes (Codespaces) | yes | partial | no | no |
| No-install-required | yes (cloud) | yes (cloud) | no | no | no |
| Hardware reqs | Docker (~4 GB RAM) | none (cloud) | Docker | minimal | minimal |
| Cost | free hobby + paid | free hobby + paid | free | free | free |
| AI-agent rule install | no | no | no | no | **yes** |

**Verdict:** **Loses badly on reproducibility.** devcontainers run identical
Docker images everywhere; e156-eco runs whatever's on the host. Wins only
on (a) no-Docker requirement (fits 4 GB student laptops) and (b) AI-agent
rule install. **For African students on shared lab machines without
admin/Docker, Docker-based options are out**, which is the gap this fills.

---

## Cross-niche scorecard

Rating each tool 1-5 on the dimensions e156-ecosystem-starter targets:

| Tool | Cross-plat | Templating | AI rules | Quality gate | Verifier | One-click | Maturity | **Total** |
|---|---|---|---|---|---|---|---|---|
| Chezmoi | 5 | 5 | 0 | 0 | 0 | 3 | 5 | 18 |
| awesome-cursorrules | 0 | 0 | 4 | 0 | 0 | 0 | 3 | 7 |
| pre-commit | 5 | 1 | 0 | 5 | 1 | 4 | 5 | 21 |
| devcontainers | 5 | 3 | 0 | 0 | 1 | 4 | 5 | 18 |
| Nix home-manager | 3 | 5 | 0 | 1 | 1 | 2 | 5 | 17 |
| Scoop / Chocolatey | 1 | 0 | 0 | 0 | 0 | 5 | 5 | 11 |
| **e156-eco v0.8.0** | **5** | **3** | **5** | **5** | **5** | **5** | **1** | **29** |

**Caveat:** the "29" is inflated by `e156-eco` scoring 5 on dimensions
(verifier, AI rules) that other tools don't even attempt. If you weight
maturity heavily — which you should for production use — the picture flips:
**Chezmoi at 18×0.7-maturity-weight = 12.6, e156-eco at 29×0.2-maturity-weight = 5.8**.

A more honest summary:

- **For pure dotfile management:** use Chezmoi.
- **For pure pre-push quality gating:** use pre-commit (or layer Sentinel on top).
- **For pure reproducible dev env:** use devcontainers if you have Docker, else Nix.
- **For AI-agent rule curation specifically:** awesome-cursorrules has more, e156-eco's are deeper per rule.
- **For the integrated stack** (rules + memory + Sentinel + Overmind + ProjectIndex + one-click install + Windows-first + low-bandwidth + no-Docker target): **e156-ecosystem-starter is the only tool I can find that does this.** Defensible top-1 in a niche that may have fewer than 5 inhabitants.

---

## Where e156-eco genuinely beats the field

1. **Cross-agent context propagation.** AGENTS.md → CLAUDE.md / GEMINI.md /
   CODEX.md as canonical-with-pointers is unusual. Most rule packs target
   a single agent; this one keeps Claude / Gemini / Codex in lockstep.
2. **Incident-backed rules with *Why* lines.** Every rule in `rules/lessons.md`
   traces back to a specific past bug. Most community rule packs are
   "best practices" without provenance.
3. **No-Docker, no-admin, Windows-first install on 4 GB RAM laptops.** None
   of devcontainers / Gitpod / Nix can do this.
4. **Sentinel's 53-rule AI-agent-defect catalog.** pre-commit has more total
   rules but nothing focused on "Claude/Cursor will write XSS sinks /
   hardcoded paths / placeholder HMAC".
5. **TruthCert HMAC-signed verification bundles.** No comparable tool ships
   a per-project signed-attestation primitive aimed at research-output
   reproducibility.

## Where it gets beaten

1. **Maturity** — 1 day old vs 7-10 years for Chezmoi / pre-commit / Nix.
   Edge cases not yet found.
2. **Templating depth** — `{{NAME}}` literal vs Chezmoi's Go template engine
   with conditionals, ranges, and crypto helpers.
3. **No encrypted secrets** — Chezmoi has age/gpg/vault; we have nothing.
4. **No cross-machine sync** — Chezmoi has git-backed sync; you'd manually
   re-run `update-ecosystem.ps1` per machine.
5. **No reproducibility guarantees** — runs on whatever Python / git /
   ollama happen to be installed; Nix and devcontainers are deterministic.
6. **Single-platform code signing** — unsigned `.bat` triggers SmartScreen;
   real Windows installers (Scoop, winget) are signed.

---

## Final rank

| Use case | Recommendation |
|---|---|
| Manage personal dotfiles across machines | **Chezmoi** |
| Block AI-agent-written defects on git push | **Sentinel** (which e156-eco installs) |
| Reproducible dev env with $$ to spend on Docker | **devcontainers** |
| Reproducible dev env with $$ + Linux-only | **Nix home-manager** |
| Browse a big library of Cursor-specific rules | **awesome-cursorrules** |
| Bootstrap a Windows research-student laptop with AI agents + quality stack on a 4 GB box, no admin, no Docker, in <2 minutes | **e156-ecosystem-starter** (essentially uncontested) |

**Honest verdict:** uncontested in its niche by virtue of niche selection,
not technical superiority. The niche itself is small (research students on
underpowered Windows laptops who want AI agents + quality gates + verifier
in one shot). For anyone outside that exact profile, the established tools
above are better choices. Inside it, this is the only thing that ships.
