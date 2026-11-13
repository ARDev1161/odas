"""Regression contracts for paired real-trace A/B capacity (not identity)."""
import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from o2_paired_capacity_ab import compare


class PairedCapacityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.oracle = self.root / "oracle.json"
        self.oracle.write_text(json.dumps({
            "sample_rate_hz": 16000,
            "ground_truth": [
                {"hop": 0, "t_s": .004, "sources": [{"id": "a"}, {"id": "b"}]},
                {"hop": 1, "t_s": .012, "sources": [{"id": "a"}, {"id": "b"}]}
            ]
        }))
        self.paths = {}
        for name, counts in (("upstream", [2, 2]), ("dev", [1, 1]), ("feature", [1, 2])):
            path = self.root / (name + ".jsonl")
            rows = []
            for i, count in enumerate(counts):
                rows.append({"hop_index": i, "hop_frames": 128, "sample_offset": i * 128,
                             "active_tracks_after": count,
                             "tracks_after": [{"track_id": j + 1} for j in range(count)]})
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            self.paths[name] = path
        self.wav = self.root / "frozen.wav"
        self.wav.write_bytes(b"RIFF frozen fixture bytes")
        self.hashes = {name: hashlib.sha256(self.wav.read_bytes()).hexdigest() for name in self.paths}
        self.wav_paths = {name: self.wav for name in self.paths}

    def test_real_capacity_differences_are_not_idf1(self):
        report = compare(self.oracle, self.paths, self.hashes, self.wav_paths)
        self.assertEqual(report["status"], "CAPACITY_ONLY_NOT_QUALITY_PASS")
        self.assertEqual(report["idf1"], "NOT_MEASURED")
        self.assertEqual([report["variants"][name]["multi_track_overlap_hops"]
                          for name in ("upstream", "dev", "feature")], [2, 0, 1])
        self.assertEqual([report["variants"][name]["missing_source_hops_lower_bound"]
                          for name in ("upstream", "dev", "feature")], [0, 2, 1])

    def test_verify_real_wav_bytes(self):
        wav = self.root / "frozen.wav"
        wav.write_bytes(b"RIFF frozen fixture bytes")
        digest = hashlib.sha256(wav.read_bytes()).hexdigest()
        hashes = {name: digest for name in self.paths}
        paths = {name: wav for name in self.paths}
        self.assertEqual(compare(self.oracle, self.paths, hashes, paths)["wav_sha256"], digest)
        wav.write_bytes(wav.read_bytes() + b"tampered")
        with self.assertRaisesRegex(ValueError, "actual WAV bytes"):
            compare(self.oracle, self.paths, hashes, paths)

    def test_reject_missing_real_wav_path(self):
        with self.assertRaisesRegex(ValueError, "real WAV path"):
            compare(self.oracle, self.paths, self.hashes, {"upstream": self.oracle})

    def test_reject_mismatched_wav(self):
        self.hashes["dev"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            compare(self.oracle, self.paths, self.hashes, self.wav_paths)

    def test_reject_missing_variant(self):
        with self.assertRaisesRegex(ValueError, "require upstream"):
            compare(self.oracle, {"dev": self.paths["dev"]}, self.hashes, self.wav_paths)

    def test_reject_invalid_clock(self):
        path = self.paths["feature"]
        lines = path.read_text().splitlines()
        row = json.loads(lines[1])
        row["sample_offset"] = 0
        path.write_text(lines[0] + "\n" + json.dumps(row) + "\n")
        with self.assertRaisesRegex(ValueError, "sample offset"):
            compare(self.oracle, self.paths, self.hashes, self.wav_paths)


if __name__ == "__main__":
    unittest.main()
