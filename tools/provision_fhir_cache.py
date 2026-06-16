"""
Provision the pinned FHIR package cache used by Stage 1c (HAPI CLI backend).

Stage 1c resolves FHIR R4 core + US Core 6.1.0 + their terminology dependencies
(hl7.terminology.r4, us.nlm.vsac, us.cdc.phinvads, etc. — ~550MB total) into a
project-local cache directory (FHIR_PACKAGE_CACHE_HOME, default .fhir-cache/)
rather than the developer's home directory, so every machine/CI runner resolves
identical package versions.

Run this once during the Docker build or as a CI cache-warm step — NOT on every
test run, and NOT committed to git (.fhir-cache/ is gitignored; it's ~550MB).
If it hasn't been run, Stage 1c still works: the validator resolves and caches
packages lazily on first use, just with a slower first run.

Usage:
  python tools/provision_fhir_cache.py
  FHIR_PACKAGE_CACHE_HOME=/opt/fhir-cache python tools/provision_fhir_cache.py
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage1"))
from stage1c_fhir_uscore_validator import (  # noqa: E402
    FHIR_PACKAGE_CACHE_HOME, FHIR_VERSION, JAVA_BIN, US_CORE_IG, VALIDATOR_JAR,
)

# Minimal synthetic resource — enough to force the validator to resolve and
# cache every package in the FHIR R4 + US Core dependency closure, without
# depending on test fixtures that may not exist or may change over time.
_DUMMY_PATIENT = {
    "resourceType": "Patient",
    "id": "provision-cache-dummy",
    "identifier": [{"system": "http://example.org/mrn", "value": "0"}],
    "name": [{"family": "Cache", "given": ["Provision"]}],
    "gender": "unknown",
}


def main() -> None:
    jar = Path(VALIDATOR_JAR)
    if not jar.exists():
        print(f"HAPI Validator CLI not found at {jar}. Download it first:\n"
              f"  https://github.com/hapifhir/org.hl7.fhir.core/releases/latest/download/validator_cli.jar")
        sys.exit(1)

    cache_dir = Path(FHIR_PACKAGE_CACHE_HOME)
    cache_dir.mkdir(parents=True, exist_ok=True)
    print(f"Provisioning FHIR package cache at {cache_dir} ...")

    with tempfile.TemporaryDirectory() as tmpdir:
        dummy = Path(tmpdir) / "Patient.ndjson"
        dummy.write_text(json.dumps(_DUMMY_PATIENT) + "\n")
        out = Path(tmpdir) / "out.json"

        for label, ig in [("base FHIR R4", None), (f"US Core ({US_CORE_IG})", US_CORE_IG)]:
            print(f"  Resolving packages for {label} ...")
            cmd = [
                JAVA_BIN, f"-Duser.home={cache_dir}", "-Xmx4g", "-jar", str(jar),
                "-version", FHIR_VERSION, "-output", str(out), "-tx", "n/a",
            ]
            if ig:
                cmd += ["-ig", ig]
            cmd += [str(dummy)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            if proc.returncode not in (0, 1):  # 1 = validation findings, not a crash
                print(proc.stdout[-2000:])
                print(proc.stderr[-2000:])
                print(f"Package resolution failed for {label} (exit {proc.returncode}).")
                sys.exit(1)

    size_mb = sum(f.stat().st_size for f in cache_dir.rglob("*") if f.is_file()) // (1024 * 1024)
    print(f"Done. Cache populated at {cache_dir} ({size_mb:,} MB).")


if __name__ == "__main__":
    main()
