/* O2 regression: two or more SSL candidates can cross theta_new in one hop.
 * A pending birth reserves its slot immediately even before ids[] commit.
 * This tests the actual private predicate used by mod_sst_process.
 */
#include <stdio.h>
#include <stdlib.h>
#include "../src/module/sst_slot_reservation.h"

static unsigned int first_slot(const unsigned long long *ids,
                               const unsigned long long *pending,
                               unsigned int count) {
    unsigned int slot;
    for (slot = 0U; slot < count; ++slot) {
        if (sst_slot_available(ids, pending, slot))
            return slot;
    }
    return count;
}

static int check(unsigned int actual, unsigned int expected, const char *test) {
    if (actual == expected) return 0;
    fprintf(stderr, "%s: slot %u != expected %u\n", test, actual, expected);
    return 1;
}

int main(void) {
    unsigned long long ids[4] = {0ULL, 7ULL, 0ULL, 0ULL};
    unsigned long long pending[4] = {0ULL, 0ULL, 0ULL, 0ULL};
    unsigned int slot;
    unsigned int errors = 0U;
    unsigned long long next = 10ULL;

    /* Three real-candidate-equivalent decisions in ONE hop. The historic
     * implementation incorrectly returned slot 0 for every iteration. */
    slot = first_slot(ids, pending, 4U);
    errors += check(slot, 0U, "first birth");
    pending[slot] = next++;
    slot = first_slot(ids, pending, 4U);
    errors += check(slot, 2U, "second birth must not overwrite pending");
    pending[slot] = next++;
    slot = first_slot(ids, pending, 4U);
    errors += check(slot, 3U, "third birth must use third distinct slot");
    pending[slot] = next++;
    errors += check(first_slot(ids, pending, 4U), 4U, "at capacity");
    if (pending[0] != 10ULL || pending[2] != 11ULL ||
        pending[3] != 12ULL || ids[1] != 7ULL) {
        fprintf(stderr, "pending IDs overwritten or existing track changed\n");
        ++errors;
    }

    /* Committing a birth frees the pending reservation but occupies the slot
     * in ids[] instead; this slot stays unavailable. */
    ids[2] = pending[2];
    pending[2] = 0ULL;
    errors += check(first_slot(ids, pending, 4U), 4U,
                    "committed birth remains occupied");

    /* Retirement/reuse: clearing id AND pending makes a slot available. */
    ids[1] = 0ULL;
    errors += check(first_slot(ids, pending, 4U), 1U,
                    "retired track slot can be reused");
    pending[1] = 999ULL;
    errors += check(first_slot(ids, pending, 4U), 4U,
                    "new reservation persists until commit");

    errors += check(first_slot(ids, pending, 0U), 0U, "zero slots");
    /* Untouched empty slots must still be available. */
    {
        unsigned long long empty_ids[1] = {0ULL};
        unsigned long long empty_pending[1] = {0ULL};
        errors += check(first_slot(empty_ids, empty_pending, 1U), 0U,
                        "single empty slot");
        empty_pending[0] = 1ULL;
        errors += check(first_slot(empty_ids, empty_pending, 1U), 1U,
                        "single pending slot");
        empty_pending[0] = 0ULL;
        empty_ids[0] = 1ULL;
        errors += check(first_slot(empty_ids, empty_pending, 1U), 1U,
                        "single occupied slot");
    }
    if (errors != 0U) return EXIT_FAILURE;
    puts("SST birth reservations are unique until end-of-hop commit");
    return EXIT_SUCCESS;
}
