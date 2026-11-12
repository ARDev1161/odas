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

    def test_rejects_missing_native_hop(self):
        oracle, trace = self.fixtures()
        trace[1]["hop_index"] = 5
        with self.assertRaises(ValueError):
            audit(oracle, trace)


if __name__ == "__main__":
    unittest.main()
