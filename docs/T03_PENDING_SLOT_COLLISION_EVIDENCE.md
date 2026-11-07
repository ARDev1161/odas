# T03: confirmed same-hop SST pending-slot overwrite

Evidence: exact frozen LibriSpeech Acoustix S2 PCM, recorded by libaudition
[real-speech replay run 42408672657](https://github.com/ARDev1161/libaudition/actions/runs/42408672657),
libaudition PR #97 and ODAS instrumented PR #7 commit
`14bd92b9e8a94e7b14d400d52685a00057edf5af`.

Source T03 WAV SHA256:
`c14fe750e47064de1b105c5fceab1ffe8e5330157b7519818a5c175d6c54f0ee`.
240000 input frames at 16000 Hz, 1875 raw 128-frame hops,
zero recorder drops, 1875 validated JSONL entries.
No new audio was simulated or altered for this diagnosis.

## Measured T03

Real voice intervals: speaker_1 frames 3200–39120 and speaker_2
9600–83920 (approximately overlapping hops 75–305 inclusive).
ODAS's `theta_new` was approximately **0.9**. During overlapping
hops, seven new **provisional** tracks were born (IDs 4–10);
all seven were retired after five hops (40 ms), with **zero**
promotions to active state A. The primary ID 2 stayed active.
No overlap hop had two `birth_posterior > theta_new` candidates.

Thus same-hop slot collision is NOT an established explanation of
the missing second active speaker in the *overlap interval*: other
O2 issues remain, especially probation thresholds, association and SSL
candidate strength. This change should not be claimed to fix two-voice
recall without independent paired replay measurements.

## Independently observed pending-slot collision

**T03 hop index 699** has three SSL birth posteriors over threshold:
- candidate 0: 0.999961019
- candidate 1: 0.95117712
- candidate 2: 0.999346554

Prior to the hop, existing tracks include active ID 2 and provisional
ID 11. In the original dynamic birth loop, slot availability is checked
using only `ids[slot] == 0`, while newly reserved IDs are written to
`idsAdded[slot]` and are **not** committed to `ids[slot]` until the
whole candidate loop ends. This permits all three candidates to choose
the same slot repeatedly.

Trace result: only ID **14** is retained as a new provisional track at
hop 699. IDs **12 and 13** were never emitted as actual track births
(the internal ID counter advanced). This is a real observed defect,
distinct from tracking correctness and the 7-person quality goal.

## Fix and acceptance

The hot-path predicate now checks that BOTH arrays are zero before
accepting a free slot; no dynamic memory allocations or public ABI
changes. A C regression exercises three candidates on the same hop,
existing and pending occupancy, full capacity, zero slots and retirement
reuse. The canonical `SST regression` workflow builds this test with
`ODAS_BUILD_TESTS=ON` and runs it in CTest.

After this PR passes, evaluate **the same exact T03 PCM SHA** through
a temporary libaudition test branch that pins the proposed ODAS fix
commit (and includes trace instrumentation if comparing full JSONL).
Expected structural effect at hop 699: preserve separate pending
births if free capacity exists; this is NOT acceptance of two-speaker
separation or ASR quality. Record before/after trace and ID metrics,
check T00 silence and T02 control, and keep this algorithm fix isolated.

Quality metrics SI-SDRi/SIRi/WER remain NOT MEASURED.
