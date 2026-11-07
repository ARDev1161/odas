#!/usr/bin/env python3
"""Schema-only fixtures. Not audio, not measured Acoustix results."""
import copy
import io
import json
import unittest

from validate_sst_raw_trace import TraceError, validate_record, validate_stream


def observed(hop=0):
    return {
        "schema": "odas_sst_raw_v1",
        "odas_timestamp": hop + 1,
        "hop_index": hop, "sample_offset": hop * 128,
        "hop_frames": 128, "theta_new": 0.15,
        "ssl_candidates": [{
            "index": 0, "x": 0.6, "y": 0.8, "z": 0.0,
            "strength": 0.25, "birth_posterior": 0.2,
            "track_posteriors": [{"track_id": 9, "posterior": 0.4}],
        }],
        "births": [], "retirements": [],
        "tracks_after": [{"slot": 0, "track_id": 9,
                          "state": "A", "activity": 0.4}],
        "active_tracks_after": 1,
    }


class RawTraceTests(unittest.TestCase):
    def test_contiguous_trace(self):
        lines = "\n".join(json.dumps(observed(i)) for i in range(3)) + "\n"
        result = validate_stream(io.StringIO(lines))
        self.assertEqual(result["validated_hops"], 3)
        self.assertEqual(result["oracle_metrics"], "NOT_MEASURED")

    def test_no_first_hop(self):
        with self.assertRaises(TraceError):
            validate_record(observed(4))

    def test_gap(self):
        with self.assertRaises(TraceError):
            validate_stream(io.StringIO(json.dumps(observed()) + "\n" +
                                        json.dumps(observed(2)) + "\n"))

    def test_empty(self):
        with self.assertRaises(TraceError):
            validate_stream(io.StringIO(""))

    def test_bad_timestamp(self):
        item = observed()
        item["odas_timestamp"] = 2
        with self.assertRaises(TraceError):
            validate_record(item)

    def test_unsupported_hop(self):
        item = observed()
        item["hop_frames"] = 256
        with self.assertRaises(TraceError):
            validate_record(item)

    def test_nonfinite_record(self):
        item = observed()
        item["ssl_candidates"][0]["birth_posterior"] = float("nan")
        with self.assertRaises(TraceError):
            validate_record(item)

    def test_posterior_mass(self):
        item = observed()
        item["ssl_candidates"][0]["birth_posterior"] = 0.9
        with self.assertRaises(TraceError):
            validate_record(item)

    def test_duplicate_active_track_slot(self):
        item = observed()
        track = copy.deepcopy(item["tracks_after"][0])
        track["track_id"] = 11
        item["tracks_after"].append(track)
        item["active_tracks_after"] = 2
        with self.assertRaises(TraceError):
            validate_record(item)

    def test_missing_field(self):
        item = observed()
        del item["ssl_candidates"][0]["birth_posterior"]
        with self.assertRaises(TraceError):
            validate_record(item)

    def test_boolean_id(self):
        item = observed()
        item["births"] = [True]
        with self.assertRaises(TraceError):
            validate_record(item)

    def test_duplicate_key_jsonl(self):
        line = json.dumps(observed()).replace(
            '"hop_frames": 128,', '"hop_frames": 128, "hop_frames": 512,')
        with self.assertRaisesRegex(TraceError, "duplicate JSON key"):
            validate_stream(io.StringIO(line + "\n"))

    def test_oracle_claim_rejected(self):
        item = observed()
        item["oracle_matches"] = 1
        with self.assertRaises(TraceError):
            validate_record(item)

    def test_provisional_birth_and_retirement(self):
        item = observed()
        item["births"] = [10]
        item["retirements"] = [9]
        item["tracks_after"] = [{"slot": 0, "track_id": 10,
                                 "state": "P", "activity": 0.0}]
        self.assertEqual(validate_record(item), 0)

    def test_zero_ssl_candidates(self):
        item = observed()
        item["ssl_candidates"] = []
        self.assertEqual(validate_record(item), 0)


if __name__ == "__main__":
    unittest.main()
