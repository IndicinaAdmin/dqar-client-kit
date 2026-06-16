"""
Download the HAPI FHIR Validator CLI jar at Docker build time.

tools/validator_cli.jar is gitignored (177MB) so it is not committed.
This script is called as a Dockerfile RUN step to fetch and verify it.

To upgrade the validator version:
  1. Update VALIDATOR_VERSION and EXPECTED_SHA256 below.
  2. Rebuild the Docker image.
"""

import hashlib
import pathlib
import sys
import urllib.request

VALIDATOR_VERSION = "6.9.10"
DOWNLOAD_URL = (
    "https://github.com/hapifhir/org.hl7.fhir.core"
    f"/releases/download/{VALIDATOR_VERSION}/validator_cli.jar"
)
EXPECTED_SHA256 = "176e814c62e72820c4bdbbe0ad6998dcda038d7af32ad902aba97a4d58b9473c"

dest = pathlib.Path(__file__).resolve().parent / "validator_cli.jar"

if dest.exists():
    print(f"validator_cli.jar already present at {dest} — skipping download.")
    sys.exit(0)

print(f"Downloading HAPI Validator CLI {VALIDATOR_VERSION} (~177MB) ...")
dest.parent.mkdir(parents=True, exist_ok=True)
urllib.request.urlretrieve(DOWNLOAD_URL, dest)

actual = hashlib.sha256(dest.read_bytes()).hexdigest()
if actual != EXPECTED_SHA256:
    dest.unlink(missing_ok=True)
    print(f"SHA256 mismatch — expected {EXPECTED_SHA256}, got {actual}")
    sys.exit(1)

print(f"OK — {dest} ({dest.stat().st_size // (1024*1024)}MB, sha256: {actual[:16]}…)")
