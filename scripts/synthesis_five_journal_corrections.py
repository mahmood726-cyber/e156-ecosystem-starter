#!/usr/bin/env python3
"""Bounded, source-attested counting for the five-journal correction study.

This is a registry validator and *notice* counter, not a scientific error
detector, an online scraper, a source authenticator, or a measure of accuracy.
Only published primary notices actually read in full earn full-notice credit.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit

SCHEMA = "synthesis-five-journal-notice-v1"
SCHEMA_V2 = "synthesis-five-journal-notice-v2"

JOURNALS = {
    "The Lancet": "www.thelancet.com",
    "New England Journal of Medicine": "www.nejm.org",
    "Nature": "www.nature.com",
    "JACC": "www.jacc.org",
    "Circulation": "www.ahajournals.org",
}
DEPTHS = {
    "FULL_PRIMARY_NOTICE",
    "INDEXED_EXCERPT_ONLY",
    "METADATA_ONLY",
    "SOURCE_BLOCKED",
}
MECHANISMS = {
    "ARM_DIRECTION",
    "SURVIVAL_RISK_TABLE",
    "FIGURE_SOURCE_DATA",
    "FIGURE_DUPLICATION",
    "NUMERIC_RESULT",
    "EVENT_DEFINITION",
    "UNIT_DIMENSION",
    "DOSE_SPECIFIC_SAFETY",
    "SUPPLEMENT_VERSION",
    "CLINICAL_LABEL",
    "GUIDELINE_ALGORITHM",
    "REFERENCE_LINK",
    "ATTRIBUTION",
    "PROTOCOL_HISTORY",
    "FIGURE_LEGEND",
    "METHODS_DESCRIPTION",
    "OTHER",
}
# An original available as a legitimate public full-text article (including a
# deposited author manuscript) is eligible for targeted source comparison.
# Public readability does NOT by itself establish a Creative Commons licence.
ORIGINAL_ACCESS_STATES = {
    "NOT_CHECKED",
    "FREE_FULL_TEXT_IDENTIFIED",
    "SOURCE_SPAN_RECHECKED",
}
ORIGINAL_SOURCE_FORMATS = {
    "PUBLISHER_HTML", "PUBLISHER_PDF", "PMC_FULL_HTML",
    "REPOSITORY_AUTHOR_MANUSCRIPT",
}
ORIGINAL_SOURCE_HOSTS = {
    "www.nature.com", "www.ahajournals.org", "www.thelancet.com",
    "www.jacc.org", "www.nejm.org", "pmc.ncbi.nlm.nih.gov",
    "www.sciencedirect.com",
}
ACCESS_BASIS = "PUBLIC_FULL_TEXT_READABLE_LICENSE_NOT_ASSESSED"

DOI_RE = re.compile(r"^10\.\d{4,9}/[^\s?#]+$", re.IGNORECASE)
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def normalize_doi(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("nonempty DOI string required")
    doi = value.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
            break
    doi = doi.lower()
    if not DOI_RE.fullmatch(doi):
        raise ValueError("invalid DOI notation; do not infer missing identifiers")
    return doi


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _iso_day(value: Any) -> bool:
    if not _nonempty(value) or not ISO_DATE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def validate_original_access(article: dict) -> dict:
    """Check source-provenance assertions, not the truth of external source text."""
    info = article.get("original_access")
    if not isinstance(info, dict) or info.get("status") not in ORIGINAL_ACCESS_STATES:
        raise ValueError("v2 article needs explicit original full-text access status")
    state = info["status"]
    if state == "NOT_CHECKED":
        if set(info) != {"status"}:
            raise ValueError("unreviewed original cannot carry unsupported access details")
        return info
    if not _nonempty(article.get("original_doi")):
        raise ValueError("reviewed original must have its exact DOI")
    fulltext = info.get("full_text_url")
    if not _nonempty(fulltext):
        raise ValueError("public original full-text URL is required")
    parts = urlsplit(fulltext)
    if parts.scheme != "https" or (parts.hostname or "").lower() not in ORIGINAL_SOURCE_HOSTS:
        raise ValueError("unsupported original full-text host; use official or PMC source")
    if not _iso_day(info.get("observed_on")):
        raise ValueError("invalid original source observation date")
    if info.get("source_format") not in ORIGINAL_SOURCE_FORMATS:
        raise ValueError("original source format not independently identified")
    for field in ("source_version", "source_locator", "comparison_note"):
        if not _nonempty(info.get(field)):
            raise ValueError("original access evidence requires " + field)
    if info.get("access_basis") != ACCESS_BASIS:
        raise ValueError("do not infer copyright licence from public readability")
    return info


def validate_notice(record: Any) -> dict:
    """Validate explicit metadata/attestations; do not claim to verify truth."""
    if not isinstance(record, dict) or record.get("schema") not in {SCHEMA, SCHEMA_V2}:
        raise ValueError("unknown or missing notice schema")
    journal = record.get("journal")
    if not isinstance(journal, str) or journal not in JOURNALS:
        raise ValueError("not one of the five exact main journals")
    doi = normalize_doi(record.get("notice_doi"))
    source = record.get("primary_notice_url")
    if not _nonempty(source):
        raise ValueError("source URL missing")
    parts = urlsplit(source)
    if parts.scheme != "https" or (parts.hostname or "").lower() != JOURNALS[journal]:
        raise ValueError("must use the specified journal's HTTPS publisher source")
    if not _iso_day(record.get("observed_on")):
        raise ValueError("invalid evidence observation date")
    depth = record.get("review_depth")
    if depth not in DEPTHS:
        raise ValueError("unknown notice review depth")
    if depth == "FULL_PRIMARY_NOTICE":
        if record.get("primary_notice_read_entirely") is not True:
            raise ValueError("cannot credit unread primary notice")
        if record.get("source_format") not in {"PUBLISHER_PDF", "PUBLISHER_HTML"}:
            raise ValueError("full notice must be publisher full-text or PDF")
        if not _nonempty(record.get("notice_body_locator")):
            raise ValueError("full notice needs exact body locator")
    elif record.get("primary_notice_read_entirely") is True:
        raise ValueError("non-full notice cannot claim entire source read")
    articles = record.get("articles")
    if not isinstance(articles, list):
        raise ValueError("articles must be a list, even when unknown")
    for article in articles:
        if not isinstance(article, dict):
            raise ValueError("article reference must be an object")
        if not _nonempty(article.get("original_title")) and not _nonempty(article.get("original_doi")):
            raise ValueError("article title or DOI required; keep unknowns explicit")
        if article.get("original_doi") is not None:
            normalize_doi(article["original_doi"])
        if record["schema"] == SCHEMA_V2:
            validate_original_access(article)
        changes = article.get("changes")
        if not isinstance(changes, list):
            raise ValueError("changes must be a list")
        for change in changes:
            if not isinstance(change, dict) or change.get("mechanism") not in MECHANISMS:
                raise ValueError("unknown correction mechanism")
            if not _nonempty(change.get("claim_locator")):
                raise ValueError("each notice-described change needs a source locator")
            if not _nonempty(change.get("summary")):
                raise ValueError("change needs a short paraphrased source-backed summary")
            if change.get("current_vor_state") not in {
                "NOT_CHECKED", "NOTICE_SAYS_UPDATED", "EXACT_CLAIM_RECHECKED",
                "VERSION_CONFLICT", "INACCESSIBLE",
            }:
                raise ValueError("exact current Version-of-Record state required")
    normalized = dict(record)
    normalized["notice_doi"] = doi
    return normalized


def summarize(records: list[dict], *, target: int = 1000) -> dict:
    """Summarize distinct *notices* and observed source depth, never error counts."""
    if not isinstance(target, int) or isinstance(target, bool) or target <= 0:
        raise ValueError("target must be a positive integer")
    distinct: dict[str, dict] = {}
    duplicate_rows = 0
    for raw in records:
        item = validate_notice(raw)
        key = item["notice_doi"]
        if key in distinct:
            if item != distinct[key]:
                raise ValueError("conflicting entries for notice DOI " + key)
            duplicate_rows += 1
        else:
            distinct[key] = item

    by_journal = {name: {"discovered": 0, "full_primary_notice": 0,
                         "indexed_excerpt_only": 0, "metadata_only": 0,
                         "source_blocked": 0} for name in JOURNALS}
    depths = Counter()
    mechanism_entries = Counter()
    referenced_article_entries = 0
    notice_described_change_entries = 0
    original_source_spans_checked = 0
    original_full_text_located_unpaired = 0
    oa_paired_notice_ids: set[str] = set()
    for item in distinct.values():
        depth = item["review_depth"]
        depths[depth] += 1
        bucket = by_journal[item["journal"]]
        bucket["discovered"] += 1
        bucket[{
            "FULL_PRIMARY_NOTICE": "full_primary_notice",
            "INDEXED_EXCERPT_ONLY": "indexed_excerpt_only",
            "METADATA_ONLY": "metadata_only",
            "SOURCE_BLOCKED": "source_blocked",
        }[depth]] += 1
        for article in item["articles"]:
            if item["schema"] == SCHEMA_V2:
                access_state = article["original_access"]["status"]
                if access_state == "SOURCE_SPAN_RECHECKED":
                    original_source_spans_checked += 1
                    if depth == "FULL_PRIMARY_NOTICE":
                        oa_paired_notice_ids.add(item["notice_doi"])
                elif access_state == "FREE_FULL_TEXT_IDENTIFIED":
                    original_full_text_located_unpaired += 1
            referenced_article_entries += 1
            for change in article["changes"]:
                notice_described_change_entries += 1
                mechanism_entries[change["mechanism"]] += 1

    complete = depths["FULL_PRIMARY_NOTICE"]
    return {
        "schema": "synthesis-five-journal-notice-summary-v1",
        "target_full_notices": target,
        "total_distinct_notice_records": len(distinct),
        "full_primary_notices": complete,
        "remaining_to_full_notice_target": max(0, target - complete),
        "full_notices_paired_with_public_original_claim": len(oa_paired_notice_ids),
        "remaining_to_oa_paired_target": max(0, target - len(oa_paired_notice_ids)),
        "original_article_spans_rechecked": original_source_spans_checked,
        "original_full_text_located_without_claim_recheck": original_full_text_located_unpaired,
        "indexed_excerpt_only": depths["INDEXED_EXCERPT_ONLY"],
        "metadata_only": depths["METADATA_ONLY"],
        "source_blocked": depths["SOURCE_BLOCKED"],
        "duplicate_rows_removed": duplicate_rows,
        "referenced_article_entries_not_unique_papers": referenced_article_entries,
        "notice_described_change_entries_not_error_roots": notice_described_change_entries,
        "mechanism_entries_not_error_roots": dict(sorted(mechanism_entries.items())),
        "by_journal": by_journal,
        "limitations": [
            "All source-read and reviewer fields are caller attestations, not authenticated by code.",
            "One notice may modify multiple articles/claims; one article may receive multiple notices.",
            "No count of independent errors, Synthesis discoveries, author confirmations or emails.",
            "Retrospective publisher corrections are development data, not held-out accuracy validation.",
            "Public readability is distinct from a verified reuse licence; original version identity matters.",
            "A source-limited notice cannot earn paired-credit even if a PMC original span is readable.",
        ],
    }


def main() -> None:
    if __package__:
        from scripts.synthesis_source_rights import read_authorized
    else:
        from synthesis_source_rights import read_authorized
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("register", type=Path, help="JSON list of source-notice records")
    parser.add_argument("--target", type=int, default=1000)
    args = parser.parse_args()
    data = json.loads(read_authorized(args.register, operation="process"))
    if not isinstance(data, list):
        parser.error("JSON register must be an array")
    print(json.dumps(summarize(data, target=args.target), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

