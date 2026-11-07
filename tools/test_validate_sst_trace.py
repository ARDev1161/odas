#!/usr/bin/env python3
"""Contract tests only: fabricated records are NOT real Acoustix observations."""
import copy
import io
import json
import unittest
from validate_sst_trace import TraceError, validate_record, validate_stream


def record(hop=0):
    return {
        "hop_index": hop, "sample_offset": hop * 128,
        "ssl_candidates": [{"index": 0, "azimuth_deg": 30.0,
                            "elevation_deg": 0.0, "strength": 0.4,
                            "birth_evidence": 0.5}],
        "sst_tracks": [{"track_id": 7, "existence_probability": 0.8,
                        "assigned_ssl_index": 0}],
        "counters": {"ssl_candidates": 1, "active_sst_tracks": 1,
                     "births": 1, "retirements": 0,
                     "unmatched_ssl_candidates": 0,
                     "oracle_active_sources": 1, "oracle_matches": 1,
                     "false_tracks": 0, "id_switches": 0},
    }


class ContractTests(unittest.TestCase):
    def test_contiguous(self):
        self.assertEqual(validate_stream(io.StringIO(
            json.dumps(record(0)) + "\n" + json.dumps(record(1)) + "\n"
        ))["validated_hops"], 2)

    def test_empty_is_blocked(self):
        with self.assertRaises(TraceError):
            validate_stream(io.StringIO(""))

    def test_nonzero_initial_hop(self):
        with self.assertRaises(TraceError):
            validate_stream(io.StringIO(json.dumps(record(3)) + "\n"))

    def test_nonzero_initial_offset(self):
        item = record()
        item["sample_offset"] = 128
        with self.assertRaises(TraceError):
            validate_stream(io.StringIO(json.dumps(item) + "\n"))

    def test_false_tracks_exceed_active(self):
        item = record()
        item["counters"]["false_tracks"] = 2
        with self.assertRaises(TraceError):
            validate_record(item)

    def test_false_tracks_conflict_with_matches(self):
        item = record()
        item["counters"]["false_tracks"] = 1
        with self.assertRaises(TraceError):
            validate_record(item)

    def test_noncontiguous(self):
        with self.assertRaises(TraceError):
            validate_stream(io.StringIO(json.dumps(record(0)) + "\n" + json.dumps(record(2)) + "\n"))

    def test_nan(self):
        item = record()
        item["ssl_candidates"][0]["strength"] = float("nan")
        with self.assertRaises(TraceError):
            validate_record(item)

    def test_invalid_association(self):
        item = record()
        item["sst_tracks"][0]["assigned_ssl_index"] = 1
        with self.assertRaises(TraceError):
            validate_record(item)

    def test_impossible_oracle(self):
        item = record()
        item["counters"]["oracle_matches"] = 2
        with self.assertRaises(TraceError):
            validate_record(item)

    def test_duplicate_tracks(self):
        item = record()
        item["sst_tracks"].append(copy.deepcopy(item["sst_tracks"][0]))
        item["counters"]["active_sst_tracks"] = 2
        with self.assertRaises(TraceError):
            validate_record(item)

    def test_boolean_counter(self):
        item = record()
        item["counters"]["births"] = True
        with self.assertRaises(TraceError):
            validate_record(item)

    def test_candidate_bound(self):
        item = record()
        item["ssl_candidates"] *= 129
        item["counters"]["ssl_candidates"] = 129
        with self.assertRaises(TraceError):
            validate_record(item)


if __name__ == "__main__":
    unittest.main()
