"""Capture versioned, open-access PMC evidence for a Synthesis review."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
from http.client import HTTPException
import json
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET

if __package__:
    from scripts.synthesis_five_journal_corrections import normalize_doi
else:
    from synthesis_five_journal_corrections import normalize_doi


EFETCH_HOST = "eutils.ncbi.nlm.nih.gov"
EFETCH = f"https://{EFETCH_HOST}/entrez/eutils/efetch.fcgi"
MAX_BYTES = 32 * 1024 * 1024
PMCID = re.compile(r"PMC[1-9][0-9]*")
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
ALI_LICENSE_REF = "{http://www.niso.org/schemas/ali/1.0/}license_ref"
CC_LINK = re.compile(r"https?://creativecommons\.org/((?:licenses|publicdomain)/[^?#\s]+)")
OPEN_LICENSE = re.compile(r"(?:licenses/by|publicdomain/zero)/[0-9]+\.[0-9]+")
RESERVED_RIGHTS = re.compile(r"\ball[\s_-]+rights[\s_-]+reserved\b", re.IGNORECASE)
CC_TERMS = re.compile(r"https?://(?:www\.)?creativecommons\.org/"
                      r"((?:licenses|publicdomain)/[a-z0-9-]+(?:/[0-9]+\.[0-9]+)?)", re.IGNORECASE)
CC_TYPE = re.compile(r"(?:cc-?)?(by(?:-(?:nc|nd|sa))*|0|zero)(?:-?([0-9]+\.[0-9]+))?(?:-?license)?")
CC_ATTRIBUTION = r"(?:CC[\s_-]*BY|Creative[\s_-]+Commons[\s_-]+Attribution)"
CC_ATTRIBUTION_NAME = re.compile(rf"\b{CC_ATTRIBUTION}(?:[\s_-]*([0-9]+\.[0-9]+))?\b", re.IGNORECASE)
RESTRICTIVE_CC_NAME = re.compile(rf"\b{CC_ATTRIBUTION}[\s_-]+(?:NC|ND|SA|Non[\s_-]?Commercial|"
                                r"No[\s_-]?Derivatives|Share[\s_-]?Alike)(?![a-z0-9])", re.IGNORECASE)
TEXT_MARKERS = {
    "sup": ("^{", "}"), "sub": ("_{", "}"), "xref": ("[", "]"), "ext-link": ("[", "]"),
    "bold": ("**", "**"), "italic": ("*", "*"),
}
TABLE_MARKUP = frozenset({
    "table", "caption", "colgroup", "col", "thead", "tbody", "tfoot", "tr", "th", "td",
    "break", "p", *TEXT_MARKERS,
})
MAX_LINKED_CORRECTIONS = 8
CORRECTION_ID_TYPES = {"pmc", "pmcid", "pmid", "pubmed", "doi"}


def text(node):
    def fragments(element):
        separator = " " if element.tag in {"break", "p", "list-item"} else ""
        opening, closing = TEXT_MARKERS.get(element.tag, (separator, separator))
        yield opening
        yield element.text or ""
        for child in element:
            yield from fragments(child)
            yield child.tail or ""
        yield closing

    return " ".join("".join(fragments(node)).split()) if node is not None else ""


def article_id(meta, kind):
    if meta is None:
        raise ValueError("Article metadata is missing")
    values = [text(node) for node in meta.findall("article-id") if node.get("pub-id-type") == kind]
    if len(values) != 1 or not values[0]:
        raise ValueError(f"Expected one article ID of type {kind}")
    return values[0]


def licence_type_agrees(declared_type, url_terms):
    declared_type = re.sub(r"[\u2010-\u2015]", "-", declared_type)
    if RESERVED_RIGHTS.search(declared_type) or RESTRICTIVE_CC_NAME.search(declared_type):
        return False
    normalized = re.sub(r"[\s_-]+", "-", declared_type.strip().casefold())
    code = CC_TYPE.fullmatch(normalized)
    if code:
        family, version = code.groups()
    elif attribution := CC_ATTRIBUTION_NAME.search(declared_type):
        family, version = "by", attribution[1]
    else:
        return True
    expected = "publicdomain/zero" if family in {"0", "zero"} else f"licenses/{family}"
    return url_terms.startswith(expected + "/") if version is None else url_terms == f"{expected}/{version}"


def license_url(permissions):
    links = set()
    prose_terms = set()
    if any(RESERVED_RIGHTS.search("".join(declaration.itertext()))
           for node in permissions for declaration in node):
        raise ValueError("PMC rights declarations conflict with open access")
    for license_node in (item for node in permissions for item in node.findall("license")):
        references = license_node.findall(ALI_LICENSE_REF)
        if any(ref.get("start_date") is not None for ref in references):
            raise ValueError("Dated PMC licence declarations require manual review")
        declarations = [text(ref) for ref in references]
        if license_node.get(XLINK_HREF) is not None:
            declarations.append(license_node.get(XLINK_HREF))
        types = [license_node.get("license-type", ""), *(ref.get("content-type", "") for ref in references)]
        if not declarations:
            raise ValueError("Expected an explicit, unambiguous CC BY or CC0 license")
        for value in declarations:
            match = CC_LINK.fullmatch(value)
            if not match or not OPEN_LICENSE.fullmatch(match[1].rstrip("/")):
                raise ValueError("Expected an explicit, unambiguous CC BY or CC0 license")
            terms = match[1].rstrip("/")
            if any(not licence_type_agrees(declared_type, terms) for declared_type in types):
                raise ValueError("PMC licence type conflicts with the declared licence URL")
            links.add(terms)
        for paragraph in license_node.iter("license-p"):
            prose = re.sub(r"[\u2010-\u2015]", "-", "".join(paragraph.itertext()))
            if RESTRICTIVE_CC_NAME.search(prose):
                raise ValueError("PMC licence prose conflicts with open access")
            references = [node.get(XLINK_HREF, "") for node in paragraph.iter()]
            prose_terms.update(match[1].casefold() for value in [prose, *references]
                               for match in CC_TERMS.finditer(value))
            prose_terms.update(f"licenses/by/{match[1]}" if match[1] else "licenses/by"
                               for match in CC_ATTRIBUTION_NAME.finditer(prose))
    if len(links) != 1:
        raise ValueError("Expected an explicit, unambiguous CC BY or CC0 license")
    licence = next(iter(links))
    # A CC0 data waiver does not weaken the declared article-level CC BY terms.
    if licence.startswith("licenses/by/"):
        prose_terms = {term for term in prose_terms if term.split("/")[:2] != ["publicdomain", "zero"]}
    if prose_terms.difference((licence, licence.rsplit("/", 1)[0])):
        raise ValueError("PMC licence prose conflicts with the declared licence")
    return "https://creativecommons.org/" + licence + "/"


def table_rows(table):
    for group in table:
        if group.tag == "tr":
            yield group, group
        elif group.tag in {"thead", "tbody", "tfoot"}:
            for row in group.findall("tr"):
                yield group, row


def table_markup_issue(table, rows):
    cells = {
        node: (row_index, cell_index)
        for row_index, (_, row) in enumerate(rows, 1)
        for cell_index, cell in enumerate((child for child in row if child.tag in {"td", "th"}), 1)
        for node in cell.iter()
    }
    row_nodes = {row for _, row in rows}
    cell_nodes = {cell for row in row_nodes for cell in row if cell.tag in {"td", "th"}}
    for node in table.iter():
        styled = {"style", "style-type"}.intersection(node.attrib)
        misplaced = ((node.tag == "tr" and node not in row_nodes)
                     or (node.tag in {"td", "th"} and node not in cell_nodes)
                     or (node.tag == "table" and node is not table))
        if node.tag not in TABLE_MARKUP or styled or misplaced:
            issue = {"code": "UNSUPPORTED_TABLE_MARKUP", "element": node.tag, "attributes": sorted(styled)}
            if node in cells:
                issue["row"], issue["cell"] = cells[node]
            return issue
    return None


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
        styled = {"style", "style-type"}.intersection(wrapper.attrib)
        if styled:
            evidence["manual_review"] = {"code": "UNSUPPORTED_TABLE_MARKUP", "element": "table-wrap",
                                         "attributes": sorted(styled)}
        elif len(tables) != 1:
            evidence["manual_review"] = {"code": "EXPECTED_ONE_JATS_TABLE", "table_count": len(tables)}
        else:
            source_rows = list(table_rows(tables[0]))
            issue = table_markup_issue(tables[0], source_rows)
            rows = [] if issue else [
                {"group": group.tag, "cells": [
                    {"kind": cell.tag, "text": text(cell), "rowspan": cell.get("rowspan", "1"),
                     "colspan": cell.get("colspan", "1")}
                    for cell in row if cell.tag in {"td", "th"}
                ]}
                for group, row in source_rows
            ]
            if rows and all(row["cells"] for row in rows):
                evidence.update(status="STRUCTURED", rows=rows)
            else:
                evidence["manual_review"] = issue or {"code": "MISSING_TABLE_ROWS_OR_CELLS"}
        yield evidence


def article_entries(payload):
    if len(payload) > MAX_BYTES:
        raise ValueError("XML exceeds the capture size limit")
    root = ET.fromstring(payload)
    if root.tag == "article":
        return [root]
    if root.tag == "pmc-articleset":
        articles = list(root)
        if (root.text or "").strip() or any(node.tag != "article" or (node.tail or "").strip()
                                             for node in articles):
            raise ValueError("Unexpected non-article record in PMC article set")
        return articles
    raise ValueError("Expected a PMC JATS article or article set")


def locate_quotes(body, tables, quotes):
    """Index only requested excerpts so receipts do not copy article prose."""
    if not quotes:
        return {}
    wrappers = list(body.iter("table-wrap"))
    table_paragraphs = {node for wrapper in wrappers for node in wrapper.iter("p")}
    locations = [(f"body p {index}", text(node)) for index, node in enumerate(body.iter("p"), 1)
                 if node not in table_paragraphs]
    unresolved_text = set()
    for wrapper, table in zip(wrappers, tables):
        locator = table["locator"]
        locations.extend((f"{locator} {key}", table[key]) for key in ("label", "caption", "footnotes"))
        if table["status"] != "STRUCTURED":
            for node in wrapper:
                if node.tag not in {"label", "caption", "table-wrap-foot"}:
                    unresolved_text.update((text(node), " ".join("".join(node.itertext()).split())))
        for row_index, row in enumerate(table.get("rows", []), 1):
            locations.extend((f"{locator} row {row_index} cell {cell_index}", cell["text"])
                             for cell_index, cell in enumerate(row["cells"], 1))
    # Unresolved table text can rule out uniqueness without becoming evidence.
    return {quote: [] if any(quote in value for value in unresolved_text)
            else [location for location, value in locations if quote in value] for quote in quotes}


def capture(payload, pmcid, expected_doi=None, *, quotes=(), for_archive=False):
    if not PMCID.fullmatch(pmcid):
        raise ValueError("A canonical PMCID is required")
    articles = article_entries(payload)
    if for_archive and len(articles) != 1:
        raise ValueError("A PMC archive must contain exactly one top-level article")
    matches = [
        article for article in articles
        if any(text(node) == pmcid and node.get("pub-id-type") == "pmcid"
               for node in article.findall("front/article-meta/article-id"))
    ]
    if len(matches) != 1:
        raise ValueError("Expected exactly one JATS article matching the requested PMCID")
    article = matches[0]
    meta = article.find("front/article-meta")
    if any(node is not article and node.tag in {"article", "sub-article", "response"} for node in article.iter()):
        raise ValueError("Nested PMC articles and responses require separate rights review")
    article_permissions = meta.findall("permissions")
    licence = license_url(article_permissions)
    for permissions in article.iter("permissions"):
        if permissions not in article_permissions:
            license_url((permissions,))
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
    tables = list(table_evidence(body))
    tables_by_node = dict(zip(body.iter("table-wrap"), tables))
    supplements = []
    for position, node in enumerate(article.iter("supplementary-material"), 1):
        wrappers = list(node.iter("table-wrap"))
        inline = [tables_by_node[wrapper]["locator"] for wrapper in wrappers
                  if wrapper in tables_by_node and tables_by_node[wrapper]["status"] == "STRUCTURED"]
        unresolved = [tables_by_node[wrapper]["locator"] for wrapper in wrappers
                      if wrapper in tables_by_node and tables_by_node[wrapper]["status"] != "STRUCTURED"]
        targets = list(dict.fromkeys(child.get(XLINK_HREF) for child in node.iter() if child.get(XLINK_HREF)))
        manual = bool(targets) or not inline or len(inline) != len(wrappers)
        supplements.append({
            "locator": f"article supplementary-material {position}", "jats_id": node.get("id"),
            "label": text(node.find("label")), "targets": targets, "inline_tables": inline,
            "status": "MANUAL_REVIEW" if manual else "INLINE_CAPTURED",
            **({"unresolved_inline_tables": unresolved} if unresolved else {}),
            **({"reason": "External attachment or incomplete inline table evidence"} if manual else {}),
        })
    pmids = [text(node) for node in meta.findall("article-id") if node.get("pub-id-type") == "pmid"]
    return {
        "status": "CAPTURED",
        "source": {
            "pmcid": pmcid, "doi": doi, "version": version, "license": licence,
            "snapshot_sha256": sha256(payload).hexdigest(),
            **({"pmid": pmids[0]} if len(pmids) == 1 and re.fullmatch(r"[1-9][0-9]*", pmids[0]) else {}),
        },
        "article_type": article.get("article-type"),
        "sections": [
            {"locator": f"body sec {position}", "jats_id": node.get("id"),
             "title": text(node.find("title"))}
            for position, node in enumerate(body.iter("sec"), start=1)
        ],
        "tables": tables,
        **({"quote_locations": locate_quotes(body, tables, quotes)} if quotes else {}),
        "correction_links": [
            {"locator": f"article-meta related-article {position}", "relation": node.get("related-article-type"),
             "id_type": node.get("ext-link-type"), "target": node.get(XLINK_HREF)}
            for position, node in enumerate(meta.findall("related-article"), start=1)
            if node.get("related-article-type") in {"correction-forward", "corrected-article"}
            and node.get(XLINK_HREF)
        ],
        "supplement_links": supplements,
    }


def is_efetch_origin(url):
    target = urlsplit(url)
    return target.scheme == "https" and target.netloc.lower() == EFETCH_HOST


class PmcRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not is_efetch_origin(newurl):
            raise HTTPError(req.full_url, code, "PMC retrieval refused a redirect outside the HTTPS EFetch origin",
                            headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def archive_snapshot(payload, result, directory):
    source = result["source"]
    name = source["snapshot_sha256"] + ".xml"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / name
    if target.is_file():
        with target.open("rb") as stream:
            if stream.read(MAX_BYTES + 1) != payload:
                raise ValueError("Existing PMC archive does not match its content digest")
    else:
        temporary = None
        try:
            with NamedTemporaryFile(dir=directory, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
            temporary.replace(target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    source["snapshot_file"] = f"{directory.name}/{name}"


def _read_xml(path):
    with path.open("rb") as source:
        return source.read(MAX_BYTES + 1)


def retrieve_pmc_evidence(pmcid, *, doi=None, version=None, xml=None, archive=None, quotes=(), correction_of=None):
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
            payload = _read_xml(xml)
        else:
            query = urlencode({"db": "pmc", "id": pmcid, "retmode": "xml"})
            url = EFETCH + "?" + query
            request = Request(url, headers={"User-Agent": "Synthesis-evidence-capture/1"})
            with build_opener(PmcRedirectHandler()).open(request, timeout=20) as source:
                final_url = source.geturl()
                if not is_efetch_origin(final_url):
                    raise ValueError("PMC response is outside the HTTPS EFetch origin")
                payload = source.read(MAX_BYTES + 1)
        result = capture(payload, pmcid, doi, quotes=quotes, for_archive=archive is not None)
        if version is not None and result["source"]["version"] != version:
            raise ValueError("The captured PMC version does not match the requested version")
        if xml is None:
            result["source"].update(retrieval_url=final_url, retrieved_at=datetime.now(timezone.utc).isoformat())
        if correction_of is not None:
            result = _linked_entry(result, correction_of, archive, payload)
        elif archive is not None:
            archive_snapshot(payload, result, archive)
    except (OSError, HTTPException, ValueError, ET.ParseError, LookupError, RecursionError) as exc:
        result = {"status": "HOLD", "reason": str(exc)}
    result["capture_mode"] = mode
    if url:
        result["attempted_url"] = url
    return result


def link_matches(link, source):
    kind, target = link["id_type"], link["target"]
    if kind in {"pmc", "pmcid"}:
        return target in (source["pmcid"], source["pmcid"][3:], source["version"])
    if kind in {"pmid", "pubmed"}:
        return target == source.get("pmid")
    if kind == "doi":
        try:
            return normalize_doi(target) == source["doi"]
        except ValueError:
            return False
    return False


def matching_links(links, source):
    version_pattern = re.escape(source["pmcid"]) + r"\.[1-9][0-9]*"
    versioned = [link for link in links if link["id_type"] in {"pmc", "pmcid"}
                 and re.fullmatch(version_pattern, link["target"])]
    return [link for link in (versioned or links) if link_matches(link, source)]


def _linked_entry(result, original, archive, payload=None):
    if result["status"] != "CAPTURED":
        return result
    backlinks = matching_links([link for link in result["correction_links"]
                                if link["relation"] == "corrected-article"], original["source"])
    if not backlinks or result["source"]["pmcid"] == original["source"]["pmcid"]:
        return {"status": "HOLD", "reason": "Linked XML lacks a typed correction backlink to this article"}
    if result["article_type"] is not None and result["article_type"].casefold() != "correction":
        return {"status": "HOLD", "reason": "Linked XML declares an article type other than correction"}
    forward_links = [link for link in original["correction_links"] if link["relation"] == "correction-forward"
                     and link["id_type"] in CORRECTION_ID_TYPES]
    if forward_links and not matching_links(forward_links, result["source"]):
        return {"status": "HOLD", "reason": "Linked correction does not match a typed forward link from the article"}
    if archive is not None and payload is not None:
        archive_snapshot(payload, result, archive)
    result["backlinks"] = backlinks
    return result


def linked_correction_evidence(original, paths, *, follow=False, archive=None, quotes=()):
    """Verify explicit sidecars and, when authorized, direct PMC correction links."""
    entries = []
    for path in paths:
        try:
            payload = _read_xml(path)
            articles = article_entries(payload)
            if len(articles) != 1:
                raise ValueError("A linked XML file must contain exactly one article")
            pmcid = article_id(articles[0].find("front/article-meta"), "pmcid")
            captured = capture(payload, pmcid, quotes=quotes)
            captured["capture_mode"] = "ARCHIVED_XML"
            entries.append(_linked_entry(captured, original, archive, payload))
        except (OSError, ValueError, ET.ParseError, LookupError, RecursionError) as exc:
            entries.append({"status": "HOLD", "reason": str(exc)})

    seen = set()
    for link in original["correction_links"]:
        if link["relation"] != "correction-forward":
            continue
        matched = [entry for entry in entries if entry["status"] == "CAPTURED"
                   and link_matches(link, entry["source"])]
        target = link["target"]
        if link["id_type"] in {"pmc", "pmcid"} and re.fullmatch(r"[1-9][0-9]*", target):
            target = "PMC" + target
        if (not matched and follow and link["id_type"] in {"pmc", "pmcid"}
                and re.fullmatch(r"PMC[1-9][0-9]*(?:\.[1-9][0-9]*)?", target)
                and target.split(".")[0] != original["source"]["pmcid"]
                and target not in seen and len(seen) < MAX_LINKED_CORRECTIONS):
            seen.add(target)
            entry = retrieve_pmc_evidence(target.split(".")[0], version=target if "." in target else None,
                                         quotes=quotes, correction_of=original, archive=archive)
            entry["forward_link"] = link["locator"]
            entries.append(entry)
            matched = [entry] if entry["status"] == "CAPTURED" else []
        link["resolution"] = "CAPTURED" if matched else "MANUAL_REVIEW"
        if not matched:
            link["resolution_reason"] = "Supply verified PMC correction XML or follow a typed direct PMC link"
    return entries


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
