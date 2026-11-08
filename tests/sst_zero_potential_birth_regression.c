/* O2 regression: native SSL can emit a fixed-size nPots array of
 * zero-strength filler candidates at the first sphere point (+Z).
 * A wider active GMM can assign 0.978 birth probability to those empty
 * slots. Never create an SST source from such no-evidence candidates.
 */
#include <float.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#include "../src/module/sst_potential_evidence.h"

static int check(int actual, int expected, const char *label)
{
    if (actual == expected) return 0;
    fprintf(stderr, "%s: got %d, expected %d\n", label, actual, expected);
    return 1;
}

int main(void)
{
    int errors = 0;
    unsigned int i;
    const float theta = 0.9f;

    /* Measured real Acoustix zero-PCM GMM-wide case:
     * zero SSL strength, but posterior nearly 0.978. */
    for (i = 0; i < 4U; ++i) {
        errors += check(sst_potential_can_birth(0.0f, 0.978264868f, theta),
                        0, "four zero-strength SSL placeholder slots");
    }
    errors += check(sst_potential_can_birth(-0.0f, 1.0f, theta), 0,
                    "negative zero does not count as evidence");
    errors += check(sst_potential_can_birth(-0.1f, 1.0f, theta), 0,
                    "negative SSL strength is invalid evidence");
    errors += check(sst_potential_can_birth(NAN, 1.0f, theta), 0,
                    "NaN SSL strength");
    errors += check(sst_potential_can_birth(INFINITY, 1.0f, theta), 0,
                    "infinite SSL strength");
    errors += check(sst_potential_can_birth(0.3f, NAN, theta), 0,
                    "NaN posterior");
    errors += check(sst_potential_can_birth(0.3f, INFINITY, theta), 0,
                    "infinite posterior");
    errors += check(sst_potential_can_birth(0.3f, 0.9f, theta), 0,
                    "birth posterior exactly at strict threshold");
    errors += check(sst_potential_can_birth(0.3f, 0.8f, theta), 0,
                    "real candidate but posterior below threshold");
    errors += check(sst_potential_can_birth(0.3f, 0.95f, theta), 1,
                    "real positive-score candidate above threshold");
    errors += check(sst_potential_can_birth(0.3f, 1.0f, theta), 1,
                    "perfect real positive-score birth posterior");
    errors += check(sst_potential_can_birth(FLT_MIN, 0.95f, theta), 1,
                    "genuinely positive subnormal-boundary score preserved");

    /* No new tunable global floor: real positive SSL evidence retains
     * existing birth threshold behavior. */
    if (errors != 0) return EXIT_FAILURE;
    puts("SST births require strictly positive finite SSL evidence");
    return EXIT_SUCCESS;
}
