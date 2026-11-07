
   /**
    * \file     mixture2mixture.c
    * \author   François Grondin <francois.grondin2@usherbrooke.ca>
    * \version  2.0
    * \date     2018-03-18
    * \copyright
    *
    * Permission is hereby granted, free of charge, to any person obtaining
    * a copy of this software and associated documentation files (the
    * "Software"), to deal in the Software without restriction, including
    * without limitation the rights to use, copy, modify, merge, publish,
    * distribute, sublicense, and/or sell copies of the Software, and to
    * permit persons to whom the Software is furnished to do so, subject to
    * the following conditions:
    *
    * The above copyright notice and this permission notice shall be
    * included in all copies or substantial portions of the Software.
    *
    * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
    * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
    * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
    * NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
    * LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
    * OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
    * WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
    *
    */

    #include <system/mixture2mixture.h>

    mixture2mixture_obj * mixture2mixture_construct(const gaussians_1d_obj * active_gmm, const gaussians_1d_obj * inactive_gmm, const float diffuse_cst, const float Pfalse, const float Pnew, const float Ptrack, const float epsilon) {

        mixture2mixture_obj * obj;

        obj = (mixture2mixture_obj *) malloc(sizeof(mixture2mixture_obj));

        obj->active = gaussians_1d_construct_gaussians(active_gmm);
        obj->inactive = gaussians_1d_construct_gaussians(inactive_gmm);
        obj->diffuse = diffuse_cst;

        obj->Pfalse = Pfalse;
        obj->Pnew = Pnew;
        obj->Ptrack = Ptrack;
        obj->epsilon = epsilon;

        return obj;

    }

    void mixture2mixture_destroy(mixture2mixture_obj * obj) {

        gaussians_1d_destroy(obj->active);
        gaussians_1d_destroy(obj->inactive);

        free((void *) obj);

    }

    void mixture2mixture_process(mixture2mixture_obj * obj, mixture_obj * mixture, const pots_obj * pots, const coherences_obj * coherences, postprobs_obj * postprobs) {

        unsigned int iPot;
        unsigned int iTrack;
        unsigned int iTrackNewFalse;

        signed int t;

        // Compute likelihood

        // p(E^s_l|A), p(E^s_l|I) & p(z^s_l|D)

        for (iPot = 0; iPot < mixture->nPots; iPot++) {

            mixture->p_Ez_AICD[0 * pots->nPots + iPot] = gaussians_1d_eval(obj->active, pots->array[iPot * 4 + 3]);
            mixture->p_Ez_AICD[1 * pots->nPots + iPot] = gaussians_1d_eval(obj->inactive, pots->array[iPot * 4 + 3]);
            mixture->p_Ez_AICD[2 * pots->nPots + iPot] = obj->diffuse;

        }

        // p(z^s_l|C,t)

        for (iTrack = 0; iTrack < mixture->nTracks; iTrack++) {

            for (iPot = 0; iPot < mixture->nPots; iPot++) {

                mixture->p_Ez_AICD[(3 + iTrack) * pots->nPots + iPot] = coherences->array[iTrack * mixture->nPots + iPot];

            }

        }

        // p(E^s_l,z^s_l|phis_c)

        for (iPot = 0; iPot < mixture->nPots; iPot++) {

            for (iTrackNewFalse = 0; iTrackNewFalse < mixture->nTracksNewFalse; iTrackNewFalse++) {

                t = (((signed int) iTrackNewFalse) - 2);

                if (t == -2) {

                    mixture->p_Eszs_phics[iTrackNewFalse * mixture->nPots + iPot] = mixture->p_Ez_AICD[1 * pots->nPots + iPot] * mixture->p_Ez_AICD[2 * pots->nPots + iPot];

                }
                else if (t == -1) {

                    mixture->p_Eszs_phics[iTrackNewFalse * mixture->nPots + iPot] = mixture->p_Ez_AICD[0 * pots->nPots + iPot] * mixture->p_Ez_AICD[2 * pots->nPots + iPot];

                }
                else {

                    mixture->p_Eszs_phics[iTrackNewFalse * mixture->nPots + iPot] = mixture->p_Ez_AICD[0 * pots->nPots + iPot] * mixture->p_Ez_AICD[(t + 3) * pots->nPots + iPot];

                }

            }

        }

        // Prior probabilities

        for (iPot = 0; iPot < mixture->nPots; iPot++) {

            for (iTrackNewFalse = 0; iTrackNewFalse < mixture->nTracksNewFalse; iTrackNewFalse++) {

                t = (((signed int) iTrackNewFalse) - 2);

                if (t == -2) {

                    mixture->p_phics[iTrackNewFalse * mixture->nPots + iPot] = obj->Pfalse;

                }
                else if (t == -1) {

                    mixture->p_phics[iTrackNewFalse * mixture->nPots + iPot] = obj->Pnew;

                }
                else {

                    mixture->p_phics[iTrackNewFalse * mixture->nPots + iPot] = obj->Ptrack;

                }                    

            }

        }

        /*
         * Exact factorization of the upstream joint assignment posterior.
         *
         * combining_generate() enumerated all (nTracks+2)^nPots labels,
         * despite imposing NO one-to-one constraint on assignments.
         * Consequently the joint likelihood is the product of the local
         * evidence masses, and each marginal can be calculated directly.
         *
         * Preserve upstream's global epsilon mass, evaluated in log space
         * to avoid underflow in products of many small probabilities.
         * The work is O(nPots * (nTracks+2)) with no per-hop allocation.
         */
        {
            double log_evidence = 0.0;
            double evidence_scale = 1.0;
            int has_zero_mass = 0;

            for (iPot = 0; iPot < mixture->nPots; ++iPot) {
                double mass = 0.0;

                for (iTrackNewFalse = 0;
                     iTrackNewFalse < mixture->nTracksNewFalse;
                     ++iTrackNewFalse) {
                    const unsigned int k = iTrackNewFalse * mixture->nPots + iPot;
                    const double term = (double) mixture->p_Eszs_phics[k] *
                                        (double) mixture->p_phics[k];

                    if (isfinite(term) && term > 0.0) {
                        mass += term;
                    }
                }

                if (mass > 0.0) {
                    log_evidence += log(mass);
                } else {
                    has_zero_mass = 1;
                }
            }

            if (has_zero_mass != 0) {
                evidence_scale = 0.0;
            } else if (obj->epsilon > 0.0f) {
                /* E/(epsilon+E) without ever forming E = exp(log_evidence). */
                const double log_ratio = log((double) obj->epsilon) - log_evidence;
                if (log_ratio >= 0.0) {
                    const double ratio = exp(-log_ratio);
                    evidence_scale = ratio / (1.0 + ratio);
                } else {
                    evidence_scale = 1.0 / (1.0 + exp(log_ratio));
                }
            }

            for (iPot = 0; iPot < mixture->nPots; ++iPot) {
                double mass = 0.0;

                for (iTrackNewFalse = 0;
                     iTrackNewFalse < mixture->nTracksNewFalse;
                     ++iTrackNewFalse) {
                    const unsigned int k = iTrackNewFalse * mixture->nPots + iPot;
                    const double term = (double) mixture->p_Eszs_phics[k] *
                                        (double) mixture->p_phics[k];

                    if (isfinite(term) && term > 0.0) {
                        mass += term;
                    }
                }

                if (mass <= 0.0 || evidence_scale <= 0.0) {
                    postprobs->arrayNew[iPot] = 0.0f;
                    for (iTrack = 0; iTrack < mixture->nTracks; ++iTrack) {
                        postprobs->arrayTrack[iTrack * mixture->nPots + iPot] = 0.0f;
                    }
                    continue;
                }

                /* Label -1 denotes a new source, label -2 is false. */
                {
                    const unsigned int k = mixture->nPots + iPot;
                    const double new_mass =
                        (double) mixture->p_Eszs_phics[k] *
                        (double) mixture->p_phics[k];
                    postprobs->arrayNew[iPot] =
                        (float) (evidence_scale * new_mass / mass);
                }

                for (iTrack = 0; iTrack < mixture->nTracks; ++iTrack) {
                    const unsigned int k = (iTrack + 2U) * mixture->nPots + iPot;
                    const double match_mass =
                        (double) mixture->p_Eszs_phics[k] *
                        (double) mixture->p_phics[k];
                    /* Temporarily store the local match probability. */
                    postprobs->arrayTrack[iTrack * mixture->nPots + iPot] =
                        (float) (match_mass / mass);
                }
            }

            /*
             * Probability that at least one potential matches this track:
             * 1 - product(1 - local_match_probability). Because the old
             * enumeration also includes epsilon in the denominator, apply
             * the same global evidence_scale to this union probability.
             */
            for (iTrack = 0; iTrack < mixture->nTracks; ++iTrack) {
                double none_match = 1.0;
                for (iPot = 0; iPot < mixture->nPots; ++iPot) {
                    const unsigned int k = iTrack * mixture->nPots + iPot;
                    const double p = (double) postprobs->arrayTrack[k];
                    none_match *= 1.0 - fmin(1.0, fmax(0.0, p));
                    postprobs->arrayTrack[k] = (float) (evidence_scale * p);
                }
                postprobs->arrayTrackTotal[iTrack] =
                    (float) (evidence_scale * (1.0 - none_match));
            }
        }

    }
