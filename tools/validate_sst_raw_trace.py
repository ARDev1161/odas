#!/usr/bin/env python3
"""Validate actual ODAS offline decision JSONL; this does NOT evaluate oracle accuracy.

The recorder is compiled with ODAS_OFFLINE_SST_TRACE=ON and writes genuine
mod_sst_process observations. Unit-test fixtures are contract examples only.
"""
import argparse
import json
import math
import sys


class TraceError(ValueError):
    pass


def _unique_pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise TraceError(f"duplicate JSON key: {key}")
        obj[key] = value
    return obj


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise TraceError(f"{name}: expected integer >= {minimum}")
    return value


def _float(value, name, probability=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise TraceError(f"{name}: expected finite number")
    if probability and not (0.0 <= value <= 1.0):
        raise TraceError(f"{name}: outside [0,1]")
    return value


def _keys(obj, expected, context):
    if type(obj) is not dict or set(obj) != set(expected):
        raise TraceError(f"{context}: missing or unexpected fields")


TOP = ("schema", "odas_timestamp", "hop_index", "sample_offset",
       "hop_frames", "theta_new", "ssl_candidates", "births",
       "retirements", "tracks_after", "active_tracks_after")
CANDIDATE = ("index", "x", "y", "z", "strength",
             "birth_posterior", "track_posteriors")
TRACK = ("slot", "track_id", "state", "activity")


def validate_record(item, previous=None):
    _keys(item, TOP, "hop")
    if item["schema"] != "odas_sst_raw_v1":
        raise TraceError("unexpected trace schema")
    hop = _integer(item["hop_index"], "hop_index")
    timestamp = _integer(item["odas_timestamp"], "odas_timestamp", 1)
    offset = _integer(item["sample_offset"], "sample_offset")
    if _integer(item["hop_frames"], "hop_frames", 1) != 128:
        raise TraceError("hop_frames must equal 128")
    if timestamp != hop + 1 or offset != hop * 128:
        raise TraceError("ODAS timestamp / sample offset mismatch")
    if (previous is None and hop != 0) or (
        previous is not None and hop != previous + 1
    ):
        raise TraceError("non-contiguous ODAS hop timeline")
    _float(item["theta_new"], "theta_new", probability=True)
    candidates = item["ssl_candidates"]
    if type(candidates) is not list or len(candidates) > 128:
        raise TraceError("SSL candidates must be a bounded array")
    previous_ids = None
    for idx, c in enumerate(candidates):
        _keys(c, CANDIDATE, "candidate")
        if _integer(c["index"], "candidate index") != idx:
            raise TraceError("SSL candidate index mismatch")
        for n in ("x", "y", "z", "strength"):
            _float(c[n], n)
        pnew = _float(c["birth_posterior"], "birth_posterior", True)
        tracks = c["track_posteriors"]
        if type(tracks) is not list or len(tracks) > 32:
            raise TraceError("track_posteriors must be a bounded array")
        ids = []
        mass = pnew
        for track in tracks:
            _keys(track, ("track_id", "posterior"), "track posterior")
            tid = _integer(track["track_id"], "track_id", 1)
            if tid in ids:
                raise TraceError("duplicate prior track ID")
            ids.append(tid)
            mass += _float(track["posterior"], "track posterior", True)
        if mass > 1.0001:
            raise TraceError("candidate posterior mass exceeds one")
        if previous_ids is not None and ids != previous_ids:
            raise TraceError("prior track ordering inconsistent across candidates")
        previous_ids = ids
    for field in ("births", "retirements"):
        events = item[field]
        if type(events) is not list or len(events) > 32:
            raise TraceError(f"{field}: expected bounded array")
        ids = [_integer(tid, field, 1) for tid in events]
        if len(set(ids)) != len(ids):
            raise TraceError(f"{field}: duplicate event ID")
    after = item["tracks_after"]
    if type(after) is not list or len(after) > 32:
        raise TraceError("tracks_after: expected bounded array")
    ids, slots = set(), set()
    for track in after:
        _keys(track, TRACK, "active track")
        tid = _integer(track["track_id"], "active track ID", 1)
        slot = _integer(track["slot"], "active track slot")
        if tid in ids or slot in slots:
            raise TraceError("duplicate active track ID or slot")
        ids.add(tid)
        slots.add(slot)
        if track["state"] not in ("P", "A", "T"):
            raise TraceError("invalid SST track state")
        _float(track["activity"], "activity", True)
    if _integer(item["active_tracks_after"], "active_tracks_after") != len(after):
        raise TraceError("active_tracks_after disagrees with tracks_after")
    return hop


def validate_stream(stream):
    previous = None
    count = 0
    for lineno, line in enumerate(stream, 1):
        try:
            if not line.strip() or len(line) > 1000000:
                raise TraceError("empty or oversized JSONL record")
            record = json.loads(
                line, object_pairs_hook=_unique_pairs,
                parse_constant=lambda value: (_ for _ in ()).throw(
                    TraceError(f"nonfinite JSON token {value}")))
            previous = validate_record(record, previous)
        except (ValueError, TypeError, KeyError) as error:
            raise TraceError(f"line {lineno}: {error}") from error
        count += 1
    if count == 0:
        raise TraceError("empty trace: no real ODAS observations")
    return {"validated_hops": count, "last_hop": previous,
            "oracle_metrics": "NOT_MEASURED"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", help="actual recorded ODAS offline JSONL file")
    args = parser.parse_args()
    try:
        with open(args.trace, encoding="utf-8") as handle:
            print(json.dumps(validate_stream(handle), sort_keys=True))
        return 0
    except (OSError, TraceError) as error:
        print(f"BLOCKED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
