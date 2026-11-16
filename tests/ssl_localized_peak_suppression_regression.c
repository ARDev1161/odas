/* Deterministic experimental SSL valley-bounded suppression contract.
 * The second peak must remain visible outside the selected TDOA window.
 * This is a unit contract, NOT evidence of better speaker separation.
 */
#include <stdio.h>
#include <stdlib.h>
#include <system/xcorr2xcorr.h>

static int check(const float *a, const float *expected, unsigned int n,
                 const char *label)
{
    unsigned int i;
    for (i = 0; i < n; ++i) {
        if (a[i] != expected[i]) {
            fprintf(stderr, "%s sample %u: %.6f != %.6f\n",
                    label, i, a[i], expected[i]);
            return 1;
        }
    }
    return 0;
}

int main(void)
{
    xcorr2xcorr_obj reset = {8U};
    float samples[8] = {0.2f, 0.5f, 1.0f, 0.6f, 0.4f, 0.7f, 0.5f, 0.1f};
    float *signals[1] = {samples};
    xcorrs_obj xcorrs = {1U, 8U, signals};
    unsigned int tdoa_values[1] = {2U};
    tdoas_obj tdoas = {1U, 1U, tdoa_values, NULL, NULL};
    unsigned int delta_values[1] = {1U};
    deltas_obj deltas = {1U, delta_values};
    char active[1] = {1};
    pairs_obj pairs = {1U, active};
    /* Bin 4 is the valley preceding the independent peak at bin 5.
     * Preserve it: a descending-shoulder reset must stop before climbing
     * into the next local maximum. */
    const float expected[8] = {0.2f, 0.0f, 0.0f, 0.0f,
                                0.4f, 0.7f, 0.5f, 0.1f};
    const float unchanged[8] = {0.2f, 0.5f, 1.0f, 0.6f,
                                0.4f, 0.7f, 0.5f, 0.1f};
    unsigned int i;
    xcorr2xcorr_process_reset(&reset, &tdoas, &deltas, &pairs, 0U, &xcorrs);
    if (check(samples, expected, 8U, "local shoulder")) return EXIT_FAILURE;

    /* Disabled pair must not be altered. */
    for (i = 0; i < 8U; ++i) samples[i] = unchanged[i];
    active[0] = 0;
    xcorr2xcorr_process_reset(&reset, &tdoas, &deltas, &pairs, 0U, &xcorrs);
    if (check(samples, unchanged, 8U, "disabled pair")) return EXIT_FAILURE;

    /* A spatial point index beyond nPoints must leave all correlations intact.
     * Without the guard, this reads beyond the flattened TDOA table. */
    active[0] = 1;
    xcorr2xcorr_process_reset(&reset, &tdoas, &deltas, &pairs,
                              tdoas.nPoints, &xcorrs);
    if (check(samples, unchanged, 8U, "out-of-range spatial point"))
        return EXIT_FAILURE;

    /* Invalid point and wide boundary delta must not overflow. */
    active[0] = 1;
    tdoa_values[0] = 8U;
    xcorr2xcorr_process_reset(&reset, &tdoas, &deltas, &pairs, 0U, &xcorrs);
    if (check(samples, unchanged, 8U, "invalid index")) return EXIT_FAILURE;
    tdoa_values[0] = 0U;
    delta_values[0] = 20U;
    xcorr2xcorr_process_reset(&reset, &tdoas, &deltas, &pairs, 0U, &xcorrs);
    for (i = 0; i < 8U; ++i) {
        if (samples[i] != 0.0f) return EXIT_FAILURE;
    }
    /*
     * Two active microphone pairs and a second spatial point must use the
     * pair-specific TDOA.  Suppressing one candidate must not erase the
     * independent pair's distant peak (the overlapping-voice hypothesis).
     */
    {
        xcorr2xcorr_obj multi_reset = {8U};
        float a[8] = {0.0f, 0.2f, 0.9f, 0.3f, 0.0f, 0.7f, 0.2f, 0.0f};
        float b[8] = {0.0f, 0.8f, 0.1f, 0.0f, 0.4f, 0.9f, 0.3f, 0.0f};
        float *multi_signals[2] = {a, b};
        xcorrs_obj multi_xcorrs = {2U, 8U, multi_signals};
        /* Point 0: [2, 5], point 1: [5, 1]. */
        unsigned int multi_tdoa_values[4] = {2U, 5U, 5U, 1U};
        tdoas_obj multi_tdoas = {2U, 2U, multi_tdoa_values, NULL, NULL};
        unsigned int multi_deltas[2] = {1U, 0U};
        deltas_obj multi_delta_obj = {2U, multi_deltas};
        char multi_active[2] = {1, 1};
        pairs_obj multi_pairs = {2U, multi_active};
        const float expected_a[8] = {0.0f, 0.2f, 0.9f, 0.3f,
                                     0.0f, 0.0f, 0.0f, 0.0f};
        /* Pair 1 uses delta=0 at bin 1; bin 2 is a descending
         * shoulder (0.8 -> 0.1 -> 0.0), not an independent peak.
         * The reset must remove bin 2 while preserving the distant
         * peak at bin 5. */
        const float expected_b[8] = {0.0f, 0.0f, 0.0f, 0.0f,
                                     0.4f, 0.9f, 0.3f, 0.0f};
        xcorr2xcorr_process_reset(&multi_reset, &multi_tdoas,
                                  &multi_delta_obj, &multi_pairs,
                                  1U, &multi_xcorrs);
        if (check(a, expected_a, 8U, "point1 pair0")) return EXIT_FAILURE;
        if (check(b, expected_b, 8U, "point1 pair1")) return EXIT_FAILURE;
    }
    /* Long monotonic shoulder must not erase a distant weak source.
     * This was the failure mode observed in real-speech T03 after
     * unbounded valley expansion; a local test is necessary, not sufficient.
     */
    {
        xcorr2xcorr_obj local = {12U};
        float long_shoulder[12] = {0.0f, 0.1f, 0.5f, 1.0f,
                                   0.9f, 0.8f, 0.7f, 0.6f,
                                   0.5f, 0.4f, 0.7f, 0.0f};
        float *channel[1] = {long_shoulder};
        xcorrs_obj corr = {1U, 12U, channel};
        unsigned int point[1] = {3U};
        tdoas_obj tdoa = {1U, 1U, point, NULL, NULL};
        unsigned int radius[1] = {1U};
        deltas_obj d = {1U, radius};
        char enabled[1] = {1};
        pairs_obj p = {1U, enabled};
        xcorr2xcorr_process_reset(&local, &tdoa, &d, &p, 0U, &corr);
        if (long_shoulder[3] != 0.0f || long_shoulder[4] != 0.0f ||
            long_shoulder[5] != 0.0f || long_shoulder[6] != 0.7f ||
            long_shoulder[10] != 0.7f) {
            fprintf(stderr, "bounded shoulder erased distant correlation\\n");
            return EXIT_FAILURE;
        }
    }
    /* A weaker local maximum inside the optional shoulder must survive.
     * Its amplitude is below the selected peak, but its adjacent bins
     * make it a separate candidate rather than a monotonic shoulder.
     */
    {
        xcorr2xcorr_obj local = {10U};
        float two_peaks[10] = {0.0f, 0.1f, 1.0f, 0.3f, 0.7f,
                               0.2f, 0.1f, 0.0f, 0.0f, 0.0f};
        float *channel[1] = {two_peaks};
        xcorrs_obj corr = {1U, 10U, channel};
        unsigned int point[1] = {2U};
        tdoas_obj tdoa = {1U, 1U, point, NULL, NULL};
        unsigned int radius[1] = {1U};
        deltas_obj d = {1U, radius};
        char enabled[1] = {1};
        pairs_obj p = {1U, enabled};
        xcorr2xcorr_process_reset(&local, &tdoa, &d, &p, 0U, &corr);
        if (two_peaks[4] != 0.7f || two_peaks[2] != 0.0f) {
            fprintf(stderr, "secondary local maximum erased\\n");
            return EXIT_FAILURE;
        }
    }
    puts("valley-bounded SSL TDOA suppression contract PASS");
    return EXIT_SUCCESS;
}
