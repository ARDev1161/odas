import math
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from o2_t03_birth_bottleneck import analyze, uncontested_strength_gate


def fixture(strength_a=.5, strength_b=.10, posterior_a=.95, posterior_b=1e-6):
    oracle = {"sample_rate_hz": 16000, "ground_truth": [{
        "hop": 0, "t_s": .004,
        "sources": [
            {"id": "speaker_1", "bearing_deg": 20, "elevation_deg": 0},
            {"id": "speaker_2", "bearing_deg": -20, "elevation_deg": 0},
        ]
    }]}
    def pot(index, az, strength, posterior):
        rad = math.radians(az)
        return {"index": index, "x": math.cos(rad), "y": math.sin(rad),
                "z": 0.0, "strength": strength,
                "birth_posterior": posterior}
    trace = [{
        "hop_index": 0, "sample_offset": 0, "hop_frames": 128,
        "theta_new": .9,
        "ssl_candidates": [
            pot(0, 20, strength_a, posterior_a),
            pot(1, -20, strength_b, posterior_b),
        ],
        "births": [1], "retirements": [],
        "tracks_after": [{"track_id": 1, "state": "P"}]
    }, {
        "hop_index": 1, "sample_offset": 128, "hop_frames": 128,
        "theta_new": .9, "ssl_candidates": [], "births": [],
        "retirements": [1], "tracks_after": []
    }]
    return oracle, trace


