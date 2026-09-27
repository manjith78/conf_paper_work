"""
Reproducible downloader for the official PhysioNet dataset used by this
project:

  "Wearable Device Dataset from Induced Stress and Structured Exercise
  Sessions", v1.0.0, PhysioNet, DOI: 10.13026/zzf8-xv61.

This script performs EXACTLY the steps that were performed manually to
obtain the copy this project was built from, so that copy is reproducible
by anyone re-running this script:

  1. Download the official get-zip archive (resumable, since the file is
     ~73 MB and slow public mirrors can be interrupted).
  2. Verify the downloaded zip's size against the size PhysioNet reports.
  3. Verify the zip's own SHA-256 against the value recorded in
     data/metadata/dataset_manifest.json (the hash of the copy this
     project actually used -- if PhysioNet ever changes the archive's
     bytes, this script will detect the mismatch and refuse to silently
     proceed).
  4. Extract the archive.
  5. Verify EVERY extracted file against the dataset's own SHA256SUMS.txt
     (708 files, shipped by PhysioNet inside the dataset itself). This is
     the authoritative integrity check -- it verifies the payload, not
     just the outer zip.

If any check fails, the script stops and reports exactly what failed. It
never silently continues with unverified data.

Usage (from the project's src/preprocessing directory, or anywhere -- paths
are computed relative to this file):

    python download_dataset.py
    python download_dataset.py --skip-download   # re-verify an existing copy
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

DATASET_URL = "https://physionet.org/content/wearable-device-dataset/get-zip/1.0.0/"
RAW_DIR = os.path.join(REPO_ROOT, "data", "raw")
ZIP_PATH = os.path.join(RAW_DIR, "dataset.zip")
EXTRACT_DIR = os.path.join(RAW_DIR, "extracted")
MANIFEST_PATH = os.path.join(REPO_ROOT, "data", "metadata", "dataset_manifest.json")

# The exact expected values for the copy this project was built and
# verified against. Recorded here (not just in the manifest) so this
# script is self-contained and can verify a fresh download against a
# known-good reference without first trusting the manifest file.
EXPECTED_ZIP_SIZE_BYTES = 73121143
EXPECTED_ZIP_SHA256 = "229b6cd388d0193bea1320e01bee7ca8525c168920add7d95f4969ae6d57899c"
EXPECTED_EXTRACTED_FILE_COUNT = 708  # per the dataset's own SHA256SUMS.txt


def sha256_of_file(path, chunk_size=1024 * 1024):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def download(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    print(f"Downloading:\n  {url}\n  -> {dest}")
    # Resumable download via curl (handles slow/interrupted connections
    # better than urllib for a ~73 MB file from a public research mirror).
    if os.path.exists(dest):
        print(f"  Partial/existing file found ({os.path.getsize(dest)} bytes) -- resuming.")
    cmd = ["curl", "-L", "-C", "-", "-o", dest, url]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise RuntimeError(f"curl failed with exit code {result.returncode}")


def verify_zip(path):
    actual_size = os.path.getsize(path)
    print(f"Zip size: {actual_size} bytes (expected {EXPECTED_ZIP_SIZE_BYTES})")
    if actual_size != EXPECTED_ZIP_SIZE_BYTES:
        print("  MISMATCH -- the downloaded file does not match the expected size.")
        return False
    print("Computing SHA-256 of the downloaded zip (this takes a moment)...")
    actual_hash = sha256_of_file(path)
    print(f"Zip SHA-256: {actual_hash}")
    print(f"Expected:    {EXPECTED_ZIP_SHA256}")
    if actual_hash != EXPECTED_ZIP_SHA256:
        print("  MISMATCH -- the downloaded archive's contents differ from the "
              "reference copy this project was built and verified against. "
              "This could mean PhysioNet has updated the archive, or the "
              "download was corrupted. Do NOT proceed without investigating.")
        return False
    print("  OK -- zip matches the verified reference exactly.")
    return True


def extract(zip_path, out_dir):
    print(f"Extracting to {out_dir} ...")
    os.makedirs(out_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        bad_file = zf.testzip()
        if bad_file is not None:
            raise RuntimeError(f"Corrupt entry in zip: {bad_file}")
        zf.extractall(out_dir)
    print("  Extraction OK (zip integrity test passed).")


def find_dataset_root(extract_dir):
    """The zip extracts into a single top-level folder named after the
    dataset; find it rather than hardcoding the exact PhysioNet folder
    name (which is versioned)."""
    entries = [e for e in os.listdir(extract_dir) if os.path.isdir(os.path.join(extract_dir, e))]
    if len(entries) != 1:
        raise RuntimeError(f"Expected exactly one top-level extracted folder, found: {entries}")
    return os.path.join(extract_dir, entries[0])


def verify_extracted_files(dataset_root):
    """Verifies every extracted file against the dataset's OWN
    SHA256SUMS.txt, shipped by PhysioNet inside the archive. This is the
    authoritative per-file integrity check."""
    sums_path = os.path.join(dataset_root, "SHA256SUMS.txt")
    if not os.path.exists(sums_path):
        raise RuntimeError(f"SHA256SUMS.txt not found at {sums_path} -- cannot verify payload integrity.")

    print(f"Verifying extracted files against {sums_path} ...")
    n_checked, n_failed, n_missing = 0, 0, 0
    failures = []
    with open(sums_path, "r") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            expected_hash, rel_path = line.split(None, 1)
            rel_path = rel_path.strip()
            full_path = os.path.join(dataset_root, rel_path)
            if not os.path.exists(full_path):
                n_missing += 1
                failures.append(f"MISSING: {rel_path}")
                continue
            actual_hash = sha256_of_file(full_path)
            n_checked += 1
            if actual_hash != expected_hash:
                n_failed += 1
                failures.append(f"HASH MISMATCH: {rel_path}")

    print(f"  Checked: {n_checked} files, {n_failed} hash mismatches, {n_missing} missing files.")
    if n_checked != EXPECTED_EXTRACTED_FILE_COUNT:
        print(f"  WARNING: expected {EXPECTED_EXTRACTED_FILE_COUNT} files listed in "
              f"SHA256SUMS.txt, found {n_checked}. The dataset's own manifest "
              f"may have changed, or extraction is incomplete.")
    if failures:
        print("  FAILURES:")
        for msg in failures[:50]:
            print(f"    {msg}")
        if len(failures) > 50:
            print(f"    ... and {len(failures) - 50} more")
        return False
    print("  OK -- every file in SHA256SUMS.txt matches exactly.")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-download", action="store_true",
                         help="Skip downloading; verify/extract an existing data/raw/dataset.zip.")
    parser.add_argument("--skip-extract", action="store_true",
                         help="Skip extraction; verify an existing data/raw/extracted/ tree.")
    args = parser.parse_args()

    if not args.skip_download:
        download(DATASET_URL, ZIP_PATH)

    if not os.path.exists(ZIP_PATH):
        print(f"ERROR: {ZIP_PATH} does not exist. Run without --skip-download first.")
        sys.exit(1)

    if not verify_zip(ZIP_PATH):
        print("\nABORTING: zip verification failed. Refusing to extract unverified data.")
        sys.exit(1)

    if not args.skip_extract:
        extract(ZIP_PATH, EXTRACT_DIR)

    dataset_root = find_dataset_root(EXTRACT_DIR)
    print(f"Dataset root: {dataset_root}")

    if not verify_extracted_files(dataset_root):
        print("\nABORTING: one or more extracted files failed integrity verification.")
        sys.exit(1)

    print("\nSUCCESS: dataset downloaded, extracted, and fully verified.")
    print(f"Dataset root for downstream processing: {dataset_root}")


if __name__ == "__main__":
    main()
