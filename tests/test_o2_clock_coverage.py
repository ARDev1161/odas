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
        self.assertEqual(report["status"], "SYNTHETIC_EXCITATION")
        self.assertFalse(report["real_speech_quality_eligible"])
        self.assertEqual(report["wer"], "NOT_MEASURED")

    def test_recorded_speech_provenance_does_not_imply_quality_pass(self):
        oracle, trace = self.fixtures()
        oracle["speech_recordings_supplied"] = True
        report = audit(oracle, trace)["speech_provenance"]
        self.assertEqual(report["status"], "RECORDED_SPEECH")
        self.assertTrue(report["real_speech_quality_eligible"])
        self.assertEqual(report["sss_quality"], "NOT_MEASURED")

    def test_missing_provenance_is_unknown(self):
        report = audit(*self.fixtures())["speech_provenance"]
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertFalse(report["real_speech_quality_eligible"])

    def test_recorded_segments_contradict_synthetic_flag(self):
        oracle, trace = self.fixtures()
        oracle["speech_recordings_supplied"] = False
        schedule = {"sample_rate_hz": 16000, "segments": [
            {"source_id": "speaker_1", "clean_source_sha256": "a" * 64}]}
        result = audit(oracle, trace, schedule=schedule)["speech_provenance"]
        self.assertEqual(result["status"], "CONFLICTING_EVIDENCE")
        self.assertEqual(result["schedule_status"], "RECORDED_SEGMENTS_CONTRADICT_ORACLE")
        self.assertFalse(result["real_speech_quality_eligible"])

    def test_schedule_sample_rate_mismatch_rejected(self):
        oracle, trace = self.fixtures()
        with self.assertRaises(ValueError):
            audit(oracle, trace, schedule={"sample_rate_hz": 8000, "segments": []})

    def test_schedule_without_segments_rejected(self):
        oracle, trace = self.fixtures()
        with self.assertRaises(ValueError):
            audit(oracle, trace, schedule={"sample_rate_hz": 16000})

    def test_rejects_missing_native_hop(self):
        oracle, trace = self.fixtures()
        trace[1]["hop_index"] = 5
        with self.assertRaises(ValueError):
            audit(oracle, trace)


if __name__ == "__main__":
    unittest.main()
