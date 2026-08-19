# Proving a detector can fail

A detector that has never been observed to fail is not known to be able to.

This page is the companion to the [error library](META-ERROR-LIBRARY.md). The
library catalogues defects in evidence syntheses. This one catalogues defects in
the machinery that looks for them — because on **2026-08-19**, auditing one
working corpus of **135 topic objects**, that is where nearly all of the day's
findings actually were.

---

## The headline is a confirmation, and it is the reason this page exists

Across that day's audit the **stored quantities held**. Six pooled figures
survived independent recomputation; six recorded limitations survived independent
test; the null-cursor re-audit found **0 of 47** search records resting on a proof
that does not hold, and **0** delivered pages built on one. Every substantive
correction of the day was to a *reason*, an *attribution*, or a *check* — never to
a stored number.

> **The objects kept being right and the instruments kept being wrong.**

That asymmetry is the finding. If you are building checks for your own review,
the failure mode you should expect is not a detector that misses a defect. It is
a detector that **reports clean because it never looked**, and reads identically
to one that looked and found nothing.

*Denominator and selection: one corpus, 135 topic objects, audited on
2026-08-19 by its own maintainers. It is enriched by construction — this is a
corpus being actively repaired, so instruments were under deliberate scrutiny
that day and defects in them were being hunted. Do not read these as base rates
for anything.*

---

## The four forms of a check that finds nothing because it never looked

All four produce an empty result. None of them is distinguishable from a genuine
all-clear by reading the output.

| Form | What it looks like | Seen in |
|---|---|---|
| An over-escaped `\\b` in a raw string | Valid code that matches nothing, and **reports clean** | a text detector |
| `$?` read through a pipe | The exit code of `tail`, which is **always 0** | a shell gate |
| A guard whose triggering condition never occurred | **Green**, and unproven | a pre-commit hook |
| **A case-sensitive key lookup on a field spelled differently** | **An empty tally, indistinguishable from a clean one** | see below |

### The fourth one, in full, because it is ours and it nearly buried a true finding

A cross-family model seat, running an unrelated task, reported that this
programme's own dashboard was serving estimates its reviews had withdrawn. The
verification pass written here — to *check* that claim rather than believe it —
returned zero:

```
rows with a numeric pooled value AND a mapped object: 0
object says WITHDRAWN                                : 0
```

The lookup was `r.get('pooled_or')`. **The field is `pooled_OR`.** Every row was
skipped, the tally was empty, and the output read exactly like a clean corpus —
while **92 rows were in fact serving values their objects had withdrawn**.

> **An outside seat handed over a true finding and our own check said it was
> false.** Had that zero been believed, the finding would have been recorded as
> *"the other seat was wrong"* — the most expensive possible outcome of a correct
> delegation.

It was caught only because the same script printed the sample keys beside the
count, for an unrelated reason. **The diagnosis took one line of output that was
there by accident.**

**And the class reproduced twice more the same day, in the selftests of
instruments written after it was written down**, both by the author who wrote it
down: `"does not search" in why` against a string reading `"DOES NOT SEARCH"`,
and `"not a finding that the trials pool" in note` against `"That is NOT a
finding…"`. In both, the code under test was correct and the test failed. Had the
polarity been the other way — an assertion passing on a string it never matched —
neither would have been noticed.

