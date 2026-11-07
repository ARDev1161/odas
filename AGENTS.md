# ODAS fork development rules

This repository is the ARDev1161 ODAS fork used by
[libaudition](https://github.com/ARDev1161/libaudition).

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

- Completed: eliminate exhaustive assignment-table enumeration via exact
  factorized posterior marginals and test against a brute-force oracle.
- Next: diagnose 7–8 SSL candidates suppressing SST track birth; inspect
  the explicit `epsilon` regularizer and threshold/probability semantics
  with recorded internal posterior metrics before changing behavior.
- Later: robust memory allocation failure handling, finite-input checks,
  realistic seven-speaker moving-room tests, and real speech separation
  and ASR metrics. Do not assume passing synthetic CTest proves real-world
  seven-speaker performance.
