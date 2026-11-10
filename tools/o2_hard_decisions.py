#!/usr/bin/env python3
"""Count actual native SST births/retirements, never infer identity from posterior."""
import argparse
import json
from collections import Counter

def analyze(lines):
    stats = Counter()
    previous = None
    prev_hop = None
    for number, line in enumerate(lines, 1):
        if not line.strip():
            raise ValueError(f"line {number}: empty row")
        row = json.loads(line)
        if row.get("schema") != "odas_sst_raw_v1":
            raise ValueError(f"line {number}: schema")
        hop = row.get("hop_index")
        if type(hop) is not int or hop < 0 or (prev_hop is not None and hop != prev_hop + 1):
            raise ValueError(f"line {number}: non-contiguous hop")
        prev_hop = hop
        tracks = row.get("tracks_after")
        births = row.get("births")
        retired = row.get("retirements")
        if not isinstance(tracks, list) or not isinstance(births, list) or not isinstance(retired, list):
            raise ValueError(f"line {number}: missing decisions")
        active = set()
        for track in tracks:
            if not isinstance(track, dict) or type(track.get("track_id")) is not int:
                raise ValueError(f"line {number}: malformed track")
            ident = track["track_id"]
            if ident <= 0 or ident in active:
                raise ValueError(f"line {number}: duplicate/invalid track")
            active.add(ident)
        for name, ids in (("births", births), ("retirements", retired)):
            if any(type(v) is not int or v <= 0 for v in ids) or len(ids) != len(set(ids)):
                raise ValueError(f"line {number}: invalid {name}")
        born, gone = set(births), set(retired)
        if born & gone:
            raise ValueError(f"line {number}: born and retired same hop")
        if previous is not None:
            if active - previous != born or previous - active != gone:
                raise ValueError(f"line {number}: transition mismatch")
        elif not born.issubset(active):
            raise ValueError(f"line {number}: birth absent from output")
        stats["hops"] += 1
        stats["births"] += len(born)
        stats["retirements"] += len(gone)
        stats["hops_with_two_tracks"] += len(active) >= 2
        stats["max_simultaneous_tracks"] = max(stats["max_simultaneous_tracks"], len(active))
        stats["hops_with_birth"] += bool(born)
        stats["hops_with_retirement"] += bool(gone)
        previous = active
    if not stats["hops"]:
        raise ValueError("empty trace")
    return dict(stats, oracle_identity="NOT_MEASURED", sss_quality="NOT_MEASURED")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("trace")
    args = parser.parse_args()
    with open(args.trace, encoding="utf-8") as f:
        print(json.dumps(analyze(f), sort_keys=True))

if __name__ == "__main__":
    main()
