import json
import unittest
from analyze_sst_birth_pressure import summarize
from validate_sst_raw_trace import TraceError


def hop(index, candidates, births):
    return {"schema": "odas_sst_raw_v1", "odas_timestamp": index + 1,
            "hop_index": index, "sample_offset": index * 128, "hop_frames": 128,
            "theta_new": 0.15, "ssl_candidates": [
                {"index": i, "x": 1.0, "y": 0.0, "z": 0.0,
                 "strength": 0.4, "birth_posterior": p,
                 "track_posteriors": []} for i, p in enumerate(candidates)],
            "births": births, "retirements": [], "tracks_after": [],
            "active_tracks_after": 0}


class BirthPressureTests(unittest.TestCase):
    def test_two_eligible_one_birth_is_diagnostic_not_proof(self):
        result = summarize([json.dumps(hop(0, [0.3, 0.2], [7]))])
        self.assertEqual(result["multi_eligible_underfilled_hops"], 1)
        self.assertEqual(result["unfilled_candidate_count"], 1)
        self.assertFalse(result["slot_collision_confirmed"])

    def test_two_births_no_underfill(self):
        result = summarize([json.dumps(hop(0, [0.3, 0.2], [7, 8]))])
        self.assertEqual(result["multi_eligible_underfilled_hops"], 0)

    def test_below_threshold_not_counted(self):
        result = summarize([json.dumps(hop(0, [0.14, 0.2], []))])
        self.assertEqual(result["multi_eligible_hops"], 0)

    def test_empty_rejected(self):
        with self.assertRaises(TraceError):
            summarize([])

    def test_noncontiguous_rejected(self):
        with self.assertRaises(TraceError):
            summarize([json.dumps(hop(0, [], [])), json.dumps(hop(2, [], []))])


if __name__ == "__main__":
    unittest.main()
