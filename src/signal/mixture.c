   
   /**
    * \file     mixture.c
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
    
    #include <signal/mixture.h>

    /*
     * The SST mixture's assignments are independent across SSL potential
     * sources. Their posterior marginals can be evaluated exactly without
     * constructing (nTracks+2)^nPots combinations.
     *
     * Keep the original structure members for source compatibility; the
     * legacy combinatorial workspaces are intentionally left NULL.
     */
    mixture_obj * mixture_construct_zero(const unsigned int nPots, const unsigned int nTracks) {

        mixture_obj * obj = (mixture_obj *) calloc(1, sizeof(mixture_obj));

        if (obj == NULL) {
            return NULL;
        }

        obj->nPots = nPots;
        obj->nTracks = nTracks;
        obj->nTracksNewFalse = nTracks + 2U;
        obj->nCombinations = 0U;
        obj->assignations = NULL;

        obj->p_Ez_AICD = (float *) calloc(((size_t) nTracks + 3U) * nPots, sizeof(float));
        obj->p_Eszs_phics = (float *) calloc(((size_t) nTracks + 2U) * nPots, sizeof(float));
        obj->p_phics = (float *) calloc(((size_t) nTracks + 2U) * nPots, sizeof(float));
        obj->p_Ez_phic = NULL;
        obj->p_phic = NULL;
        obj->p_phic_Ez = NULL;

        if ((nPots > 0U) &&
            (obj->p_Ez_AICD == NULL || obj->p_Eszs_phics == NULL ||
             obj->p_phics == NULL)) {
            mixture_destroy(obj);
            return NULL;
        }

        return obj;
    }

    void mixture_destroy(mixture_obj * obj) {

        if (obj == NULL) {
            return;
        }

        if (obj->assignations != NULL) {
            assignations_destroy(obj->assignations);
        }

        free((void *) obj->p_Ez_AICD);
        free((void *) obj->p_Eszs_phics);
        free((void *) obj->p_phics);
        free((void *) obj->p_Ez_phic);
        free((void *) obj->p_phic);
        free((void *) obj->p_phic_Ez);
        free((void *) obj);
    }

    void mixture_printf(const mixture_obj * obj) {

        unsigned int iTrack;
        unsigned int iTrackNewFalse;
        unsigned int iPot;

        printf("p(E|A) = ");
        for (iPot = 0; iPot < obj->nPots; iPot++) {
            printf("%+1.3e ",obj->p_Ez_AICD[0 * obj->nPots + iPot]);
        }
        printf("\n");

        printf("p(E|I) = ");
        for (iPot = 0; iPot < obj->nPots; iPot++) {
            printf("%+1.3e ",obj->p_Ez_AICD[1 * obj->nPots + iPot]);
        }
        printf("\n");

        printf("p(z|D) = ");
        for (iPot = 0; iPot < obj->nPots; iPot++) {
            printf("%+1.3e ",obj->p_Ez_AICD[2 * obj->nPots + iPot]);
        }
        printf("\n");

        for (iTrack = 0; iTrack < obj->nTracks; iTrack++) {
            printf("p(z|C,%u) = ",iTrack);
            for (iPot = 0; iPot < obj->nPots; iPot++) {
                printf("%+1.3e ", obj->p_Ez_AICD[3 * obj->nPots + iPot]);
            }
            printf("\n");
        }
        printf("\n");

        printf("p(E,z|phi(s)):\n");
        for (iTrackNewFalse = 0; iTrackNewFalse < obj->nTracksNewFalse; iTrackNewFalse++) {
            
            printf("  phi = %d: ",iTrackNewFalse-2);
            for (iPot = 0; iPot < obj->nPots; iPot++) {
                printf("%+1.3e ",obj->p_Eszs_phics[iTrackNewFalse * obj->nPots + iPot]);
            }
            printf("\n");

        }
        printf("\n");

        printf("p(phi(s)):\n");
        for (iTrackNewFalse = 0; iTrackNewFalse < obj->nTracksNewFalse; iTrackNewFalse++) {
            
            printf("  phi = %d: ",iTrackNewFalse-2);
            for (iPot = 0; iPot < obj->nPots; iPot++) {
                printf("%+1.3e ",obj->p_phics[iTrackNewFalse * obj->nPots + iPot]);
            }
            printf("\n");

        }
        printf("\n");

        printf("Joint assignments factored: no exponential workspace allocated.\\n");

    }
