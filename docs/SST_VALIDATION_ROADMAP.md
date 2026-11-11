# ODAS SST validation roadmap (fork `dev`)

**Status:** working acceptance plan, 2026-11-07.
**Canonical end-to-end roadmap:** [libaudition acoustic validation](https://github.com/ARDev1161/libaudition/blob/docs/acoustic-validation-roadmap/docs/ACOUSTIC_VALIDATION_ROADMAP.md).
The libaudition document owns simulator gates S0–S3 and product gates L1–L6;
this one owns ODAS-specific implementation and algorithm validation.
Keep both plans synchronized when an SST change alters expected behavior.

## Development boundary

- Integration branch: `ARDev1161/odas:dev`. `master` is an unchanged
  upstream reference and is never an integration target for our changes.
- **One task = one separate `fix/*`/`feat/*` branch + PR into `dev`.**
  Each task has independent unit tests, benchmark and a documented
  baseline/after comparison. Merge only after CI and code review.
- The downstream `libaudition` consumes an **exact dev commit SHA**
  pinned in CMake. During evaluation of unfinished fork work,
  libaudition uses a temporary SHA-pinned PR branch.
  Never use a moving `GIT_TAG dev` or edit libaudition `main` directly.
- Preserve upstream C API/ABI unless explicitly reviewed; do not
  reimplement SST algorithms inside libaudition or audition_ros2.

## Proven baseline and remaining deficit

The fork already contains:

| Milestone | Status / evidence |
| --- | --- |
| O0.1 Remove `(nTracks + 2)^nPots` explicit assignment enumeration | **DONE:** exact independent assignment marginals, O(nPots × nTracks), tested against brute-force |
| O0.2 Stop 7–8 SSL candidates suppressing all SST births | **DONE:** candidate-local epsilon normalizer; 4..8 SSL all produced 2,448 SST observations with maximum 3 simultaneous tracks on fixed 12-second Acoustix |
| O0.3 Preserve strong-candidate probability when weak candidates are added | **DONE:** fork self-test with independent reference |
| O0.4 Broader real speech / real mic quality | **NOT DONE**; current 7 synthetic source-hop coverage is only 1,462/7,814 = 18.71% |

Reference commits / CI: SST factorization PR #1, candidate-local normalization
PR #3, fork `dev` commit
`c4fb33b75c28e2246d6f87741861ab0325fc74a3`;
[Acoustix 12s result](https://github.com/ARDev1161/libaudition/actions/runs/42339729226).

The fixture uses synthetic voiced-like excitations, *not* real speech.
Track observation count ≠ unique speakers and ≠ separated WAV quality.
Do not claim seven-way source separation based on this benchmark.

## O1 — mathematical and numerical correctness (priority P0)

Check inputs/corner cases: 0/1/2/4/5/6/7/8/16/32/128 SSL
potentials, 0/1/2/4/8 SST tracks, `epsilon=0`,
small/normal/large positive epsilon; zero/local-vanishing evidence,
finite extreme activity, NaN/Inf, quiet/silent frames and reset.
Define explicit policy for invalid values; no NaN can silently
propagate into `arrayNew`/`arrayTrack`/`arrayTrackTotal`.
A valid posterior remains finite in [0,1]; per-candidate
normalization including unmodelled mass is ≤1.

**Acceptance:**
1. Independent exhaustive-reference enumeration for small cases
   agrees to declared numeric tolerance (existing self-test).
2. Stress ≥128 candidates × 8 tracks has bounded memory, no
   combination-table construction and no integer-overflow artifacts.
3. Equivalent strong SSL candidates must retain their local birth
   marginals when unrelated weak candidates are appended.
4. ASan/UBSan and optimized builds pass. Add negative tests for
   allocation failures and malformed dimensions where achievable.
5. Benchmarks explicitly record per-hop CPU time, maximum allocations
   and peak memory. No unbounded work or heap allocation on
   an audio callback.

Keep exact assignment semantics and the **intentional change**
of positive-epsilon semantics documented separately.

## O2 — source creation, decay and association (priority P0)

Use libaudition Acoustix real-voice scenarios T00–T08 and the old
12-second synthetic regression as immutable comparisons.

- Track creation and disappearance; no long false tracks on digital silence.
- Prevent weak new candidates from suppressing strong tracks or producing
  phantom tracks. Compare false tracks, unmatched source hops and ID churn.
- Test 1 vs 2 vs 3 simultaneously speaking sources at varying azimuth
  separation (30/60/120 degrees), SNR and reverberation.
- Test moving microphone frame and source reacquisition, breaks,
  teleports, no input, reset, source crossing and track ID reuse.
- Measure true positive/false positive, one-to-one geometric recall,
  azimuth median/P90, matched 3D angle, fragmentation, IDF1 and latency.
- Evaluate candidate-local epsilon, `theta_new` and retirement thresholds
  **separately**, using a frozen validation split. No arbitrary retuning
  against the seven-source 12s recording.

**Acceptance:** the known 7–8 candidate birth-collapse must not recur;
for new tracking quality changes, a paired held-out evaluation must
improve a declared target metric without regressing source precision,
ID stability or T00 silence. The 2-source quantitative criteria live
in libaudition L3; thresholds must be implemented and reviewed before
becoming CI hard gates.

## O3 — separation/SSS support (priority P1)

SST supplies source hypotheses; it does **not** by itself produce clean
independent speech. Diagnose whether contamination comes from (a)
unresolved SSL DOA, (b) SST identity drift, (c) SSS beamforming and
channel leakage, or (d) downstream libaudition routing/ASR attribution.

Use licensed human speech and per-source convolved mic stems:
separation SI-SDRi/SIRi, target speech retention, interference leakage,
WER/CER per actual voice and identity switch error. Include explicit
nearby user voice + loudspeaker remote speech (T04).

**Acceptance:** source content must be verified with audio references,
not only angles or IDs; benchmark on held-out scenes. If resolution is
physically beyond the 4-mic array, clearly label the limitation
instead of making the green CI imply complete separation.

## O4 — cross-project integration and CI (priority P0 for each fix)

1. Open ODAS task branch + PR to `dev`.
2. Add deterministic unit tests and numerical oracle / before-after
   measurements, including negative cases and performance costs.
3. Require fork `SST regression` GitHub Actions PASS.
4. Pin the PR commit in a **temporary libaudition test branch**, run
   ODAS backend / audio integration CI and full 12s Acoustix. For
   real speech claims, also run the licensed speech benchmark.
5. Compare the same input WAV, manifest, seed, geometry, sound
   references and metrics. Save generated files and GitHub run links.
6. Only after a passing task and review, squash merge into `odas/dev`.
7. Update the stable libaudition dependency via a **separate** SHA-pin
   PR; verify both repository and integrated CI on the merged dev SHA.
8. Update statuses and any changed quantitative acceptance criteria
   in both roadmaps.

Every PR description includes: hypothesis, changed algorithm and API
contract, test coverage, measured before/after, limitations, reproducible
instructions, CI evidence and rollback. Never merge a red or unverified
ODAS algorithm change into `dev`.


## T03 native hard-decision evidence (2026-11-11)

Frozen real-voice T03 trace: `libaudition` Actions run `42422756648`, artifact
`acoustix-s2-real-odas-diagnostics`, `t03_eval_two/odas/sst_raw_trace.jsonl`;
SHA256 `ccb57a22dcf21c3aaa9bd13c9c98863b3217673cc767e9f87c31e2e7c94f5af6`.
The offline replay on ODAS PR #19 at feature SHA
`a77914b5ec25a86dde49045fd968eb5709cfdd14` passed both
[hard-decision CI](https://github.com/ARDev1161/odas/actions/runs/42911933740)
and [SST regression CI](https://github.com/ARDev1161/odas/actions/runs/42911933790).

| Raw trace metric | Observed |
| --- | ---: |
| Total hops | 1,875 |
| Births / retirements | 13 / 13 |
| Hops with 0 / 1 / 2 / 3 / 4 tracks | 988 / 846 / 27 / 10 / 4 |
| Hops with at least two tracks | 41 |
| Multi-track episodes | 7 |
| Multi-track episode lengths (hops) | 6, 5, 8, 6, 5, 5, 6 |
| Longest multi-track episode / P90 | 8 / 8 hops |
| Track episode median / P90 | 5 / 5 hops |

**Interpretation:** SST does create multiple concurrent tracks, but these are
short-lived. None of these counts proves a second correctly associated speaker;
identity/IDF1, false tracks, SI-SDRi, SIRi and WER remain **NOT MEASURED**.
Do not tune `theta_new` or claim a separation improvement from these counts.

**Exact measured multi-track intervals** (start inclusive, end exclusive; native hop indices):

| Episode | Hop interval | Length |
| --- | --- | ---: |
| 1 | [26, 32) | 6 |
| 2 | [142, 147) | 5 |
| 3 | [170, 178) | 8 |
| 4 | [203, 209) | 6 |
| 5 | [220, 225) | 5 |
| 6 | [263, 268) | 5 |
| 7 | [698, 704) | 6 |

These intervals were emitted by the actual native trace replay at feature HEAD
`dc7d8feaa9497efe54c2d555a0de451665667cc6`, with [O2 CI PASS](https://github.com/ARDev1161/odas/actions/runs/42928760189)
(two jobs) and [SST regression PASS](https://github.com/ARDev1161/odas/actions/runs/42928760398).
The [machine-readable artifact](https://github.com/ARDev1161/odas/actions/runs/42928760189/artifacts/13816020077)
contains the same boundaries. They are **not** oracle speaker matches;
no absolute time conversion or identity inference is justified without a verified
hop duration, origin, and coordinate-frame mapping. In particular, the seven
intervals do not establish sustained two-speaker tracking.

**Next mandatory gate:** align native `hop_index` with the frozen oracle
speech-active intervals and source DOAs, perform one-to-one matching per hop,
report oracle-matched concurrent coverage, ID switches, false tracks,
birth-to-first-match latency and retire/reacquisition. Validate the timebase
and coordinate frame first; if the trace omits track DOA or oracle timestamps,
report **BLOCKED** rather than assigning identities from track count.
Then run byte-identical upstream/dev/feature A/B on T03, T04 and T07 with
real separated WAV metrics before accepting any SST algorithm change.

## Immediate sequence

| Step | State | Exit |
| --- | --- | --- |
| Fix exponential assignment state + regression | **DONE** | Fork PR #1 merged in `dev` |
| Fix candidate-count-dependent birth collapse | **DONE** | Fork PR #3 merged in `dev`; 4–8 SSL regression |
| Evaluate actual voice corpus and separation metrics | **WAITING ON libaudition S2** | Meaningful human-speech oracle and verified evaluation |
| Diagnose ID stability and track false positives | **OPEN** | Scenario T00/T03/T05/T08 reports, repeatable tests |
| Evaluate 2–3 talker separation and source attribution | **OPEN** | Held-out SI-SDRi/SIRi, DOA and ASR report |
| Physical array correlation | **OPEN** | ReSpeaker recording, geometry and noise calibration |

This document is a technical task plan, not a statement that ODAS
can distinguish seven simultaneously speaking people with four microphones.
