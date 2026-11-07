#!/usr/bin/env python3
"""Inspect a native supplementary table; do not run the NMA."""
import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("inputs", type=Path)
    p.add_argument("supplement_docx", type=Path)
    a = p.parse_args()
    d = json.loads(a.inputs.read_text(encoding="utf-8"))
    if hashlib.sha256(a.supplement_docx.read_bytes()).hexdigest() != d["sources"]["supplement_docx_sha256"]:
        raise ValueError("Downloaded supplementary source hash differs")
    with zipfile.ZipFile(a.supplement_docx) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    tables = []
    for table in root.findall(".//w:tbl", ns):
        rows = [["".join(t.text or "" for t in cell.findall(".//w:t", ns))
                 for cell in row.findall("./w:tc", ns)]
                for row in table.findall("./w:tr", ns)]
        if len(rows) > 100 and rows[0][0] == d["native_S3_inventory"]["table_first_header"]:
            tables.append(rows)
    if len(tables) != 1:
        raise ValueError("Expected exactly one matching characteristics table")
    cfg = d["native_S3_inventory"]
    rows = tables[0][cfg["table_data_header_rows"]:]
    if any(len(row) != cfg["expected_data_columns"] for row in rows):
        raise ValueError("Unexpected source-table column structure")
    registered = sum(row[3].strip() not in ("", "/") for row in rows)
    multicentre = sum(row[4].strip().lower() == "mc" for row in rows)
    out = {
        "comparison_rows": len(rows),
        "registered_rows": registered,
        "multicentre_rows": multicentre,
        "registered_percent": round(100 * registered / len(rows), 1),
        "multicentre_percent": round(100 * multicentre / len(rows), 1),
        "sum_intervention_n": sum(int(row[11]) for row in rows),
        "sum_control_n": sum(int(row[12]) for row in rows),
        "sum_rowwise_total_n": sum(int(row[13]) for row in rows),
        "registry_row_counts": dict(Counter(row[3] for row in rows if row[3].strip())),
        "scope": "Row inventory, not unique-participant count or fitted overlap test."
    }
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
