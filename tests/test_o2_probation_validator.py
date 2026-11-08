"""Contract tests for exported ODAS probation evidence (not acoustic quality)."""
import unittest
from tools.o2_probation_validator import InvalidTrace, evaluate


def sample(ps=(0.3,) * 5):
    return {"tracks": [{"id": 1, "generation": 0, "birth_hop": 20,
        "hops": [{"hop": 20 + i, "association": p, "state": "provisional"}
                 for i, p in enumerate(ps)]}]}


class ProbationValidatorTests(unittest.TestCase):
    def test_five_hop_promotion_evidence(self):
        self.assertTrue(evaluate(sample())["tracks"][0]["crosses_threshold"])

    def test_weak_marginals(self):
        self.assertFalse(evaluate(sample((0.01,) * 5))["tracks"][0]["crosses_threshold"])

    def test_incomplete_is_unknown_not_fail(self):
        result = evaluate(sample((0.9,) * 4))["tracks"][0]
        self.assertIsNone(result["crosses_threshold"])
        self.assertFalse(result["evidence_complete"])

    def test_missing_hop_rejected(self):
        data = sample()
        data["tracks"][0]["hops"][2]["hop"] += 1
        with self.assertRaises(InvalidTrace):
            evaluate(data)

    def test_duplicate_identity_rejected(self):
        data = sample()
        data["tracks"].append(data["tracks"][0].copy())
        with self.assertRaises(InvalidTrace):
            evaluate(data)

    def test_nan_rejected(self):
        data = sample()
        data["tracks"][0]["hops"][0]["association"] = float("nan")
        with self.assertRaises(InvalidTrace):
            evaluate(data)

    def test_out_of_range_rejected(self):
        for p in (-0.1, 1.1):
            with self.subTest(p=p), self.assertRaises(InvalidTrace):
                evaluate(sample((p,) * 5))

    def test_generation_reuse_is_distinct(self):
        data = sample()
        second = sample()["tracks"][0]
        second["generation"] = 1
        data["tracks"].append(second)
        self.assertEqual(len(evaluate(data)["tracks"]), 2)

    def test_order_invariant_between_tracks(self):
        data = sample()
        second = sample((0.01,) * 5)["tracks"][0]
        second["id"] = 2
        data["tracks"].append(second)
        a = evaluate(data)["tracks"]
        data["tracks"].reverse()
        b = evaluate(data)["tracks"]
        self.assertEqual(a, list(reversed(b)))

    def test_retired_track_cannot_resume_after_window(self):
        data = sample((0.2,) * 8)
        data["tracks"][0]["hops"][5]["state"] = "retired"
        with self.assertRaisesRegex(InvalidTrace, "after retirement"):
            evaluate(data)

    def test_active_track_cannot_revert_to_provisional(self):
        data = sample()
        data["tracks"][0]["hops"][1]["state"] = "active"
        with self.assertRaisesRegex(InvalidTrace, "revert"):
            evaluate(data)

    def test_active_then_retired_is_valid(self):
        data = sample()
        data["tracks"][0]["hops"][1]["state"] = "active"
        for item in data["tracks"][0]["hops"][2:4]:
            item["state"] = "active"
        data["tracks"][0]["hops"][4]["state"] = "retired"
        self.assertTrue(evaluate(data)["tracks"][0]["evidence_complete"])

    def test_invalid_threshold_types_fail_closed(self):
        for value in (None, "0.8", True, [], {}, float("nan"), float("inf"), -0.1, 1.1):
            with self.subTest(value=value), self.assertRaisesRegex(InvalidTrace, "invalid threshold"):
                evaluate(sample(), threshold=value)

    def test_valid_numeric_threshold_boundary(self):
        self.assertTrue(evaluate(sample(), threshold=0)["tracks"][0]["crosses_threshold"])
        self.assertFalse(evaluate(sample(), threshold=1)["tracks"][0]["crosses_threshold"])

    def test_unhashable_track_identity_fails_closed(self):
        for field, value in (("id", []), ("generation", {}), ("birth_hop", [])):
            with self.subTest(field=field), self.assertRaisesRegex(InvalidTrace, "invalid identity"):
                data = sample()
                data["tracks"][0][field] = value
                evaluate(data)

    def test_boolean_and_negative_identity_fails_closed(self):
        for field in ("id", "generation", "birth_hop"):
            for value in (True, -1, 1.5, None):
                with self.subTest(field=field, value=value), self.assertRaisesRegex(InvalidTrace, "invalid identity"):
                    data = sample()
                    data["tracks"][0][field] = value
                    evaluate(data)

    def test_invalid_lifecycle(self):
        data = sample()
        data["tracks"][0]["hops"][0]["state"] = "unknown"
        with self.assertRaises(InvalidTrace):
            evaluate(data)


if __name__ == "__main__":
    unittest.main()