**Status: open, no detector.** A general lint for case-mismatched dictionary
access is possible in principle and is not written. What is written is the
discipline in [the remedies](#the-remedies--all-four-are-mechanical) below, and
discipline is not a command. Recorded as the weakest entry on this page.

---

## A verification is only ever about the artefact it fetched

The largest instance found that day was ours, and it invalidated the *reporting*
of everything else.

A delivery check started a local HTTP server over the repository, fetched each
page from `127.0.0.1`, compared the MD5 to the file on disk, and printed
**"All N pages confirmed in served bytes."** Every word true; none of it about
delivery. **It served the build directory to itself**, so `md5(served) ==
md5(disk)` was a tautology — the check could not fail for the reason anyone cared
about.

| Measured | Value |
|---|---|
| Live copy of one review page | MD5 `ca872295…` — identical to the published branch |
| Local build of the same page | MD5 `d9164e1c…` |
| Branch the pages were built from | **never pushed** |
| Divergence | **96 commits** ahead of the published branch, 0 behind |

> **The deployment was perfectly current with respect to the published branch.
> What was stale was the published branch, relative to a branch that was never
> pushed at all.** Ninety-six commits of green "served bytes" verifications were
> true of a build and silent about the artefact a reader opens.

**What replaced it**, and the properties are the transferable part:

- It fetches the **public URL**, derived from the git remote.
- It **names the host on every line and in the summary**. A check that does not
  name its host is not a delivery check.
- It **fails closed**: an unreachable public URL is `NOT_ASSESSABLE` with a
  non-zero exit, and it **never falls back to local and passes**.
- It reports the **deploy ref** against the ref being verified, because a push to
  a branch the pipeline does not track produces a remote branch and no
  deployment.
- `--build-only` survives, because checking a build before deciding to deploy is
  a real need — but it prints `BUILD CHECK` on every line, never the word
  *delivered*, and **cannot return a delivery pass**. The mode is in the output,
  not only in the invocation.
- **The old script was deleted, not kept.** An available broken instrument is a
  trap for whoever runs it next.

**First run against the public host: 7 pages, 0 delivered** — two returned HTTP
404 (they did not exist publicly at all) and five were stale. That is the number
the tautological check had been reporting as a pass. The same check now reports
**16 OK and 1 not-assessable of 17**.

---

## A file named a gate must be able to fail

A sweep that day found **four** files named `*_gate.py` with no reachable
non-zero exit. They could only ever pass.

**And the four were not broken — the name was.** Reading them settled it: each
self-describes as advisory ("TRIAGE, NOT A VERDICT" / "a flag means READ THE
TRIAL"). They were correctly-built triage tools wearing the wrong name, and
wiring them to block would have contradicted their own stated contract. All four
were renamed to `*_triage.py`; none had its behaviour changed.

> That distinction is the point. **A gate that cannot fail is not a defect while
> nothing runs it. It is a trap for whoever wires it in next**, who will
> reasonably assume that a thing called a gate can block.

This kit ships that check, generalised:

```bash
python scripts/gate-can-fail.py                 # check the current directory
python scripts/gate-can-fail.py path/to/repo    # check somewhere else
python scripts/gate-can-fail.py --json          # machine-readable
python scripts/gate-can-fail.py --selftest      # prove it fires, and that it does not
```

**Measured, on the corpus that motivated it, after the four renames: 39 files
named `*_gate.py` checked, 3 excluded by verb prefix, 0 that cannot fail.**
Before the renames it found 4. Verdicts are the same three the self-audit
uses — `CLEAN` (0), `DEFECTS-FOUND` (1), `INCONCLUSIVE` (2) — and an unparsable
file returns `INCONCLUSIVE`, never `CLEAN`.

### The version of this check that would have missed all four

`sys.exit(main())` is the standard gate shape, so the first version treated a
non-constant argument as *can fail*. All four motivating files end exactly that
way, with a `main()` whose only return is `0`. **The first version would have
missed every file it was written for, and its unit tests were passing
throughout.** It was caught by replaying it against the four real files under
their original names, rather than against an invented probe.

That replay is now `test_silent_main_is_flagged` in
[`tests/test_gate_can_fail.py`](../tests/test_gate_can_fail.py), and it is the
reason the suite exists.

### What it does not check, named rather than implied

Reachability is judged **syntactically** — the statement exists in the file. It
does not prove any input can reach it. A gate containing `if False: sys.exit(1)`
passes this lint and cannot fail in practice. **Proving a gate can fire on a real
input is a known-answer test**: run it against a stored known-bad input and
assert it refuses. That is a different instrument and this one does not
substitute for it.

`CLEAN` over an empty set is not evidence either, and the tool says so in as many
words rather than printing a reassuring zero.

---

## The remedies — all four are mechanical

Understanding these classes does not prevent them. Each one below was broken by
someone who had written the rule down, in one case inside the instrument that
enforces it, in one case within the hour.

**1. Make the instrument report what it looked at, not only what it found.** A
count printed beside the keys it scanned is refutable; a count alone is not.
Every sweep in that day's work prints its denominator and its `NOT_ASSESSABLE`
reasons broken out.

**2. Break out `NOT_ASSESSABLE` by reason, never as one number.** A large
not-assessable folded into a single line reads as *"nothing to see here"*. One
sweep that day reported 172 not-assessable rows as: 150 with no record or no
object, 16 measure mismatches, 3 ambiguous outcomes, 2 scope differences, 1 with
too few intervals. Only the broken-out form tells you the check was structurally
unable to run, rather than ran and passed.

**3. When a not-assessable verdict is returned, print the keys the row actually
has beside the keys you looked for.** One audit's first run reported five
not-assessable rows; **all five were the audit failing to look** — two records
spelled the fields differently, three nested them one level down. Chasing key
names is endless and is itself the trap. Printing both lists is not.

**4. Test in both directions, on real inputs, and keep the known-bad.** A
detector with only a positive test passes CI while matching everything; one with
only a negative test passes CI while matching nothing. And unit tests written by
the detector's author share its blind spots — every false positive in this kit
was found by running the detectors over real files, never by a unit test.

---

## Confirmations, with their denominators

An audit that reports only its hits is measuring the auditor. The same day's
instrument checks that came back clean:

| Check | Result | Denominator |
|---|---|---|
| Search records resting on an unproven completeness proof | **0** | 47 search rows across 18 objects |
| Topics with a **delivered page** resting on such a record | **0** | the same 47 rows, traced to their pages |
| Files named a gate that cannot fail, after the renames | **0** | 39 files named `*_gate.py`, 3 more excluded by verb prefix |
| Delivered pages whose bytes match what they were built from | **16 OK, 1 not assessable** | 17 delivered pages, fetched from the public host |
| Cross-family blind re-read disagreeing with our merge decisions | **0 different** | 12 clusters read blind by a third-party model family |

The last row deserves a qualifier. The blind reader returned **UNCLEAR on ten of
the twelve** clusters, and its stated reason every time was that the field it was
asked to compare is auto-generated boilerplate. **The UNCLEARs were the finding**,
not the zero — and they are what produced the measurement in
[M5](META-ERROR-LIBRARY.md#m5--a-review-question-that-is-a-template).

### And one result that is NOT a confirmation, kept here so it cannot be read as one

A third limb of the benchmark sweep asks, independently of any card, whether each
published benchmark reconciles with the review's own trials. **It returned zero
convictions. It also assessed zero.** All **172** rows came back
`NOT_ASSESSABLE`, for reasons it breaks out rather than totalling:

| Reason | Rows |
|---|---:|
| No benchmark record and/or no review object for that page | 150 |
| **Measure mismatch** — the benchmark measures what the review does not | 16 |
| Several outcomes carry that measure and the benchmark names none | 3 |
| **Scope differs** — the benchmark synthesises a different trial set | 2 |
| Fewer than two per-trial estimates carry an interval | 1 |

**A zero over an empty denominator is not a clean result, and putting it in a
confirmations table would be the exact defect this page is about.** It is here in
its own block for that reason.

The limb is still worth having, and the story of how it got to zero is the useful
part. **It first returned eight.** Two of the eight were the instrument comparing
a hazard-ratio benchmark against a **mean difference in a symptom score**, and
against a **rate ratio over recurrent events** — two quantities compared by their
**slot** rather than by their **definition**, with the arithmetic completing
without complaint. With measure-matching and scope-matching enforced, all eight
collapsed into the `NOT_ASSESSABLE` reasons above. **Done correctly it convicts
nobody, and that is the honest answer rather than a disappointing one** — but
"convicts nobody" and "checked everybody and found nothing" are different
statements, and only the first is true here.

---

## What this page does not claim

- **It is one corpus, one team, one day.** The counts describe those instruments.
  They are not rates for detectors in general, and the sample is enriched by
  construction.
- **It does not claim these are all the forms.** Four are listed because four
  were observed. A fifth is likelier than not.
- **A detector that passes everything here can still be wrong.** Everything on
  this page is about whether a check is *capable of failing*. Whether it fails on
  the *right* inputs is a separate question, and the answer to it is a
  known-answer test against a stored known-bad, not a lint.
- **"No detector" is stated where it is true.** The case-sensitive-lookup class
  has none. It is on this page anyway, because a class you can name and cannot
  yet catch is worth more to a reader than a silence.

---

## Related

- [`META-ERROR-LIBRARY.md`](META-ERROR-LIBRARY.md) — the defect classes in the
  syntheses themselves, and the offline detectors that find them.
- [`SOURCING-METHOD.md`](SOURCING-METHOD.md) — where to get the number that puts
  a defect right, and how to record its provenance.
- [`ACCESS-LEDGER.md`](ACCESS-LEDGER.md) — what actually blocks access, measured.

MIT-licensed, like the rest of the kit.
