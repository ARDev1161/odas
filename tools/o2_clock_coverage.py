#!/usr/bin/env python3
"""Audit frozen ODAS trace against Acoustix oracle clock without inventing speaker matches."""
import argparse
import json
import re
from pathlib import Path


def audit(oracle, trace, sample_rate=16000, schedule=None):
    rows = oracle.get("ground_truth")
    if not isinstance(rows, list) or not rows:
        raise ValueError("missing oracle ground_truth")
    if oracle.get("sample_rate_hz") != sample_rate:
        raise ValueError("oracle sample rate mismatch")
    if not isinstance(trace, list) or not trace:
        raise ValueError("missing native trace")
    hop = trace[0].get("hop_frames")
    if not isinstance(hop, int) or hop <= 0:
        raise ValueError("invalid native hop")
    for i, rec in enumerate(trace):
        if rec.get("hop_index") != i or rec.get("hop_frames") != hop:
            raise ValueError("non-contiguous native hop indices or variable hop")
        if rec.get("sample_offset") != i * hop:
            raise ValueError("native sample offset mismatch")
    for i, rec in enumerate(rows):
        if rec.get("hop") != i:
            raise ValueError("non-contiguous oracle hop indices")
        expected_t = (i + 0.5) * hop / sample_rate
        if abs(rec.get("t_s", -1) - expected_t) > 1e-6:
            raise ValueError("oracle hop-center clock mismatch")
    if len(rows) > len(trace):
        raise ValueError("oracle longer than native trace")
    # Tail is unlabelled: occupancy is observable, false positives are not.
    tail = trace[len(rows):]
    counts = [rec.get("active_tracks_after") for rec in tail]
    if any(value is not None for value in counts):
        if any(type(value) is not int or value < 0 for value in counts):
            raise ValueError("invalid or incomplete tail occupancy")
        tail_status = "MEASURED_UNLABELED"
    else:
        counts = []
        tail_status = "NOT_AVAILABLE"
    # This is only a cardinality ceiling on possible oracle matches. No DOA,
    # source ID, or separation quality can be inferred from occupancy alone.
    overlap = {"status": "NOT_AVAILABLE", "oracle_overlap_hops": 0,
               "native_multi_track_hops_during_overlap": 0,
               "capacity_deficit_hops": 0, "max_possible_two_source_recall": "NOT_MEASURED",
               "speaker_matches": "NOT_MEASURED",
               "oracle_source_hops": 0, "max_matchable_source_hops": "NOT_MEASURED",
               "max_possible_source_hop_recall": "NOT_MEASURED"}
    source_fields = ["sources" in row for row in rows]
    if any(source_fields) and not all(source_fields):
        raise ValueError("incomplete oracle source annotations")
    if all(source_fields):
        if any(not isinstance(row["sources"], list) for row in rows):
            raise ValueError("invalid oracle source annotations")
        # Cardinality bounds require distinct, well-formed oracle identities.
        # Duplicate source IDs in one hop would inflate the recall ceiling.
        for row in rows:
            identities = [src.get("id") if isinstance(src, dict) else None
                          for src in row["sources"]]
            if any(not isinstance(identity, (str, int)) or isinstance(identity, bool)
                   or identity == "" for identity in identities):
                raise ValueError("invalid oracle source identity")
            if len(set(identities)) != len(identities):
                raise ValueError("duplicate oracle source identity within hop")
        scene_counts = [rec.get("active_tracks_after") for rec in trace[:len(rows)]]
        if all(type(n) is int and n >= 0 for n in scene_counts):
            overlaps = [i for i, row in enumerate(rows) if len(row["sources"]) >= 2]
            possible = sum(scene_counts[i] >= 2 for i in overlaps)
            source_hops = sum(len(row["sources"]) for row in rows)
            matchable_hops = sum(min(len(row["sources"]), scene_counts[i])
                                 for i, row in enumerate(rows))
            overlap.update(status="MEASURED_CAPACITY_ONLY",
                           oracle_source_hops=source_hops,
                           max_matchable_source_hops=matchable_hops,
                           max_possible_source_hop_recall=(matchable_hops / source_hops
                                                           if source_hops else "NOT_APPLICABLE"),
                           oracle_overlap_hops=len(overlaps),
                           native_multi_track_hops_during_overlap=possible,
                           capacity_deficit_hops=len(overlaps) - possible,
                           max_possible_two_source_recall=(possible / len(overlaps)
                                                           if overlaps else "NOT_APPLICABLE"))
        elif any(n is not None for n in scene_counts):
            raise ValueError("invalid or incomplete scene occupancy")
    # Tracks during oracle-labelled zero-source hops are an occupancy warning,
    # not automatically false positives: environmental noise can be tracked.
    silent = {"status": "NOT_AVAILABLE", "oracle_silent_hops": 0,
              "occupied_silent_hops": "NOT_MEASURED",
              "silent_track_hops": "NOT_MEASURED",
              "max_silent_tracks": "NOT_MEASURED",
              "false_tracks": "NOT_MEASURED"}
    if all(source_fields):
        silent_indices = [i for i, row in enumerate(rows) if not row["sources"]]
        if all(type(rec.get("active_tracks_after")) is int and
               rec["active_tracks_after"] >= 0 for rec in trace[:len(rows)]):
            values = [trace[i]["active_tracks_after"] for i in silent_indices]
            silent.update(status="MEASURED_OCCUPANCY_ONLY",
                          oracle_silent_hops=len(values),
                          occupied_silent_hops=sum(n > 0 for n in values),
                          silent_track_hops=sum(values),
                          max_silent_tracks=max(values, default=0))
    speech_supplied = oracle.get("speech_recordings_supplied")
    if type(speech_supplied) is not bool:
        speech_status = "UNKNOWN"
    else:
        speech_status = "EXTERNAL_RECORDINGS_DECLARED" if speech_supplied else "EXTERNAL_RECORDINGS_NOT_SUPPLIED"
    schedule_status = "NOT_CHECKED"
    if schedule is not None:
        segments = schedule.get("segments")
        if not isinstance(segments, list):
            raise ValueError("missing speech schedule segments")
        if schedule.get("sample_rate_hz") != sample_rate:
            raise ValueError("speech schedule sample rate mismatch")
        if any(not isinstance(s, dict) or not isinstance(s.get("source_id"), str)
               or not isinstance(s.get("clean_source_sha256"), str)
               for s in segments):
            raise ValueError("invalid speech schedule segment provenance")
        if segments:
            # A declared corpus segment must fit the rendered 12-second scene.
            # Validate the actual frame schedule before treating it as evidence.
            scene_frames = len(rows) * hop
            for segment in segments:
                start = segment.get("scheduled_start_frame")
                end = segment.get("scheduled_end_frame")
                placed = segment.get("placed_end_frame")
                original = segment.get("original_utterance_frames")
                if any(type(n) is not int for n in (start, end, placed, original)):
                    raise ValueError("missing or non-integer speech segment frame bounds")
                if not (0 <= start < placed <= end <= scene_frames):
                    raise ValueError("speech segment outside oracle scene or invalid placement")
                if original <= 0 or placed - start > original:
                    raise ValueError("invalid original utterance frame count")
                if not re.fullmatch(r"[0-9a-f]{64}", segment["clean_source_sha256"]):
                    raise ValueError("invalid clean source SHA256")
            # The flag reports externally supplied recordings, not whether
            # the renderer used its configured speech corpus. A schedule
            # declares corpus selection but cannot prove WAV sample identity.
            speech_status = "CORPUS_SEGMENTS_DECLARED"
            schedule_status = "CORPUS_SEGMENTS_DECLARED"
        else:
            schedule_status = "NO_SEGMENTS"
    return {
        "speech_provenance": {
            "schedule_status": schedule_status,
            "status": speech_status,
            "real_speech_quality_eligible": False,
            "wer": "NOT_MEASURED",
            "sss_quality": "NOT_MEASURED",
        },
        "overlap_capacity_upper_bound": overlap,
        "oracle_silent_track_occupancy": silent,
        "tail_track_occupancy": {
            "status": tail_status,
            "evaluated_hops": len(counts),
            "occupied_hops": sum(n > 0 for n in counts),
            "track_hops": sum(counts),
            "max_simultaneous_tracks": max(counts, default=0),
            "false_tracks": "NOT_MEASURED",
        },
        "status": "PARTIAL_CLOCK_ONLY",
        "oracle_hops": len(rows),
        "native_hops": len(trace),
        "hop_frames": hop,
        "sample_rate_hz": sample_rate,
        "oracle_duration_s": len(rows) * hop / sample_rate,
        "native_duration_s": len(trace) * hop / sample_rate,
        "unscored_native_tail_hops": len(trace) - len(rows),
        "unscored_native_tail_s": (len(trace) - len(rows)) * hop / sample_rate,
        "coordinate_frame": "NOT_VERIFIED",
        "speaker_association": "NOT_MEASURED",
        "idf1": "NOT_MEASURED",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("oracle", type=Path)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--schedule", type=Path)
    args = parser.parse_args()
    oracle = json.loads(args.oracle.read_text(encoding="utf-8"))
    with args.trace.open(encoding="utf-8") as source:
        trace = [json.loads(line) for line in source if line.strip()]
    schedule = json.loads(args.schedule.read_text(encoding="utf-8")) if args.schedule else None
    report = audit(oracle, trace, schedule=schedule)
    rendered = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
