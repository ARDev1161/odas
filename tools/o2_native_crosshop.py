#!/usr/bin/env python3
"""Cross-hop native SST event consistency checker (not speaker identity validation).

Read-only evidence analysis; intentionally separate from per-track association
probability and oracle matching. Native trace may start with existing tracks,
so first-hop state is treated as an unknown baseline.
"""
import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.validate_sst_raw_trace import TraceError, _unique_pairs, validate_record


def inspect(lines):
    previous = None
    live = set()
    states = {}
    births = retirements = 0
    for line_number, line in enumerate(lines, 1):
        try:
            if not line.strip() or len(line) > 1000000:
                raise TraceError("empty or oversized JSONL line")
            record = json.loads(
                line, object_pairs_hook=_unique_pairs,
                parse_constant=lambda value: (_ for _ in ()).throw(
                    TraceError("nonfinite JSON constant " + value)))
            previous = validate_record(record, previous)
            born, retired = set(record["births"]), set(record["retirements"])
            after = {track["track_id"] for track in record["tracks_after"]}
            next_states = {track["track_id"]: track["state"]
                           for track in record["tracks_after"]}
            if born & retired:
                raise TraceError("same-hop birth and retirement of same ID")
            # The first snapshot may predate recording, but its explicit
            # events must still agree with the observed after-hop snapshot.
            if born - after:
                raise TraceError("birth absent from after-hop snapshot")
            if retired & after:
                raise TraceError("retired ID remains in after-hop snapshot")
            if line_number > 1:
                if born & live:
                    raise TraceError("birth of already-live ID")
                if retired - live:
                    raise TraceError("retirement of unknown ID")
                expected = (live | born) - retired
                if expected != after:
                    raise TraceError("snapshot/event mismatch: missing birth or retirement")
                # A confirmed track cannot silently return to probation within
                # the same lifetime. ID reuse is allowed only after retirement.
                for tid in live & after:
                    if states[tid] == "A" and next_states[tid] == "P":
                        raise TraceError("active-to-provisional without new birth")
            live = after
            states = next_states
            births += len(born)
            retirements += len(retired)
        except (ValueError, TypeError, KeyError) as error:
            raise TraceError(f"line {line_number}: {error}") from error
    if previous is None:
        raise TraceError("empty native SST trace")
    return {"validated_hops": previous + 1, "birth_events": births,
            "retirement_events": retirements,
            "event_snapshot_consistency": "PASS",
            "speaker_identity": "NOT_MEASURED",
            "five_hop_association": "NOT_MEASURED"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jsonl", type=Path)
    args = parser.parse_args()
    try:
        with args.jsonl.open(encoding="utf-8") as source:
            print(json.dumps(inspect(source), sort_keys=True))
    except (OSError, TraceError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
