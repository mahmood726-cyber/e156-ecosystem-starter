#!/usr/bin/env python3
"""Inspect public aggregate exports and R-code text; do not execute the R model."""
import argparse
import csv
import hashlib
import io
import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("inputs", type=Path)
    p.add_argument("data_zip", type=Path)
    p.add_argument("code_docx", type=Path)
    a = p.parse_args()
    d = json.loads(a.inputs.read_text(encoding="utf-8"))
    for file, key in ((a.data_zip, "data_zip_sha256"), (a.code_docx, "code_docx_sha256")):
        if hashlib.sha256(file.read_bytes()).hexdigest() != d["sources"][key]:
            raise ValueError(f"Source hash differs: {file.name}")
    cfg = d["network_count_refutation"]
    with zipfile.ZipFile(a.data_zip) as z:
        rows = list(csv.DictReader(io.StringIO(z.read(cfg["csv"]).decode("utf-8-sig"))))
        refs = list(csv.DictReader(io.StringIO(z.read("Supplementary_data_final/reference_arms.csv").decode("utf-8-sig"))))
    ids = sorted({r["study"] for r in rows if r["models"] == cfg["model"]})
    excluded = cfg["explicit_excluded_study"]
    if excluded not in ids:
        raise ValueError("Excluded study missing from source data")
    arms = sorted({r["arm_drug"] for r in refs if r["study"] == excluded})
    if arms != sorted(cfg["excluded_arms"]):
        raise ValueError("Source arm identities differ")
    with zipfile.ZipFile(a.code_docx) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    code = "\n".join("".join(t.text or "" for t in q.findall(".//w:t", ns)) for q in root.findall(".//w:p", ns))
    if cfg["published_R_filter"] not in code:
        raise ValueError("Documented exclusion statement absent from code text")
    print(json.dumps({"doi": d["doi"], "stage1_studies": len(ids),
                      "network_studies_after_documented_exclusion": len(set(ids) - {excluded}),
                      "excluded_study": excluded, "source_arms": arms,
                      "scope": "Static source inspection only; not a native R or MCMC replay."}, indent=2))

if __name__ == "__main__":
    main()
