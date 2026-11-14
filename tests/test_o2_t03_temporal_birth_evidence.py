import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from o2_t03_temporal_birth_evidence import audit


def pot(degrees, strength):
    radians = math.radians(degrees)
    return {"x": math.cos(radians), "y": math.sin(radians),
            "z": 0.0, "strength": strength, "birth_posterior": 0.95 if strength > 0.36 else 0.05}


def sample(strengths):
    oracle, trace = {"ground_truth": []}, []
    for i, strengths_at_hop in enumerate(strengths):
        oracle["ground_truth"].append({"sources": [
            {"id": "a", "bearing_deg": -30, "elevation_deg": 0},
            {"id": "b", "bearing_deg": 30, "elevation_deg": 0}]})
        trace.append({"theta_new": 0.9,
                      "ssl_candidates": [pot(d, s) for d, s in
                                         zip((-30, 30), strengths_at_hop)]})
    return oracle, trace


class TemporalEvidenceTests(unittest.TestCase):
    def test_persistent_geometry_but_weak_birth(self):
        oracle, trace = sample([[.5, .1]] * 6)
        result = audit(oracle, trace)
        self.assertEqual(result["pair_geometry_hops"], 6)
        self.assertEqual(result["longest_pair_geometry_streak_hops"], 6)
        self.assertEqual(result["pair_above_uncontested_gate_hops"], 0)

    def test_interrupted_evidence_resets_streak(self):
        oracle, trace = sample([[.5, .5]] * 3 + [[.5]] + [[.5, .5]] * 2)
        result = audit(oracle, trace)
        self.assertEqual(result["pair_geometry_hops"], 5)
        self.assertEqual(result["longest_pair_geometry_streak_hops"], 3)
        self.assertEqual(result["longest_pair_above_gate_streak_hops"], 3)

    def test_five_hop_confirmation_run_histogram(self):
        oracle, trace = sample([[.5, .5]] * 6 + [[.5]] + [[.5, .5]] * 3)
        report = audit(oracle, trace)
        self.assertEqual(report["pair_above_gate_run_lengths_hops"], [6, 3])
        self.assertEqual(report["pair_geometry_run_lengths_hops"], [6, 3])
        self.assertEqual(report["pair_above_gate_runs_at_least_5_hops"], 1)
        self.assertEqual(report["pair_above_gate_hops_in_runs_at_least_5"], 6)

    def test_consecutive_failed_hops_do_not_duplicate_completed_runs(self):
        oracle, trace = sample([[.5, .5]] * 3 + [[.5, .1]] * 3 + [[.5, .5]] * 2)
        result = audit(oracle, trace)
        self.assertEqual(result["pair_geometry_run_lengths_hops"], [8])
        self.assertEqual(result["pair_above_gate_run_lengths_hops"], [3, 2])
        self.assertEqual(result["pair_actual_birth_posterior_run_lengths_hops"], [3, 2])
        self.assertEqual(sum(result["pair_above_gate_run_lengths_hops"]),
                         result["pair_above_uncontested_gate_hops"])
        self.assertEqual(sum(result["pair_actual_birth_posterior_run_lengths_hops"]),
                         result["pair_above_actual_birth_posterior_hops"])

    def test_actual_posterior_competition_blocks_strong_pair(self):
        oracle, trace = sample([[.5, .5]] * 6)
        for row in trace:
            row["ssl_candidates"][1]["birth_posterior"] = 0.2
        result = audit(oracle, trace)
        self.assertEqual(result["pair_above_gate_run_lengths_hops"], [6])
        self.assertEqual(result["pair_actual_birth_posterior_run_lengths_hops"], [])
        self.assertEqual(result["pair_above_actual_birth_posterior_hops"], 0)

    def test_reject_nonfinite_native_birth_posterior(self):
        oracle, trace = sample([[.5, .5]])
        trace[0]["ssl_candidates"][0]["birth_posterior"] = float("nan")
        with self.assertRaisesRegex(ValueError, "birth posterior"):
            audit(oracle, trace)

    def test_no_evidence_runs(self):
        oracle, trace = sample([[.5]] * 4)
        report = audit(oracle, trace)
        self.assertEqual(report["pair_above_gate_run_lengths_hops"], [])
        self.assertEqual(report["pair_geometry_runs_at_least_5_hops"], 0)

    def test_duration_uses_native_hop_and_sample_rate(self):
        oracle, trace = sample([[.5, .5]] * 3)
        oracle["sample_rate_hz"] = 8000
        for i, row in enumerate(trace):
            row["hop_index"] = i
            row["hop_frames"] = 80
        result = audit(oracle, trace)
        self.assertAlmostEqual(result["longest_pair_geometry_streak_ms"], 30.0)
        self.assertAlmostEqual(result["longest_pair_above_gate_streak_ms"], 30.0)

    def test_rejects_misaligned_hops(self):
        oracle, trace = sample([[.5, .5]] * 2)
        trace[1]["hop_index"] = 7
        with self.assertRaises(ValueError):
            audit(oracle, trace)

    def test_rejects_nonfinite_candidate_strength(self):
        oracle, trace = sample([[.5, .5]])
        trace[0]["ssl_candidates"][1]["strength"] = float("nan")
        with self.assertRaises(ValueError):
            audit(oracle, trace)

    def test_rejects_inconsistent_hop_sizes(self):
        oracle, trace = sample([[.5, .5]] * 2)
        trace[0]["hop_frames"] = 128
        trace[1]["hop_frames"] = 256
        with self.assertRaises(ValueError):
            audit(oracle, trace)

    def test_rejects_duplicate_oracle_speaker_identity(self):
        oracle, trace = sample([[.5, .5]])
        oracle["ground_truth"][0]["sources"][1]["id"] = "a"
        with self.assertRaisesRegex(ValueError, "oracle source identities"):
            audit(oracle, trace)

    def test_rejects_misaligned_native_sample_offset(self):
        oracle, trace = sample([[.5, .5]] * 2)
        trace[1]["sample_offset"] = 129
        with self.assertRaisesRegex(ValueError, "sample offset"):
            audit(oracle, trace)

    def test_duplicate_direction_is_not_two_sources(self):
        oracle, trace = sample([[.5, .5]])
        trace[0]["ssl_candidates"] = [pot(-30, .5), pot(-30, .5)]
        self.assertEqual(audit(oracle, trace)["pair_geometry_hops"], 0)


if __name__ == "__main__":
    unittest.main()
