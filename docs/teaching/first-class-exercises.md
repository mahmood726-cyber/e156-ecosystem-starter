# Three exercises for the student's first class

After the 15-min demo, give students 60-75 minutes of hands-on time with these three exercises in order. They are designed to (a) prove the install works, (b) experience the recon behaviour, (c) feel one Sentinel block.

## Exercise 1: Sanity check (10 min)

**Goal**: confirm the install is real, not a marketing promise.

**Steps**:
1. Open your codespace (or the local terminal if you installed locally).
2. Run `e156 version`. It should print a version like `v0.8.0` or a git SHA.
3. Run `cat ~/.claude/rules/rules.md | head -40`. You should see the workflow rules. Read the first two sections aloud to your neighbour.
4. Run `ls ~/.claude/memory/`. You should see `MEMORY.md` and a `templates/` folder with four `.md` files.

**What success looks like**: you can name the four rules files and the four memory templates without re-checking. If any are missing, raise a hand.

## Exercise 2: Portfolio recon (20 min)

**Goal**: experience the "before any new project, look at what already exists" rule.

**Steps**:
1. Pick a topic you might actually want to work on — anything in cardiology, infectious disease, oncology, paediatrics, etc. Examples: "fragility index in HFpEF", "PRISMA flow diagram", "AACT trial-coverage audit", "transportability across cohorts".
2. Run: `python /workspaces/e156-ecosystem-starter/scripts/find-related-repos.py "<your topic>" --top 5 --plain`
3. Read the output. The script reads a sample manifest of 7 worked-example repos.
4. **Write down** in 3 lines: what's reusable from existing repos vs what would be genuinely net-new for your topic.

**What success looks like**: you can articulate which prior repo(s) would inform your work, and you have NOT scaffolded a new project yet (that comes in Exercise 3).

## Exercise 3: Trigger one Sentinel block (30 min)

**Goal**: feel one quality-gate block in action — the experience the install is built around.

**Steps**:
1. In the codespace, `cd ~/code/my-first-repo`.
2. Create a Python file with one of the patterns Sentinel blocks. Easiest: hardcoded local path.
   ```bash
   echo 'import os; data = open("C:/Users/me/data.csv").read()' > badscript.py
   git add badscript.py
   git commit -m "demo of sentinel block"
   git push
   ```
3. The push will fail. Read the error message — it should say something like "P0-hardcoded-local-path: badscript.py:1".
4. **Fix the violation**: change the line to read from a relative path or an env var. Re-add, re-commit, re-push. It should succeed.
5. (Optional) Try adding `SENTINEL_BYPASS=1 git push` instead. It works — but the bypass is logged. Run `cat ~/.sentinel-logs/bypass.log` to see your own bypass.

**What success looks like**: you can name one specific pattern Sentinel catches, and you've felt the difference between "the test suite catches it eventually" and "the gate stops it at git-push time."

## Wrap-up discussion (10 min)

- "What was easier than you expected?"
- "What was harder than you expected?"
- "Pick the one rule from `~/.claude/rules/rules.md` you'd most want to delete or change for your own work. Why?" — This last question is important: the rules are not gospel. They encode Mahmood's lab's incidents. Students with different methodologies should fork and edit.
