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
python3 -m unittest discover -s tests -p test_o2_posterior_ambiguity.py -v
python3 tools/o2_posterior_ambiguity.py \
  ../evidence/t03_eval_two/odas/sst_raw_trace.jsonl \
  | tee ../t03_posterior_ambiguity.json
```

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
