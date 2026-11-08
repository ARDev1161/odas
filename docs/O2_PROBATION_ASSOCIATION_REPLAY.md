# O2: five-hop association replay contract (T03)

Status: diagnostic specification, **not an algorithm fix or quality PASS**.
Base: `odas/dev`; source evidence: libaudition PR #100, real Acoustix/ODAS run
https://github.com/ARDev1161/libaudition/actions/runs/42422756648 .
This document intentionally does not modify SST thresholds.

## Frozen observations and falsifiable hypotheses

The T03 reference has 243 oracle two-voice hops, 97 with two distinct SSL
candidates within 25 degrees of distinct voices, but 0 with two active SST
tracks. Thirteen provisional births occurred, one promoted. Seven births
occurred during oracle overlap, none promoted. The offline runner uses
`probability_window=5` and `probability_threshold=0.8`.
These observations **do not** prove that association caused the failures.

H1: a candidate is present on successive hops but repeatedly associated to
different provisional IDs. H2: the candidate remains associated with one ID,
but its marginal stays below promotion threshold. H3: SSL candidates vanish
before five valid hops. H4: geometric ambiguity/competition assigns both
candidates to the same existing track. H5: a lifecycle/reset/drop event
invalidates an otherwise qualifying probation window.

## Deterministic replay checks (next implementation)

1. Load the exact frozen T03 six-channel WAV and manifest; require SHA256
   equality with the recorded baseline, expected frame/hop count, and zero
   recorder drops. Reject missing/duplicate hop indices and nonfinite
   probabilities. Do not synthesize missing frames.
2. For every birth ID, collect the five consecutive post-birth raw ODAS hops.
   Preserve **candidate index, direction, marginal, track association, birth
   and retirement decisions**, and exact hop number. Explicitly distinguish
   absent candidate, zero marginal and missing trace field.
3. Compute independently `1 - product(1 - p_i)` for each ID's five
   association marginals. Compare against ODAS decisions without rounding
   before the comparison. Record whether the ID survives five hops, and
   report earliest failure hop.
4. For each oracle overlap hop, solve a *one-to-one* angular match between
   distinct SSL candidates and the two known speaker directions. Report
   matching at 25 and 45 degrees separately. A matched direction is not a
   separated audio stream or a speaker identity.
5. Produce per-ID and aggregate JSON: births, five-hop survival, promotions,
   failures by H1–H5 evidence, unmatched/ambiguous cases, max simultaneous
   active tracks, and false tracks on T00 silence. If evidence cannot
   distinguish H1 from H2/H3, label **undetermined**, never infer a cause.
6. Replay T02 and T07 controls on identical inputs before any parameter
   experiment. Reject any claimed fix that only increases T03 promotions
   while increasing T00 false tracks or causing T07 ID churn.

## Regression matrix

- One stable candidate for 5+ hops with high marginals: expect promotion.
- One stable candidate with marginals below threshold: no promotion.
- Two candidates swap indices but retain directions: verify ID continuity
  independent of input array order.
- Two close candidates cross, separate and disappear: check deterministic
  tie resolution and bounded provisional lifecycle.
- Missing hop, duplicate ID, NaN, negative probability, stale ID reuse:
  validator rejects malformed evidence, rather than fabricating PASS.
- Reset during probation: previous generation cannot be promoted afterward.

## Exit gate

An implementation PR must include executable deterministic tests, exact
commands, raw trace provenance, paired before/after metrics, CTest PASS,
fork SST regression CI PASS, and real Acoustix replay on the **same** WAV.
Any proposed association fix must be a separate `fix/*` branch from
current `dev`; pin its SHA only in a temporary libaudition evaluation PR.
No automatic merge into `odas/master` or `libaudition/main`.
SI-SDRi/SIRi/WER and hardware acceptance remain NOT MEASURED.
