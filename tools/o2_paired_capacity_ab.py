#!/usr/bin/env python3
"""Compare frozen native ODAS SST traces; report capacity, never speaker identity."""
import argparse
import hashlib
import json
from pathlib import Path

from o2_clock_coverage import audit


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare(oracle_path, variants, wav_hashes, wav_paths):
    if set(wav_paths) != set(variants):
        raise ValueError("require a real WAV path for each variant")
    measured = {name: sha256(path) for name, path in wav_paths.items()}
    if measured != wav_hashes:
        raise ValueError("declared WAV SHA256 differs from actual WAV bytes")
    if set(variants) != {"upstream", "dev", "feature"}:
        raise ValueError("require upstream, dev and feature traces")
    if set(wav_hashes) != set(variants) or len(set(wav_hashes.values())) != 1:
        raise ValueError("A/B input WAV SHA256 mismatch")
    digest = next(iter(wav_hashes.values()))
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("invalid WAV SHA256")
    oracle = json.loads(Path(oracle_path).read_text(encoding="utf-8"))
    output = {}
    for name in ("upstream", "dev", "feature"):
        with Path(variants[name]).open(encoding="utf-8") as stream:
            trace = [json.loads(line) for line in stream if line.strip()]
        report = audit(oracle, trace)
        overlap = report["overlap_capacity_upper_bound"]
        if overlap["status"] != "MEASURED_CAPACITY_ONLY":
            raise ValueError(f"{name}: missing measured occupancy")
        output[name] = {
            "trace_sha256": sha256(variants[name]),
            "overlap_hops": overlap["oracle_overlap_hops"],
            "multi_track_overlap_hops": overlap["native_multi_track_hops_during_overlap"],
            "source_hop_recall_ceiling": overlap["max_possible_source_hop_recall"],
            "two_source_recall_ceiling": overlap["max_possible_two_source_recall"],
            "missing_source_hops_lower_bound": report["source_capacity_deficit"]["total_missing_source_hops_lower_bound"],
        }
    if len({v["overlap_hops"] for v in output.values()}) != 1:
        raise ValueError("inconsistent overlap clocks")
    return {"status": "CAPACITY_ONLY_NOT_QUALITY_PASS", "wav_sha256": digest,
            "oracle_sha256": sha256(oracle_path), "variants": output,
            "idf1": "NOT_MEASURED", "sss_quality": "NOT_MEASURED",
            "coordinate_frame": "NOT_VERIFIED"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--oracle", type=Path, required=True)
    for name in ("upstream", "dev", "feature"):
        parser.add_argument("--" + name, type=Path, required=True)
        parser.add_argument("--" + name + "-wav-sha256", required=True)
        parser.add_argument("--" + name + "-wav", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    names = ("upstream", "dev", "feature")
    result = compare(args.oracle, {n: getattr(args, n) for n in names},
                     {n: getattr(args, n + "_wav_sha256") for n in names},
                     {n: getattr(args, n + "_wav") for n in names})
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
