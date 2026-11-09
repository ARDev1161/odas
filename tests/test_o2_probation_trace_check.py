"""Contract tests for offline native probation evidence (not acoustic tests)."""
import json
import tempfile
import unittest
from pathlib import Path
from tools.o2_probation_trace_check import InvalidTrace, audit


def record(hop=0, count=0, mean=None):
    return {"schema": "odas_sst_raw_v1", "hop_index": hop,
            "sample_offset": 128 * hop, "hop_frames": 128, "odas_timestamp": hop + 1,
            "tracks_after": [{"track_id": 1, "slot": 0, "state": "P",
                              "probation_observations": count,
                              "probation_mean_activity": mean}]}


class ProbationTraceTest(unittest.TestCase):
    def check(self, rows, valid):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.jsonl"
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            if valid:
                return audit(path)
            with self.assertRaises(InvalidTrace):
                audit(path)

    def test_zero_observations(self):
        self.assertEqual(self.check([record()], True)["provisional_observations"], 1)

    def test_real_observation_counter(self):
        self.check([record(0), record(1, 1, 0.6), record(2, 2, 0.7)], True)

    def test_reject_nonfinite_mean(self):
        self.check([record(0, 1, float("nan"))], False)

    def test_reject_boolean_counter(self):
        self.check([record(0, True, 0.5)], False)

    def test_reject_missing_counter(self):
        row = record()
        del row["tracks_after"][0]["probation_observations"]
        self.check([row], False)

    def test_reject_zero_counter_with_mean(self):
        self.check([record(0, 0, 0.0)], False)

    def test_reject_out_of_range_mean(self):
        self.check([record(0, 1, 1.1)], False)

    def test_reject_noncontiguous_clock(self):
        self.check([record(0), record(2)], False)

    def test_reject_duplicate_id(self):
        row = record()
        row["tracks_after"].append(dict(row["tracks_after"][0]))
        self.check([row], False)

    def test_reject_missing_native_timestamp(self):
        row = record()
        del row["odas_timestamp"]
        self.check([row], False)

    def test_reject_incorrect_native_timestamp(self):
        row = record()
        row["odas_timestamp"] = 3
        self.check([row], False)

    def test_reject_boolean_sample_clock(self):
        row = record()
        row["sample_offset"] = False
        self.check([row], False)

    def test_reject_duplicate_slot(self):
        row = record()
        other = dict(row["tracks_after"][0])
        other["track_id"] = 2
        row["tracks_after"].append(other)
        self.check([row], False)

    def test_accept_distinct_slots(self):
        row = record()
        other = dict(row["tracks_after"][0])
        other["track_id"] = 2
        other["slot"] = 1
        row["tracks_after"].append(other)
        self.check([row], True)

    def test_reject_live_probation_counter_regression(self):
        self.check([record(0, 2, 0.5), record(1, 1, 0.5)], False)

    def test_accept_monotonic_probation_counter(self):
        self.check([record(0, 1, 0.5), record(1, 1, 0.5),
                    record(2, 2, 0.6)], True)

    def test_accept_reused_id_after_absent_hop(self):
        empty = record(1)
        empty["tracks_after"] = []
        self.check([record(0, 3, 0.6), empty, record(2, 1, 0.4)], True)

    def check_raw(self, text, valid):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.jsonl"
            path.write_text(text)
            if valid:
                return audit(path)
            with self.assertRaises(InvalidTrace):
                audit(path)

    def test_reject_duplicate_top_level_clock(self):
        raw = json.dumps(record())
        self.check_raw(raw.replace('"hop_index": 0', '"hop_index": 0, "hop_index": 1') + "\n", False)

    def test_reject_duplicate_nested_probation_count(self):
        raw = json.dumps(record(0, 1, 0.5))
        self.check_raw(raw.replace('"probation_observations": 1',
                                   '"probation_observations": 1, "probation_observations": 0') + "\n", False)

    def test_reject_nonstandard_nan_even_in_unused_field(self):
        raw = json.dumps(record()).replace('"schema":', '"unused": NaN, "schema":')
        self.check_raw(raw + "\n", False)

    def test_reject_nonstandard_infinity(self):
        raw = json.dumps(record()).replace('"schema":', '"unused": Infinity, "schema":')
        self.check_raw(raw + "\n", False)

    def test_reject_empty(self):
        self.check([], False)


if __name__ == "__main__":
    unittest.main()
