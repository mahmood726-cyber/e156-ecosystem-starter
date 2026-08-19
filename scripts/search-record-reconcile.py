#!/usr/bin/env python3
"""A SEARCH RECORD MUST RECONCILE WITH THE IDENTIFIERS IT LISTS -- by a command, not by reading.

WHY THIS EXISTS. A record that states `records_returned_total: 137` and names none of them is a
number nothing can recompute. It is indistinguishable from a number that was asserted, and
re-running the query later silently substitutes a different set under the same count.

The sharper reason is the one measured on 2026-08-19. A paginated search that stops with a null
cursor looks finished. On one of our own topics the cursor returned null after 100 + 100 + 3 =
203 records against a reported total of 430 -- 227 records the pagination never returned, WHILE
REPORTING THE SEARCH COMPLETE. Every search we had run before that relied on the null cursor as
its completeness proof. It is corroboration. It is never the proof.

    THE PROOF IS THE SUM ACROSS PAGES, RECONCILED AGAINST THE REPORTED TOTAL.

WHAT IT CHECKS, for every search record that carries an identifier list:

    len(list)  ==  len(set(list))  ==  sum of per-page `returned`  ==  the reported total

Four quantities, and each catches a different failure:

  * list vs SUM-ACROSS-PAGES -- a page transcribed short, or transcribed twice
  * SUM vs REPORTED TOTAL    -- an unexhausted cursor: the search is not finished
  * list vs DISTINCT         -- the same identifier written twice, which inflates a denominator
                                while every other number still reconciles

The third is the one a human reading the file would not do. A duplicated identifier keeps the
sum right and the total right and is invisible to every check but a set comparison.

WHAT THIS DOES NOT ESTABLISH
  - NOT that the identifiers are the RIGHT ones, or that the query was well aimed. It compares a
    record against itself. A record whose stated numbers are both untrue passes here.
  - NOT anything about a record that names no identifiers. That is NOT_ASSESSABLE, counted
    separately, and it is NEVER a pass.
  - NOT recall. Whether the search found the trials that exist is a different measurement; see
    docs/SEARCH-COMPLETENESS.md for how to run it against a known included set.

INPUT FORMAT. A JSON object. Every key is optional except that you need either an identifier
list or per-page counts for anything to be checkable:

    {
      "query_as_executed": "intervention=colchicine; condition=...; page_size=100",
      "nct_ids":  ["NCT02551094", "NCT03048825", "..."],
      "pages": [
        {"returned": 100, "total_reported": 137, "next_page_token": "NF0g5i..."},
        {"returned":  37,                        "next_page_token": "null -- exhausted"}
      ]
    }

  The identifier list may be spelled `pmids`, `nct_ids`, `identifiers` or `records`, or split
  across `page_1` / `page_2` / ... keys. The total may be spelled `total_reported`,
  `total_count`, `totalCount` or `total`, on a page or at the top level.

  AN ABSENT `next_page_token` FIELD IS NOT A NULL ONE. A record that never wrote down what the
  cursor said has made no claim about completeness, and reading its silence as "the cursor said
  done" would convict it of a proof it never offered.

USAGE
    python scripts/search-record-reconcile.py my_search_record.json
    python scripts/search-record-reconcile.py evidence/            # every *.json beneath it
    python scripts/search-record-reconcile.py --selftest           # can-fire proof, then exit

EXIT CODES
    0  every assessable record reconciles
    1  at least one record REFUSED, or --selftest failed
    2  no input given, or nothing readable at the path

Standard library only. Offline. No API key, no model call. MIT-licensed, like the rest of the
kit. Part of the Nafis method: https://github.com/mahmood726-cyber/e156-ecosystem-starter
"""
import glob
import io
import json
import os
import sys

LIST_KEYS = ("pmids", "nct_ids", "identifiers", "records")
RETURNED = ("returned", "records_returned", "count")
TOTAL = ("total_reported", "total_count", "totalCount", "total")

CURSOR_LIE = "CURSOR_SAID_DONE_BUT_THE_SUM_DOES_NOT_RECONCILE"


def _identifiers(doc):
    """The identifier list, however this record spells it -- including page-split lists."""
    for key in LIST_KEYS:
        value = doc.get(key)
        if isinstance(value, list) and value and all(isinstance(x, str) for x in value):
            return key, list(value)
    names, parts = [], []
    for key, value in doc.items():
        if key.startswith("page_") and isinstance(value, list) \
                and all(isinstance(x, str) for x in value):
            names.append(key)
            parts.extend(value)
    if parts:
        return "+".join(sorted(names)), parts
    return None, None


