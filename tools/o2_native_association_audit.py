#!/usr/bin/env python3
"""Audit native odas_sst_raw_v1 association evidence without inventing probation probabilities.

A candidate's posterior for an existing track is NOT a per-track association
event, and max/sum across candidates must not be fed to the five-hop validator.
"""
import argparse
import json
from pathlib import Path

from tools.validate_sst_raw_trace import TraceError, _unique_pairs, validate_record


def audit(lines):
    previous = None
    count = 0
    candidate_hops = 0
    existing_track_posterior_hops = 0
    provisional_hops = 0
    births = 0
    zero_evidence_hops = 0
    zero_evidence_births = 0
    for lineno, line in enumerate(lines, 1):
        try:
            if not line.strip() or len(line) > 1000000:
                raise TraceError("empty or oversized JSONL record")
            record = json.loads(line, object_pairs_hook=_unique_pairs,
                                parse_constant=lambda value: (_ for _ in ()).throw(
                                    TraceError("nonfinite JSON token " + value)))
            previous = validate_record(record, previous)
        except (ValueError, TypeError, KeyError) as exc:
            raise TraceError(f"line {lineno}: {exc}") from exc
        count += 1
        candidate_hops += bool(record["ssl_candidates"])
        existing_track_posterior_hops += any(
            candidate["track_posteriors"] for candidate in record["ssl_candidates"])
        provisional_hops += any(t["state"] == "P" for t in record["tracks_after"])
        births += len(record["births"])
        if not any(candidate["strength"] > 0.0 for candidate in record["ssl_candidates"]):
            zero_evidence_hops += 1
            zero_evidence_births += len(record["births"])
    if not count:
        raise TraceError("empty native trace")
    return {
        "schema": "odas_sst_raw_v1_association_audit",
        "validated_hops": count,
        "hops_with_ssl_candidates": candidate_hops,
        "hops_with_existing_track_marginals": existing_track_posterior_hops,
        "hops_with_provisional_tracks": provisional_hops,
        "birth_events": births,
        "zero_positive_ssl_evidence_hops": zero_evidence_hops,
        "zero_positive_ssl_evidence_births": zero_evidence_births,
        "zero_evidence_birth_guard": "PASS" if zero_evidence_births == 0 else "FAIL",
        "five_hop_probation": "BLOCKED_MISSING_PER_TRACK_ASSOCIATION_EVENT",
        "oracle_speaker_identity": "NOT_MEASURED",
        "separation_quality": "NOT_MEASURED",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    args = parser.parse_args()
    try:
        with args.trace.open(encoding="utf-8") as stream:
            report = audit(stream)
            print(json.dumps(report, sort_keys=True))
            if report["zero_evidence_birth_guard"] != "PASS":
                raise SystemExit(2)
    except (OSError, TraceError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
