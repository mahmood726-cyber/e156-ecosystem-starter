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

> **Three more forms were observed on 2026-08-26** — a check that can only fail
> once, one whose control expires with its own success, and one that reads a
> different layer from the one its defect lives on. The full seven-row taxonomy,
> with a distinct remedy for each, is
> [below](#the-fifth-form-arrived-and-so-did-the-sixth-and-seventh). This section
> is left at four because that is what had been observed when it was written.

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
Before the renames it found 4.

> **That measurement was correct and had stopped meaning anything.** Every
> instrument written after it was named `lint_*` or `audit_*`, so none of them
> was in the population. Rescoped from the name to the role and re-run on
> 2026-08-26: **230 files that return a verdict, 42 that cannot ever fail, and
> not one of the 42 named `*_gate.py`.** See
> [The rule was scoped to a NAME](#the-rule-was-scoped-to-a-name-and-the-names-moved). Verdicts are the same three the self-audit
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

## The fifth form arrived, and so did the sixth and seventh

This page's closing note predicted that four forms would not be all of them. On
**2026-08-26**, auditing the same corpus — now **156 topic objects** and the
**163 pages** they are delivered as — three more turned up in one day. They are
set out below with the original four, because the taxonomy is only useful as a
whole: **each form has a different remedy, and only one of them is "fix the
check".**

| Form | What it looks like | Remedy |
|---|---|---|
| **1. Cannot fail** | No reachable non-zero exit. Green forever. | **Rewrite** — or rename it, if it was always a report |
| **2. Can only fail once** | A one-shot migration check left wired in after the migration. Passes because the condition it tested is now permanently absent. | **Remove it.** The check is finished, not broken |
| **3. Its control expires with its own success** | The control is pinned to a live artefact carrying the defect. The moment the defect is fixed, the control either fails and looks like a regression, or passes for a reason that no longer holds. | **Re-pin the control** to a synthetic fixture or an immutable version. The check itself is fine |
| **4. Its triggering condition never occurred** | Green, and unproven. Nothing has ever put it in a position to refuse. **Sharpest form: not merely unexercised but _broken_ and unexercised** — a reader in this corpus passed a value through where the branch six lines above correctly unwraps it, and crashed the first time anything invoked it. An audit enumerating gates calls that one healthy. | **Known-answer test** against a stored known-bad |
| **5. A case-sensitive key lookup on a field spelled differently** | An empty tally, indistinguishable from a clean one | **Print the keys you looked for beside the keys the record has** |
| **6. It reads a different layer from the one the defect lives on** | A confident PASS over a large population, about a layer where the defect does not exist. Not weak — **incapable** | **Move the check to the layer that carries the claim** |
| **7. It compares only the intersection of two surfaces** | Anything present in one and absent from the other is *out of scope* rather than a divergence. It can never detect absence | **Derive the expected set from the source, not from the overlap** |

Forms 2 and 3 are the ones that look healthiest, because both were once correct
and both still run clean. Form 3 is the more dangerous, because *it will fail one
day for the wrong reason* and whoever sees that failure will be looking at a
green fix.

**What backs each row, stated plainly, because a taxonomy is easy to pad.** Forms
1, 4 and 5 are worked above with counts. Form 6 has its own section below, with a
sweep. Form 7's instance is a gate that compared a Word manuscript against an HTML
page **on the sections both surfaces emit**: anything present in one and absent
from the other was therefore *out of scope* rather than a divergence, and an
extraction-provenance table was missing from **every Word manuscript this
programme ever produced** with nothing able to report it. The intersection is not
the expected set, and using it as one converts every missing section into a pass;
the replacement derives the expected set from the object — which sections it
*earns*, given what it holds — and asks both surfaces for it.

**Form 2 is the one row here with no worked instance.** It was named while
classifying a set of green results, and no specific file has been identified and
read for it. It is listed because a form you can name and have not yet caught is
worth more to a reader than a silence — and it is flagged as the weakest row on
this page, the way the case-sensitive-lookup class was flagged as the weakest on
the last one.

**A control must be synthetic, or pinned to an immutable version.** That rule is
form 3 in one sentence, and it is now written into the instruments here: their
controls are synthesised into a temporary directory on each run and deleted
afterwards, or read at a pinned commit with `git show <sha>:<path>`, and if git
cannot supply the pinned bytes the gate raises rather than proceeding. Only their
*baselines* track corpus state, and a baseline is a ratchet meant to fall — which
is a different thing from a control, and the output has to say which one it is
printing.

---

## The rule was scoped to a NAME, and the names moved

This is the most uncomfortable result on the page, because it is a correction to
a confirmation printed further down it.

The check above — *a file named a gate must be able to fail* — was written on
2026-08-19 and reported **0 of 39 files named `*_gate.py` that cannot fail**.
That number was true then and it is true now. **It was also, by then, measuring
almost nothing.**

Every instrument written since that day is named `lint_*`, `audit_*`, `check_*`,
`verify_*` or `*_check.py`. None of them ends in `_gate.py`, so none of them was
ever subject to the rule. **Nobody evaded it. The rule was scoped to a filename
and the filenames moved**, and a rule that narrows silently as a codebase grows
is worse than no rule, because it keeps printing a clean result over a shrinking
population.

Rescoped from the **name** to the **role** — a file that returns a verdict — and
re-run on 2026-08-26:

| Population | Checked | Cannot ever fail |
|---|---:|---:|
| Files named `*_gate.py` | **43** | **0** |
| Files that **return a verdict** (`lint_`, `audit_`, `check_`, `verify_`, `prove_`, `*_gate.py`, `*_check.py`) | **230** | **42** |

**Not one of the 42 is named `*_gate.py`.** The published zero was not wrong; it
was complete over a population that had stopped containing the interesting cases.

Two details that make the wider count honest rather than merely bigger:

- **A file that cannot fail is not automatically a defect under the wider
  scope.** Some are triage by design and say so in their own closing lines. Those
  are listed in a `KNOWN_TRIAGE` map with the reason written out, so "it is only
  a report" has to be argued rather than assumed.
- **The verb exclusions are counted and named on every run.** `test_`, `add_`,
  `extend_`, `fix_`, `make_`, `regenerate_` put *gate* in the object position —
  the file acts *on* a gate rather than being one. Three files are excluded that
  way today, and all three are printed. If that list starts growing it is being
  used as a hiding place, and the fix then is to rename the file rather than
  extend the tuple.

**The generalisation is not about filenames.** Any rule whose population is
defined by a convention will retire itself as the convention drifts, and it will
do so silently and in the flattering direction. Ask of every standing check: *what
defines the set it runs over, and could that set shrink without anyone deciding
it should?*

---

## A gate that reads a different layer from the one its defect lives on

A lint in this corpus exists to catch a method claim asserted without a field to
back it. Run on 2026-08-26 it printed, for every object including the two whose
pages carry the defect:

```
sotagliflozin-hf                         asserts 0 claim(s), 0 unbacked
sglt2-hf                                 asserts 0 claim(s), 0 unbacked
...
PASS, measured on 141 object(s) carrying manuscript prose
```

Exit 0. Meanwhile the delivered pages were asserting *"risk of bias was assessed
with RoB 2"* over a panel denying any assessment existed — **23 pages, 22
objects**, counted independently at that morning's commit and reported in
[H9](META-ERROR-LIBRARY.md#h9--a-page-that-denies-holding-the-evidence-it-holds).

**The lint reads the object. The sentence does not exist in the object** — the
projector composes it at render time. A gate that inspects the source cannot see
a claim created downstream of it, and its green says nothing at all about that
class. Not weak, not flaky: **structurally incapable**, and confident.

> *True of a level it never touched. Blind to the level it was written for.*

Swept mechanically across the whole instrument layer:

| | |
|---:|---|
| **584** | modules in `scripts/` that can exit non-zero, i.e. can gate |
| 166 | read the OBJECT only |
| 191 | read the OBJECT and the PAGE |
| 138 | read the PAGE only |
| **59** | **claim a page-or-reader defect and read only the object** |

> **It recurred the same evening, in an instrument written that day.** A gate built to
> measure search quality reports that **154 of 155 stores have no protocol commit and 137 of
> 155 hold no executed search**. The one topic in the corpus with a protocol committed *and
> publicly anchored before its first query*, its search executed and recorded, and both ends
> independently verifiable, is counted by that gate as having **neither** — because the gate
> reads `ssot/<name>/<name>.json` and those artefacts were written to `PROTOCOL.md` and
> `SEARCH-RECORD.json` beside it. Verified at `29d61df0a`. **Writing the artefact and
> registering it where the checker looks are two jobs**, and if a new artefact does not move
> the number that measures it, one of the two is in the wrong place. Detail in
> [`SEARCH-COMPLETENESS.md` §7](SEARCH-COMPLETENESS.md#the-best-registered-search-in-the-corpus-is-invisible-to-the-gate-that-measures-search-quality).

**The 59 is a floor and each row is a candidate for reading, not a verdict.** The
claim-layer is inferred from each module's own docstring and exit messages, which
is a weak instrument, and the sweep says so in its own header before it prints a
number. An object-reading gate is not wrong — plenty of defects genuinely live on
the object. The finding is only ever a **mismatch between what is read and what
is claimed**.

One more thing, small and worth keeping because it is the same disease: the lint
above closes its PASS with a caveat that *"this says nothing about the 140
objects with no prose"*. It read 155 objects and found 141 carrying prose. **The
number is 14.** The honesty note had a stale denominator in it.

---

## A verdict without its scope is not readable evidence

The single most portable rule of that day, and it cost the least to learn.

A manuscript guard passed **25 of 25**. It examined **1,266 characters of a
553,676-byte page — 0.23% of it**. It could not have caught any of the five
rendering defects shipped that morning, because all five were in a panel it does
not read. **A real check, working correctly, of something else.**

Nothing about that output is false. It is simply unreadable as evidence, because
the reader has no way to know how much of the artefact the verdict is about.

> **Every gate should print the fraction of the artefact it examined, beside its
> verdict.**

The instruments written here fail this too, and are named rather than exempted: a
split guard prints `10 (baseline 10)` and never says it walked 156 objects to get
there. And the same omission spoiled a measurement in the other direction — a
defect was reported as *25 instances corpus-wide* when a single page carried 39,
because the count was scoped to one tab and published as a corpus figure.

Two neighbouring rules from the same day, both cheap:

- **Predict a deploy's effect from what the BUILD touches, not from the commit
  list.** A generator change has no commit-list footprint on the pages it alters.
  One page predicted unchanged moved by 880 KB, and the mechanism was confirmed
  after the fact rather than the surprise being accepted: embedded rasters 24 →
  21, 3,973 KB → 3,113 KB, exactly one figure at three view sizes.
- **A count is not a finding until you know which sentence it appears in.** A
  phrase appearing 61 times looked like a fix that had not landed. It was 61
  occurrences across 54 distinct contexts of the *new* wording — the fix working,
  counted as the fix failing.

---

## Two ways a keyword check convicts the wrong thing

Both found on 2026-08-26, both in instruments written that day, and both ran in the
flattering direction — which is the pattern worth taking, not the two instances.

### A word that means two different things in two different literatures

An indicator was being built to report whether a review's risk-of-bias assessment
had been **adjudicated** — two assessors disagreeing, and somebody deciding. The
first predicate searched whole pages for `adjudicated by`.

It flagged one page as adjudicated. That page's trials say their endpoints were
**"adjudicated by the Central Events Committee (CEC)"**.

> **Clinical endpoint adjudication and risk-of-bias assessor adjudication share a
> word and nothing else.** One is a committee deciding whether a reported stroke
> was a stroke. The other is a person deciding between two readers of a bias
> domain. Nothing but the verb connects them.

Scoped to the risk-of-bias section, the count went **1 → 0**, and 0 is the true
state: **no object in that corpus holds an adjudication record**. So the error
converted the corpus's single most important negative finding — *dual assessment
exists and adjudication does not* — into a page that appeared to have both.

Note the direction. A keyword collision could in principle have produced a false
*accusation*; this one produced a false *reassurance*, on exactly the question the
indicator was built to answer.

**The control is synthetic, and that decision is the transferable part.** The
obvious fixture is the real page that caused it. That control would die the day
that page rebuilds — [form 3](#the-fifth-form-arrived-and-so-did-the-sixth-and-seventh),
a control expiring on its own success. Instead a synthetic page is generated by the
test: a risk-of-bias section stating *"no adjudication has been performed"*, and
trial prose elsewhere stating *"all suspected efficacy events were adjudicated by
the Central Events Committee (CEC)"*. It must report two readers and **not**
adjudicated. Run while writing this: both limbs hold.

**The generalisation.** Before a keyword becomes a predicate, ask **what else that
word means in the documents you are searching**. Medical prose is full of terms
that are also methods terms — *blinded*, *masked*, *randomised*, *censored*,
*imputed*, *adjudicated*, *withdrawn*. Every one of them appears in trial
descriptions meaning something other than what your check means. **Scope the
predicate to the section that owns the concept**, and keep a fixture that contains
both senses so the distinction is tested rather than assumed.

### A comment describing a removed claim must not be indistinguishable from the claim

When the badge above was dismantled, the CSS rules that coloured it were deleted —
leaving them behind would let a green dot return silently the moment anything
emitted the class again. A comment was written in their place explaining what had
been removed and why.

**A guard that greps for the badge's vocabulary cannot tell that comment from the
thing it describes.** Writing down that a claim was removed reintroduces the
claim's signature, and the act of documenting a fix trips the check that protects
it.

The comment as committed at `04a51ca9f` states its own rule and obeys it:

```css
/* the tier-dot vocabulary was removed with the single-badge scheme on 2026-08-26.
   Leaving the rules behind would let the green dot return silently the moment anything
   emitted the class again. The word the old badge used is deliberately NOT written here:
   a comment describing a removed claim should not trip the grep that guards it. */
```

Verified: the badge's word occurs **0 times** in that file, and **0 times in any
comment in it**.

**Stated honestly: the tripping event itself is not reproducible from committed
history.** The word never reached a commit, so what is published here is the *rule*
and the artefact that states it, on the author's account of how the rule was
arrived at — not a measurement. It is on this page anyway because the mechanism is
general and cheap to avoid, and a rule you can name is worth more than a silence.

**Two ways out, and prefer the first.** Describe the removal *without* naming the
token — "the previous single-badge vocabulary" carries the meaning and not the
signature. Where the token genuinely must appear, the guard needs to exclude
comments explicitly and say in its own output that it does, so that the exclusion
is a decision on the record rather than a silent hole someone can later hide a
real claim in.

---

## The remedies — all four are mechanical

These four are the remedies for the four forms above. The three forms found later
have their own, in [the taxonomy
table](#the-fifth-form-arrived-and-so-did-the-sixth-and-seventh) — and the point
of separating them is that **only one of the seven is fixed by fixing the
check**.

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
| Files named a gate that cannot fail, after the renames | **0** | 39 files named `*_gate.py`, 3 more excluded by verb prefix — **and see the note below: this row's denominator had stopped containing the interesting cases** |
| Delivered pages whose bytes match what they were built from | **16 OK, 1 not assessable** | 17 delivered pages, fetched from the public host |
| Cross-family blind re-read disagreeing with our merge decisions | **0 different** | 12 clusters read blind by a third-party model family |

> **A confirmation in this table decayed, and the decay was invisible.** The
> gate row was measured over files matching a *name*. Every instrument written
> after it was named something else, so by 2026-08-26 the row was a true zero
> over a population that no longer held the cases worth checking. Rescoped to
> the *role*: **42 of 230**. The row is left as published, with this note beside
> it, because deleting it would hide the very failure the page is about. See
> [The rule was scoped to a NAME](#the-rule-was-scoped-to-a-name-and-the-names-moved).

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
- **It does not claim these are all the forms.** The first version of this page
  listed four and said a fifth was likelier than not. **Three more arrived on one
  day**, bringing it to seven. That prediction resolving does not make the new
  number final; it makes an eighth likelier than not.
- **A keyword predicate is a claim about language, not about data.** Two entries here
  turned on one word meaning two things, and both errors ran in the flattering direction.
  Ask what else your keyword means in the documents you are searching, before it becomes a
  check.
- **A confirmation on this page can decay without anyone touching it.** One did:
  a zero measured over a population defined by a naming convention, which
  stopped containing new instruments as the convention drifted. Re-ask of every
  standing check *what defines the set it runs over*, not only *what did it
  return*.
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