def _first_int(holder, keys):
    if not isinstance(holder, dict):
        return None
    for key in keys:
        if isinstance(holder.get(key), int):
            return holder[key]
    return None


def _page_sum(pages):
    values = []
    for page in pages or []:
        got = _first_int(page, RETURNED)
        if got is not None:
            values.append(got)
    return sum(values) if values else None


def _reported_total(doc, pages):
    for page in pages or []:
        got = _first_int(page, TOTAL)
        if got is not None:
            return got
    got = _first_int(doc, TOTAL)
    if got is not None:
        return got
    return _first_int(doc.get("counts"), TOTAL)


def check(doc):
    """(verdict, why, numbers) for one search record."""
    key, ids = _identifiers(doc)
    pages = doc.get("pages") if isinstance(doc.get("pages"), list) else None
    page_sum = _page_sum(pages)
    total = _reported_total(doc, pages)

    # THE NULL-CURSOR LIMB. A live token means incomplete -- that direction is obvious and was
    # never the problem. This is the CONVERSE, which is false: a null token alongside a sum that
    # does not reach the reported total is its own verdict, and it fires even when the record
    # lists no identifiers, because page counts and a total are enough to catch it.
    if pages:
        last = pages[-1] if isinstance(pages[-1], dict) else {}
        token = str(last.get("next_page_token") or "").strip().lower()
        cursor_done = ("next_page_token" in last
                       and ("null" in token or "exhaust" in token or token == "none"))
        if cursor_done and page_sum is not None and total is not None and page_sum != total:
            return (CURSOR_LIE,
                    "the pages sum to %d against a reported total of %d -- %d record(s) the "
                    "pagination never returned WHILE THE CURSOR REPORTED THE SEARCH COMPLETE. "
                    "A null next_page_token is corroboration, never the proof."
                    % (page_sum, total, total - page_sum),
                    {"listed": len(ids) if ids else None,
                     "distinct": len(set(ids)) if ids else None,
                     "sum_across_pages": page_sum, "reported_total": total,
                     "shortfall": total - page_sum, "cursor": "null"})

    if not ids:
        return ("NOT_ASSESSABLE",
                "the record lists no identifiers, so nothing can be checked against it. "
                "THIS IS NOT A PASS.",
                {"listed": None, "distinct": None,
                 "sum_across_pages": page_sum, "reported_total": total})

    numbers = {"listed": len(ids), "distinct": len(set(ids)), "sum_across_pages": page_sum,
               "reported_total": total, "list_key": key}
    refusals = []
    if len(set(ids)) != len(ids):
        dupes = sorted({x for x in ids if ids.count(x) > 1})
        refusals.append("DUPLICATE IDENTIFIERS in the list: %s" % dupes[:6])
    if page_sum is not None and page_sum != len(ids):
        refusals.append("the list has %d and the pages sum to %d" % (len(ids), page_sum))
    if total is not None and total != len(ids):
        refusals.append("the list has %d and the record reports a total of %d -- if that "
                        "shortfall is deliberate the record must DECLARE it" % (len(ids), total))
    if refusals:
        return "REFUSED", "; ".join(refusals), numbers
    return "RECONCILES", "listed == distinct == pages == reported", numbers


def _looks_like_a_search_record(doc):
    return isinstance(doc, dict) and any(
        k in doc for k in ("query_as_executed", "query", "pages")) or (
        isinstance(doc, dict) and _identifiers(doc)[1] is not None)


def _targets(argv):
    files = []
    for arg in argv:
        if os.path.isdir(arg):
            files.extend(sorted(glob.glob(os.path.join(arg, "**", "*.json"), recursive=True)))
        else:
            files.append(arg)
    return files


