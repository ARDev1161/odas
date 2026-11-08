"""Contract-only native trace audit tests; no Acoustix quality assertions."""
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.o2_native_association_audit import audit
from tools.validate_sst_raw_trace import TraceError


def record(hop):
    return {
        "schema": "odas_sst_raw_v1", "odas_timestamp": hop + 1,
        "hop_index": hop, "sample_offset": hop * 128, "hop_frames": 128,
        "theta_new": 0.15,
        "ssl_candidates": [{"index": 0, "x": 1.0, "y": 0.0, "z": 0.0,
                            "strength": 0.5, "birth_posterior": 0.2,
                            "track_posteriors": [{"track_id": 9, "posterior": 0.4}]}],
        "births": [], "retirements": [],
        "tracks_after": [{"slot": 0, "track_id": 9, "state": "P", "activity": 0.3}],
        "active_tracks_after": 1,
    }


def lines(*items):
    return io.StringIO("".join(json.dumps(item) + "\n" for item in items))


class NativeAuditTests(unittest.TestCase):
    def test_real_schema_counters_do_not_claim_probation(self):
        first, second = record(0), record(1)
        second["ssl_candidates"] = []
        first["births"] = [10]
        result = audit(lines(first, second))
        self.assertEqual(result["validated_hops"], 2)
        self.assertEqual(result["hops_with_ssl_candidates"], 1)
        self.assertEqual(result["hops_with_existing_track_marginals"], 1)
        self.assertEqual(result["hops_with_provisional_tracks"], 2)
        self.assertEqual(result["birth_events"], 1)
        self.assertEqual(result["observed_track_hops"], 2)
        self.assertEqual(result["distinct_provisional_track_ids"], 1)
        self.assertEqual(result["observed_provisional_to_active_ids"], 0)
        self.assertEqual(result["zero_positive_ssl_evidence_hops"], 1)
        self.assertEqual(result["zero_positive_ssl_evidence_births"], 0)
        self.assertEqual(result["zero_evidence_birth_guard"], "PASS")
        self.assertEqual(result["five_hop_probation"],
                         "BLOCKED_MISSING_PER_TRACK_ASSOCIATION_EVENT")

    def test_birth_on_zero_ssl_evidence_is_measured_as_failure(self):
        item = record(0)
        item["ssl_candidates"][0]["strength"] = 0.0
        item["births"] = [10]
        result = audit(lines(item))
        self.assertEqual(result["zero_positive_ssl_evidence_hops"], 1)
        self.assertEqual(result["zero_positive_ssl_evidence_births"], 1)
        self.assertEqual(result["zero_evidence_birth_guard"], "FAIL")
        self.assertEqual(result["five_hop_probation"],
                         "BLOCKED_MISSING_PER_TRACK_ASSOCIATION_EVENT")

    def test_silent_no_candidates_is_valid_control(self):
        item = record(0)
        item["ssl_candidates"] = []
        item["tracks_after"] = []
        item["active_tracks_after"] = 0
        result = audit(lines(item))
        self.assertEqual(result["zero_evidence_birth_guard"], "PASS")
        self.assertEqual(result["zero_positive_ssl_evidence_hops"], 1)

    def test_observed_provisional_to_active_transition(self):
        first, second, third = record(0), record(1), record(2)
        second["tracks_after"][0]["state"] = "A"
        third["tracks_after"] = []
        third["active_tracks_after"] = 0
        third["retirements"] = [9]
        result = audit(lines(first, second, third))
        self.assertEqual(result["observed_track_hops"], 2)
        self.assertEqual(result["distinct_observed_track_ids"], 1)
        self.assertEqual(result["distinct_provisional_track_ids"], 1)
        self.assertEqual(result["distinct_active_track_ids"], 1)
        self.assertEqual(result["observed_provisional_to_active_ids"], 1)
        self.assertEqual(result["distinct_retirement_event_ids"], 1)
        self.assertEqual(result["oracle_speaker_identity"], "NOT_MEASURED")

    def test_active_without_observed_provisional_is_not_counted_as_promotion(self):
        item = record(0)
        item["tracks_after"][0]["state"] = "A"
        result = audit(lines(item))
        self.assertEqual(result["distinct_active_track_ids"], 1)
        self.assertEqual(result["observed_provisional_to_active_ids"], 0)

    def test_recycled_id_does_not_inherit_old_provisional_evidence(self):
        first, second, third = record(0), record(1), record(2)
        second["tracks_after"] = []
        second["active_tracks_after"] = 0
        second["retirements"] = [9]
        third["births"] = [9]
        third["tracks_after"][0]["state"] = "A"
        result = audit(lines(first, second, third))
        self.assertEqual(result["recycled_track_id_birth_events"], 1)
        self.assertEqual(result["observed_provisional_to_active_episodes"], 0)

    def test_new_provisional_after_recycle_can_promote(self):
        first, second, third, fourth = (record(i) for i in range(4))
        second["tracks_after"] = []
        second["active_tracks_after"] = 0
        second["retirements"] = [9]
        third["births"] = [9]
        fourth["tracks_after"][0]["state"] = "A"
        result = audit(lines(first, second, third, fourth))
        self.assertEqual(result["recycled_track_id_birth_events"], 1)
        self.assertEqual(result["observed_provisional_to_active_episodes"], 1)

    def test_disappearance_without_retirement_cannot_promote_reused_id(self):
        first, missing, reused = (record(i) for i in range(3))
        missing["tracks_after"] = []
        missing["active_tracks_after"] = 0
        reused["tracks_after"][0]["state"] = "A"
        result = audit(lines(first, missing, reused))
        self.assertEqual(result["unannounced_track_disappearances"], 1)
        self.assertEqual(result["unannounced_track_appearances"], 1)
        self.assertEqual(result["observed_provisional_to_active_episodes"], 0)

    def test_continuous_provisional_can_promote_without_birth_event(self):
        first, second = record(0), record(1)
        second["tracks_after"][0]["state"] = "A"
        result = audit(lines(first, second))
        self.assertEqual(result["unannounced_track_disappearances"], 0)
        self.assertEqual(result["observed_provisional_to_active_episodes"], 1)

    def test_active_to_provisional_is_detected_not_counted_as_promotion(self):
        first, second, third, fourth = (record(i) for i in range(4))
        first["tracks_after"][0]["state"] = "A"
        second["tracks_after"][0]["state"] = "P"
        third["tracks_after"][0]["state"] = "A"
        fourth["tracks_after"][0]["state"] = "A"
        result = audit(lines(first, second, third, fourth))
        self.assertEqual(result["active_to_provisional_regressions"], 1)
        self.assertEqual(result["lifecycle_integrity"], "FAIL")
        self.assertEqual(result["observed_provisional_to_active_episodes"], 1)

    def test_birth_and_retirement_same_id_is_conflicting(self):
        item = record(0)
        item["births"] = [9]
        item["retirements"] = [9]
        result = audit(lines(item))
        self.assertEqual(result["simultaneous_birth_retirement_ids"], 1)
        self.assertEqual(result["lifecycle_integrity"], "FAIL")

    def test_normal_lifecycle_integrity_passes(self):
        first, second = record(0), record(1)
        second["tracks_after"][0]["state"] = "A"
        self.assertEqual(audit(lines(first, second))["lifecycle_integrity"], "PASS")

    def test_standalone_cli_success_and_guard_failure(self):
        # Run the actual executable with no PYTHONPATH from an unrelated cwd.
        script = Path(__file__).resolve().parents[1] / "tools" / "o2_native_association_audit.py"
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "native.jsonl"
            good = record(0)
            trace.write_text(json.dumps(good) + "\n", encoding="utf-8")
            env = dict(__import__("os").environ)
            env.pop("PYTHONPATH", None)
            ok = subprocess.run([sys.executable, str(script), str(trace)],
                                cwd=tmp, env=env, text=True, capture_output=True)
            self.assertEqual(ok.returncode, 0, ok.stderr)
            report = json.loads(ok.stdout)
            self.assertEqual(report["validated_hops"], 1)
            self.assertEqual(report["zero_evidence_birth_guard"], "PASS")
            bad = record(0)
            bad["ssl_candidates"][0]["strength"] = 0.0
            bad["births"] = [10]
            trace.write_text(json.dumps(bad) + "\n", encoding="utf-8")
            failed = subprocess.run([sys.executable, str(script), str(trace)],
                                    cwd=tmp, env=env, text=True, capture_output=True)
            self.assertEqual(failed.returncode, 2, failed.stderr)
            self.assertEqual(json.loads(failed.stdout)["zero_evidence_birth_guard"], "FAIL")

    def test_empty_rejected(self):
        with self.assertRaises(TraceError):
            audit(io.StringIO(""))

    def test_missing_hop_rejected(self):
        with self.assertRaises(TraceError):
            audit(lines(record(0), record(2)))

    def test_duplicate_json_key_rejected(self):
        line = json.dumps(record(0)).replace('"hop_frames": 128,',
                                              '"hop_frames": 128, "hop_frames": 128,')
        with self.assertRaises(TraceError):
            audit(io.StringIO(line + "\n"))

    def test_nonfinite_rejected(self):
        line = json.dumps(record(0)).replace('"strength": 0.5',
                                              '"strength": NaN')
        with self.assertRaises(TraceError):
            audit(io.StringIO(line + "\n"))


if __name__ == "__main__":
    unittest.main()
