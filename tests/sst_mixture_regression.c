/* Regression tests for the factorized SST assignment posterior.
 * Compare with an independent, explicitly enumerated small reference.
 */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#include <signal/coherence.h>
#include <signal/mixture.h>
#include <signal/pot.h>
#include <signal/postprob.h>
#include <system/mixture2mixture.h>
#include <utils/gaussian.h>

static int failures = 0;

static void check_close(const char *name, double got, double expected, double tol) {
    if (!isfinite(got) || fabs(got - expected) > tol) {
        fprintf(stderr, "%s: got %.12g expected %.12g\n", name, got, expected);
        ++failures;
    }
}

static unsigned int count_combinations(unsigned int n_pots, unsigned int n_tracks) {
    unsigned int count = 1U;
    for (unsigned int p = 0; p < n_pots; ++p)
        count *= n_tracks + 3U;
    return count;
}

static int test_case(unsigned int n_pots, unsigned int n_tracks, float epsilon) {
    gaussians_1d_obj *active = gaussians_1d_construct_null(1U);
    gaussians_1d_obj *inactive = gaussians_1d_construct_null(1U);
    active->array[0] = gaussian_1d_construct_weightmusigma(1.0f, 0.55f, 0.19f);
    inactive->array[0] = gaussian_1d_construct_weightmusigma(1.0f, 0.18f, 0.21f);

    mixture2mixture_obj *model = mixture2mixture_construct(
        active, inactive, 0.36f, 0.11f, 0.21f, 0.68f, epsilon);
    mixture_obj *mix = mixture_construct_zero(n_pots, n_tracks);
    pots_obj *pots = pots_construct_zero(n_pots);
    coherences_obj *coherences = coherences_construct_zero(n_pots, n_tracks);
    postprobs_obj *actual = postprobs_construct_zero(n_pots, n_tracks);

    if (!mix || !model || !pots || !coherences || !actual ||
        mix->assignations != NULL || mix->nCombinations != 0U ||
        mix->p_Ez_phic != NULL || mix->p_phic_Ez != NULL) {
        fprintf(stderr, "Unexpected mixture allocation or legacy assignment buffer\n");
        return 1;
    }

    for (unsigned int p = 0; p < n_pots; ++p) {
        pots->array[4U * p + 3U] = 0.17f + 0.085f * (float)(p % 5U);
        for (unsigned int t = 0; t < n_tracks; ++t) {
            coherences->array[t * n_pots + p] =
                0.15f + 0.04f * (float)((t + 2U * p) % 8U);
        }
    }

    mixture2mixture_process(model, mix, pots, coherences, actual);

    /* Independent exhaustive reference for the revised probability model:
       label -2 false, -1 new, 0..nTracks-1 tracked, and one extra
       candidate-local unmodelled label carrying epsilon mass.
       This intentionally uses enumerated combinations, not factorization. */
    const unsigned int combinations = count_combinations(n_pots, n_tracks);
    /* Extra label at radix-1 is local epsilon / unmodelled source. */
    const unsigned int radix = n_tracks + 3U;
    double total = 0.0;

    for (unsigned int combo = 0; combo < combinations; ++combo) {
        unsigned int digits = combo;
        double weight = 1.0;
        for (unsigned int p = 0; p < n_pots; ++p) {
            const unsigned int label = digits % radix;
            digits /= radix;
            const unsigned int k = label * n_pots + p;
            weight *= label == radix - 1U
                ? (double)epsilon
                : (double)mix->p_Eszs_phics[k] * (double)mix->p_phics[k];
        }
        total += weight;
    }

    double *new_marginals = (double *)calloc(n_pots, sizeof(double));
    double *track_marginals =
        (double *)calloc((size_t)n_pots * n_tracks, sizeof(double));
    double *track_totals = (double *)calloc(n_tracks, sizeof(double));

    for (unsigned int combo = 0; combo < combinations; ++combo) {
        unsigned int digits = combo;
        double weight = 1.0;
        unsigned int assigned[8] = {0};
        for (unsigned int p = 0; p < n_pots; ++p) {
            const unsigned int label = digits % radix;
            digits /= radix;
            const unsigned int k = label * n_pots + p;
            weight *= label == radix - 1U
                ? (double)epsilon
                : (double)mix->p_Eszs_phics[k] * (double)mix->p_phics[k];
        }
        const double posterior = weight / total;
        digits = combo;
        for (unsigned int p = 0; p < n_pots; ++p) {
            const unsigned int label = digits % radix;
            digits /= radix;
            if (label == 1U)
                new_marginals[p] += posterior;
            if (label >= 2U && label < radix - 1U) {
                const unsigned int t = label - 2U;
                track_marginals[t * n_pots + p] += posterior;
                assigned[t] = 1U;
            }
        }
        for (unsigned int t = 0; t < n_tracks; ++t)
            if (assigned[t])
                track_totals[t] += posterior;
    }

    for (unsigned int p = 0; p < n_pots; ++p)
        check_close("new candidate posterior", actual->arrayNew[p],
                    new_marginals[p], 3e-5);
    for (unsigned int t = 0; t < n_tracks; ++t) {
        check_close("track exists posterior", actual->arrayTrackTotal[t],
                    track_totals[t], 3e-5);
        for (unsigned int p = 0; p < n_pots; ++p)
            check_close("track-candidate posterior",
                        actual->arrayTrack[t * n_pots + p],
                        track_marginals[t * n_pots + p], 3e-5);
    }

    free(new_marginals);
    free(track_marginals);
    free(track_totals);
    postprobs_destroy(actual);
    coherences_destroy(coherences);
    pots_destroy(pots);
    mixture_destroy(mix);
    mixture2mixture_destroy(model);
    gaussians_1d_destroy(active);
    gaussians_1d_destroy(inactive);
    return 0;
}

