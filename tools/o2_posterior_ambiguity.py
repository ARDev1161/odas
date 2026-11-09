#!/usr/bin/env python3
"""Summarize actual native SSL→SST posterior marginals, not hard assignments.

This is an observational diagnostic. It cannot establish speaker identity,
source separation or correct association without an independent oracle.
"""
import argparse
import json
import math


def summarize(stream):
    hops = 0
    candidates = 0
    candidates_with_tracks = 0
    ambiguous = 0
    top_marginal_sum = 0.0
    low_confidence = 0
    invalid = 0
    for line_no, line in enumerate(stream, 1):
        row = json.loads(line)
        if row.get("schema") != "odas_sst_raw_v1":
            raise ValueError(f"line {line_no}: unexpected schema")
        hops += 1
        for candidate in row["ssl_candidates"]:
            candidates += 1
            values = [entry["posterior"] for entry in candidate["track_posteriors"]]
            if not values:
                continue  # Newly born tracks have no pre-update marginal.
            if any(type(v) not in (int, float) or not math.isfinite(v)
                   or v < 0 or v > 1 for v in values):
                invalid += 1
                continue
            candidates_with_tracks += 1
            ranked = sorted(values, reverse=True)
            top_marginal_sum += ranked[0]
            if ranked[0] < 0.5:
                low_confidence += 1
            if len(ranked) >= 2 and ranked[0] - ranked[1] < 0.1:
                ambiguous += 1
    if not hops:
        raise ValueError("empty trace")
    if invalid:
        raise ValueError(f"{invalid} candidate rows have invalid posterior marginals")
    return {
        "validated_schema_hops": hops,
        "ssl_candidate_observations": candidates,
        "candidate_observations_with_existing_tracks": candidates_with_tracks,
        "near_tie_margin_lt_0_1": ambiguous,
        "top_marginal_lt_0_5": low_confidence,
        "mean_top_existing_track_marginal": (
            top_marginal_sum / candidates_with_tracks if candidates_with_tracks else None),
        "hard_assignments": "NOT_OBSERVED",
        "oracle_identity": "NOT_MEASURED",
        "separation_quality": "NOT_MEASURED",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace")
    args = parser.parse_args()
    with open(args.trace, encoding="utf-8") as stream:
        print(json.dumps(summarize(stream), sort_keys=True))


if __name__ == "__main__":
    main()
