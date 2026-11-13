#!/usr/bin/env python3
"""Measured T03 SSL -> SST birth-bottleneck audit (NOT an SSS quality score)."""
import argparse
import json
import math
import statistics
from pathlib import Path

ACTIVE_MEAN = 0.40
INACTIVE_MEAN = 0.25
COMMON_VARIANCE = 0.0025
# These are the frozen native T03 defaults, not proposed tuning values.
FALSE_PRIOR = 0.10
NEW_PRIOR = 0.10


def angle_deg(candidate, source):
    az = math.radians(source["bearing_deg"])
    el = math.radians(source["elevation_deg"])
    direction = (math.cos(el) * math.cos(az),
                 math.cos(el) * math.sin(az), math.sin(el))
    vector = (candidate["x"], candidate["y"], candidate["z"])
    if any(not math.isfinite(float(x)) for x in vector):
        raise ValueError("non-finite SSL direction")
    norm = math.sqrt(sum(float(x) ** 2 for x in vector))
    if not 0.9 <= norm <= 1.1:
        raise ValueError("non-unit SSL direction")
    cosine = sum(float(a) * b for a, b in zip(vector, direction)) / norm
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


def uncontested_strength_gate(theta):
    """Minimum SSL strength for P(new)>theta even with NO existing tracks.

    Assumes equal-variance Gaussian active/inactive strength models, identical
    diffuse likelihoods and the explicitly frozen new/false priors.
    Other positive terms (track coherence, epsilon) only reduce P(new).
    """
    if not 0.0 < theta < 1.0:
        raise ValueError("invalid birth threshold")
    slope = (ACTIVE_MEAN - INACTIVE_MEAN) / COMMON_VARIANCE
    intercept = -(ACTIVE_MEAN ** 2 - INACTIVE_MEAN ** 2) / (2 * COMMON_VARIANCE)
    log_prior_odds = math.log(NEW_PRIOR / FALSE_PRIOR)
    return (math.log(theta / (1.0 - theta)) - intercept - log_prior_odds) / slope


