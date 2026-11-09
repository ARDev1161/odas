# O2: what native SST association evidence actually means

The offline `odas_sst_raw_v1` trace already exports `ssl_candidates[].track_posteriors[]`, with the pre-update track ID and `postprobs[previous_track_count]->arrayTrack[t*nPots+p]` for each candidate. These are **soft posterior marginals**, not discrete candidate-to-track assignments, observed identity, or acoustic separation quality.

## Data path (reviewed in `src/module/mod_sst.c`)

1. `mixture2mixture_process` computes the posterior over SSL candidates and existing SST tracks.
2. Immediately after this call, the offline trace captures the pre-update track ID ordering.
3. The SST update uses the posterior and activity to update or retire tracks.
4. The offline JSONL is emitted after updates; `tracks_after` describes the resulting state, whereas `track_posteriors` refers to **tracks before the update**.

This is why a post-update slot must never be used as the key for a pre-update posterior. Match by `track_id` and keep the hop index. A missing posterior for a newly born track is expected, not a recorder defect.

## Next diagnostic gate

For a frozen real Acoustix T03 WAV, save the SHA-256, exact ODAS SHA, configuration, full trace, and oracle. Per hop, compare pre-update posterior mass for each existing track against the known source bearings and subsequent `tracks_after` state. Report candidate ambiguity, wrong-direction posterior mass, births, retirements, false tracks, and one-to-one oracle recall separately.

A true hard association event **does not currently exist** in this probabilistic SST update. Do not invent one by taking `argmax` and calling it native evidence. If a hard decision is added later, it must be instrumented at the actual decision site and tested independently.

This document is a source-level diagnostic finding, **not** a T03 replay, an algorithm fix, or an acoustic PASS.
