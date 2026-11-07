
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
         * The upstream constant 'epsilon + product(local_evidence)' couples
         * all SSL candidates: adding a weak extra candidate can drive the
         * global evidence product below epsilon and suppress the birth
         * posterior of every otherwise unchanged source.
         *
         * Treat epsilon as an explicit "unmodelled / no assignment" mass
         * for EACH potential source instead. Labels {-2, -1, tracks}
         * retain their original likelihoods and priors; the extra mass
         * is independent for each candidate. With epsilon == 0, this is
         * algebraically identical to the exhaustive upstream model.
         *
         * Computing these independent marginals and their track-union
         * probabilities requires O(nPots * (nTracks+2)) work, no per-hop
         * allocations and no products across unrelated SSL candidates.
         */
        {
            const double epsilon = isfinite(obj->epsilon) && obj->epsilon > 0.0f
                                       ? (double)obj->epsilon : 0.0;

            for (iPot = 0; iPot < mixture->nPots; ++iPot) {
                double mass = epsilon;

                for (iTrackNewFalse = 0;
                     iTrackNewFalse < mixture->nTracksNewFalse;
                     ++iTrackNewFalse) {
                    const unsigned int k = iTrackNewFalse * mixture->nPots + iPot;
                    const double term = (double)mixture->p_Eszs_phics[k] *
                                        (double)mixture->p_phics[k];
                    if (isfinite(term) && term > 0.0) {
                        mass += term;
                    }
                }

                if (!isfinite(mass) || mass <= 0.0) {
                    postprobs->arrayNew[iPot] = 0.0f;
                    for (iTrack = 0; iTrack < mixture->nTracks; ++iTrack) {
                        postprobs->arrayTrack[iTrack * mixture->nPots + iPot] = 0.0f;
                    }
                    continue;
                }

                /* Label -1 denotes a new source; -2 denotes a false peak. */
                {
                    const unsigned int k = mixture->nPots + iPot;
                    const double q = (double)mixture->p_Eszs_phics[k] *
                                     (double)mixture->p_phics[k];
                    postprobs->arrayNew[iPot] =
                        (float)(isfinite(q) && q > 0.0 ? q / mass : 0.0);
                }

                for (iTrack = 0; iTrack < mixture->nTracks; ++iTrack) {
                    const unsigned int k = (iTrack + 2U) * mixture->nPots + iPot;
                    const double q = (double)mixture->p_Eszs_phics[k] *
                                     (double)mixture->p_phics[k];
                    postprobs->arrayTrack[iTrack * mixture->nPots + iPot] =
                        (float)(isfinite(q) && q > 0.0 ? q / mass : 0.0);
                }
            }

            /*
             * The assignment labels are independent. The probability that
             * any potential belongs to an existing track is the complement
             * of all candidates NOT belonging to that track.
             */
            for (iTrack = 0; iTrack < mixture->nTracks; ++iTrack) {
                double none_match = 1.0;
                for (iPot = 0; iPot < mixture->nPots; ++iPot) {
                    const unsigned int k = iTrack * mixture->nPots + iPot;
                    const double p = (double)postprobs->arrayTrack[k];
                    none_match *= 1.0 - fmin(1.0, fmax(0.0, p));
                }
                postprobs->arrayTrackTotal[iTrack] = (float)(1.0 - none_match);
            }
        }

    }
