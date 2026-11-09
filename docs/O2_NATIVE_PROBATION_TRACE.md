# O2 native provisional-track probation evidence

This change adds two fields **only to provisional (P) entries** in the existing
`odas_sst_raw_v1` offline JSONL `tracks_after` array:

- `probation_observations`: actual native `n_prob[slot]` counter, incremented
  when a provisional track receives an activity observation.
- `probation_mean_activity`: native `mean_prob[slot] / n_prob[slot]`, or
  JSON `null` when the counter is zero.

These are **not** candidate-to-track association probabilities, speaker IDs,
separation quality, or proof of a correct five-hop association. The fields
are emitted only when `ODAS_OFFLINE_SST_TRACE` is enabled and the existing
`ODAS_SST_TRACE_JSONL` and `ODAS_SST_TRACE_HOP_FRAMES=128` controls are
set. No production processing path or tracker threshold changes.

Acceptance still pending: exact-HEAD CI build with offline trace enabled,
and SHA-pinned T00/T02/T03/T07 real Acoustix replay with complete JSONL
and matching input WAV hashes. In particular T03 two-speaker DOA pairing
and source-separated audio remain unproven; do not claim PASS from these
new counters. The next instrumented step must expose native per-track
candidate association *events*, not reconstruct them from marginals.
