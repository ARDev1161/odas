import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from o2_ab_provenance import validate


def fixtures():
    template = {
        "scenario": "T03", "wav_sha256": "a" * 64,
        "oracle_sha256": "b" * 64,
        "geometry_m": [[.032, 0, 0], [0, .032, 0],
                       [-.032, 0, 0], [0, -.032, 0]],
        "pcm_channels": [1, 2, 3, 4],
        "ssl_config_sha256": "c" * 64,
        "sst_config_sha256": "d" * 64,
        "sss_config_sha256": "e" * 64,
        "seed": 42, "commit_sha": "f" * 40,
    }
    return {name: copy.deepcopy(template)
            for name in ("upstream", "dev", "feature")}


class PairedABProvenanceTests(unittest.TestCase):
    def test_comparable_inputs_are_not_quality_pass(self):
        self.assertEqual(validate(fixtures())["status"],
                         "COMPARABLE_INPUTS_ONLY_NOT_QUALITY_PASS")

    def test_rejects_any_mismatched_frozen_input(self):
        for field, value in (
            ("wav_sha256", "0" * 64),
            ("oracle_sha256", "0" * 64),
            ("ssl_config_sha256", "0" * 64),
            ("sst_config_sha256", "0" * 64),
            ("sss_config_sha256", "0" * 64),
            ("seed", 43),
            ("pcm_channels", [0, 1, 2, 3]),
            ("geometry_m", [[0, 0, 0]] * 4),
        ):
            with self.subTest(field=field):
                data = fixtures()
                data["feature"][field] = value
                with self.assertRaises(ValueError):
                    validate(data)

    def test_rejects_missing_variant_and_invalid_commit(self):
        data = fixtures()
        del data["dev"]
        with self.assertRaises(ValueError):
            validate(data)
        data = fixtures()
        data["feature"]["commit_sha"] = "not-a-commit"
        with self.assertRaises(ValueError):
            validate(data)

    def test_rejects_missing_and_malformed_hash(self):
        data = fixtures()
        del data["dev"]["oracle_sha256"]
        with self.assertRaises(ValueError):
            validate(data)
        data = fixtures()
        data["dev"]["wav_sha256"] = "z" * 64
        with self.assertRaises(ValueError):
            validate(data)


if __name__ == "__main__":
    unittest.main()
