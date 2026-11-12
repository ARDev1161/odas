import hashlib
import json
import wave
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from o2_provenance_gate import verify

class ProvenanceGateTests(unittest.TestCase):
    def test_complete_evidence_and_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = {
                "sample_rate_hz": 16000, "hop_samples": 128,
                "first_sample_index": 0, "pcm_channels": [1, 2, 3, 4],
                "microphones_m": [[0.032, 0, 0], [0, 0.032, 0],
                                  [-0.032, 0, 0], [0, -0.032, 0]],
                "seed": 42, "config_sha256": "a" * 64}
            with wave.open(str(root / "wav"), "wb") as recording:
                recording.setnchannels(6)
                recording.setsampwidth(2)
                recording.setframerate(16000)
                recording.writeframes(b"\\x00" * 12 * 128)
            for key in ("wav", "oracle", "native_trace"):
                data = (root / "wav").read_bytes() if key == "wav" else key.encode()
                (root / key).write_bytes(data)
                manifest[key] = {"path": key, "sha256": hashlib.sha256(data).hexdigest()}
            self.assertEqual(verify(manifest, root)["status"], "PASS")
            (root / "wav").write_bytes(b"changed")
            self.assertEqual(verify(manifest, root)["status"], "BLOCKED")
            self.assertIn("wav: SHA256 mismatch", verify(manifest, root)["problems"])
            # Restore the original valid recording before checking metadata.
            with wave.open(str(root / "wav"), "wb") as recording:
                recording.setnchannels(6)
                recording.setsampwidth(2)
                recording.setframerate(16000)
                recording.writeframes(b"\\x00" * 12 * 128)
            manifest["wav"]["sha256"] = hashlib.sha256((root / "wav").read_bytes()).hexdigest()
            manifest["sample_rate_hz"] = 48000
            self.assertIn("wav: sample rate differs from manifest", verify(manifest, root)["problems"])
            manifest["sample_rate_hz"] = 16000
            manifest["first_sample_index"] = None
            self.assertEqual(verify(manifest, root)["status"], "BLOCKED")
            manifest["first_sample_index"] = 0
            manifest["pcm_channels"] = [0, 1, 2, 7]
            self.assertIn("wav: microphone channel index exceeds WAV channels", verify(manifest, root)["problems"])
            manifest["pcm_channels"] = [0, 1, 2, 3]
            self.assertEqual(verify(manifest, root)["status"], "BLOCKED")
            manifest["pcm_channels"] = [1, 2, 3, 4]
            manifest["wav"]["path"] = "../outside.wav"
            escaped = verify(manifest, root)
            self.assertIn("wav: path escapes evidence root", escaped["problems"])
            self.assertFalse(escaped["verified_file_hashes"])
            manifest["wav"]["path"] = "wav"
            self.assertTrue(verify(manifest, root)["verified_file_hashes"])
            (root / "oracle").unlink()
            self.assertFalse(verify(manifest, root)["verified_file_hashes"])

    def test_malformed_manifest_and_blank_paths_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for malformed in (None, [], "text", 42, True):
                with self.subTest(manifest=malformed):
                    result = verify(malformed, root)
                    self.assertEqual(result["status"], "BLOCKED")
                    self.assertFalse(result["verified_file_hashes"])
                    self.assertIn("manifest: expected JSON object", result["problems"])
            for blank in ("", " ", "\t", "\n", "\r"):
                with self.subTest(path=blank):
                    result = verify({"wav": {"path": blank, "sha256": "a" * 64}}, root)
                    self.assertEqual(result["status"], "BLOCKED")
                    self.assertFalse(result["verified_file_hashes"])
                    self.assertIn("wav: missing file path", result["problems"])

    def test_empty_manifest_never_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            result = verify({}, Path(directory))
            self.assertEqual(result["status"], "BLOCKED")
            self.assertTrue(result["problems"])

if __name__ == "__main__":
    unittest.main()
