/* Deterministic experimental SSL greedy-peak suppression contract.
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
    puts("localized SSL TDOA suppression contract PASS");
    return EXIT_SUCCESS;
}
