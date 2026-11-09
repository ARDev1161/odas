#!/usr/bin/env python3
"""Summarize actual native SSL→SST posterior marginals, not hard assignments.

This is an observational diagnostic. It cannot establish speaker identity,
source separation or correct association without an independent oracle.
"""
import argparse
import json
import math


def _unique_keys(pairs):
    row = {}
    for key, value in pairs:
        if key in row:
            raise ValueError(f"duplicate JSON key: {key}")
        row[key] = value
    return row


def _reject_constant(value):
    raise ValueError(f"nonfinite JSON constant: {value}")


def summarize(stream):
    hops = 0
    candidates = 0
    candidates_with_tracks = 0
    ambiguous = 0
    top_marginal_sum = 0.0
    low_confidence = 0
    invalid = 0
    birth_observations = 0
    birth_comparable = 0
    birth_below_top_track = 0
    birth_above_top_track = 0
    birth_posterior_sum = 0.0
    birth_ge_0_1 = 0
    birth_ge_0_5 = 0
    birth_wins_ge_0_1 = 0
    birth_wins_ge_0_5 = 0
    max_birth_posterior = 0.0
    for line_no, line in enumerate(stream, 1):
        row = json.loads(line, object_pairs_hook=_unique_keys,
                         parse_constant=_reject_constant)
        if row.get("schema") != "odas_sst_raw_v1":
            raise ValueError(f"line {line_no}: unexpected schema")
        hops += 1
        for candidate in row["ssl_candidates"]:
            candidates += 1
            if "birth_posterior" not in candidate:
                raise ValueError(f"line {line_no}: missing native birth_posterior")
            birth = candidate["birth_posterior"]
            if type(birth) not in (int, float) or not math.isfinite(birth) or not 0 <= birth <= 1:
                raise ValueError(f"line {line_no}: invalid birth_posterior")
            birth_observations += 1
            birth_posterior_sum += birth
            max_birth_posterior = max(max_birth_posterior, birth)
            birth_ge_0_1 += birth >= 0.1
            birth_ge_0_5 += birth >= 0.5
            entries = candidate["track_posteriors"]
            seen_ids = set()
            values = []
            for entry in entries:
                track_id = entry["track_id"]
                if type(track_id) is not int or track_id < 0 or track_id in seen_ids:
                    raise ValueError(f"line {line_no}: invalid or repeated track_id")
                seen_ids.add(track_id)
                values.append(entry["posterior"])
            if not values:
                continue  # Newly born tracks have no pre-update marginal.
            if any(type(v) not in (int, float) or not math.isfinite(v)
                   or v < 0 or v > 1 for v in values):
                invalid += 1
                continue
            candidates_with_tracks += 1
            ranked = sorted(values, reverse=True)
            if birth is not None:
                birth_comparable += 1
                birth_below_top_track += birth < ranked[0]
                birth_above_top_track += birth > ranked[0]
                birth_wins_ge_0_1 += birth > ranked[0] and birth >= 0.1
                birth_wins_ge_0_5 += birth > ranked[0] and birth >= 0.5
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
        "birth_posterior_observations": birth_observations,
        "mean_birth_posterior": (birth_posterior_sum / birth_observations if birth_observations else None),
        "birth_posterior_ge_0_1": birth_ge_0_1,
        "birth_posterior_ge_0_5": birth_ge_0_5,
        "max_birth_posterior": max_birth_posterior,
        "birth_above_top_track_and_ge_0_1": birth_wins_ge_0_1,
        "birth_above_top_track_and_ge_0_5": birth_wins_ge_0_5,
        "birth_vs_existing_track_comparable": birth_comparable,
        "birth_below_top_existing_track_marginal": birth_below_top_track,
        "birth_above_top_existing_track_marginal": birth_above_top_track,
        "birth_vs_track_ties": birth_comparable - birth_below_top_track - birth_above_top_track,
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
