"""
Stage 2 — PHI redaction / anonymization (Path B only, client-initiated).

Reads the same raw NDJSON extract Stage 1 validated and writes a redacted
copy — one gzip-compressed NDJSON file per input file, same resource-type
filenames, ready for delivery to the Sonian Aidbox sandbox. Optional and
never runs as part of the default Stage 1 pipeline (see orchestrate.py
--redact).

Redaction uses stage2/redact.py (vendored from HealthClawGuardrails). Each
identifier is SHA-256 hashed with a per-engagement salt, so the same member
hashes to the same pseudonym across every resource in this extract (needed
for the Level 3-5 measure attribution joins) without being guessable or
comparable across engagements.

After writing the redacted copy, Stage 1b structural validation re-runs
against it (same check used on the raw extract) to confirm redaction did
not corrupt JSON structure or resourceType/filename alignment — matches the
"confirms redaction did not corrupt structural integrity" step the spec
calls for at Stage 3 ingest, run here instead so breakage is caught
immediately, client-side.

No PHI appears in the output report — aggregate redaction counts only.

Usage:
  python stage2/anonymize_extract.py --ndjson-dir data/export --engagement client-name
"""

import argparse
import gzip
import json
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage1"))

from stage2.redact import redact, RedactionStats
import stage1b_ndjson_validator as _1b


def _load_or_create_salt(output_dir: Path, engagement: str) -> str:
    """Reuse the same salt across repeated runs for this engagement, so
    re-running Stage 2 on a refreshed extract keeps consistent hashes.

    Stored next to (not inside) output_dir: output_dir is the deliverable
    that ships to Sonian, and the salt must never travel with the hashed
    extract it salts — shipping both together lets the recipient brute-force
    the identifier hashes, defeating the point of salting them.
    """
    salt_path = output_dir.parent / f".dqar-redact-salt-{engagement}"
    if salt_path.exists():
        return salt_path.read_text().strip()
    salt = secrets.token_hex(16)
    salt_path.write_text(salt + "\n")
    return salt


def run(
    ndjson_dir: str = "data/export",
    output_dir: str = "data/redacted",
    engagement: str = "client",
    output_path: str = None,
    salt: str = None,
    reverify: bool = True,
) -> dict:
    in_dir = Path(ndjson_dir)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(in_dir.glob("*.ndjson"))
    if not files:
        print(f"No .ndjson files found in {in_dir}")
        sys.exit(1)

    if salt is None:
        salt = _load_or_create_salt(out_dir, engagement)

    print("Stage 2 — PHI redaction / anonymization")
    print(f"  {len(files)} files in {in_dir} -> {out_dir}\n")

    totals = RedactionStats()
    file_results = []

    for ndjson_file in files:
        plain_out = out_dir / ndjson_file.name
        resource_count = 0
        with open(ndjson_file, "r", encoding="utf-8") as src, \
             open(plain_out, "w", encoding="utf-8") as dst:
            for line in src:
                line = line.strip()
                if not line:
                    continue
                resource = json.loads(line)
                redacted, stats = redact(resource, salt=salt)
                dst.write(json.dumps(redacted) + "\n")
                totals.merge(stats)
                resource_count += 1

        file_results.append({"file": ndjson_file.name, "resource_count": resource_count})
        print(f"  {ndjson_file.name:35s}  {resource_count:>6} resources redacted")

    # Re-verify structural integrity on the redacted plaintext before compressing.
    reverify_report = None
    if reverify:
        print("\n  Re-running Stage 1b against redacted output...")
        reverify_report = _1b.run(
            ndjson_dir=str(out_dir),
            output_path=str(out_dir / f"stage2-reverify-{engagement}.json"),
        )
        failed = reverify_report.get("summary", {}).get("files_failed", 0)
        if failed:
            print(f"  WARNING: {failed} file(s) failed structural validation after redaction.")
        else:
            print("  Redacted extract passes Stage 1b structural validation.")

    # Compress each file in place and drop the plaintext copy.
    for ndjson_file in files:
        plain_out = out_dir / ndjson_file.name
        gz_out = out_dir / (ndjson_file.name + ".gz")
        with open(plain_out, "rb") as src, gzip.open(gz_out, "wb") as dst:
            dst.write(src.read())
        plain_out.unlink()

    report = {
        "report_type": "dqar-stage2-redaction",
        "stage": "2",
        "engagement": engagement,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(out_dir.resolve()),
        "summary": {
            "files_redacted": len(files),
            "total_resources": sum(f["resource_count"] for f in file_results),
            **totals.as_dict(),
        },
        "files": file_results,
        "reverify_stage1b": reverify_report,
    }

    if output_path is None:
        output_path = f"data/reports/stage2-{engagement}.json"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(report, indent=2))

    print(f"\nStage 2 complete: {report['summary']['total_resources']:,} resources redacted")
    print(f"Redacted extract : {out_dir} (*.ndjson.gz)")
    print(f"Report           : {output_path}")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 2: PHI redaction / anonymization")
    parser.add_argument("--ndjson-dir", default="data/export")
    parser.add_argument("--output-dir", default="data/redacted")
    parser.add_argument("--engagement", default="client")
    parser.add_argument("--output", default=None, help="Path for the stage2 summary JSON report")
    parser.add_argument("--salt", default=None, help="Override the auto-generated per-engagement salt")
    parser.add_argument("--no-reverify", action="store_true", help="Skip the post-redaction Stage 1b re-check")
    args = parser.parse_args()

    run(
        ndjson_dir=args.ndjson_dir,
        output_dir=args.output_dir,
        engagement=args.engagement,
        output_path=args.output,
        salt=args.salt,
        reverify=not args.no_reverify,
    )
