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
    observed_track_hops = 0
    unique_track_ids = set()
    observed_provisional_ids = set()
    provisional_to_active_ids = set()
    active_ids = set()
    retired_ids = set()
    # Track IDs may be recycled; do not carry provisional evidence across retirement.
    provisional_live_ids = set()
    recycled_track_id_births = 0
    observed_provisional_to_active_episodes = 0
    retired_prior_ids = set()
    active_live_ids = set()
    previous_after_ids = set()
    unannounced_disappearances = 0
    unannounced_appearances = 0
    active_to_provisional_regressions = 0
    simultaneous_birth_retirement_ids = 0
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
        current_after_ids = {track["track_id"] for track in record["tracks_after"]}
        birth_ids = set(record["births"])
        retirement_ids = set(record["retirements"])
        simultaneous_birth_retirement_ids += len(birth_ids & retirement_ids)
        # The trace is a snapshot, not an identity oracle. Missing lifecycle
        # events must not allow old provisional evidence to promote a new episode.
        disappeared = previous_after_ids - current_after_ids - retirement_ids
        appeared = current_after_ids - previous_after_ids - birth_ids
        unannounced_disappearances += len(disappeared)
        unannounced_appearances += len(appeared) if count else 0
        provisional_live_ids.difference_update(disappeared)
        active_live_ids.difference_update(disappeared)
        count += 1
        candidate_hops += bool(record["ssl_candidates"])
        existing_track_posterior_hops += any(
            candidate["track_posteriors"] for candidate in record["ssl_candidates"])
        provisional_hops += any(t["state"] == "P" for t in record["tracks_after"])
        births += len(record["births"])
        recycled_track_id_births += len(set(record["births"]) & retired_prior_ids)
        for tid in record["births"]:
            provisional_live_ids.discard(tid)
            active_live_ids.discard(tid)
        observed_track_hops += len(record["tracks_after"])
        active_ids_before_hop = set(active_live_ids)
        for track in record["tracks_after"]:
            tid = track["track_id"]
            unique_track_ids.add(tid)
            if track["state"] == "P":
                if tid in active_live_ids:
                    active_to_provisional_regressions += 1
                    active_live_ids.discard(tid)
                    provisional_live_ids.discard(tid)
                observed_provisional_ids.add(tid)
                provisional_live_ids.add(tid)
            elif track["state"] == "A":
                active_ids.add(tid)
                active_live_ids.add(tid)
                if tid in provisional_live_ids:
                    if tid not in active_ids_before_hop:
                        observed_provisional_to_active_episodes += 1
                    provisional_to_active_ids.add(tid)
        retired_ids.update(record["retirements"])
        retired_prior_ids.update(record["retirements"])
        provisional_live_ids.difference_update(record["retirements"])
        active_live_ids.difference_update(record["retirements"])
        previous_after_ids = current_after_ids
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
        "observed_track_hops": observed_track_hops,
        "distinct_observed_track_ids": len(unique_track_ids),
        "distinct_provisional_track_ids": len(observed_provisional_ids),
        "distinct_active_track_ids": len(active_ids),
        "observed_provisional_to_active_ids": len(provisional_to_active_ids),
        "distinct_retirement_event_ids": len(retired_ids),
        "recycled_track_id_birth_events": recycled_track_id_births,
        "unannounced_track_disappearances": unannounced_disappearances,
        "unannounced_track_appearances": unannounced_appearances,
        "active_to_provisional_regressions": active_to_provisional_regressions,
        "simultaneous_birth_retirement_ids": simultaneous_birth_retirement_ids,
        "lifecycle_integrity": "FAIL" if (active_to_provisional_regressions or simultaneous_birth_retirement_ids) else "PASS",
        "observed_provisional_to_active_episodes": observed_provisional_to_active_episodes,
        "zero_positive_ssl_evidence_hops": zero_evidence_hops,
        "zero_positive_ssl_evidence_births": zero_evidence_births,
        "zero_evidence_birth_guard": "PASS" if zero_evidence_births == 0 else "FAIL",
        "five_hop_probation": "BLOCKED_MISSING_PER_TRACK_ASSOCIATION_EVENT",
        "identity_note": "track IDs are diagnostic only; no generation or speaker identity is exported",
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
            if report["zero_evidence_birth_guard"] != "PASS" or report["lifecycle_integrity"] != "PASS":
                raise SystemExit(2)
    except (OSError, TraceError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
