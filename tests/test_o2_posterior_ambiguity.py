"""Independent contracts for native posterior ambiguity diagnostics."""
import io
import json
import unittest
from tools.o2_posterior_ambiguity import summarize


def trace(posteriors):
    return io.StringIO(json.dumps({
        "schema": "odas_sst_raw_v1",
        "ssl_candidates": [{"birth_posterior": 0.25, "track_posteriors": [
            {"track_id": i + 1, "posterior": v}
            for i, v in enumerate(posteriors)]}]
    }) + "\n")


class PosteriorAmbiguityTests(unittest.TestCase):
    def test_two_nearly_equal_marginals(self):
        result = summarize(trace([0.42, 0.39]))
        self.assertEqual(result["near_tie_margin_lt_0_1"], 1)
        self.assertEqual(result["top_marginal_lt_0_5"], 1)
        self.assertEqual(result["hard_assignments"], "NOT_OBSERVED")

    def test_clear_margin_is_not_identity_proof(self):
        result = summarize(trace([0.9, 0.05]))
        self.assertEqual(result["near_tie_margin_lt_0_1"], 0)
        self.assertEqual(result["oracle_identity"], "NOT_MEASURED")

    def test_new_track_without_prior_marginal(self):
        result = summarize(trace([]))
        self.assertEqual(result["candidate_observations_with_existing_tracks"], 0)
        self.assertIsNone(result["mean_top_existing_track_marginal"])

    def test_reject_nonfinite_marginal(self):
        with self.assertRaises(ValueError):
            summarize(trace([float("nan")]))

    def test_reject_negative_marginal(self):
        with self.assertRaises(ValueError):
            summarize(trace([-0.1]))

    def test_reject_duplicate_track_id(self):
        row = {"schema": "odas_sst_raw_v1", "ssl_candidates": [
            {"birth_posterior": 0.25, "track_posteriors": [
                {"track_id": 7, "posterior": 0.6},
                {"track_id": 7, "posterior": 0.3}]}]}
        with self.assertRaisesRegex(ValueError, "repeated track_id"):
            summarize(io.StringIO(json.dumps(row) + "\n"))

    def test_reject_boolean_track_id(self):
        row = {"schema": "odas_sst_raw_v1", "ssl_candidates": [
            {"birth_posterior": 0.25, "track_posteriors": [{"track_id": True, "posterior": 0.6}]}]}
        with self.assertRaisesRegex(ValueError, "invalid or repeated track_id"):
            summarize(io.StringIO(json.dumps(row) + "\n"))

    def test_birth_vs_track_posterior_competition(self):
        row = {"schema": "odas_sst_raw_v1", "ssl_candidates": [
            {"birth_posterior": 0.02, "track_posteriors": [
                {"track_id": 9, "posterior": 0.8}]},
            {"birth_posterior": 0.7, "track_posteriors": [
                {"track_id": 9, "posterior": 0.2}]},
            {"birth_posterior": 0.4, "track_posteriors": [
                {"track_id": 9, "posterior": 0.4}]},
            {"birth_posterior": 0.9, "track_posteriors": []}]}
        result = summarize(io.StringIO(json.dumps(row) + "\n"))
        self.assertEqual(result["birth_posterior_observations"], 4)
        self.assertEqual(result["birth_vs_existing_track_comparable"], 3)
        self.assertEqual(result["birth_below_top_existing_track_marginal"], 1)
        self.assertEqual(result["birth_above_top_existing_track_marginal"], 1)
        self.assertEqual(result["birth_vs_track_ties"], 1)
        self.assertAlmostEqual(result["mean_birth_posterior"], 0.505)

    def test_reject_invalid_birth_posterior(self):
        for value in (-0.01, 1.1, float("nan"), True, "0.4"):
            row = {"schema": "odas_sst_raw_v1", "ssl_candidates": [
                {"birth_posterior": value, "track_posteriors": []}]}
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "birth_posterior"):
                summarize(io.StringIO(json.dumps(row) + "\n"))

    def test_missing_birth_evidence_fails_closed(self):
        row = {"schema": "odas_sst_raw_v1",
               "ssl_candidates": [{"track_posteriors": []}]}
        with self.assertRaisesRegex(ValueError, "missing native birth_posterior"):
            summarize(io.StringIO(json.dumps(row) + "\n"))

    def test_duplicate_birth_key_fails_closed(self):
        raw = ('{"schema":"odas_sst_raw_v1","ssl_candidates":['
               '{"birth_posterior":0.1,"birth_posterior":0.9,'
               '"track_posteriors":[]}]}\n')
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            summarize(io.StringIO(raw))

    def test_nonfinite_json_constant_fails_closed(self):
        raw = ('{"schema":"odas_sst_raw_v1","ssl_candidates":['
               '{"birth_posterior":Infinity,"track_posteriors":[]}]}\n')
        with self.assertRaisesRegex(ValueError, "nonfinite JSON constant"):
            summarize(io.StringIO(raw))

    def test_reject_empty_trace(self):
        with self.assertRaises(ValueError):
            summarize(io.StringIO(""))


if __name__ == "__main__":
    unittest.main()
