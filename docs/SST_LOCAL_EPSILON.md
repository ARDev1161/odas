# Candidate-local evidence normalization in ODAS SST

Task branch: `fix/sst-local-evidence-normalization`, based on `dev`.
This changes the SST probability model; it is separate from the already merged
exact factorization/performance task.

## Reproduced problem

On libaudition's fixed 12-second Acoustix room scene, with the pinned 2024 ODAS
and the factorized-equivalent first fork patch, SST produces no tracks when
SSL emits 7 or 8 candidates. Four inputs produce 2,448 tracked observations.
Changing maximum SST track slots from 4 to 8 does not repair the problem.

The upstream implementation computes the normalizer of the joint
candidate-assignment space with an **absolute global** `epsilon`:

`E = product_i(sum_label q_i(label))`
`P(new_i) = [q_i(new) / sum_label q_i(label)] * E / (E + epsilon)`

Each `q_i` contains the candidate's evidence likelihood and prior. The
factor `E/(E+epsilon)` unintentionally **couples every birth posterior to the
number of unrelated weak candidates**. More candidates can drive `E` below
a fixed epsilon even though the strongest candidate did not change.

## Revised model

Interpret epsilon as a candidate-local "unmodelled/no-assignment" mass:

`P(new_i) = q_i(new) / (epsilon + sum_label q_i(label))`

`P(track_t | pot_i) = q_i(track_t) / (epsilon + sum_label q_i(label))`

`P(any pot assigned to track_t) = 1 - product_i(1 - P(track_t|pot_i))`

The existing false, new and tracked likelihoods and priors are unchanged.
No new C API option is needed. All marginals remain in [0,1], runtime and
memory remain linear in candidate/track count, and the normalizer never
multiplies evidence across unrelated candidates.

For epsilon=0 and valid nonzero evidence this agrees with the original
enumerated ODAS model. **For epsilon>0 it deliberately changes the
probability semantics**, so measured real-world quality must be compared
before making production claims. Existing ODAS users who rely on the old
global-epsilon behavior may need retuning; document this at integration.

## Tests and acceptance

- `tests/sst_mixture_regression.c`: brute-force oracle with an explicit
  local unmodelled state for small candidate/track combinations and
  epsilon=0 and positive epsilon.
- Large case (128 candidates, eight tracks) must remain finite and avoid
  combinatorial allocations.
- Check that a strong candidate's birth posterior is unchanged when the
  number of unrelated weak candidates increases from four to eight.
- Fork `SST regression` GitHub Actions and libaudition's full Acoustix
  12-second scene must pass. Compare baseline 4/4, 8/8 and 8/8→SST4
  track counts, oracle association and azimuth metrics; a structural
  CTest PASS does not establish real-speech separation quality.

**Merge only into `dev` after the experiment passes. `master` stays intact.**
