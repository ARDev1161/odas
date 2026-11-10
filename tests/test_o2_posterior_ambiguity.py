"""Independent contracts for native posterior ambiguity diagnostics."""
import io
import json
import math
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
        self.assertEqual(result["birth_posterior_ge_0_1"], 1)
        self.assertEqual(result["birth_ge_0_1_with_existing_tracks"], 0)
        self.assertEqual(result["birth_ge_0_1_without_existing_tracks"], 1)
        self.assertEqual(result["birth_ge_0_1_competing_top_ge_0_5"], 0)
        self.assertEqual(result["birth_ge_0_1_competing_top_lt_0_5"], 0)
        self.assertEqual(result["birth_above_top_track_and_ge_0_1"], 0)

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
        self.assertEqual(result["birth_posterior_ge_0_1"], 3)
        self.assertEqual(result["birth_ge_0_1_with_existing_tracks"], 2)
        self.assertEqual(result["birth_ge_0_1_competing_top_ge_0_5"], 0)
        self.assertEqual(result["birth_ge_0_1_competing_top_lt_0_5"], 2)
        self.assertEqual(result["birth_ge_0_1_without_existing_tracks"], 1)
        self.assertEqual(result["birth_posterior_ge_0_5"], 2)
        self.assertEqual(result["birth_above_top_track_and_ge_0_1"], 1)
        self.assertEqual(result["birth_above_top_track_and_ge_0_5"], 1)
        self.assertEqual(result["max_birth_posterior"], 0.9)

    def test_reject_invalid_birth_posterior(self):
        for value in (-0.01, 1.1, float("nan"), True, "0.4"):
            row = {"schema": "odas_sst_raw_v1", "ssl_candidates": [
                {"birth_posterior": value, "track_posteriors": []}]}
            with self.subTest(value=value), self.assertRaisesRegex(
                    ValueError, "nonfinite JSON constant" if isinstance(value, float) and math.isnan(value)
                    else "birth_posterior"):
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

    def test_high_birth_evidence_is_counted_by_hop_not_only_candidate(self):
        def hop(births):
            return json.dumps({"schema": "odas_sst_raw_v1", "ssl_candidates": [
                {"birth_posterior": birth, "track_posteriors": []}
                for birth in births]}) + "\n"
        stream = io.StringIO("".join([
            hop([0.1, 0.5, 0.01]),
            hop([0.2]),
            hop([0.09]),
            hop([0.8, 0.7]),
            hop([0.1]),
        ]))
        result = summarize(stream)
        self.assertEqual(result["birth_posterior_ge_0_1"], 6)
        self.assertEqual(result["birth_posterior_ge_0_5"], 3)
        self.assertEqual(result["hops_with_birth_posterior_ge_0_1"], 4)
        self.assertEqual(result["hops_with_birth_posterior_ge_0_5"], 2)
        self.assertEqual(result["max_birth_posterior_ge_0_1_candidates_per_hop"], 2)
        self.assertEqual(result["longest_consecutive_hops_with_birth_posterior_ge_0_1"], 2)

    def test_no_birth_evidence_has_zero_run_length(self):
        stream = io.StringIO(json.dumps({"schema": "odas_sst_raw_v1",
            "ssl_candidates": [{"birth_posterior": 0.01, "track_posteriors": []}]}) + "\n")
        result = summarize(stream)
        self.assertEqual(result["hops_with_birth_posterior_ge_0_1"], 0)
        self.assertEqual(result["longest_consecutive_hops_with_birth_posterior_ge_0_1"], 0)

    def test_five_hop_runs_are_contiguous_not_candidate_counts(self):
        def hop(births):
            return json.dumps({"schema": "odas_sst_raw_v1", "ssl_candidates": [
                {"birth_posterior": value, "track_posteriors": []}
                for value in births]}) + "\n"
        # One five-hop run, a single low-evidence break, and one four-hop run.
        rows = [hop([0.2, 0.9])] * 5 + [hop([0.01])] + [hop([0.3])] * 4
        result = summarize(io.StringIO("".join(rows)))
        self.assertEqual(result["high_birth_ge_0_1_run_count"], 2)
        self.assertEqual(result["high_birth_ge_0_1_runs_at_least_5_hops"], 1)
        self.assertEqual(result["high_birth_ge_0_1_hops_in_runs_at_least_5"], 5)
        self.assertEqual(result["longest_consecutive_hops_with_birth_posterior_ge_0_1"], 5)

    def test_no_five_hop_runs_on_disjoint_high_birth(self):
        row = lambda v: json.dumps({"schema": "odas_sst_raw_v1", "ssl_candidates": [
            {"birth_posterior": v, "track_posteriors": []}]}) + "\n"
        result = summarize(io.StringIO(row(0.9) + row(0.0) + row(0.9)))
        self.assertEqual(result["high_birth_ge_0_1_run_count"], 2)
        self.assertEqual(result["high_birth_ge_0_1_runs_at_least_5_hops"], 0)
        self.assertEqual(result["high_birth_ge_0_1_hops_in_runs_at_least_5"], 0)

    def test_hop_index_gap_breaks_apparent_five_hop_birth_run(self):
        def hop(index):
            return json.dumps({"schema": "odas_sst_raw_v1", "hop_index": index,
                "ssl_candidates": [{"birth_posterior": 0.7, "track_posteriors": []}]}) + "\n"
        result = summarize(io.StringIO("".join(hop(i) for i in [10, 11, 12, 15, 16])))
        self.assertEqual(result["hop_index_gaps"], 1)
        self.assertEqual(result["explicit_hop_index_rows"], 5)
        self.assertEqual(result["high_birth_ge_0_1_runs_at_least_5_hops"], 0)
        self.assertEqual(result["longest_consecutive_hops_with_birth_posterior_ge_0_1"], 3)

    def test_hop_index_rejects_duplicates_and_reverse_order(self):
        def hop(index):
            return json.dumps({"schema": "odas_sst_raw_v1", "hop_index": index,
                "ssl_candidates": []}) + "\n"
        for indices in ([1, 1], [2, 1]):
            with self.subTest(indices=indices), self.assertRaisesRegex(ValueError, "non-increasing hop_index"):
                summarize(io.StringIO("".join(hop(i) for i in indices)))

    def test_hop_index_rejects_mixed_indexing(self):
        indexed = {"schema": "odas_sst_raw_v1", "hop_index": 1, "ssl_candidates": []}
        unindexed = {"schema": "odas_sst_raw_v1", "ssl_candidates": []}
        for rows in ([indexed, unindexed], [unindexed, indexed]):
            with self.subTest(rows=rows), self.assertRaisesRegex(ValueError, "hop_index|mixed indexed"):
                summarize(io.StringIO("".join(json.dumps(row) + "\n" for row in rows)))

    def test_high_birth_competing_confident_track_is_not_a_birth_assignment(self):
        row = {"schema": "odas_sst_raw_v1", "ssl_candidates": [
            {"birth_posterior": 0.2, "track_posteriors": [{"track_id": 1, "posterior": 0.8}]},
            {"birth_posterior": 0.6, "track_posteriors": [{"track_id": 1, "posterior": 0.3}]},
            {"birth_posterior": 0.05, "track_posteriors": [{"track_id": 1, "posterior": 0.9}]},
            {"birth_posterior": 0.8, "track_posteriors": []}]}
        result = summarize(io.StringIO(json.dumps(row) + "\n"))
        self.assertEqual(result["birth_ge_0_1_with_existing_tracks"], 2)
        self.assertEqual(result["birth_ge_0_1_competing_top_ge_0_5"], 1)
        self.assertEqual(result["birth_ge_0_1_competing_top_lt_0_5"], 1)
        self.assertEqual(result["birth_ge_0_1_without_existing_tracks"], 1)
        self.assertEqual(result["hard_assignments"], "NOT_OBSERVED")

    def test_strong_birth_competition_cross_tab_has_wins_losses_and_ties(self):
        cases = [(0.8, 0.6), (0.2, 0.7), (0.6, 0.8),
                 (0.2, 0.3), (0.5, 0.5)]
        row = {"schema": "odas_sst_raw_v1", "ssl_candidates": [
            {"birth_posterior": birth, "track_posteriors": [
                {"track_id": 1, "posterior": top}]} for birth, top in cases]}
        result = summarize(io.StringIO(json.dumps(row) + "\n"))
        self.assertEqual(result["strong_birth_wins_confident"], 1)
        self.assertEqual(result["strong_birth_wins_weak"], 1)
        self.assertEqual(result["strong_birth_loses_confident"], 1)
        self.assertEqual(result["strong_birth_loses_weak"], 1)
        self.assertEqual(result["strong_birth_ties"], 1)
        self.assertEqual(sum(result[key] for key in (
            "strong_birth_wins_confident", "strong_birth_wins_weak",
            "strong_birth_loses_confident", "strong_birth_loses_weak",
            "strong_birth_ties")), result["birth_ge_0_1_with_existing_tracks"])
        self.assertEqual(result["hard_assignments"], "NOT_OBSERVED")

    def test_reject_empty_trace(self):
        with self.assertRaises(ValueError):
            summarize(io.StringIO(""))


if __name__ == "__main__":
    unittest.main()