def analyze(oracle, trace):
    if oracle.get("sample_rate_hz") != 16000:
        raise ValueError("unexpected frozen sample rate")
    rows = oracle.get("ground_truth")
    if not isinstance(rows, list) or not rows or len(rows) > len(trace):
        raise ValueError("invalid oracle/native timeline")
    hop = 128
    overlap = []
    for i, rec in enumerate(trace):
        if (type(rec.get("hop_index")) is not int or rec["hop_index"] != i
                or type(rec.get("sample_offset")) is not int
                or rec["sample_offset"] != i * hop
                or rec.get("hop_frames") != hop):
            raise ValueError("native hop clock mismatch")
    for i, row in enumerate(rows):
        if row.get("hop") != i or not math.isclose(
                row.get("t_s", -100), (i + .5) * hop / 16000, abs_tol=1e-6):
            raise ValueError("oracle hop clock mismatch")
        if len(row.get("sources", [])) == 2:
            overlap.append(i)
    if not overlap:
        raise ValueError("no actual two-source oracle overlap")

    counts = [0, 0, 0]
    geometry = {25: 0, 45: 0}
    second_strengths = []
    second_posteriors = []
    second_below_gate = 0
    strong_second_posterior_classes = {"new_source": 0, "existing_track": 0,
                                       "unassigned_residual": 0}
    births_in_overlap = []
    for i in overlap:
        rec = trace[i]
        theta = rec.get("theta_new")
        if type(theta) not in (int, float) or not math.isfinite(theta):
            raise ValueError("invalid native birth threshold")
        threshold = uncontested_strength_gate(theta)
        pots = rec.get("ssl_candidates")
        if not isinstance(pots, list):
            raise ValueError("missing native SSL candidates")
        eligible = 0
        for pot in pots:
            strength = pot.get("strength")
            pnew = pot.get("birth_posterior")
            if (type(strength) not in (int, float)
                    or type(pnew) not in (int, float)
                    or not math.isfinite(strength) or not math.isfinite(pnew)
                    or not 0 <= pnew <= 1):
                raise ValueError("invalid native SSL probability")
            eligible += strength > 0 and pnew > theta
        counts[min(eligible, 2)] += 1
        births_in_overlap.extend((i, ident) for ident in rec.get("births", []))
        sources = sorted(rows[i]["sources"], key=lambda s: s["id"])
        if len({s["id"] for s in sources}) != 2:
            raise ValueError("duplicate oracle source")
        if len(pots) < 2:
            continue
        distances = [[angle_deg(pot, src) for pot in pots] for src in sources]
        # One-to-one pair: minimize worst angular error, then total error.
        # This is an SSL geometric diagnostic, NOT an SST speaker match.
        worst, _, j, k = min(
            (max(distances[0][j], distances[1][k]),
             distances[0][j] + distances[1][k], j, k)
            for j in range(len(pots)) for k in range(len(pots)) if j != k
        )
        for tolerance in geometry:
            geometry[tolerance] += worst <= tolerance
        if worst <= 25:
            second = pots[k]
            second_strengths.append(second["strength"])
            second_posteriors.append(second["birth_posterior"])
            second_below_gate += second["strength"] < threshold
            if second["strength"] >= threshold:
                track_posteriors = second.get("track_posteriors", [])
                if not isinstance(track_posteriors, list):
                    raise ValueError("invalid native track posterior list")
                seen_track_ids = set()
                for track in track_posteriors:
                    track_id = track.get("track_id") if isinstance(track, dict) else None
                    if type(track_id) is not int or track_id <= 0 or track_id in seen_track_ids:
                        raise ValueError("invalid or duplicate native track identity")
                    seen_track_ids.add(track_id)
                    p = track.get("posterior") if isinstance(track, dict) else None
                    if (type(p) not in (int, float) or not math.isfinite(p)
                            or not 0.0 <= p <= 1.0):
                        raise ValueError("invalid native track posterior")
                existing_mass = sum(t["posterior"] for t in track_posteriors)
                new_mass = second["birth_posterior"]
                if existing_mass + new_mass > 1.0 + 1e-6:
                    raise ValueError("native posterior mass exceeds one")
                residual_mass = max(0.0, 1.0 - existing_mass - new_mass)
                if new_mass > max(existing_mass, residual_mass):
                    decision = "new_source"
                elif existing_mass > max(new_mass, residual_mass):
                    decision = "existing_track"
                else:
                    decision = "unassigned_residual"
                strong_second_posterior_classes[decision] += 1

    promotion_count = 0
    rejected_count = 0
    for birth_hop, ident in births_in_overlap:
        if type(ident) is not int or ident <= 0:
            raise ValueError("invalid native birth identity")
        found_active = False
        found_retire = False
        for rec in trace[birth_hop:]:
            found_active |= any(t.get("track_id") == ident and t.get("state") == "A"
                                for t in rec.get("tracks_after", []))
            if ident in rec.get("retirements", []):
                found_retire = True
                break
        promotion_count += found_active
        rejected_count += found_retire and not found_active

    return {
        "status": "DIAGNOSTIC_ONLY_NOT_SST_OR_SSS_PASS",
        "oracle_two_voice_hops": len(overlap),
        "birth_eligible_hops": {
            "zero": counts[0], "one": counts[1], "two_or_more": counts[2]
        },
        "distinct_ssl_pair_hops_25deg": geometry[25],
        "distinct_ssl_pair_hops_45deg": geometry[45],
        "second_direction_25deg_matches": len(second_strengths),
        "second_direction_median_strength": statistics.median(second_strengths)
            if second_strengths else None,
        "second_direction_median_birth_posterior": statistics.median(second_posteriors)
            if second_posteriors else None,
        "second_direction_max_birth_posterior": max(second_posteriors)
            if second_posteriors else None,
        "second_direction_strength_below_no_track_gmm_gate": second_below_gate,
        "strong_second_direction_posterior_classes": strong_second_posterior_classes,
        "no_track_gmm_birth_strength_gate": uncontested_strength_gate(trace[overlap[0]]["theta_new"]),
        "provisional_births_during_overlap": len(births_in_overlap),
        "overlap_births_ever_active": promotion_count,
        "overlap_births_retired_without_promotion": rejected_count,
        "limitations": "25/45-degree geometric candidate matching does not prove independent speech, stable SST IDs, SI-SDRi, SIRi or WER",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("oracle", type=Path)
    parser.add_argument("native_jsonl", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    oracle = json.loads(args.oracle.read_text(encoding="utf-8"))
    trace = [json.loads(line) for line in args.native_jsonl.read_text(
        encoding="utf-8").splitlines() if line.strip()]
    result = analyze(oracle, trace)
    output = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    print(output, end="")


if __name__ == "__main__":
    main()
