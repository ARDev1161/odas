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
        self.assertEqual(result["multi_track_intervals_hops"], [
            {"start_hop":0,"end_hop_exclusive":2},
            {"start_hop":3,"end_hop_exclusive":4},
            {"start_hop":5,"end_hop_exclusive":6}])
        self.assertEqual(result["multi_track_episode_p90_hops"], 2)
        self.assertEqual(result["track_episode_count"], 4)
        self.assertEqual(result["track_lifetime_median_hops"], 1)
        self.assertEqual(result["track_lifetime_p90_hops"], 7)
        self.assertEqual(result["completed_track_episode_count"], 4)
        self.assertEqual(result["right_censored_track_episode_count"], 0)
        self.assertEqual(result["completed_track_lifetime_p90_hops"], 7)
    def test_open_episodes_counted_at_end(self):
        result = analyze(io.StringIO(row(0,[1,2],[1,2])+row(1,[1,2])))
        self.assertEqual(result["multi_track_episode_lengths_hops"], [2])
        self.assertEqual(result["multi_track_intervals_hops"], [{"start_hop":0,"end_hop_exclusive":2}])
        self.assertEqual(result["track_episode_count"], 2)
        self.assertEqual(result["track_lifetime_p90_hops"], 2)
        self.assertEqual(result["completed_track_episode_count"], 0)
        self.assertEqual(result["right_censored_track_episode_count"], 2)
        self.assertEqual(result["completed_track_lifetime_p90_hops"], 0)
    def test_retired_and_censored_tracks_separate(self):
        trace = row(0,[1,2],[1,2]) + row(1,[2],[],[1]) + row(2,[2])
        result = analyze(io.StringIO(trace))
        self.assertEqual(result["completed_track_episode_count"], 1)
        self.assertEqual(result["right_censored_track_episode_count"], 1)
        self.assertEqual(result["completed_track_lifetime_median_hops"], 1)
        self.assertEqual(result["completed_track_lifetime_p90_hops"], 1)
        self.assertEqual(result["track_episode_count"], 2)
    def test_episode_intervals_reused_ids_and_censoring(self):
        trace = (row(10,[1,2],[1,2]) + row(11,[2],[],[1])
                 + row(12,[1,2],[1]) + row(13,[1],[],[2]))
        result = analyze(io.StringIO(trace))
        self.assertEqual(result["track_episode_intervals_hops"], [
            {"track_id":1,"start_hop":10,"end_hop_exclusive":11,"right_censored":False,"left_censored":False},
            {"track_id":2,"start_hop":10,"end_hop_exclusive":13,"right_censored":False,"left_censored":False},
            {"track_id":1,"start_hop":12,"end_hop_exclusive":14,"right_censored":True,"left_censored":False},
        ])
        self.assertEqual(result["completed_track_episode_count"], 2)
        self.assertEqual(result["right_censored_track_episode_count"], 1)
    def test_episode_intervals_first_row_active_without_birth(self):
        result = analyze(io.StringIO(row(20,[3])+row(21,[],[],[3])))
        self.assertEqual(result["left_censored_track_episode_count"], 1)
        self.assertEqual(result["births"], 0)
        self.assertEqual(result["track_episode_intervals_hops"], [
            {"track_id":3,"start_hop":20,"end_hop_exclusive":21,"right_censored":False,"left_censored":True}
        ])
    def test_left_censored_reused_id_is_not_a_second_left_censored_episode(self):
        trace = (row(20,[3]) + row(21,[],[],[3])
                 + row(22,[3],[3]) + row(23,[],[],[3]))
        result = analyze(io.StringIO(trace))
        self.assertEqual(result["left_censored_track_episode_count"], 1)
        self.assertEqual(result["births"], 1)
        self.assertEqual(result["completed_track_episode_count"], 2)
        self.assertEqual([e["left_censored"] for e in result["track_episode_intervals_hops"]], [True, False])

    def test_nonzero_hop_origin(self):
        result = analyze(io.StringIO(row(40,[1,2],[1,2])+row(41,[1,2])+row(42,[1],[],[2])))
        self.assertEqual(result["multi_track_intervals_hops"], [{"start_hop":40,"end_hop_exclusive":42}])
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
