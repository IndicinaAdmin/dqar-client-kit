"""
Stage 2 redaction regression check.

Runs stage2/anonymize_extract.py against the deterministic, dependency-free
reference extract (tests/build_compliant_reference.py — no live FHIR server
or Synthea needed, unlike tests/fixtures/), then asserts:

  1. No raw PHI value from the known source data survives in the output
     (name, full birthdate, phone, street address).
  2. Identifier hashing is deterministic for a fixed salt and differs across
     salts (confirms cross-resource joins survive de-identification without
     being guessable across engagements).
  3. The redacted output still passes Stage 1b structural validation.

Run from project root:
    python tests/verify_stage2_redaction.py
"""

import gzip
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "stage1"))

from stage2.anonymize_extract import run as run_stage2  # noqa: E402

REFERENCE_DIR = REPO_ROOT / "data" / "compliant-reference"

# Known raw PHI values baked into tests/build_compliant_reference.py's Patient.
RAW_FAMILY_NAME   = "Reference"
RAW_PHONE         = "555-000-0001"
RAW_BIRTHDATE     = "1975-06-15"
RAW_ADDRESS_LINE  = "123 Reference Lane"
RAW_CITY          = "Springfield"


def _ensure_reference_extract() -> None:
    if not REFERENCE_DIR.exists() or not any(REFERENCE_DIR.glob("*.ndjson")):
        subprocess.run(
            [sys.executable, str(REPO_ROOT / "tests" / "build_compliant_reference.py")],
            check=True, cwd=REPO_ROOT,
        )


def _redact_to(out_dir: Path, salt: str) -> dict:
    return run_stage2(
        ndjson_dir=str(REFERENCE_DIR),
        output_dir=str(out_dir),
        engagement="verify-stage2",
        output_path=str(out_dir.parent / "stage2-summary.json"),
        salt=salt,
    )


def _read_all_text(out_dir: Path) -> str:
    chunks = []
    for gz in out_dir.glob("*.ndjson.gz"):
        chunks.append(gzip.decompress(gz.read_bytes()).decode("utf-8"))
    return "\n".join(chunks)


def _patient_identifier_hash(out_dir: Path) -> str:
    raw = gzip.decompress((out_dir / "Patient.ndjson.gz").read_bytes()).decode("utf-8")
    patient = json.loads(raw.splitlines()[0])
    return patient["identifier"][0]["value"]


def main() -> None:
    _ensure_reference_extract()
    failures = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        out_a1 = tmp / "redacted-a1"
        out_a2 = tmp / "redacted-a2"
        out_b  = tmp / "redacted-b"

        _redact_to(out_a1, salt="salt-a")
        _redact_to(out_a2, salt="salt-a")
        _redact_to(out_b,  salt="salt-b")

        # --- 1. No raw PHI survives -----------------------------------------
        text = _read_all_text(out_a1)
        for raw_value, label in [
            (RAW_FAMILY_NAME,  "family name"),
            (RAW_PHONE,        "phone number"),
            (RAW_BIRTHDATE,    "full birthdate"),
            (RAW_ADDRESS_LINE, "street address"),
            (RAW_CITY,         "city"),  # city stripped at non-demographic granularity too
        ]:
            if raw_value in text:
                failures.append(f"Raw {label} ('{raw_value}') found in redacted output")

        # given name alone ("Patient") is too common a substring to safely
        # grep for (it appears in resourceType values) — skipped intentionally.

        # --- 2. Identifier hashing: deterministic per salt, differs across salts ---
        hash_a1 = _patient_identifier_hash(out_a1)
        hash_a2 = _patient_identifier_hash(out_a2)
        hash_b  = _patient_identifier_hash(out_b)

        if not hash_a1.startswith("redacted:sha256:"):
            failures.append(f"Identifier not hashed in expected format: {hash_a1}")
        if hash_a1 != hash_a2:
            failures.append(f"Same salt produced different hashes: {hash_a1} != {hash_a2}")
        if hash_a1 == hash_b:
            failures.append("Different salts produced the same hash — salt is not being applied")

        # --- 3. Stage 1b re-verification (already run inside run_stage2, but
        #        re-assert here against the actual report return value) -------
        report = run_stage2(
            ndjson_dir=str(REFERENCE_DIR),
            output_dir=str(tmp / "redacted-verify"),
            engagement="verify-stage2",
            output_path=str(tmp / "stage2-verify.json"),
            salt="salt-verify",
        )
        reverify = report.get("reverify_stage1b") or {}
        files_failed = reverify.get("summary", {}).get("files_failed")
        if files_failed != 0:
            failures.append(f"Post-redaction Stage 1b re-verification failed: {files_failed} file(s)")

    if failures:
        print("Stage 2 redaction check FAILED:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)

    print("Stage 2 redaction check PASSED:")
    print("  - no raw PHI survives in redacted output")
    print("  - identifier hashing is salt-deterministic and salt-sensitive")
    print("  - redacted output passes Stage 1b structural validation")


if __name__ == "__main__":
    main()
