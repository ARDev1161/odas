#!/usr/bin/env python3
"""Fail-closed offline audit of native provisional SST counters.

This checks recorder consistency only. It does not infer SSL-to-track
association, identity, or separation quality.
"""
import argparse
import json
import math
from pathlib import Path


class InvalidTrace(ValueError):
    pass


def _unique_object_pairs(pairs):
    """Reject ambiguous JSON objects instead of silently taking the last key."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidTrace(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise InvalidTrace(f"nonstandard JSON numeric constant: {value}")


def audit(path):
    rows = 0
    observed = 0
    previous_hop = None
    previous_provisional = {}
    with Path(path).open(encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            try:
                row = json.loads(line, object_pairs_hook=_unique_object_pairs,
                                 parse_constant=_reject_constant)
            except (ValueError, TypeError) as exc:
                raise InvalidTrace(f"line {line_no}: invalid JSON: {exc}") from exc
            if not isinstance(row, dict) or row.get("schema") != "odas_sst_raw_v1":
                raise InvalidTrace(f"line {line_no}: unexpected schema")
            hop = row.get("hop_index")
            if type(hop) is not int or hop < 0 or (previous_hop is not None and hop != previous_hop + 1):
                raise InvalidTrace(f"line {line_no}: noncontiguous hop_index")
            previous_hop = hop
            if (type(row.get("hop_frames")) is not int or row["hop_frames"] != 128 or
                    type(row.get("sample_offset")) is not int or row["sample_offset"] != 128 * hop or
                    type(row.get("odas_timestamp")) is not int or row["odas_timestamp"] != hop + 1):
                raise InvalidTrace(f"line {line_no}: invalid sample clock")
            tracks = row.get("tracks_after")
            if not isinstance(tracks, list):
                raise InvalidTrace(f"line {line_no}: missing tracks_after")
            seen = set()
            seen_slots = set()
            current_provisional = {}
            for track in tracks:
                if not isinstance(track, dict):
                    raise InvalidTrace(f"line {line_no}: invalid track")
                track_id = track.get("track_id")
                if type(track_id) is not int or track_id <= 0 or track_id in seen:
                    raise InvalidTrace(f"line {line_no}: duplicate/invalid track ID")
                seen.add(track_id)
                slot = track.get("slot")
                if type(slot) is not int or not 0 <= slot < 32 or slot in seen_slots:
                    raise InvalidTrace(f"line {line_no}: duplicate/invalid track slot")
                seen_slots.add(slot)
                if track.get("state") != "P":
                    continue
                n = track.get("probation_observations")
                mean = track.get("probation_mean_activity")
                if type(n) is not int or n < 0:
                    raise InvalidTrace(f"line {line_no}: invalid probation count")
                if n == 0:
                    if mean is not None:
                        raise InvalidTrace(f"line {line_no}: zero-count mean must be null")
                elif type(mean) not in (float, int) or not math.isfinite(mean) or not 0 <= mean <= 1:
                    raise InvalidTrace(f"line {line_no}: invalid probation mean")
                prior = previous_provisional.get(track_id)
                if prior is not None and n < prior:
                    raise InvalidTrace(f"line {line_no}: probation counter regressed for live track {track_id}")
                current_provisional[track_id] = n
                observed += 1
            previous_provisional = current_provisional
            rows += 1
    if not rows:
        raise InvalidTrace("empty trace")
    return {"status": "PASS", "hops": rows, "provisional_observations": observed,
            "association_evidence": "BLOCKED_MISSING_PER_TRACK_ASSOCIATION_EVENT"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jsonl")
    args = parser.parse_args()
    try:
        print(json.dumps(audit(args.jsonl), sort_keys=True))
    except (InvalidTrace, OSError) as exc:
        parser.exit(2, f"FAIL: {exc}\n")


if __name__ == "__main__":
    main()
