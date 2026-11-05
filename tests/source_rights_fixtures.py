"""Build private grants for generated synthetic test bytes; no production bypass."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os


def synthetic_env(root):
    sources = []
    now = datetime.now(timezone.utc)
    resources = [("pmc:PMC123", "10.1234/synthetic", None),
                 ("pmc:PMC124", "10.1234/correction", None)]
    for path in root.iterdir():
        if path.is_file() and path.name not in {"rights.json", "rights.jsonl"}:
            resources.append((path.resolve().as_uri(),
                              "10.1234/correction" if path.name == "correction.xml" else "10.1234/synthetic",
                              sha256(path.read_bytes()).hexdigest()))
            if path.suffix == ".json":
                data = json.loads(path.read_bytes())
                for source in data.get("sources", []):
                    if source.get("retrieval_path"):
                        resources.append((source["retrieval_path"], "10.1234/synthetic", None))
    for resource, doi, digest in resources:
        source = {"resource": resource, "doi": doi, "journal": "Synthetic Journal",
                  "publisher": "Synthetic Publisher", "identity_verified": True,
                  "identity_evidence": {"ref": "synthetic:fixture-generator", "sha256": "a" * 64},
                  "permission": {"basis": "explicit_permission", "reviewed_by": "synthetic test author",
                      "reviewed_at": (now - timedelta(minutes=1)).isoformat(),
                      "expires_at": (now + timedelta(days=1)).isoformat(),
                      "operations": ["acquire", "process", "replay"],
                      "evidence": [{"ref": "synthetic:generated-test-only", "sha256": "b" * 64}],
                      "restrictions_checked": True, "conditions_satisfied": True}}
        if digest:
            source["content_sha256"] = digest
        if resource.endswith((".json", ".jsonl")):
            member = dict(source, resource="pmc:PMC123")
            member.pop("content_sha256", None)
            source["lineage"] = [member]
        sources.append(source)
    manifest = root / "rights.json"
    manifest.write_text(json.dumps({"sources": sources}), encoding="utf-8")
    return dict(os.environ, SYNTHESIS_RIGHTS_MANIFEST=str(manifest),
                SYNTHESIS_RIGHTS_LOG=str(root / "rights.jsonl"))


def synthetic_authorize(resource, operation, *, doi=None, **kwargs):
    """Only legacy parser tests replace the IO gate; boundary tests use real gates."""
    identity = "10.1234/correction" if "124" in resource or "correction.xml" in resource else "10.1234/synthetic"
    return {"decision_id": "synthetic-unit-test", "doi": doi or identity, "status": "ALLOW"}
