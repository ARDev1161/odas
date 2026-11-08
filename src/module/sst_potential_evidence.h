#ifndef ODAS_SST_POTENTIAL_EVIDENCE_H
#define ODAS_SST_POTENTIAL_EVIDENCE_H

#include <math.h>

/*
 * An SSL potential slot can contain a placeholder sphere direction with
 * exactly zero correlation score. Such a slot is NOT measured acoustic
 * evidence, even if a miscalibrated activity GMM assigns it a high
 * posterior probability of a new source.
 *
 * This invariant applies only to dynamic SST source births; no changes
 * to SSL output, established-track updates, or genuine positive-score
 * candidate probabilities. Non-finite inputs are not valid evidence.
 */
static inline int sst_potential_can_birth(float ssl_strength,
                                         float birth_posterior,
                                         float theta_new)
{
    return isfinite(ssl_strength) && ssl_strength > 0.0f &&
           isfinite(birth_posterior) &&
           birth_posterior > theta_new;
}

#endif
