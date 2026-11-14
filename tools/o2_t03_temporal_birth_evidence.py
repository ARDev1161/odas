#!/usr/bin/env python3
"""Measure how often the *oracle* second direction persists in native SSL.

Diagnostic only: oracle directions MUST NOT be used by runtime birth logic.
"""
import argparse
import json
import math
from pathlib import Path
from o2_t03_birth_bottleneck import angle_deg, uncontested_strength_gate


def audit(oracle, trace, tolerance_deg=25):
    rows = oracle["ground_truth"]
    if not isinstance(rows, list) or not rows or len(rows) > len(trace):
        raise ValueError("oracle exceeds native trace")
    if not isinstance(tolerance_deg, (int, float)) or not math.isfinite(tolerance_deg) or not 0 < tolerance_deg <= 90:
        raise ValueError("invalid angular tolerance")
    if not trace:
        raise ValueError("empty native trace")
    sample_rate = oracle.get("sample_rate_hz", 16000)
    if not isinstance(sample_rate, int) or sample_rate <= 0:
        raise ValueError("invalid oracle sample rate")
    hop_frames = trace[0].get("hop_frames", 128)
    if not isinstance(hop_frames, int) or hop_frames <= 0:
        raise ValueError("invalid hop size")
    for i, rec in enumerate(trace):
        if rec.get("hop_frames", hop_frames) != hop_frames:
            raise ValueError("variable hop size")
        if rec.get("sample_offset", i * hop_frames) != i * hop_frames:
            raise ValueError("native sample offset not aligned to oracle")
        if rec.get("hop_index", i) != i:
            raise ValueError("native trace not aligned to oracle")
        for pot in rec.get("ssl_candidates", []):
            strength = pot.get("strength")
            if not isinstance(strength, (int, float)) or not math.isfinite(strength):
                raise ValueError("non-finite SSL candidate strength")
    result = {"two_voice_hops": 0, "pair_geometry_hops": 0,
              "pair_above_uncontested_gate_hops": 0,
              "longest_pair_geometry_streak_hops": 0,
              "longest_pair_above_gate_streak_hops": 0,
              "longest_pair_geometry_streak_ms": 0.0,
              "status": "ORACLE_DIAGNOSTIC_ONLY_NOT_RUNTIME_BIRTH_FIX"}
    geometry_streak = gate_streak = 0
    geometry_runs = []
    gate_runs = []
    # Distinguish a necessary GMM-strength bound from the actual posterior.
    # The latter includes competition with existing tracks and residual mass.
    posterior_streak = 0
    posterior_runs = []
    result["pair_above_actual_birth_posterior_hops"] = 0
    result["longest_pair_actual_birth_posterior_streak_hops"] = 0

    def close_runs():
        nonlocal geometry_streak, gate_streak, posterior_streak
        if geometry_streak:
            geometry_runs.append(geometry_streak)
        if gate_streak:
            gate_runs.append(gate_streak)
        if posterior_streak:
            posterior_runs.append(posterior_streak)
        geometry_streak = gate_streak = posterior_streak = 0
    for i, row in enumerate(rows):
        sources = row.get("sources", [])
        if len(sources) == 2:
            ids = [source.get("id") for source in sources]
            if any(not isinstance(ident, (str, int)) for ident in ids) or ids[0] == ids[1]:
                raise ValueError("duplicate or invalid oracle source identities")
        if len(sources) != 2:
            close_runs()
            continue
        result["two_voice_hops"] += 1
        pots = trace[i]["ssl_candidates"]
        if len(pots) < 2:
            # A missing candidate terminates, rather than discards, the run.
            close_runs()
            continue
        # Distinct proposals must explain distinct oracle directions.
        pairs = [(j, k) for j in range(len(pots)) for k in range(len(pots))
                 if j != k and angle_deg(pots[j], sources[0]) <= tolerance_deg
                 and angle_deg(pots[k], sources[1]) <= tolerance_deg]
        matched = bool(pairs)
        threshold = uncontested_strength_gate(trace[i]["theta_new"])
        above = any(pots[j]["strength"] > threshold and
                    pots[k]["strength"] > threshold for j, k in pairs)
        # This is a counterfactual per-candidate eligibility audit, NOT a
        # prediction that ODAS can instantiate two simultaneous tracks.
        # Reject absent/non-finite posterior evidence instead of inventing it.
        for pot in pots:
            posterior = pot.get("birth_posterior")
            if not isinstance(posterior, (int, float)) or not math.isfinite(posterior) or not 0 <= posterior <= 1:
                raise ValueError("invalid native birth posterior")
        actual = any(pots[j]["birth_posterior"] > trace[i]["theta_new"] and
                     pots[k]["birth_posterior"] > trace[i]["theta_new"]
                     for j, k in pairs)
        if not actual and posterior_streak:
            posterior_runs.append(posterior_streak)
        posterior_streak = posterior_streak + 1 if actual else 0
        result["pair_above_actual_birth_posterior_hops"] += int(actual)
        result["longest_pair_actual_birth_posterior_streak_hops"] = max(
            result["longest_pair_actual_birth_posterior_streak_hops"], posterior_streak)
        if not matched and geometry_streak:
            geometry_runs.append(geometry_streak)
        if not above and gate_streak:
            gate_runs.append(gate_streak)
        geometry_streak = geometry_streak + 1 if matched else 0
        gate_streak = gate_streak + 1 if above else 0
        result["pair_geometry_hops"] += int(matched)
        result["pair_above_uncontested_gate_hops"] += int(above)
        result["longest_pair_geometry_streak_hops"] = max(
            result["longest_pair_geometry_streak_hops"], geometry_streak)
        result["longest_pair_above_gate_streak_hops"] = max(
            result["longest_pair_above_gate_streak_hops"], gate_streak)
    close_runs()
    result["pair_actual_birth_posterior_run_lengths_hops"] = sorted(posterior_runs, reverse=True)
    result["pair_geometry_run_lengths_hops"] = sorted(geometry_runs, reverse=True)
    result["pair_above_gate_run_lengths_hops"] = sorted(gate_runs, reverse=True)
    result["pair_geometry_runs_at_least_5_hops"] = sum(n >= 5 for n in geometry_runs)
    result["pair_above_gate_runs_at_least_5_hops"] = sum(n >= 5 for n in gate_runs)
    result["pair_above_gate_hops_in_runs_at_least_5"] = sum(n for n in gate_runs if n >= 5)
    result["longest_pair_geometry_streak_ms"] = (
        result["longest_pair_geometry_streak_hops"] * hop_frames * 1000.0 / sample_rate)
    result["longest_pair_above_gate_streak_ms"] = (
        result["longest_pair_above_gate_streak_hops"] * hop_frames * 1000.0 / sample_rate)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("oracle", type=Path)
    parser.add_argument("native_jsonl", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    oracle = json.loads(args.oracle.read_text())
    trace = [json.loads(line) for line in args.native_jsonl.read_text().splitlines()
             if line.strip()]
    report = audit(oracle, trace)
    output = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(output)
    print(output, end="")


if __name__ == "__main__":
    main()
