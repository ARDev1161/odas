#!/usr/bin/env python3
"""Strict, streaming validator for ODAS offline SSL/SST diagnostic JSONL.

This validates *recorded observations*, not ODAS tracking quality. It never
synthesizes missing measurements or treats a missing trace as PASS.
"""
import argparse
import json
import math
import sys


class TraceError(ValueError):
    pass


def integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise TraceError(f"{label}: expected integer >= {minimum}")
    return value


def probability(value, label):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise TraceError(f"{label}: expected finite probability in [0,1]")


def validate_record(record, previous=None):
    if not isinstance(record, dict):
        raise TraceError("hop must be an object")
    hop = integer(record.get("hop_index"), "hop_index")
    offset = integer(record.get("sample_offset"), "sample_offset")
    if previous is None and (hop != 0 or offset != 0):
        raise TraceError("trace must start at hop 0, sample offset 0")
    if previous is not None:
        if hop != previous[0] + 1 or offset != previous[1] + 128:
            raise TraceError("non-contiguous 128-frame hop timeline")
    candidates = record.get("ssl_candidates")
    tracks = record.get("sst_tracks")
    if not isinstance(candidates, list) or not isinstance(tracks, list):
        raise TraceError("ssl_candidates and sst_tracks must be arrays")
    if len(candidates) > 128:
        raise TraceError("more than 128 SSL candidates")
    candidate_ids = set()
    for c in candidates:
        if not isinstance(c, dict):
            raise TraceError("SSL candidate must be an object")
        index = integer(c.get("index"), "SSL index")
        if index in candidate_ids:
            raise TraceError("duplicate SSL candidate index")
        candidate_ids.add(index)
        for key in ("azimuth_deg", "elevation_deg", "strength"):
            value = c.get(key)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise TraceError(f"{key}: non-finite or missing")
        probability(c.get("birth_evidence"), "birth_evidence")
    track_ids = set()
    for t in tracks:
        if not isinstance(t, dict):
            raise TraceError("SST track must be an object")
        tid = integer(t.get("track_id"), "track_id")
        if tid in track_ids:
            raise TraceError("duplicate SST track ID")
        track_ids.add(tid)
        probability(t.get("existence_probability"), "existence_probability")
        assigned = t.get("assigned_ssl_index")
        if assigned is not None and (type(assigned) is not int or assigned not in candidate_ids):
            raise TraceError("SST references absent SSL candidate")
    counters = record.get("counters")
    if not isinstance(counters, dict):
        raise TraceError("missing counters")
    for name in ("ssl_candidates", "active_sst_tracks", "births", "retirements",
                 "unmatched_ssl_candidates", "oracle_active_sources",
                 "oracle_matches", "false_tracks", "id_switches"):
        integer(counters.get(name), name)
    if counters["ssl_candidates"] != len(candidates) or counters["active_sst_tracks"] != len(tracks):
        raise TraceError("counter/array count mismatch")
    if counters["oracle_matches"] > min(counters["oracle_active_sources"], len(tracks)):
        raise TraceError("impossible oracle match count")
    if counters["false_tracks"] > len(tracks):
        raise TraceError("false_tracks exceeds active SST tracks")
    if counters["oracle_matches"] + counters["false_tracks"] > len(tracks):
        raise TraceError("oracle matches plus false tracks exceeds active SST tracks")
    if counters["unmatched_ssl_candidates"] > len(candidates):
        raise TraceError("impossible unmatched SSL count")
    return hop, offset


def reject_duplicate_keys(pairs):
    """Reject ambiguous JSON objects, including nested SSL/SST/counter objects."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise TraceError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def validate_stream(stream):
    previous = None
    count = 0
    for lineno, line in enumerate(stream, 1):
        if not line.strip():
            raise TraceError(f"line {lineno}: empty record")
        try:
            record = json.loads(line, object_pairs_hook=reject_duplicate_keys,
                                parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
            previous = validate_record(record, previous)
        except (ValueError, TypeError, KeyError) as exc:
            raise TraceError(f"line {lineno}: {exc}") from exc
        count += 1
    if not count:
        raise TraceError("empty trace: no measurements")
    return {"validated_hops": count, "last_hop": previous[0], "last_sample_offset": previous[1]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", help="existing ODAS offline JSONL trace (not generated by this tool)")
    args = parser.parse_args()
    try:
        with open(args.trace, encoding="utf-8") as stream:
            print(json.dumps(validate_stream(stream), sort_keys=True))
    except (TraceError, OSError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
