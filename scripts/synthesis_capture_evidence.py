"""Capture versioned, open-access PMC evidence for a Synthesis review."""
from __future__ import annotations

import argparse
from hashlib import sha256
from http.client import HTTPException
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from synthesis_five_journal_corrections import normalize_doi


EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
MAX_BYTES = 32 * 1024 * 1024
PMCID = re.compile(r"PMC[1-9][0-9]*")
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
CC_LINK = re.compile(r"https?://creativecommons\.org/((?:licenses|publicdomain)/[^?#\s]+)")
OPEN_LICENSE = re.compile(r"(?:licenses/by|publicdomain/zero)/[0-9]+\.[0-9]+")


def text(node):
    return " ".join("".join(node.itertext()).split()) if node is not None else ""


def article_id(meta, kind):
    values = [text(node) for node in meta.findall("article-id") if node.get("pub-id-type") == kind]
    if len(values) != 1 or not values[0]:
        raise ValueError(f"Expected one article ID of type {kind}")
    return values[0]


def license_url(meta):
    links = set()
    for license_node in meta.findall("./permissions/license"):
        for node in license_node.iter():
            for value in (node.get(XLINK_HREF), text(node) if node.tag.endswith("license_ref") else None):
                match = CC_LINK.fullmatch(value) if value else None
                if match:
                    links.add(match[1].rstrip("/"))
    if len(links) != 1 or not OPEN_LICENSE.fullmatch(next(iter(links))):
        raise ValueError("Expected an explicit, unambiguous CC BY or CC0 license")
    return "https://creativecommons.org/" + next(iter(links)) + "/"


def table_evidence(body):
    for position, wrapper in enumerate(body.iter("table-wrap"), start=1):
        tables = wrapper.findall("./table") + wrapper.findall("./alternatives/table")
        evidence = {
            "locator": f"body table-wrap {position}",
            "jats_id": wrapper.get("id"),
            "label": text(wrapper.find("label")),
            "caption": text(wrapper.find("caption")),
            "footnotes": text(wrapper.find("table-wrap-foot")),
            "status": "MANUAL_REVIEW",
        }
        if len(tables) == 1:
            rows = [
                {"group": group.tag, "cells": [
                    {"kind": cell.tag, "text": text(cell), "rowspan": cell.get("rowspan", "1"),
                     "colspan": cell.get("colspan", "1")}
                    for cell in row if cell.tag in {"td", "th"}
                ]}
                for group in tables[0] if group.tag in {"thead", "tbody", "tfoot", "tr"}
                for row in ([group] if group.tag == "tr" else group.findall("tr"))
            ]
            if rows and all(row["cells"] for row in rows):
                evidence.update(status="STRUCTURED", rows=rows)
        yield evidence


def capture(payload, pmcid, expected_doi=None):
    if not PMCID.fullmatch(pmcid):
        raise ValueError("A canonical PMCID is required")
    if len(payload) > MAX_BYTES:
        raise ValueError("XML exceeds the capture size limit")
    root = ET.fromstring(payload)
    if root.tag == "article":
        articles = [root]
    elif root.tag == "pmc-articleset":
        articles = root.findall("article")
    else:
        raise ValueError("Expected a PMC JATS article or article set")
    matches = [
        article for article in articles
        if any(text(node) == pmcid and node.get("pub-id-type") == "pmcid"
               for node in article.findall("front/article-meta/article-id"))
    ]
    if len(matches) != 1:
        raise ValueError("Expected exactly one JATS article matching the requested PMCID")
    article = matches[0]
    meta = article.find("front/article-meta")
    if article_id(meta, "pmcid") != pmcid:
        raise ValueError("Article PMCID is ambiguous")
    doi = normalize_doi(article_id(meta, "doi"))
    if expected_doi is not None and doi != normalize_doi(expected_doi):
        raise ValueError("The article DOI does not match the requested DOI")
    version = article_id(meta, "pmcid-ver")
    if not re.fullmatch(re.escape(pmcid) + r"\.[1-9][0-9]*", version):
        raise ValueError("Article lacks a matching versioned PMCID")
    body = article.find("body")
    if body is None or not text(body):
        raise ValueError("Expected a nonempty JATS article body")
    return {
        "status": "CAPTURED",
        "source": {
            "pmcid": pmcid, "doi": doi, "version": version, "license": license_url(meta),
            "snapshot_sha256": sha256(payload).hexdigest(),
        },
        "sections": [
            {"locator": f"body sec {position}", "jats_id": node.get("id"),
             "title": text(node.find("title"))}
            for position, node in enumerate(body.iter("sec"), start=1)
        ],
        "tables": list(table_evidence(body)),
        "correction_links": [
            {"locator": f"article-meta related-article {position}", "relation": node.get("related-article-type"),
             "id_type": node.get("ext-link-type"), "target": node.get(XLINK_HREF)}
            for position, node in enumerate(meta.findall("related-article"), start=1)
            if node.get("related-article-type") in {"correction-forward", "corrected-article"}
            and node.get(XLINK_HREF)
        ],
        "supplement_links": [
            {"locator": f"article supplementary-material {position}", "jats_id": node.get("id"),
             "label": text(node.find("label")),
             "targets": list(dict.fromkeys(child.get(XLINK_HREF) for child in node.iter() if child.get(XLINK_HREF)))}
            for position, node in enumerate(article.iter("supplementary-material"), start=1)
        ],
    }


def retrieve_pmc_evidence(pmcid, *, doi=None, version=None, xml=None):
    """Retrieve or replay one PMC response, optionally binding a requested version."""
    mode = "ARCHIVED_XML" if xml is not None else "NCBI_EFETCH"
    url = None
    try:
        if not isinstance(pmcid, str) or not PMCID.fullmatch(pmcid):
            raise ValueError("A canonical PMCID is required")
        if doi is not None:
            doi = normalize_doi(doi)
        if version is not None and (
            not isinstance(version, str) or not re.fullmatch(re.escape(pmcid) + r"\.[1-9][0-9]*", version)
        ):
            raise ValueError("The requested version must be a versioned PMCID for the requested article")
        if xml is not None:
            with xml.open("rb") as source:
                payload = source.read(MAX_BYTES + 1)
        else:
            query = urlencode({"db": "pmc", "id": pmcid, "retmode": "xml"})
            url = EFETCH + "?" + query
            with urlopen(Request(url, headers={"User-Agent": "Synthesis-evidence-capture/1"}), timeout=20) as source:
                payload = source.read(MAX_BYTES + 1)
        result = capture(payload, pmcid, doi)
        if version is not None and result["source"]["version"] != version:
            raise ValueError("The captured PMC version does not match the requested version")
    except (OSError, HTTPException, ValueError, ET.ParseError) as exc:
        result = {"status": "HOLD", "reason": str(exc)}
    result["capture_mode"] = mode
    if url:
        result["attempted_url"] = url
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pmcid", help="Canonical PMCID, for example PMC10070245")
    parser.add_argument("--doi", help="Require this DOI to match the full-text record")
    parser.add_argument("--xml", type=Path, help="Replay a saved PMC XML response")
    args = parser.parse_args()
    result = retrieve_pmc_evidence(args.pmcid, doi=args.doi, xml=args.xml)
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0 if result["status"] == "CAPTURED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
