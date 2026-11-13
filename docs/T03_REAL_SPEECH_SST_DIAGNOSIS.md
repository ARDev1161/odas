# T03 real-speech SSL → SST diagnosis (O2)

Status: **investigation pending**. This is a trace/acceptance contract, not an algorithm fix or a passing separation benchmark.

## Frozen observations

From [libaudition Acoustix S2 real LibriSpeech replay PR #94](https://github.com/ARDev1161/libaudition/pull/94): T02 (one voice) max SST=1 and one-to-one geometric source-hop recall=98.86%; T03 (two voices) max SST=1 and recall=71.90%; T07 (seven voices) max SST=4 and recall=21.92%. These are reported spatial diagnostic metrics, **not** separation SI-SDRi/SIRi, speaker identification, or ASR WER. PR #96 comparator CI [CI](https://github.com/ARDev1161/libaudition/actions/runs/42384970262) and [WebRTC APM](https://github.com/ARDev1161/libaudition/actions/runs/42384970300) passed, but do not demonstrate improved ODAS performance.

## Reproduction prerequisites

Before tuning, record exact 6-channel input WAV SHA256, scene/oracle and source-activity schedule, Acoustix artifact run ID, ODAS fork commit SHA, libaudition runner SHA, ODAS config and compiler options. Reuse identical PCM and verify hash before and after; **never rerender** while comparing algorithm variants. Establish whether two voices actually overlap in the evaluated hops, not merely that two speakers appear in the scene.

## Bounded diagnostic trace schema (per 128-frame hop)

- `hop_index`, input first-frame sample offset, robot pose, oracle active source IDs (evaluation only).
- Each SSL potential: candidate index, azimuth/elevation, strength, normalized birth evidence and finite-value flags.
- Each SST state: transient track ID, existence probability, assigned SSL candidate index (or unmatched), birth/retirement decision and threshold, age, last-observed hop.
- Counters: number of SSL candidates, active SST tracks, births, retirements, unmatched SSL candidates, oracle active sources, one-to-one oracle matches, false tracks, ID switches.

Trace is **diagnostic only**, emitted outside the capture callback via a bounded buffer or offline runner; no unbounded allocation on the realtime path. Keep transient track IDs distinct from speaker identities. Preserve source WAV and clean references as separate artifacts. Reject malformed/nonfinite data; do not silently coerce.

## Competing explanations to test

1. Second source never yields an SSL potential (localization resolution or overlapping acoustic evidence).
2. Second potential exists but SST birth posterior/threshold rejects it.
3. Candidate assigned to an existing SST track rather than a new one.
4. A second SST track is born but retires too early or repeatedly changes ID.
5. Oracle overlap or timestamp alignment is wrong; apparent missing source is an evaluation artifact.

## Gates before an ODAS algorithm PR

- **T00 negative control:** silence/noise must not create persistent phantom tracks.
- **T02 control:** preserve one-speaker recall, recorder integrity and stable ID.
- **T03:** stratify simultaneous speech by angular separation 30/60/120°, stationary/moving robot, RT60 0.2/0.36/0.7 s; report precision, recall, IDF1, fragmentation, latency and unmatched tracks.
- **Numerics:** preserve O1 exhaustive small-case oracle, candidate counts 0..128, NaN/Inf rejection, ASan/UBSan and bounded CPU/memory.
- **Real speech:** separation leakage and SI-SDRi/SIRi/WER remain **BLOCKED** until waveform/reference alignment and pinned ASR are measured. Do not interpret an SST track as clean isolated audio.

Exit: checked-in reproducible per-hop trace from frozen real T03 WAV, smallest failing ODAS regression, independently validated cause, paired before/after report and CI. Implement any fix in its own `fix/*` branch and PR to `dev`; do not merge to `master`. Update libaudition dependency only through a separate SHA-pinned PR after the ODAS fix merges.