class BirthBottleneckTests(unittest.TestCase):
    def test_analytic_gate(self):
        self.assertAlmostEqual(uncontested_strength_gate(.9), .36162040962227, places=10)
        self.assertGreater(uncontested_strength_gate(.99), uncontested_strength_gate(.9))

    def test_one_birth_eligible_not_two(self):
        oracle, trace = fixture()
        report = analyze(oracle, trace)
        self.assertEqual(report["birth_eligible_hops"],
                         {"zero": 0, "one": 1, "two_or_more": 0})
        self.assertEqual(report["distinct_ssl_pair_hops_25deg"], 1)
        self.assertEqual(report["second_direction_strength_below_no_track_gmm_gate"], 1)
        self.assertEqual(report["overlap_births_retired_without_promotion"], 1)
        self.assertEqual(report["overlap_births_ever_active"], 0)

    def test_two_birth_candidates(self):
        oracle, trace = fixture(strength_b=.5, posterior_b=.95)
        self.assertEqual(analyze(oracle, trace)["birth_eligible_hops"]["two_or_more"], 1)
        self.assertEqual(analyze(oracle, trace)["strong_second_direction_posterior_classes"]["new_source"], 1)

    def test_strong_second_candidate_associated_to_old_track(self):
        oracle, trace = fixture(strength_b=.5, posterior_b=.04)
        trace[0]["ssl_candidates"][1]["track_posteriors"] = [
            {"track_id": 2, "posterior": .9}
        ]
        report = analyze(oracle, trace)
        self.assertEqual(report["strong_second_direction_posterior_classes"],
                         {"new_source": 0, "existing_track": 1,
                          "unassigned_residual": 0})

    def test_rejects_nonfinite_track_posterior(self):
        oracle, trace = fixture(strength_b=.5, posterior_b=.04)
        trace[0]["ssl_candidates"][1]["track_posteriors"] = [
            {"track_id": 2, "posterior": float("nan")}
        ]
        with self.assertRaisesRegex(ValueError, "invalid native track posterior"):
            analyze(oracle, trace)

    def test_rejects_overfull_posterior_mass(self):
        oracle, trace = fixture(strength_b=.5, posterior_b=.3)
        trace[0]["ssl_candidates"][1]["track_posteriors"] = [
            {"track_id": 2, "posterior": .8}
        ]
        with self.assertRaisesRegex(ValueError, "native posterior mass exceeds one"):
            analyze(oracle, trace)

    def test_rejects_duplicate_track_identity_in_posterior(self):
        oracle, trace = fixture(strength_b=.5, posterior_b=.04)
        trace[0]["ssl_candidates"][1]["track_posteriors"] = [
            {"track_id": 2, "posterior": .3},
            {"track_id": 2, "posterior": .3},
        ]
        with self.assertRaisesRegex(ValueError, "duplicate native track identity"):
            analyze(oracle, trace)

    def test_rejects_nonpositive_or_noninteger_track_identity(self):
        for ident in (0, -1, 2.0, True, None):
            with self.subTest(ident=ident):
                oracle, trace = fixture(strength_b=.5, posterior_b=.04)
                trace[0]["ssl_candidates"][1]["track_posteriors"] = [
                    {"track_id": ident, "posterior": .3}
                ]
                with self.assertRaisesRegex(ValueError, "invalid or duplicate native track identity"):
                    analyze(oracle, trace)

    def test_accepts_rounding_tolerance_in_posterior_mass(self):
        oracle, trace = fixture(strength_b=.5, posterior_b=.3)
        trace[0]["ssl_candidates"][1]["track_posteriors"] = [
            {"track_id": 2, "posterior": .70000001}
        ]
        self.assertEqual(analyze(oracle, trace)["strong_second_direction_posterior_classes"]["existing_track"], 1)

    def test_one_potential_cannot_cover_two_distinct_speakers(self):
        oracle, trace = fixture()
        trace[0]["ssl_candidates"].pop()
        report = analyze(oracle, trace)
        self.assertEqual(report["distinct_ssl_pair_hops_45deg"], 0)

    def test_clock_mismatch_fails(self):
        oracle, trace = fixture()
        trace[1]["sample_offset"] = 0
        with self.assertRaisesRegex(ValueError, "native hop clock"):
            analyze(oracle, trace)

    def test_invalid_probability_fails(self):
        oracle, trace = fixture()
        trace[0]["ssl_candidates"][1]["birth_posterior"] = float("nan")
        with self.assertRaisesRegex(ValueError, "invalid native SSL probability"):
            analyze(oracle, trace)

    def test_promotion_latency_is_measured_from_native_hops(self):
        oracle, trace = fixture()
        trace[1]["tracks_after"] = [{"track_id": 1, "state": "A"}]
        trace[1]["retirements"] = []
        report = analyze(oracle, trace)
        self.assertEqual(report["overlap_birth_promotion_latency_hops"], [1])
        self.assertEqual(report["overlap_birth_promotion_latency_median_ms"], 8.0)

    def test_no_promotion_latency_for_retired_provisional_birth(self):
        oracle, trace = fixture()
        report = analyze(oracle, trace)
        self.assertEqual(report["overlap_birth_promotion_latency_hops"], [])
        self.assertIsNone(report["overlap_birth_promotion_latency_median_ms"])

    def test_unretired_provisional_birth_is_censored_not_rejected(self):
        oracle, trace = fixture()
        trace[1]["retirements"] = []
        report = analyze(oracle, trace)
        self.assertEqual(report["overlap_births_censored_without_promotion"], 1)
        self.assertEqual(report["overlap_births_retired_without_promotion"], 0)

    def test_rejects_overlapping_reused_id_birth(self):
        oracle, trace = fixture()
        trace[1]["births"] = [1]
        with self.assertRaisesRegex(ValueError, "overlapping native track ID"):
            analyze(oracle, trace)

    def test_rejects_retirement_without_birth(self):
        oracle, trace = fixture()
        trace[1]["retirements"] = [2]
        with self.assertRaisesRegex(ValueError, "retirement without matching birth"):
            analyze(oracle, trace)

    def test_accepts_id_reuse_after_retirement(self):
        oracle, trace = fixture()
        trace.append({
            "hop_index": 2, "sample_offset": 256, "hop_frames": 128,
            "theta_new": .9, "ssl_candidates": [], "births": [1],
            "retirements": [], "tracks_after": [{"track_id": 1, "state": "A"}],
        })
        report = analyze(oracle, trace)
        self.assertEqual(report["overlap_births_ever_active"], 0)
        self.assertEqual(report["overlap_births_retired_without_promotion"], 1)

    def test_promoted_track_is_not_rejected(self):
        oracle, trace = fixture()
        trace[1]["tracks_after"] = [{"track_id": 1, "state": "A"}]
        trace[1]["retirements"] = []
        report = analyze(oracle, trace)
        self.assertEqual(report["overlap_births_ever_active"], 1)
        self.assertEqual(report["overlap_births_retired_without_promotion"], 0)


if __name__ == "__main__":
    unittest.main()
