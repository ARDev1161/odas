# ODAS fork development rules

This repository is the ARDev1161 ODAS fork used by
[libaudition](https://github.com/ARDev1161/libaudition).

## Roadmaps and acceptance evidence

- **Read `docs/SST_VALIDATION_ROADMAP.md` before changing SST/SSL/SSS,
  track birth/retirement, numerical calculations, candidate limits,
  tests, CI, or claiming quality improvements.**
- The canonical end-to-end scenario and speech-quality plan is
  [libaudition's ACOUSTIC_VALIDATION_ROADMAP](https://github.com/ARDev1161/libaudition/blob/docs/acoustic-validation-roadmap/docs/ACOUSTIC_VALIDATION_ROADMAP.md).
  Simulator S0–S3 and libaudition quality L1–L6 are owned there;
  ODAS-specific algorithm/CI gates O0–O4 are owned here.
- Never conflate an SST trace or spatial DOA match with clean separated
  audio, a stable speaker ID, or a correct transcript. Quantify
  unmatched sources, false tracks, leakage, ID switches and ASR.
- Proposed quality thresholds require a validated corpus, independent
  metric tests and a frozen baseline before becoming hard CI gates.
  Record any acceptance change as a reviewed decision.

## Branch contract

- **`dev` is the integration branch** and the equivalent of the project's
  development mainline. Integrate completed work into `dev` only.
- **`master` remains the upstream mirror/reference. Do not commit or merge
  project-specific changes into `master`.**
- Every engineering task starts from the latest `dev` in a **separate branch**:
  `fix/<specific-issue>`, `feat/<specific-feature>`, `test/<scenario>`, or
  `chore/<infrastructure>`. Do not mix unrelated work in a single branch.
- Open a PR **from the task branch into `dev`**. Merge after tests pass,
  checking the exact head SHA and the GitHub CI result. Prefer squash merging.
  If CI is red or unverified, leave the PR open and report why.
- Never silently reset/rewrite `dev`, force push, or merge into `master`.
- For algorithm changes, preserve input/output semantics where appropriate.
  Isolate behavior changes and record baselines before tuning.

## Verification required per task

1. Build ODAS from the pinned upstream-compatible CMake configuration.
2. Run `ODAS_BUILD_TESTS=ON` and `ctest --output-on-failure`. The
   `.github/workflows/sst-regression.yml` workflow must pass when touched.
3. Add a deterministic regression for every bug fix, including negative
   inputs, boundary conditions and resource limits when relevant.
4. Avoid changing public headers/ABI unintentionally; document exceptions.
5. For numerical algorithms, compare against an independent reference on
   small cases, stress larger configurations, and consider float underflow,
   overflows, NaN/Inf and runtime/memory complexity.
6. When examining library behavior in actual sound scenes, use the headless
   `ARDev1161/libaudition` Acoustix workflow. Distinguish geometric tracking,
   separated audio quality and real-speech ASR; do not conflate their scores.
7. Summarize changed files, verification, CI links, limitations and next task
   in the PR. Merge **only** when the PR itself is known to pass.

## Integration with libaudition

- Pin `libaudition` to an **exact ODAS `dev` commit SHA**, not to
  `GIT_TAG dev`. This keeps builds reproducible if `dev` advances.
- Update the `libaudition` pin only after the relevant ODAS task is merged
  and verified in `dev`. Perform the pin update in a separate
  `libaudition` branch/PR and verify the whole CMake/CI path.
- Never merge into `ARDev1161/libaudition/main` automatically.
- The historical ODAS baseline is
  `bcb845434495e293df3d48f1203b7a86e1852449`.
- Preserve the original upstream attribution/licenses when modifying ODAS.

## Current SST engineering focus

- **Completed in `dev`:** exact factorized posterior with linear
  assignment complexity (ODAS PR #1); candidate-local epsilon
  normalization preventing 7–8 weak SSL hypotheses from suppressing
  all SST track births (ODAS PR #3). Retain these as regression tests.
- **Next:** evaluate source creation precision, false tracks, ID
  persistence, 3-second silence handling, cross-talk and real speech
  separation on libaudition's validated speech corpus. See O1–O4 in
  `docs/SST_VALIDATION_ROADMAP.md`.
- Later: check resource allocation failure, numerical and adversarial
  inputs, CPU/RAM in ≥8 candidate cases and measured microphone
  correlation. Do not claim a 7-talker physical system is validated
  because the synthetic 12-second test passes.
- Every ODAS task is an isolated branch/PR into `dev`; after merge
  and passing CI, update libaudition by **exact SHA** in a separate PR.