static int test_large_no_enumeration(void) {
    const unsigned int n_pots = 128U;
    const unsigned int n_tracks = 8U;
    gaussians_1d_obj *active = gaussians_1d_construct_null(1U);
    gaussians_1d_obj *inactive = gaussians_1d_construct_null(1U);
    active->array[0] = gaussian_1d_construct_weightmusigma(1.0f, 0.5f, 0.2f);
    inactive->array[0] = gaussian_1d_construct_weightmusigma(1.0f, 0.2f, 0.2f);
    mixture2mixture_obj *model = mixture2mixture_construct(
        active, inactive, 0.2f, 0.1f, 0.1f, 0.8f, 0.0f);
    mixture_obj *mix = mixture_construct_zero(n_pots, n_tracks);
    pots_obj *pots = pots_construct_zero(n_pots);
    coherences_obj *coherences = coherences_construct_zero(n_pots, n_tracks);
    postprobs_obj *post = postprobs_construct_zero(n_pots, n_tracks);

    if (!mix || mix->assignations || mix->nCombinations != 0U) {
        fprintf(stderr, "Large SST mixture allocated exponential workspace\n");
        return 1;
    }
    for (unsigned int p = 0; p < n_pots; ++p) {
        pots->array[4U * p + 3U] = 0.55f;
        for (unsigned int t = 0; t < n_tracks; ++t)
            coherences->array[t * n_pots + p] = 0.23f + 0.013f * (float)t;
    }
    mixture2mixture_process(model, mix, pots, coherences, post);
    for (unsigned int p = 0; p < n_pots; ++p)
        if (!isfinite(post->arrayNew[p]) || !(post->arrayNew[p] > 0.0f))
            ++failures;
    for (unsigned int t = 0; t < n_tracks; ++t)
        if (!isfinite(post->arrayTrackTotal[t]) ||
            post->arrayTrackTotal[t] < 0.0f ||
            post->arrayTrackTotal[t] > 1.00001f)
            ++failures;
    postprobs_destroy(post);
    coherences_destroy(coherences);
    pots_destroy(pots);
    mixture_destroy(mix);
    mixture2mixture_destroy(model);
    gaussians_1d_destroy(active);
    gaussians_1d_destroy(inactive);
    return 0;
}

int main(void) {
    for (unsigned int p = 1; p <= 4; ++p)
        for (unsigned int t = 1; t <= 3; ++t) {
            if (test_case(p, t, 0.0f) || test_case(p, t, 1e-4f))
                return EXIT_FAILURE;
        }
    if (test_large_no_enumeration())
        return EXIT_FAILURE;
    if (failures) {
        fprintf(stderr, "SST mixture regression failed (%d mismatches)\n", failures);
        return EXIT_FAILURE;
    }
    puts("SST factorized posterior matches exhaustive reference; large-case finite");
    return EXIT_SUCCESS;
}
