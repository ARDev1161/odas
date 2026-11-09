# Reproduce native posterior competition on the frozen real-speech T03 replay

This is a **diagnostic procedure**, not evidence of a successful SST fix.
It compares the *same real LibriSpeech Acoustix WAV* with ODAS's native
SSL→SST marginals. Do not generate synthetic posteriors or substitute a
different WAV. A posterior is **not** a hard speaker assignment.

## Frozen provenance

- libaudition stacked replay PR: https://github.com/ARDev1161/libaudition/pull/100
- Confirmed real replay: https://github.com/ARDev1161/libaudition/actions/runs/42422756648
- Its artifact: `acoustix-s2-real-odas-diagnostics`, containing
  `t03_eval_two/odas/sst_raw_trace.jsonl` and the input WAV SHA.
- Source Acoustix real-speech artifact run: `42367742782`.
- Known measured baseline: 243 oracle two-voice hops, zero with two
  simultaneous active SST tracks; 97/243 with distinct SSL candidates
  within 25 degrees of separate oracle voices. This is **not** a
  separation-quality or WER result.

## Commands (user PC with gh authentication)

```sh
mkdir -p /tmp/odas-t03-replay && cd /tmp/odas-t03-replay
gh run download 42422756648 --repo ARDev1161/libaudition \
  --name acoustix-s2-real-odas-diagnostics --dir evidence
test -s evidence/t03_eval_two/odas/sst_raw_trace.jsonl
git clone https://github.com/ARDev1161/odas.git
cd odas
git checkout test/o2-posterior-ambiguity-diagnostics
echo 'ccb57a22dcf21c3aaa9bd13c9c98863b3217673cc767e9f87c31e2e7c94f5af6  ../evidence/t03_eval_two/odas/sst_raw_trace.jsonl' | sha256sum --check
python3 -m unittest discover -s tests -p test_o2_posterior_ambiguity.py -v
python3 tools/o2_posterior_ambiguity.py \
  ../evidence/t03_eval_two/odas/sst_raw_trace.jsonl \
  | tee ../t03_posterior_ambiguity.json
```

