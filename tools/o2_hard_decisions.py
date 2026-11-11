#!/usr/bin/env python3
"""Count actual native SST births/retirements, never infer identity from posterior."""
import argparse
import json
from collections import Counter

def percentile_nearest_rank(values, percentile):
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[(percentile * len(ordered) + 99) // 100 - 1]

def analyze(lines):
    stats = Counter()
    previous = None
    prev_hop = None
    two_track_streak = 0
    max_two_track_streak = 0
    multi_track_episodes = []
    multi_track_intervals = []
    multi_track_start = None
    track_ages = {}
    completed_track_lifetimes = []
    track_episode_starts = {}
    track_episode_intervals = []
    initial_unannounced_ids = set()
    first_hop = None
    for number, line in enumerate(lines, 1):
        if not line.strip():
            raise ValueError(f"line {number}: empty row")
        row = json.loads(line)
        if row.get("schema") != "odas_sst_raw_v1":
            raise ValueError(f"line {number}: schema")
        hop = row.get("hop_index")
        if type(hop) is not int or hop < 0 or (prev_hop is not None and hop != prev_hop + 1):
            raise ValueError(f"line {number}: non-contiguous hop")
        prev_hop = hop
        tracks = row.get("tracks_after")
        births = row.get("births")
        retired = row.get("retirements")
        if not isinstance(tracks, list) or not isinstance(births, list) or not isinstance(retired, list):
            raise ValueError(f"line {number}: missing decisions")
        active = set()
        for track in tracks:
            if not isinstance(track, dict) or type(track.get("track_id")) is not int:
                raise ValueError(f"line {number}: malformed track")
            ident = track["track_id"]
            if ident <= 0 or ident in active:
                raise ValueError(f"line {number}: duplicate/invalid track")
            active.add(ident)
        for name, ids in (("births", births), ("retirements", retired)):
            if any(type(v) is not int or v <= 0 for v in ids) or len(ids) != len(set(ids)):
                raise ValueError(f"line {number}: invalid {name}")
        born, gone = set(births), set(retired)
        if born & gone:
            raise ValueError(f"line {number}: born and retired same hop")
        if previous is not None:
            if active - previous != born or previous - active != gone:
                raise ValueError(f"line {number}: transition mismatch")
        elif not born.issubset(active):
            raise ValueError(f"line {number}: birth absent from output")
        # A trace beginning with active tracks lacks their true birth time.
        # Never interpret those first-observed tracks as measured births.
        if previous is None:
            first_hop = hop
            initial_unannounced_ids = active - born
        # Lifetimes are contiguous track episodes, not speaker identities.
        # Retiring and later reusing the same numeric ID creates two episodes.
        for ident in gone:
            completed_track_lifetimes.append(track_ages.pop(ident))
            track_episode_intervals.append({"track_id": ident, "start_hop": track_episode_starts[ident], "end_hop_exclusive": hop, "right_censored": False, "left_censored": ident in initial_unannounced_ids and track_episode_starts[ident] == first_hop})
            track_episode_starts.pop(ident)
        for ident in born:
            track_ages[ident] = 0
            track_episode_starts[ident] = hop
        for ident in active:
            track_ages.setdefault(ident, 0)
            track_episode_starts.setdefault(ident, hop)
            track_ages[ident] += 1
        if len(active) >= 2 and multi_track_start is None:
            multi_track_start = hop
        if len(active) < 2 and two_track_streak:
            multi_track_episodes.append(two_track_streak)
            multi_track_intervals.append({"start_hop": multi_track_start, "end_hop_exclusive": hop})
            multi_track_start = None
        stats["hops"] += 1
        stats["births"] += len(born)
        stats["retirements"] += len(gone)
        stats["hops_with_two_tracks"] += len(active) >= 2
        stats[f"hops_with_{min(len(active), 4)}_tracks"] += 1
        two_track_streak = two_track_streak + 1 if len(active) >= 2 else 0
        max_two_track_streak = max(max_two_track_streak, two_track_streak)
        stats["max_simultaneous_tracks"] = max(stats["max_simultaneous_tracks"], len(active))
        stats["hops_with_birth"] += bool(born)
        stats["hops_with_retirement"] += bool(gone)
        previous = active
    if not stats["hops"]:
        raise ValueError("empty trace")
    if two_track_streak:
        multi_track_episodes.append(two_track_streak)
        multi_track_intervals.append({"start_hop": multi_track_start, "end_hop_exclusive": prev_hop + 1})
    # Tracks still present at EOF are right-censored: the recording ended,
    # not the track. Keep legacy observed-duration summaries for compatibility,
    # but expose completed and censored episodes separately so downstream
    # analyses cannot interpret EOF as an SST retirement decision.
    for ident in track_ages:
        track_episode_intervals.append({"track_id": ident, "start_hop": track_episode_starts[ident], "end_hop_exclusive": prev_hop + 1, "right_censored": True, "left_censored": ident in initial_unannounced_ids and track_episode_starts[ident] == first_hop})
    track_episode_intervals.sort(key=lambda episode: (episode["start_hop"], episode["track_id"]))
    lifetimes = completed_track_lifetimes + list(track_ages.values())
    return dict(stats, max_consecutive_hops_with_two_tracks=max_two_track_streak,
                multi_track_episode_count=len(multi_track_episodes),
                multi_track_episode_lengths_hops=multi_track_episodes,
                multi_track_intervals_hops=multi_track_intervals,
                multi_track_episode_p90_hops=percentile_nearest_rank(multi_track_episodes, 90),
                track_episode_count=len(lifetimes),
                track_episode_intervals_hops=track_episode_intervals,
                completed_track_episode_count=len(completed_track_lifetimes),
                right_censored_track_episode_count=len(track_ages),
                left_censored_track_episode_count=sum(1 for e in track_episode_intervals if e["left_censored"]),
                completed_track_lifetime_median_hops=percentile_nearest_rank(completed_track_lifetimes, 50),
                completed_track_lifetime_p90_hops=percentile_nearest_rank(completed_track_lifetimes, 90),
                track_lifetime_median_hops=percentile_nearest_rank(lifetimes, 50),
                track_lifetime_p90_hops=percentile_nearest_rank(lifetimes, 90),
                oracle_identity="NOT_MEASURED", sss_quality="NOT_MEASURED")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("trace")
    args = parser.parse_args()
    with open(args.trace, encoding="utf-8") as f:
        print(json.dumps(analyze(f), sort_keys=True))

if __name__ == "__main__":
    main()
