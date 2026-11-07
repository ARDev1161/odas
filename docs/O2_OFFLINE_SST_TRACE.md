# O2 offline SST decision tracing on actual PCM

Status: the native recorder and schema checks are implemented; an actual
T03 replay using this fork has **NOT** been executed/validated yet.

## Build boundary

With CMake option ODAS_OFFLINE_SST_TRACE=OFF (the default), the new
recorder is not compiled. When explicitly ON, mod_sst_process writes
one synchronous JSONL record per processed hop to the path in
ODAS_SST_TRACE_JSONL. **This is NOT realtime-safe**: only use the
instrumented build for an offline, single-pipeline WAV replay worker,
never in live microphone/capture callbacks. Public headers and ODAS
tracker algorithm remain unchanged.

Compile and test the offline build:

    cmake -S . -B build-odas-offline -G Ninja \
      -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
      -DCMAKE_BUILD_TYPE=Release \
      -DODAS_BUILD_TESTS=ON \
      -DODAS_FORCE_BIN_AND_LIB_DIRS=OFF \
      -DODAS_OFFLINE_SST_TRACE=ON
    cmake --build build-odas-offline --parallel 4
    ctest --test-dir build-odas-offline --output-on-failure
    python3 -m unittest discover -s tools -p 'test_validate_sst_raw_trace.py' -v

These commands compile and run schema/ODAS regression tests, **not**
Acoustix. Do not claim audio quality PASS on this basis.

## Frozen Acoustix T03 reproduction: pending integration into libaudition

Obtain the exact existing six-channel real LibriSpeech Acoustix audio and
ground-truth artifact from libaudition Actions run 42367742782. Pin the
**exact ODAS trace branch commit SHA** in a distinct libaudition test
branch, build the actual ODAS dependency with the above trace option
enabled, and verify the resulting libaudition offline runner links that
instrumented ODAS, not the default upstream. The frozen T03 path from
libaudition PR #94 is build-s2/t03_eval_two/render/input.wav.

    # From the libaudition test checkout, after verifying the pinned input SHA:
    export ODAS_SST_TRACE_JSONL="$PWD/build-s2/t03_eval_two/odas/raw_sst.jsonl"
    export ODAS_SST_TRACE_HOP_FRAMES=128
    # Create a fresh output directory and remove any previous trace first.
    build-s2-odas/tests/audition_offline_integration \
      build-s2/t03_eval_two/render/input.wav \
      build-s2/t03_eval_two/odas
    python3 <odas-repo>/tools/validate_sst_raw_trace.py \
      "$ODAS_SST_TRACE_JSONL"

Before/after evaluations must use identical input.wav SHA256, speech
schedule, sample count, geometry, compiler settings and source references.
If the old 14-day artifact expires, regenerate using the pinned licensed
source and archive a NEW provenance before comparing; do not claim
bit-identical input without checking SHA. Run T00/T02 negative/control
cases as well as T03; store raw JSONL and hashes as CI artifacts.

## Actual observation record versus oracle metrics

A JSONL line of schema odas_sst_raw_v1 contains ODAS's native
1-based timestamp, zero-based hop_index, 128-sample offset, theta_new,
actual SSL vectors/strength/birth posteriors, marginal probabilities
against existing IDs, births, retirements, and after-hop tracks with
their P/A/T states. Numeric NaN/Inf is serialized as JSON null and
the validator rejects it, never silently changing it to zero.
Bounds: at most 128 SSL candidates, 32 track slots.

ODAS does NOT provide oracle source identities, real speakers, SI-SDRi,
SIRi, IDF1, or ASR WER. Those remain NOT MEASURED until a separate
oracle and separated-stem alignment. Synthetic schema tests are
contract tests and never acoustic-quality evidence.

## Actual T03 hypotheses to discriminate

- If the second SSL candidate is absent, investigate localization/resolution.
- If present but birth_posterior stays below theta_new, examine birth evidence.
- If probability goes to an existing track, inspect association.
- If a new track appears but disappears/probation never ends, inspect
  transitions, retirement and ID persistence.
- Check speech overlap and oracle time alignment before claiming missed sources.

**Concrete code-inspection lead, not confirmed as the T03 cause:**
the dynamic source-birth loop searches a slot where ids[slot] == 0,
but a successful birth only records idsAdded[slot] until after the
candidate loop. Multiple candidates crossing theta_new in the same hop
may overwrite the *same* pending slot. Test this hypothesis on the
actual trace and fix in a separate task PR with a deterministic
regression. Do not infer T03 improvement without measured replay.
