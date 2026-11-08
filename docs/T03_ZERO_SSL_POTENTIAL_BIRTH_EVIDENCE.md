# O2: SST must never birth a new track from an empty SSL potential

## Reproduced on native, frozen real Acoustix data

The unchanged pinned six-channel licensed real-LibriSpeech scene
was replayed through actual ODAS in libaudition test PR #103, CI
42442794479, and horizontal-prior experiment PR #104, CI 42444370597.
The original zero-PCM T00 negative control is intentionally SYNTHETIC,
not a recorded room silence. The real T02/T03/T07 WAV input SHA
and the 128-frame ODAS hop clocks remain frozen.

With active GMM variance 0.01 (mean 0.4, inactive GMM unchanged,
Pnew/Pfalse unchanged), the underlying SSL module emits exactly
nPots=4 potential records per hop. In src/module/mod_ssl.c,
maxIndex starts at 0, maxValue is read from a scan map that may be
identically zero, then even a zero-score peak gets the direction
of the first sphere entry (typically +Z). Thus a zero-strength
placeholder is an *unmeasured* source hypothesis, NOT an acoustic
detection. A wide active GMM nonetheless assigns it native
birth_posterior ~= 0.978264868, higher than theta_new~=0.9.

Direct measurements of raw ODAS traces:

| Evidence | Count |
| --- | ---: |
| T00 all-zero PCM provisional source birth events, wide GMM | **1252** |
| T00 active track hops, same case | **0** |
| T03 genuine speech, wide GMM: zero-score potentials above theta_new | **38** |
| T03 wide GMM + near-plane prior: zero-score potentials above theta_new | **35** |
| T03 wide GMM + near-plane prior: 3D correct two-voice overlap hops | **0 / 243** |

A near-horizontal prior removes some incorrect SSL directional
search points, but it cannot fix zero-salience filler *after* SSL
returns a fixed-length array. In fact it left >1800 active
track-direction observations over 45-degree elevation (from all
1875 recorded hops), showing that the prior is not a source-quality
guarantee. Do not mistake this for a claim that the prior is completely
unused: the SSL candidate directions and scores do change.

## Minimal and bounded fix

Only the **dynamic SST birth condition** now requires a finite,
strictly positive SSL potential strength *and* a finite
birth posterior above the existing theta_new. This is implemented
as a private inline predicate used by src/module/mod_sst.c.
It does not change public headers, the fixed nPots wire format,
SSL candidate vectors or strengths, existing-source association,
probation, thresholds, Kalman/particle filtering or SSS outputs.

This is a correctness **invariant**, not a global acoustic
strength threshold, and it introduces no extra allocation or I/O.
Any genuinely positive finite strength retains the old comparison
with the existing theta_new. Zero, negative, NaN and Inf strengths
must never create new SST IDs; the presence/identity of a true
human source is NOT inferred from the mere positivity of the score.

A deterministic native C regression confirms the real
zero-score/high-posterior example and the valid-score boundaries.
The standard ODAS sst-regression and ODAS_OFFLINE_SST_TRACE
CI workflows exercise it through CTest with -Werror.

## Acceptance and limitations

**Not yet accepted solely by code inspection**: reproduce the
identical T00/T02/T03/T07 WAVs with an instrumented exact ODAS SHA
that includes this fix. Assert 0 T00 provisional births with the
wide GMM, unchanged baseline T02/T03/T07 on standard GMM, and
independently compare T03 live two-voice ORACLE DOA as well as
the extra tracks that might remain in the wide-GMM case.
Archive fresh input SHA, raw JSONL, CMake variant, track ID,
source-angle and T00 false-positive evidence.

The production high-variance GMM is **not** justified by this fix.
Even if it removes the T00 births, held-out real-room negative
controls, elevation sweeps, SI-SDRi/SIRi, speaker identity and
ASR WER remain unmeasured. A zero-score guard cannot resolve
weak but positive SSL candidates, reverberation or failed
two-speaker association.

Base branch is ODAS dev; never merge into ODAS master or
libaudition main automatically.


## Verified identical-PCM paired native replay (2026-11-08)

**Full PASS** at libaudition [Acoustix Actions run 42445272845](https://github.com/ARDev1161/libaudition/actions/runs/42445272845),
on exact fixed-ODAS commit 76da9ec6be6dce89cbfbdb5fb241e7180297b53c,
after the first CI attempt had a fixed artifact-token YAML escape error.
The succeeding job verified five adversarial comparator tests, the original
and candidate native trace clocks, literal WAV SHA equality, all GMM/prior
parameter maps, exact 240000-frame / 1875-hop input and zero recorder drops.
New evidence archive ID 13602878169 contains the paired result
`zero_ssl_birth_guard_before_after.json`.

| Actual native scenario | Births before -> after | Max active SST before -> after |
| --- | ---: | ---: |
| Wide GMM, T00 explicitly SYNTHETIC zero PCM | **1252 -> 0** | 0 -> 0 |
| Wide GMM, T02 one real speech voice | 77 -> 23 | 3 -> 2 |
| Wide GMM, T03 two real speech voices | 48 -> 22 | 2 -> 2 |
| Wide GMM, T07 seven real speech voices | 100 -> 36 | 4 -> 4 |
| Wide GMM + horizontal prior, T00 zero PCM | **1252 -> 0** | 0 -> 0 |
| Wide GMM + horizontal prior, T02 one voice | 86 -> 26 | 2 -> 1 |
| Wide GMM + horizontal prior, T03 two voices | 33 -> 5 | 3 -> 2 |
| Wide GMM + horizontal prior, T07 seven voices | 70 -> 28 | 4 -> 4 |

Under wide GMM, having two active SST tracks during actual T03
two-voice overlap **disappeared**: 227/243 -> 0/243 without prior,
243/243 -> 0/243 with prior. Both old and new produced **0**
one-to-one correct two-person DOA matches within 45 degrees. Thus
removing phantom track births did NOT repair localization of the
second person; it exposed that the earlier two-track count was an
artifact of zero-signal +Z candidates.

Under original/default GMM, for both with and without horizontal
prior, all native T02/T03/T07 structural SST metrics were
**identical before and after** (including births, track counts,
retirements, active ID counts and provisional lifetimes).

No held-out real-room T00, physical ReSpeaker test, SI-SDRi/SIRi,
IDF1 or ASR WER is claimed. This fix can be merged into ODAS dev
after its latest exact commit native CTest completes green;
it is not approval for widening default active GMM variance.
