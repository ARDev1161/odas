"""Native JSONL cross-hop contract tests; no acoustic quality claims."""
import io
import json
import unittest

from tools.o2_native_crosshop import inspect
from tools.validate_sst_raw_trace import TraceError


def hop(i, ids=(), births=(), retirements=()):
    return {
        "schema": "odas_sst_raw_v1", "odas_timestamp": i + 1,
        "hop_index": i, "sample_offset": 128 * i, "hop_frames": 128,
        "theta_new": 0.15, "ssl_candidates": [],
        "births": list(births), "retirements": list(retirements),
        "tracks_after": [{"slot": j, "track_id": tid, "state": "P",
                          "activity": 0.0} for j, tid in enumerate(ids)],
        "active_tracks_after": len(ids),
    }


def stream(*records):
    return io.StringIO("".join(json.dumps(x) + "\n" for x in records))


class CrossHopTests(unittest.TestCase):
    def test_valid_birth_and_retirement(self):
        report = inspect(stream(hop(0), hop(1, [2], [2]), hop(2, [], [], [2])))
        self.assertEqual(report["validated_hops"], 3)
        self.assertEqual(report["event_snapshot_consistency"], "PASS")

    def test_first_snapshot_can_have_existing_tracks(self):
        self.assertEqual(inspect(stream(hop(0, [3]), hop(1, [3])))["validated_hops"], 2)

    def test_active_to_provisional_without_birth_rejected(self):
        first = hop(0, [2])
        first["tracks_after"][0]["state"] = "A"
        with self.assertRaisesRegex(TraceError, "active-to-provisional"):
            inspect(stream(first, hop(1, [2])))

    def test_provisional_to_active_allowed(self):
        second = hop(1, [2])
        second["tracks_after"][0]["state"] = "A"
        result = inspect(stream(hop(0, [2]), second))
        self.assertEqual(result["event_snapshot_consistency"], "PASS")

    def test_retirement_then_rebirth_resets_state(self):
        first = hop(0, [2])
        first["tracks_after"][0]["state"] = "A"
        result = inspect(stream(first, hop(1, [], [], [2]),
                                hop(2, [2], [2])))
        self.assertEqual(result["event_snapshot_consistency"], "PASS")

    def test_missing_birth_rejected(self):
        with self.assertRaisesRegex(TraceError, "snapshot/event mismatch"):
            inspect(stream(hop(0), hop(1, [2])))

    def test_missing_retirement_rejected(self):
        with self.assertRaisesRegex(TraceError, "snapshot/event mismatch"):
            inspect(stream(hop(0, [2]), hop(1)))

    def test_birth_on_live_id_rejected(self):
        with self.assertRaisesRegex(TraceError, "already-live"):
            inspect(stream(hop(0, [2]), hop(1, [2], [2])))

    def test_retire_unknown_rejected(self):
        with self.assertRaisesRegex(TraceError, "unknown"):
            inspect(stream(hop(0), hop(1, [], [], [2])))

    def test_simultaneous_event_rejected(self):
        with self.assertRaisesRegex(TraceError, "same-hop"):
            inspect(stream(hop(0), hop(1, [], [2], [2])))

    def test_noncontiguous_hop_rejected(self):
        with self.assertRaises(TraceError):
            inspect(stream(hop(0), hop(2)))

    def test_duplicate_json_key_rejected(self):
        line = json.dumps(hop(0)).replace('"hop_frames": 128,',
                                           '"hop_frames": 128, "hop_frames": 128,')
        with self.assertRaises(TraceError):
            inspect(io.StringIO(line + "\n"))

    def test_empty_rejected(self):
        with self.assertRaises(TraceError):
            inspect(io.StringIO(""))


if __name__ == "__main__":
    unittest.main()
