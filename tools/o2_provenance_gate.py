#!/usr/bin/env python3
"""Fail closed when ODAS and oracle evidence cannot be proven identical.

This is a provenance gate, not a spatial-quality metric.  The manifest must
be generated independently from the actual input files and acquisition setup.
"""
import argparse
import hashlib
import json
from pathlib import Path

FIELDS = ("wav", "oracle", "native_trace")
CONTRACT = ("sample_rate_hz", "hop_samples", "first_sample_index",
            "pcm_channels", "microphones_m", "seed", "config_sha256")

def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def verify(manifest, root):
    problems = []
    file_problems = []
    for key in FIELDS:
        entry = manifest.get(key)
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            problems.append(f"{key}: missing file path")
            file_problems.append(key)
            continue
        expected = entry.get("sha256")
        if not isinstance(expected, str) or len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
            problems.append(f"{key}: missing/invalid sha256")
            file_problems.append(key)
            continue
        path = (root / entry["path"]).resolve()
        if not path.is_relative_to(root.resolve()):
            problems.append(f"{key}: path escapes evidence root")
            file_problems.append(key)
        elif not path.is_file():
            problems.append(f"{key}: missing file")
            file_problems.append(key)
        elif sha256_file(path) != expected:
            problems.append(f"{key}: SHA256 mismatch")
            file_problems.append(key)
    for key in CONTRACT:
        if key not in manifest:
            problems.append(f"{key}: missing acquisition contract")
    if manifest.get("pcm_channels") != [1, 2, 3, 4]:
        problems.append("pcm_channels: expected [1,2,3,4]")
    geometry = manifest.get("microphones_m")
    expected_geometry = [[0.032, 0, 0], [0, 0.032, 0],
                         [-0.032, 0, 0], [0, -0.032, 0]]
    if geometry != expected_geometry:
        problems.append("microphones_m: geometry/order not verified")
    for key in ("sample_rate_hz", "hop_samples"):
        if type(manifest.get(key)) is not int or manifest[key] <= 0:
            problems.append(f"{key}: expected positive integer")
    if type(manifest.get("first_sample_index")) is not int or manifest["first_sample_index"] < 0:
        problems.append("first_sample_index: expected nonnegative integer")
    if type(manifest.get("seed")) is not int:
        problems.append("seed: expected integer")
    config = manifest.get("config_sha256")
    if not isinstance(config, str) or len(config) != 64 or any(c not in "0123456789abcdef" for c in config):
        problems.append("config_sha256: missing/invalid")
    return {"status": "BLOCKED" if problems else "PASS",
            "problems": problems, "verified_file_hashes": not any(
                "SHA256" in p or "missing file" in p or "invalid sha256" in p or "missing file path" in p
                for p in problems)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    result = verify(json.loads(args.manifest.read_text(encoding="utf-8")), args.root)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2

if __name__ == "__main__":
    raise SystemExit(main())
