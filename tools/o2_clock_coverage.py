#!/usr/bin/env python3
"""Audit frozen ODAS trace against Acoustix oracle clock without inventing speaker matches."""
import argparse
import json
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
