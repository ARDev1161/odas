import io
import json
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from o2_hard_decisions import analyze

def row(hop, ids, born=(), gone=()):
    return json.dumps({"schema":"odas_sst_raw_v1","hop_index":hop,
        "tracks_after":[{"track_id":i} for i in ids],
        "births":list(born),"retirements":list(gone)}) + "\n"

class HardDecisionTests(unittest.TestCase):
    def test_lifecycle(self):
        result = analyze(io.StringIO(row(0,[1],[1])+row(1,[1,2],[2])+row(2,[2],[],[1])))
        self.assertEqual((result["births"],result["retirements"],result["hops_with_two_tracks"]),(2,1,1))
        self.assertEqual(result["oracle_identity"],"NOT_MEASURED")
        self.assertEqual(result["max_consecutive_hops_with_two_tracks"],1)
        self.assertEqual([result[f"hops_with_{n}_tracks"] for n in (1,2)], [2,1])
    def test_multi_track_bursts_not_identity(self):
        trace = (row(0,[1,2],[1,2])+row(1,[1,2])+row(2,[1],[],[2])
                 +row(3,[1,3],[3])+row(4,[1],[],[3]))
        result = analyze(io.StringIO(trace))
        self.assertEqual(result["hops_with_two_tracks"],3)
        self.assertEqual(result["max_consecutive_hops_with_two_tracks"],2)
        self.assertEqual(result["oracle_identity"],"NOT_MEASURED")
    def test_episode_distribution_and_id_reuse(self):
        trace = (row(0,[1,2],[1,2]) + row(1,[1,2]) +
                 row(2,[1],[],[2]) + row(3,[1,3],[3]) +
                 row(4,[1],[],[3]) + row(5,[1,2],[2]) +
                 row(6,[1],[],[2]) + row(7,[],[],[1]))
        result = analyze(io.StringIO(trace))
        self.assertEqual(result["multi_track_episode_lengths_hops"], [2,1,1])
        self.assertEqual(result["multi_track_episode_count"], 3)
        self.assertEqual(result["multi_track_episode_p90_hops"], 2)
        self.assertEqual(result["track_episode_count"], 4)
        self.assertEqual(result["track_lifetime_median_hops"], 2)
        self.assertEqual(result["track_lifetime_p90_hops"], 8)
    def test_open_episodes_counted_at_end(self):
        result = analyze(io.StringIO(row(0,[1,2],[1,2])+row(1,[1,2])))
        self.assertEqual(result["multi_track_episode_lengths_hops"], [2])
        self.assertEqual(result["track_episode_count"], 2)
        self.assertEqual(result["track_lifetime_p90_hops"], 2)
    def test_transition_mismatch(self):
        with self.assertRaisesRegex(ValueError,"transition mismatch"):
            analyze(io.StringIO(row(0,[1],[1])+row(1,[1,2])))
    def test_duplicate_ids(self):
        with self.assertRaisesRegex(ValueError,"duplicate"):
            analyze(io.StringIO(row(0,[1,1],[1])))
    def test_noncontiguous_hops(self):
        with self.assertRaisesRegex(ValueError,"non-contiguous"):
            analyze(io.StringIO(row(0,[1],[1])+row(2,[1])))
    def test_no_invented_birth(self):
        with self.assertRaisesRegex(ValueError,"birth absent"):
            analyze(io.StringIO(row(0,[],[2])))
    def test_empty(self):
        with self.assertRaisesRegex(ValueError,"empty trace"):
            analyze(io.StringIO(""))
if __name__ == "__main__":
    unittest.main()
