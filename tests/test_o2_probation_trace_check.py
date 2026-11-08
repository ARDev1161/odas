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

    def test_reject_empty(self):
        self.check([], False)


if __name__ == "__main__":
    unittest.main()
