# 60-second screencast recipe

A 60-second silent screencast on the landing page would convert non-coders ~2x better than text instructions (P2-U2 from the 2026-04-27 user-POV review). Anthropic-the-AI cannot record video; this is a recipe for whoever does (a student volunteer, a colleague with OBS Studio, etc.).

**Output target**: a 60-second silent MP4 or animated GIF, embedded at the top of `docs/index.html` (the existing TODO comment marks the position). Should auto-play, muted, looping. Max 5MB so it loads fast on African mobile networks.

## Tools (free)

- **Recording**: [OBS Studio](https://obsproject.com) (Windows/macOS/Linux). Screen capture at 1080p 30fps.
- **Trimming/cropping/sped-up**: [ScreenToGif](https://www.screentogif.com) for GIF, or use OBS's built-in recording for MP4.
- **MP4 → small GIF**: [ezgif.com](https://ezgif.com/video-to-gif) for last-mile compression. Aim for ≤5 MB final size.

## Storyboard (60 seconds total)

| Time | What's on screen | Speed | Notes |
|---|---|---|---|
| 0–3s | Landing page (this site), cursor moves to the green "Open in GitHub Codespaces →" button | normal | Show the headline first |
| 3–4s | Click. Browser navigates to GitHub Codespaces creation page | normal | |
| 4–6s | "Create codespace" GitHub UI, cursor clicks the green confirm button | normal | If this needs auth, **skip the auth flow** — the video is for users who already have GitHub |
| 6–9s | Browser shows "Configuring codespace…" with a spinner | **8x speed** | This is the slowest real-life part (2-3 min) compressed to 3 seconds |
| 9–12s | VS Code interface appears in the browser, terminal pane pops up at the bottom showing the on-attach banner | normal | The banner with `[OK]` lines is the payoff — let it sit visible for ~3s |
| 12–15s | Cursor clicks in the terminal, types `e156 start`, presses Enter | normal | One word, one Enter — that's the whole UX |
| 15–25s | Gemini CLI launches. A browser popup asks for Google sign-in. Cursor clicks "Sign in with Google" → fake/blurred email picker → "Allow" | **2x speed** | Use a throwaway Google account; blur the email |
| 25–35s | Back in the terminal. Gemini agent reads the handoff briefing and starts responding ("I will run python --version…" etc.) | normal | This is the "it's working" moment |
| 35–45s | Agent surfaces the prereq diagnosis output | **2x speed** | Show the agent doing real work |
| 45–55s | Agent asks "which of the 8 example projects?" — cursor clicks/types "Forest plot tool" | normal | The handoff to user-driven work |
| 55–60s | Agent runs `find-related-repos.py`, surfaces top-3 portfolio matches | normal | End on the recon step — the "this is smarter than ChatGPT" moment |

**No narration.** Silent screencasts are universal across languages and load smaller. If text overlays are needed, use 2-3 word captions in white-on-black at the bottom: "click button", "wait ~2 min", "type one word", "agent does the rest".

## Recording checklist

- [ ] Browser zoom set to 110% (more readable on small screens)
- [ ] Cursor enlarged (OBS source filter or OS accessibility setting)
- [ ] No personal info on screen (use a clean GitHub account, blur emails)
- [ ] Disable browser notifications + system notifications during recording
- [ ] If recording on Windows, hide the taskbar and clock (clock leaks the date)
- [ ] If your codespace is in any language other than English, set `E156_LANG=en` for the recording so the demo is universally readable
- [ ] After recording: trim dead time, sped-up the build phase to 8x, sped-up the agent's typing to 2x

## Submission

Open a PR adding `docs/screencast.mp4` (or `.gif`) and replace the TODO comment in `docs/index.html` with:

```html
<video src="screencast.mp4" autoplay muted loop playsinline
       style="width:100%; max-width:720px; display:block; margin: 0 auto 28px; border-radius:8px; box-shadow:0 2px 12px rgba(0,0,0,0.1);"
       aria-label="60-second silent demo: clicking Open in Codespaces, waiting for build, typing e156 start, watching the agent respond">
</video>
```

Or for a GIF:

```html
<img src="screencast.gif" alt="60-second silent demo: clicking Open in Codespaces, waiting for build, typing e156 start, watching the agent respond"
     style="width:100%; max-width:720px; display:block; margin: 0 auto 28px; border-radius:8px; box-shadow:0 2px 12px rgba(0,0,0,0.1);">
```

A 5MB MP4 is preferable (smaller, sharper) but a GIF works on more old browsers. PR either; we'll pick.
