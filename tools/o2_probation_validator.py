#!/usr/bin/env python3
"""Strict five-hop probation evidence validator; NOT an ODAS DSP simulator.

Input is an explicitly exported per-track trace, not native ODAS JSONL.
Missing evidence fails closed; no inference of a speaker identity is made.
"""
import argparse
import json
import math
from pathlib import Path


class InvalidTrace(ValueError):
    pass


def evaluate(trace, window=5, threshold=0.8):
    if type(window) is not int or window < 1:
        raise InvalidTrace("invalid window")
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise InvalidTrace("invalid threshold")
    if not isinstance(trace, dict) or not isinstance(trace.get("tracks"), list):
        raise InvalidTrace("tracks array required")
    output = []
    seen = set()
    for track in trace["tracks"]:
        if not isinstance(track, dict) or set(("id", "generation", "birth_hop", "hops")) - track.keys():
            raise InvalidTrace("track identity/birth/hops required")
        key = (track["generation"], track["id"])
        if not all(type(x) is int and x >= 0 for x in (track["generation"], track["id"], track["birth_hop"])):
            raise InvalidTrace("invalid identity")
        if key in seen:
            raise InvalidTrace("duplicate identity in generation")
        seen.add(key)
        hops = track["hops"]
        if not isinstance(hops, list):
            raise InvalidTrace("hops must be an array")
        expected = track["birth_hop"]
        survival = 1.0
        retired = False
        active = False
        for item in hops:
            if not isinstance(item, dict) or set(("hop", "association", "state")) - item.keys():
                raise InvalidTrace("hop/association/state required")
            if type(item["hop"]) is not int or item["hop"] != expected:
                raise InvalidTrace("missing, duplicate or out-of-order hop")
            expected += 1
            p = item["association"]
            if type(p) not in (float, int) or not math.isfinite(p) or not 0 <= p <= 1:
                raise InvalidTrace("nonfinite/out-of-range association")
            if item["state"] not in ("provisional", "active", "retired"):
                raise InvalidTrace("unknown lifecycle state")
            if retired:
                raise InvalidTrace("observations after retirement")
            if active and item["state"] == "provisional":
                raise InvalidTrace("active track cannot revert to provisional")
            if item["state"] == "active":
                active = True
            if item["state"] == "retired":
                retired = True
        first = hops[:window]
        if len(first) == window:
            for item in first:
                survival *= 1 - item["association"]
            aggregate = 1 - survival
            qualifies = aggregate >= threshold
        else:
            aggregate, qualifies = None, None
        output.append({"id": track["id"], "generation": track["generation"],
                       "birth_hop": track["birth_hop"], "observed_hops": len(hops),
                       "five_hop_probability": aggregate, "crosses_threshold": qualifies,
                       "evidence_complete": len(first) == window})
    return {"window": window, "threshold": threshold, "tracks": output,
            "quality_status": "NOT_MEASURED"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--window", type=int, default=5)
    parser.add_argument("--threshold", type=float, default=0.8)
    args = parser.parse_args()
    try:
        result = evaluate(json.loads(args.trace.read_text()), args.window, args.threshold)
    except (InvalidTrace, ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
