"""
Flatten Synthea FHIR transaction bundles → per-resource NDJSON files.

Reads every *.json bundle from --synthea-dir (default: data/synthea/fhir/)
and writes one NDJSON line per resource into --output-dir (default: data/export/).
Each output file is named {ResourceType}.ndjson.

Usage:
    python tools/synthea_to_ndjson.py
    python tools/synthea_to_ndjson.py --synthea-dir data/synthea/fhir --output-dir data/export
    python tools/synthea_to_ndjson.py --exclude AuditEvent Provenance
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def flatten(
    synthea_dir: str = "data/synthea/fhir",
    output_dir: str  = "data/export",
    exclude: list    = None,
) -> dict:
    src = Path(synthea_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    exclude = set(exclude or [])

    bundles = sorted(src.glob("*.json"))
    if not bundles:
        print(f"No JSON bundles found in {src}")
        sys.exit(1)

    print(f"Synthea → NDJSON")
    print(f"  Source : {src}  ({len(bundles)} bundles)")
    print(f"  Output : {out}")
    if exclude:
        print(f"  Exclude: {', '.join(sorted(exclude))}")
    print()

    # Collect resources by type
    by_type: dict[str, list] = defaultdict(list)
    skipped_rt = set()

    for bundle_path in bundles:
        try:
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"  SKIP {bundle_path.name}: {exc}")
            continue

        if bundle.get("resourceType") != "Bundle":
            # Some Synthea files are bare resources (hospitalInformation, practitionerInformation)
            rt = bundle.get("resourceType")
            if rt and rt not in exclude:
                by_type[rt].append(bundle)
            continue

        for entry in bundle.get("entry", []):
            resource = entry.get("resource")
            if not resource:
                continue
            rt = resource.get("resourceType")
            if not rt:
                continue
            if rt in exclude:
                skipped_rt.add(rt)
                continue
            by_type[rt].append(resource)

    if not by_type:
        print("No resources found.")
        sys.exit(1)

    # Write NDJSON files
    counts = {}
    for rt in sorted(by_type):
        resources = by_type[rt]
        ndjson_path = out / f"{rt}.ndjson"
        with open(ndjson_path, "w", encoding="utf-8") as f:
            for r in resources:
                f.write(json.dumps(r, separators=(",", ":")) + "\n")
        counts[rt] = len(resources)
        print(f"  {rt}.ndjson  →  {len(resources):,} resources")

    if skipped_rt:
        print(f"\n  Excluded: {', '.join(sorted(skipped_rt))}")

    total = sum(counts.values())
    print(f"\n  {len(counts)} resource types · {total:,} resources total")
    print(f"  Written to: {out.resolve()}")

    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Flatten Synthea FHIR bundles into per-resource NDJSON files"
    )
    parser.add_argument("--synthea-dir", default="data/synthea/fhir")
    parser.add_argument("--output-dir",  default="data/export")
    parser.add_argument(
        "--exclude", nargs="*", default=[],
        metavar="RESOURCE_TYPE",
        help="Resource types to omit (e.g. --exclude AuditEvent Provenance)",
    )
    args = parser.parse_args()

    flatten(
        synthea_dir = args.synthea_dir,
        output_dir  = args.output_dir,
        exclude     = args.exclude,
    )