def run(argv):
    files = _targets(argv)
    if not files:
        sys.stderr.write("nothing to read at: %s\n" % " ".join(argv))
        return 2
    tally, refused, read_any = {}, 0, False
    for path in files:
        try:
            with io.open(path, "r", encoding="utf-8") as handle:
                doc = json.load(handle)
        except (OSError, ValueError) as exc:
            sys.stderr.write("could not read %s: %s\n" % (path, exc))
            continue
        if not _looks_like_a_search_record(doc):
            continue
        read_any = True
        verdict, why, numbers = check(doc)
        tally[verdict] = tally.get(verdict, 0) + 1
        print("%-46s %-12s %s" % (os.path.basename(path), verdict, why[:96]))
        print("     listed %s  distinct %s  pages %s  reported %s"
              % (numbers.get("listed"), numbers.get("distinct"),
                 numbers.get("sum_across_pages"), numbers.get("reported_total")))
        if verdict in (CURSOR_LIE, "REFUSED"):
            refused += 1
    if not read_any:
        sys.stderr.write("no file read looked like a search record "
                         "(needs a query, pages, or an identifier list)\n")
        return 2
    print("\n%s" % "  ".join("%s %d" % item for item in sorted(tally.items())))
    print("NOT_ASSESSABLE means the record names no identifiers. It is counted separately "
          "and is NEVER a pass.")
    return 1 if refused else 0


def selftest():
    """CAN-FIRE PROOF. A detector never shown to fire on a known-bad input is not a detector."""
    failures = []

    def expect(name, got, want):
        ok = got == want
        print("  %-70s %s  %r" % (name, "ok" if ok else "FAIL", got))
        if not ok:
            failures.append(name)

    print("A RECONCILING RECORD PASSES:")
    good = {"query": "q", "pmids": ["1", "2", "3"],
            "pages": [{"returned": 2, "total_count": 3}, {"returned": 1}]}
    expect("listed 3 == distinct 3 == pages 3 == reported 3", check(good)[0], "RECONCILES")

    print("\nTHE FOURTH CHECK -- a duplicate keeps every other number right:")
    dup = {"query": "q", "pmids": ["1", "2", "2"],
           "pages": [{"returned": 2, "total_count": 3}, {"returned": 1}]}
    expect("listed 3, pages 3, reported 3, DISTINCT 2 -> REFUSED", check(dup)[0], "REFUSED")
    expect("and it names the duplicate", "'2'" in check(dup)[1], True)

    print("\nAN UNEXHAUSTED CURSOR -- 2 listed against a reported 523:")
    short = {"query": "q", "pmids": ["1", "2"], "pages": [{"returned": 2, "total_count": 523}]}
    expect("REFUSED", check(short)[0], "REFUSED")

    print("\nTHE CASE THAT FALSIFIED THE PROOF WE HAD BEEN RELYING ON.")
    print("203 returned across three pages, cursor null, reported total 430:")
    acs = {"query": "q",
           "pages": [{"returned": 100, "total_reported": 430, "next_page_token": "PRESENT"},
                     {"returned": 100, "next_page_token": "PRESENT"},
                     {"returned": 3, "next_page_token": "null -- the cursor is exhausted"}]}
    expect("REFUSED as " + CURSOR_LIE, check(acs)[0], CURSOR_LIE)
    expect("and it names the shortfall: 227 records never returned",
           check(acs)[2]["shortfall"], 227)

    print("\nAND THE HONEST CASE MUST NOT TRIP IT -- 100 + 37 = 137 == 137, cursor null:")
    fine = {"query": "q",
            "pages": [{"returned": 100, "total_reported": 137, "next_page_token": "PRESENT"},
                      {"returned": 37, "next_page_token": "null -- the cursor is exhausted"}]}
    expect("does not fire", check(fine)[0] != CURSOR_LIE, True)

    print("\nAN ABSENT TOKEN FIELD IS NOT A NULL ONE -- silence is not a claim:")
    silent = {"query": "q", "pmids": ["1", "2"], "pages": [{"returned": 2, "total_count": 523}]}
    expect("falls through to the identifier checks, refused there", check(silent)[0], "REFUSED")

    print("\nA RECORD THAT NAMES NOTHING CANNOT PASS:")
    expect("no identifier list -> NOT_ASSESSABLE",
           check({"query": "q", "pages": [{"returned": 137, "total_count": 137}]})[0],
           "NOT_ASSESSABLE")

    print("\nPAGE-SPLIT LISTS ARE JOINED:")
    split = {"query": "q", "page_1": ["1", "2"], "page_2": ["3"],
             "counts": {"total_reported": 3}}
    expect("page_1 + page_2 read as one list of 3", check(split)[2]["listed"], 3)

    print("\n%d of %d selftest assertions passed."
          % (10 - len(failures), 10))
    if failures:
        print("FAILED: %s" % ", ".join(failures))
        return 1
    return 0


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 2
    if argv[0] == "--selftest":
        return selftest()
    return run(argv)


if __name__ == "__main__":
    sys.exit(main())
