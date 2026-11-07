#!/usr/bin/env python3
"""Summarize real offline SST birth pressure. Diagnostic, not oracle accuracy."""
import argparse
import json
from pathlib import Path

from validate_sst_raw_trace import TraceError, _unique_pairs, validate_record


def summarize(lines):
    previous = None
    hops = pressure_hops = unfilled_hops = excess_candidates = 0
    examples = []
    for line_number, line in enumerate(lines, 1):
        try:
            if not line.strip() or len(line) > 1000000:
                raise TraceError("empty or oversized JSONL record")
            record = json.loads(line, object_pairs_hook=_unique_pairs,
                                parse_constant=lambda v: (_ for _ in ()).throw(
                                    TraceError("nonfinite JSON token " + v)))
            previous = validate_record(record, previous)
        except (ValueError, TypeError, KeyError) as exc:
            raise TraceError(f"line {line_number}: {exc}") from exc
        hops += 1
        # This is a threshold-crossing diagnostic, NOT a proof of slot collision:
        # tracker state/retirement rules may legitimately reject a birth.
        eligible = sum(c["birth_posterior"] >= record["theta_new"]
                       for c in record["ssl_candidates"])
        births = len(record["births"])
        if eligible >= 2:
            pressure_hops += 1
            if births < eligible:
                unfilled_hops += 1
                excess_candidates += eligible - births
                if len(examples) < 20:
                    examples.append({"hop_index": record["hop_index"],
                                     "eligible_candidates": eligible,
                                     "reported_births": births,
                                     "tracks_after": record["active_tracks_after"]})
    if not hops:
        raise TraceError("empty trace")
    return {"schema": "odas_sst_birth_pressure_v1", "validated_hops": hops,
            "multi_eligible_hops": pressure_hops,
            "multi_eligible_underfilled_hops": unfilled_hops,
            "unfilled_candidate_count": excess_candidates,
            "examples": examples, "slot_collision_confirmed": False,
            "oracle_metrics": "NOT_MEASURED"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    args = parser.parse_args()
    try:
        with args.trace.open(encoding="utf-8") as stream:
            print(json.dumps(summarize(stream), sort_keys=True))
        return 0
    except (OSError, TraceError) as exc:
        parser.exit(2, "BLOCKED: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
