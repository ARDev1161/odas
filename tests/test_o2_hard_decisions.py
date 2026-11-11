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
            {"track_id":1,"episode":1,"start_hop":10,"end_hop_exclusive":11,"right_censored":False,"left_censored":False},
            {"track_id":2,"episode":1,"start_hop":10,"end_hop_exclusive":13,"right_censored":False,"left_censored":False},
            {"track_id":1,"episode":2,"start_hop":12,"end_hop_exclusive":14,"right_censored":True,"left_censored":False},
        ])
        self.assertEqual(result["completed_track_episode_count"], 2)
        self.assertEqual(result["right_censored_track_episode_count"], 1)
    def test_episode_intervals_first_row_active_without_birth(self):
        result = analyze(io.StringIO(row(20,[3])+row(21,[],[],[3])))
        self.assertEqual(result["left_censored_track_episode_count"], 1)
        self.assertEqual(result["births"], 0)
        self.assertEqual(result["track_episode_intervals_hops"], [
            {"track_id":3,"episode":1,"start_hop":20,"end_hop_exclusive":21,"right_censored":False,"left_censored":True}
        ])
    def test_left_censored_reused_id_is_not_a_second_left_censored_episode(self):
        trace = (row(20,[3]) + row(21,[],[],[3])
                 + row(22,[3],[3]) + row(23,[],[],[3]))
        result = analyze(io.StringIO(trace))
        self.assertEqual(result["left_censored_track_episode_count"], 1)
        self.assertEqual(result["births"], 1)
        self.assertEqual(result["completed_track_episode_count"], 2)
        self.assertEqual([e["left_censored"] for e in result["track_episode_intervals_hops"]], [True, False])

    def test_per_hop_track_observations_preserve_ids_not_identity(self):
        trace = (row(20,[7,2],[7,2]) + row(21,[2],[],[7])
                 + row(22,[],[],[2]) + row(23,[7],[7]))
        result = analyze(io.StringIO(trace))
        self.assertEqual(result["track_observations_hops"], [
            {"hop_index":20,"track_ids":[2,7],"track_episodes":[{"track_id":2,"episode":1},{"track_id":7,"episode":1}]},
            {"hop_index":21,"track_ids":[2],"track_episodes":[{"track_id":2,"episode":1}]},
            {"hop_index":22,"track_ids":[],"track_episodes":[]},
            {"hop_index":23,"track_ids":[7],"track_episodes":[{"track_id":7,"episode":2}]},
        ])
        self.assertEqual(result["oracle_identity"], "NOT_MEASURED")
        self.assertEqual(result["sss_quality"], "NOT_MEASURED")

    def test_reused_id_has_distinct_episode_keys(self):
        trace = row(0,[4],[4])+row(1,[],[],[4])+row(2,[4],[4])
        result = analyze(io.StringIO(trace))
        self.assertEqual([r["track_episodes"] for r in result["track_observations_hops"]],
                         [[{"track_id":4,"episode":1}], [], [{"track_id":4,"episode":2}]])
        self.assertEqual([(e["track_id"], e["episode"], e["start_hop"], e["end_hop_exclusive"]) for e in result["track_episode_intervals_hops"]],
                         [(4,1,0,1),(4,2,2,3)])

    def test_every_episode_interval_matches_per_hop_membership(self):
        # Independently reconstruct the observed membership for each episode.
        # Numeric track IDs can be reused and must never bridge a gap.
        trace = (row(30,[2,7],[2,7]) + row(31,[2],[],[7])
                 + row(32,[2,7],[7]) + row(33,[7],[],[2])
                 + row(34,[],[],[7]) + row(35,[2],[2]))
        result = analyze(io.StringIO(trace))
        observed = {}
        for hop in result["track_observations_hops"]:
            for episode in hop["track_episodes"]:
                key = (episode["track_id"], episode["episode"])
                observed.setdefault(key, []).append(hop["hop_index"])
        intervals = result["track_episode_intervals_hops"]
        self.assertEqual(len(observed), len(intervals))
        self.assertEqual(set(observed), {(e["track_id"], e["episode"]) for e in intervals})
        for episode in intervals:
            key = (episode["track_id"], episode["episode"])
            self.assertEqual(observed[key],
                             list(range(episode["start_hop"], episode["end_hop_exclusive"])))
        self.assertEqual(observed[(7,1)], [30])
        self.assertEqual(observed[(7,2)], [32,33])
        self.assertEqual(observed[(2,2)], [35])

    def test_no_speaker_identity_or_doa_inferred_from_track_ids(self):
        result = analyze(io.StringIO(row(0,[1,2],[1,2])+row(1,[1,2])))
        self.assertEqual(result["oracle_identity"], "NOT_MEASURED")
        self.assertEqual(result["sss_quality"], "NOT_MEASURED")
        for hop in result["track_observations_hops"]:
            self.assertEqual(set(hop), {"hop_index", "track_ids", "track_episodes"})
            self.assertTrue(all(set(e) == {"track_id", "episode"}
                                for e in hop["track_episodes"]))

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
    def test_first_row_retirement_is_not_a_valid_observation(self):
        with self.assertRaisesRegex(ValueError, "retirement without prior observation"):
            analyze(io.StringIO(row(10, [], [], [3])))

    def test_empty(self):
        with self.assertRaisesRegex(ValueError,"empty trace"):
            analyze(io.StringIO(""))
if __name__ == "__main__":
    unittest.main()