The CI now **fails closed** unless the downloaded native trace SHA-256 is
`ccb57a22dcf21c3aaa9bd13c9c98863b3217673cc767e9f87c31e2e7c94f5af6`.
It also checks the following **frozen diagnostic baseline**, not an
acoustic-quality acceptance threshold: 1,875 hops, 7,500 SSL candidate
observations, 3,548 with existing tracks, 201 birth posteriors ≥0.1,
49 ≥0.5, 76 birth wins ≥0.1, and 48 birth wins ≥0.5.
These numbers come from the real native-trace CI job
[42614437264](https://github.com/ARDev1161/odas/actions/runs/42614437264).
Any change requires explicitly reviewing the trace provenance or diagnostic
semantics, rather than silently accepting new evidence as equivalent.

The frozen T03 trace has **1,875 explicit native hop indices and zero
index gaps**, verified from the real CI log for
[run #42687780555](https://github.com/ARDev1161/odas/actions/runs/42687780555)
(artifact [#13705138219](https://github.com/ARDev1161/odas/actions/runs/42687780555/artifacts/13705138219)).
The workflow now asserts both facts so a truncated or non-contiguous trace
cannot silently pass a temporal-persistence baseline. This is trace
integrity evidence, not speaker association or separation quality.

The replay artifact's ODAS SHA may **differ** from this diagnostic
script's SHA; the script only reads the emitted `odas_sst_raw_v1`
schema. Do not describe the analysis as a paired ODAS algorithm A/B
comparison. Record the trace provenance, input WAV SHA and script SHA
in any result.

## Automated real-trace CI

The PR includes `.github/workflows/o2-real-t03-posterior-replay.yml`.
It downloads the **original** run `42422756648` artifact, computes the
native trace SHA-256 and runs this diagnostic on actual Acoustix/ODAS output.
It uploads only the SHA and derived JSON metrics; it does **not** run a new
Acoustix simulation, validate identity against the oracle, or claim a fix.
Artifact `13593769507` was verified present and unexpired on 2026-11-09.
A missing/expired artifact or cross-repository token restriction is a
**BLOCKED** integration gate, not evidence of an SST algorithm failure.

## Measured high-birth competition split (2026-11-09)

The exact PR HEAD `64ffb1ec950ecf23fd0aabe952709c2bf916eedb`
completed [real native-trace CI #42699580088](https://github.com/ARDev1161/odas/actions/runs/42699580088)
with artifact [#13710037873](https://github.com/ARDev1161/odas/actions/runs/42699580088/artifacts/13710037873).
The original T03 trace checksum was verified before deriving these numbers:

| Native candidate evidence | Count |
| --- | ---: |
| SSL candidates with birth posterior >= 0.1 | 201 |
| With at least one existing-track posterior | 200 |
| Without existing-track posteriors | 1 |
| With birth > top existing-track posterior AND birth >= 0.1 | 76 |

Thus **200/201 strong birth observations already had a competing
existing-track marginal**. This does not imply those 200 candidates
belong to a second oracle speaker, nor that an SST track was born:
native marginals are not hard assignments. The two-way 200/1 split
is now a frozen regression assertion in the real replay workflow,
and the workflow also runs when its unit-test file changes.

## Interpretation and next gate

`birth_below_top_existing_track_marginal` counts SSL candidates whose
new-track probability is smaller than the strongest existing-track
marginal. `birth_above_top_existing_track_marginal` counts the reverse.
`birth_vs_existing_track_comparable` excludes candidates with no
pre-existing tracks; ties are counted separately. The additional `birth_posterior_ge_0_1` and `birth_posterior_ge_0_5`
counts measure **absolute** birth evidence across all candidates;
`birth_above_top_track_and_ge_0_1` and `_ge_0_5` count only candidates
with existing tracks where birth exceeds the strongest track marginal
**and** clears the stated absolute threshold. These are descriptive
thresholds, **not** the ODAS internal acceptance threshold or a proposed
CI quality gate. They distinguish relative wins caused by near-zero
competing track probabilities from substantial birth evidence.
The additional per-hop metrics `hops_with_birth_posterior_ge_0_1`,
`hops_with_birth_posterior_ge_0_5`,
`max_birth_posterior_ge_0_1_candidates_per_hop`, and
`longest_consecutive_hops_with_birth_posterior_ge_0_1` distinguish
isolated high-birth candidates from sustained runs of evidence. The
consecutive-hop statistic is based on trace order, not physical seconds;
it must not be interpreted as track survival or oracle identity. These per-hop metrics are diagnostic; their frozen T03 regression values
are now checked by CI (see the measured table below). They are **not**
acoustic-quality acceptance thresholds and do not establish persistent
speaker identity.

## Measured contiguous birth evidence on frozen T03 (2026-11-09)

Exact feature HEAD `288c8e983610f680ce6e5acef106cf69beecad71`:
[real-trace CI #42652383272](https://github.com/ARDev1161/odas/actions/runs/42652383272),
[JSON artifact #13690042690](https://github.com/ARDev1161/odas/actions/runs/42652383272/artifacts/13690042690).
The CI verified the original trace SHA-256 above and printed these **observed** metrics:

| Statistic | T03 |
| --- | ---: |
| Total hops | 1,875 |
| Hops with any candidate birth posterior >= 0.1 | 187 |
| Hops with any candidate birth posterior >= 0.5 | 46 |
| Maximum >=0.1 candidates in one hop | 4 |
| Runs of adjacent hops with >=0.1 evidence | 69 |
| Runs at least five hops long | 11 |
| Total hops within runs at least five hops long | 94 |
| Longest such run (hops) | 27 |

**Interpretation boundary:** these runs aggregate *any* SSL candidate in a
hop. A five-hop run can involve five different bearings, five different
candidates or even different speakers; it is **not** evidence that one
native SST provisional track accumulated five consecutive associations.
The observation rules out the hypothesis that *all* high-birth evidence
is isolated to single hops, but does **not** establish probation survival,
track creation correctness, or speaker identity. Next diagnostic gate:
join each candidate to the geometric oracle and native per-track
probation/association events, with timestamp and coordinate-frame checks;
compare T00/T02/T03/T07 on unchanged input WAVs before changing SST.

These values do not
prove that the second oracle voice was rejected: the trace has no
ground-truth speaker identity. Compare T03 against T02 and T07 using
the same script, then join candidate positions to the **independent**
per-hop geometric oracle by timestamp and angle before choosing an
SST algorithm change.

**PASS** means valid native JSONL, diagnostic unit tests passing, and
a provenance-preserving output report. **BLOCKED** means the original
artifact is unavailable, the input hash cannot be verified, or the
trace fails validation. **NOT MEASURED** remains the status of
SI-SDRi/SIRi, per-speaker leakage and WER.

Do not merge this diagnostic PR as a claimed fix for 0/243; algorithm
changes require a separate branch, paired real T00/T02/T03/T07
evaluation, and regression checks for false tracks and ID churn.
