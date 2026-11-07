#ifndef ODAS_SST_SLOT_RESERVATION_H
#define ODAS_SST_SLOT_RESERVATION_H

/*
 * Private SST helper: the birth loop reserves idsAdded[] until its
 * end-of-hop commit. An empty ids[] entry is NOT available when another
 * candidate has already reserved it in idsAdded[] on this same hop.
 * No public API or additional runtime allocation.
 */
static inline int sst_slot_available(const unsigned long long *ids,
                                      const unsigned long long *ids_added,
                                      unsigned int slot)
{
    return ids[slot] == 0ULL && ids_added[slot] == 0ULL;
}

#endif
