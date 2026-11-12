import unittest

from tools.o2_clock_coverage import audit


class ClockCoverageTests(unittest.TestCase):
    def fixtures(self, oracle_count=2, native_count=3):
        oracle = {"sample_rate_hz": 16000, "ground_truth": [
            {"hop": i, "t_s": (i + 0.5) * 128 / 16000}
            for i in range(oracle_count)
        ]}
        trace = [{"hop_index": i, "sample_offset": i * 128, "hop_frames": 128}
                 for i in range(native_count)]
        return oracle, trace

    def test_rejects_nonfinite_oracle_time(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            oracle, trace = self.fixtures()
            oracle["ground_truth"][0]["t_s"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "oracle hop-center clock"):
                audit(oracle, trace)

    def test_rejects_boolean_native_hop_and_index(self):
        for field, value in (("hop_frames", True), ("hop_index", False), ("sample_offset", False)):
            oracle, trace = self.fixtures()
            trace[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit(oracle, trace)

    def test_rejects_boolean_oracle_hop_and_time(self):
        for field, value in (("hop", False), ("t_s", True)):
            oracle, trace = self.fixtures()
            oracle["ground_truth"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit(oracle, trace)

    def test_tail_is_explicitly_unscored(self):
        result = audit(*self.fixtures())
        self.assertEqual(result["status"], "PARTIAL_CLOCK_ONLY")
        self.assertEqual(result["unscored_native_tail_hops"], 1)
        self.assertEqual(result["idf1"], "NOT_MEASURED")

    def test_exact_coverage(self):
        result = audit(*self.fixtures(3, 3))
        self.assertEqual(result["unscored_native_tail_hops"], 0)

    def test_rejects_oracle_longer_than_trace(self):
        with self.assertRaises(ValueError):
            audit(*self.fixtures(4, 3))

    def test_rejects_shifted_native_sample_clock(self):
        oracle, trace = self.fixtures()
        trace[1]["sample_offset"] += 128
        with self.assertRaises(ValueError):
            audit(oracle, trace)

    def test_rejects_shifted_oracle_time(self):
        oracle, trace = self.fixtures()
        oracle["ground_truth"][0]["t_s"] += 0.008
        with self.assertRaises(ValueError):
            audit(oracle, trace)

    def test_tail_occupancy_is_not_false_track_metric(self):
        oracle, trace = self.fixtures(2, 5)
        for rec, n in zip(trace, [0, 1, 2, 1, 0]):
            rec["active_tracks_after"] = n
        result = audit(oracle, trace)
        tail = result["tail_track_occupancy"]
        self.assertEqual(tail["status"], "MEASURED_UNLABELED")
        self.assertEqual(tail["evaluated_hops"], 3)
        self.assertEqual(tail["occupied_hops"], 2)
        self.assertEqual(tail["track_hops"], 3)
        self.assertEqual(tail["max_simultaneous_tracks"], 2)
        self.assertEqual(tail["false_tracks"], "NOT_MEASURED")

    def test_incomplete_tail_occupancy_fails_closed(self):
        oracle, trace = self.fixtures(2, 4)
        trace[2]["active_tracks_after"] = 1
        with self.assertRaises(ValueError):
            audit(oracle, trace)

    def test_rejects_boolean_tail_occupancy(self):
        oracle, trace = self.fixtures()
        trace[-1]["active_tracks_after"] = True
        with self.assertRaises(ValueError):
            audit(oracle, trace)

    def test_cli_sample_rate_cannot_follow_wrong_oracle(self):
        oracle, trace = self.fixtures()
        oracle["sample_rate_hz"] = 8000
        with self.assertRaises(ValueError):
            audit(oracle, trace)

    def test_synthetic_excitation_not_real_speech(self):
        oracle, trace = self.fixtures()
        oracle["speech_recordings_supplied"] = False
        report = audit(oracle, trace)["speech_provenance"]
        self.assertEqual(report["status"], "EXTERNAL_RECORDINGS_NOT_SUPPLIED")
        self.assertFalse(report["real_speech_quality_eligible"])
        self.assertEqual(report["wer"], "NOT_MEASURED")

    def test_recorded_speech_provenance_does_not_imply_quality_pass(self):
        oracle, trace = self.fixtures()
        oracle["speech_recordings_supplied"] = True
        report = audit(oracle, trace)["speech_provenance"]
        self.assertEqual(report["status"], "EXTERNAL_RECORDINGS_DECLARED")
        self.assertFalse(report["real_speech_quality_eligible"])
        self.assertEqual(report["sss_quality"], "NOT_MEASURED")

    def test_missing_provenance_is_unknown(self):
        report = audit(*self.fixtures())["speech_provenance"]
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertFalse(report["real_speech_quality_eligible"])

    def test_corpus_schedule_does_not_conflict_with_external_flag(self):
        oracle, trace = self.fixtures()
        oracle["speech_recordings_supplied"] = False
        schedule = {"sample_rate_hz": 16000, "segments": [
            {"source_id": "speaker_1", "clean_source_sha256": "a" * 64, "scheduled_start_frame": 0, "placed_end_frame": 128, "scheduled_end_frame": 128, "original_utterance_frames": 128}]}
        result = audit(oracle, trace, schedule=schedule)["speech_provenance"]
        self.assertEqual(result["status"], "CORPUS_SEGMENTS_DECLARED")
        self.assertEqual(result["schedule_status"], "CORPUS_SEGMENTS_DECLARED")
        self.assertFalse(result["real_speech_quality_eligible"])

    def test_schedule_does_not_prove_rendered_audio_identity(self):
        oracle, trace = self.fixtures()
        oracle["speech_recordings_supplied"] = True
        schedule = {"sample_rate_hz": 16000, "segments": [
            {"source_id": "speaker_1", "clean_source_sha256": "a" * 64, "scheduled_start_frame": 0, "placed_end_frame": 128, "scheduled_end_frame": 128, "original_utterance_frames": 128}]}
        result = audit(oracle, trace, schedule=schedule)["speech_provenance"]
        self.assertEqual(result["status"], "CORPUS_SEGMENTS_DECLARED")
        self.assertFalse(result["real_speech_quality_eligible"])
        self.assertEqual(result["sss_quality"], "NOT_MEASURED")

    def test_schedule_sample_rate_mismatch_rejected(self):
        oracle, trace = self.fixtures()
        with self.assertRaises(ValueError):
            audit(oracle, trace, schedule={"sample_rate_hz": 8000, "segments": []})

    def test_schedule_without_segments_rejected(self):
        oracle, trace = self.fixtures()
        with self.assertRaises(ValueError):
            audit(oracle, trace, schedule={"sample_rate_hz": 16000})


    def test_rejects_segment_outside_oracle_scene(self):
        oracle, trace = self.fixtures()
        segment = {"source_id": "speaker_1", "clean_source_sha256": "a" * 64,
                   "scheduled_start_frame": 0, "placed_end_frame": 128,
                   "scheduled_end_frame": 300, "original_utterance_frames": 128}
        with self.assertRaisesRegex(ValueError, "outside oracle"):
            audit(oracle, trace, schedule={"sample_rate_hz": 16000, "segments": [segment]})

    def test_rejects_truncated_original_utterance(self):
        oracle, trace = self.fixtures()
        segment = {"source_id": "speaker_1", "clean_source_sha256": "a" * 64,
                   "scheduled_start_frame": 0, "placed_end_frame": 128,
                   "scheduled_end_frame": 128, "original_utterance_frames": 64}
        with self.assertRaisesRegex(ValueError, "original utterance"):
            audit(oracle, trace, schedule={"sample_rate_hz": 16000, "segments": [segment]})

    def test_rejects_invalid_corpus_sha(self):
        oracle, trace = self.fixtures()
        segment = {"source_id": "speaker_1", "clean_source_sha256": "not-a-digest",
                   "scheduled_start_frame": 0, "placed_end_frame": 128,
                   "scheduled_end_frame": 128, "original_utterance_frames": 128}
        with self.assertRaisesRegex(ValueError, "SHA256"):
            audit(oracle, trace, schedule={"sample_rate_hz": 16000, "segments": [segment]})

    def test_overlap_capacity_ceiling_is_not_speaker_matching(self):
        oracle, trace = self.fixtures(4, 4)
        for i, row in enumerate(oracle["ground_truth"]):
            row["sources"] = [{"id": "a"}, {"id": "b"}] if i in (1, 2, 3) else []
        for rec, n in zip(trace, (0, 1, 2, 0)):
            rec["active_tracks_after"] = n
        result = audit(oracle, trace)["overlap_capacity_upper_bound"]
        self.assertEqual(result["status"], "MEASURED_CAPACITY_ONLY")
        self.assertEqual(result["oracle_overlap_hops"], 3)
        self.assertEqual(result["native_multi_track_hops_during_overlap"], 1)
        self.assertEqual(result["capacity_deficit_hops"], 2)
        self.assertAlmostEqual(result["max_possible_two_source_recall"], 1 / 3)
        self.assertEqual(result["speaker_matches"], "NOT_MEASURED")

    def test_source_hop_capacity_counts_partial_single_track_coverage(self):
        oracle, trace = self.fixtures(3, 3)
        oracle["ground_truth"][0]["sources"] = [{"id": "a"}, {"id": "b"}]
        oracle["ground_truth"][1]["sources"] = [{"id": "a"}, {"id": "b"}]
        oracle["ground_truth"][2]["sources"] = [{"id": "a"}]
        for rec, n in zip(trace, (1, 2, 0)):
            rec["active_tracks_after"] = n
        result = audit(oracle, trace)["overlap_capacity_upper_bound"]
        self.assertEqual(result["oracle_source_hops"], 5)
        self.assertEqual(result["max_matchable_source_hops"], 3)
        self.assertAlmostEqual(result["max_possible_source_hop_recall"], 0.6)
        self.assertEqual(result["native_multi_track_hops_during_overlap"], 1)
        self.assertEqual(result["speaker_matches"], "NOT_MEASURED")

    def test_zero_source_hops_has_no_source_recall(self):
        oracle, trace = self.fixtures(2, 2)
        for row in oracle["ground_truth"]:
            row["sources"] = []
        for rec in trace:
            rec["active_tracks_after"] = 1
        result = audit(oracle, trace)["overlap_capacity_upper_bound"]
        self.assertEqual(result["oracle_source_hops"], 0)
        self.assertEqual(result["max_matchable_source_hops"], 0)
        self.assertEqual(result["max_possible_source_hop_recall"], "NOT_APPLICABLE")

    def test_overlap_capacity_requires_complete_scene_occupancy(self):
        oracle, trace = self.fixtures(2, 2)
        for row in oracle["ground_truth"]:
            row["sources"] = [{"id": "a"}, {"id": "b"}]
        trace[0]["active_tracks_after"] = 1
        with self.assertRaisesRegex(ValueError, "scene occupancy"):
            audit(oracle, trace)

    def test_overlap_capacity_not_available_without_oracle_sources(self):
        result = audit(*self.fixtures())["overlap_capacity_upper_bound"]
        self.assertEqual(result["status"], "NOT_AVAILABLE")
        self.assertEqual(result["speaker_matches"], "NOT_MEASURED")

    def test_no_overlap_has_no_invented_recall(self):
        oracle, trace = self.fixtures(2, 2)
        for row in oracle["ground_truth"]:
            row["sources"] = []
        for rec in trace:
            rec["active_tracks_after"] = 0
        result = audit(oracle, trace)["overlap_capacity_upper_bound"]
        self.assertEqual(result["status"], "MEASURED_CAPACITY_ONLY")
        self.assertEqual(result["max_possible_two_source_recall"], "NOT_APPLICABLE")

    def test_rejects_missing_native_hop(self):
        oracle, trace = self.fixtures()
        trace[1]["hop_index"] = 5
        with self.assertRaises(ValueError):
            audit(oracle, trace)


    def test_rejects_duplicate_oracle_source_ids(self):
        oracle, trace = self.fixtures(2, 2)
        oracle["ground_truth"][0]["sources"] = [{"id": "speaker_1"}, {"id": "speaker_1"}]
        oracle["ground_truth"][1]["sources"] = []
        with self.assertRaisesRegex(ValueError, "duplicate oracle source identity"):
            audit(oracle, trace)

    def test_rejects_malformed_oracle_source_identity(self):
        oracle, trace = self.fixtures(2, 2)
        oracle["ground_truth"][0]["sources"] = [{"id": ""}]
        oracle["ground_truth"][1]["sources"] = []
        with self.assertRaisesRegex(ValueError, "invalid oracle source identity"):
            audit(oracle, trace)

    def test_rejects_partial_oracle_source_annotations(self):
        oracle, trace = self.fixtures(2, 2)
        oracle["ground_truth"][0]["sources"] = [{"id": "speaker_1"}]
        with self.assertRaisesRegex(ValueError, "incomplete oracle source annotations"):
            audit(oracle, trace)

    def test_distinct_source_ids_are_accepted(self):
        oracle, trace = self.fixtures(2, 2)
        oracle["ground_truth"][0]["sources"] = [{"id": "speaker_1"}, {"id": "speaker_2"}]
        oracle["ground_truth"][1]["sources"] = []
        for rec in trace:
            rec["active_tracks_after"] = 2
        self.assertEqual(audit(oracle, trace)["overlap_capacity_upper_bound"]["oracle_source_hops"], 2)

    def test_oracle_silent_occupancy_is_not_false_track_metric(self):
        oracle, trace = self.fixtures(4, 4)
        for row, sources in zip(oracle["ground_truth"], [[], [{"id": "a"}], [], []]):
            row["sources"] = sources
        for rec, count in zip(trace, [2, 1, 0, 3]):
            rec["active_tracks_after"] = count
        result = audit(oracle, trace)["oracle_silent_track_occupancy"]
        self.assertEqual(result["status"], "MEASURED_OCCUPANCY_ONLY")
        self.assertEqual(result["oracle_silent_hops"], 3)
        self.assertEqual(result["occupied_silent_hops"], 2)
        self.assertEqual(result["silent_track_hops"], 5)
        self.assertEqual(result["max_silent_tracks"], 3)
        self.assertEqual(result["false_tracks"], "NOT_MEASURED")

    def test_silent_occupancy_not_inferred_from_missing_track_counts(self):
        oracle, trace = self.fixtures(2, 2)
        for row in oracle["ground_truth"]:
            row["sources"] = []
        result = audit(oracle, trace)["oracle_silent_track_occupancy"]
        self.assertEqual(result["status"], "NOT_AVAILABLE")
        self.assertEqual(result["occupied_silent_hops"], "NOT_MEASURED")

    def test_silent_occupancy_not_inferred_without_oracle_annotations(self):
        result = audit(*self.fixtures())["oracle_silent_track_occupancy"]
        self.assertEqual(result["status"], "NOT_AVAILABLE")
        self.assertEqual(result["false_tracks"], "NOT_MEASURED")


    def test_source_capacity_deficit_run_and_missing_source_hops(self):
        oracle, trace = self.fixtures(5, 5)
        for row, sources in zip(oracle["ground_truth"],
                                [[{"id": "a"}, {"id": "b"}],
                                 [{"id": "a"}, {"id": "b"}],
                                 [{"id": "a"}], [], [{"id": "a"}, {"id": "b"}]]):
            row["sources"] = sources
        for rec, count in zip(trace, [1, 0, 0, 0, 2]):
            rec["active_tracks_after"] = count
        report = audit(oracle, trace)["source_capacity_deficit"]
        self.assertEqual(report["status"], "MEASURED_CAPACITY_ONLY")
        self.assertEqual(report["hops_with_insufficient_capacity"], 3)
        self.assertEqual(report["longest_capacity_deficit_run_hops"], 3)
        self.assertEqual(report["total_missing_source_hops_lower_bound"], 4)

    def test_capacity_deficit_intervals_are_half_open_and_scored(self):
        oracle, trace = self.fixtures(6, 6)
        counts = [1, 0, 2, 0, 1, 0]
        sources = [[{"id": "a"}, {"id": "b"}],
                   [{"id": "a"}], [{"id": "a"}, {"id": "b"}],
                   [], [{"id": "a"}, {"id": "b"}], [{"id": "a"}]]
        for row, src in zip(oracle["ground_truth"], sources):
            row["sources"] = src
        for rec, count in zip(trace, counts):
            rec["active_tracks_after"] = count
        result = audit(oracle, trace)["source_capacity_deficit"]
        self.assertEqual(result["capacity_deficit_intervals"], [
            {"start_hop": 0, "end_hop": 2, "missing_source_hops_lower_bound": 2},
            {"start_hop": 4, "end_hop": 6, "missing_source_hops_lower_bound": 2}])
        self.assertEqual(result["longest_capacity_deficit_run_s"], 2 * 128 / 16000)

    def test_capacity_deficit_intervals_empty_when_fully_covered(self):
        oracle, trace = self.fixtures(2, 2)
        for row in oracle["ground_truth"]:
            row["sources"] = [{"id": "a"}]
        for rec in trace:
            rec["active_tracks_after"] = 1
        result = audit(oracle, trace)["source_capacity_deficit"]
        self.assertEqual(result["capacity_deficit_intervals"], [])
        self.assertEqual(result["longest_capacity_deficit_run_s"], 0)

    def test_source_capacity_deficit_without_oracle_is_not_measured(self):
        report = audit(*self.fixtures())["source_capacity_deficit"]
        self.assertEqual(report["status"], "NOT_AVAILABLE")
        self.assertEqual(report["longest_capacity_deficit_run_hops"], "NOT_MEASURED")

    def test_source_capacity_deficit_all_tracks_present(self):
        oracle, trace = self.fixtures(2, 2)
        for row in oracle["ground_truth"]:
            row["sources"] = [{"id": "a"}]
        for rec in trace:
            rec["active_tracks_after"] = 2
        report = audit(oracle, trace)["source_capacity_deficit"]
        self.assertEqual(report["longest_capacity_deficit_run_hops"], 0)
        self.assertEqual(report["total_missing_source_hops_lower_bound"], 0)


if __name__ == "__main__":
    unittest.main()
