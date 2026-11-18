
   /**
    * \file     xcorr2xcorr.c
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
    
    #include <system/xcorr2xcorr.h>

    xcorr2xcorr_obj * xcorr2xcorr_construct_zero(const unsigned int frameSize) {

        xcorr2xcorr_obj * obj;

        obj = (xcorr2xcorr_obj *) malloc(sizeof(xcorr2xcorr_obj));

        obj->frameSize = frameSize;

        return obj;

    }

    void xcorr2xcorr_destroy(xcorr2xcorr_obj * obj) {

        free((void *) obj);

    }

    void xcorr2xcorr_process_max(xcorr2xcorr_obj * obj, const xcorrs_obj * xcorrs, const tdoas_obj * tdoas, const deltas_obj * deltas, const pairs_obj * pairs, xcorrs_obj * xcorrsMax) {

        unsigned int iSignal;
        unsigned int iSampleMax;
        unsigned int iSampleMaxLeft;
        unsigned int iSampleMaxRight;
        unsigned int iSample;
        unsigned int delta;
        float maxValue;

        if (obj->frameSize == 0U) {
            return;
        }
        for (iSignal = 0; iSignal < xcorrs->nSignals; iSignal++) {

            if (pairs->array[iSignal] == 0x01) {

                delta = deltas->array[iSignal];
                iSampleMaxLeft = tdoas->min[iSignal];
                iSampleMaxRight = tdoas->max[iSignal];
                if (iSampleMaxLeft >= obj->frameSize) {
                    continue;
                }
                if (iSampleMaxRight >= obj->frameSize) {
                    iSampleMaxRight = obj->frameSize - 1U;
                }

                for (iSampleMax = iSampleMaxLeft; iSampleMax <= iSampleMaxRight; iSampleMax++) {

                    maxValue = xcorrs->array[iSignal][iSampleMax];

                    /* Clamp the smoothing window to the correlation frame.
                     * Unsigned subtraction previously wrapped when a valid
                     * TDOA range reached the first delta bins. */
                    const unsigned int first = iSampleMax > delta
                        ? iSampleMax - delta : 0U;
                    const unsigned int last = delta < obj->frameSize - 1U - iSampleMax
                        ? iSampleMax + delta : obj->frameSize - 1U;
                    for (iSample = first; iSample <= last; iSample++) {

                        if (xcorrs->array[iSignal][iSample] > maxValue) {

                            maxValue = xcorrs->array[iSignal][iSample];

                        }

                    }

                    xcorrsMax->array[iSignal][iSampleMax] = maxValue;

                }

            }

        }

    }

    /*
     * Experimental SSL A/B: suppress only the TDOA neighbourhood of the
     * selected peak.  The upstream reset also erases the entire monotonic
     * shoulder on both sides; a weaker overlapping speaker can occupy
     * that shoulder and disappear before the next SSL proposal.
     *
     * Keep this isolated in a feature branch until paired Acoustix tests
     * demonstrate increased independent-source recall without ghosts.
     */
    void xcorr2xcorr_process_reset(xcorr2xcorr_obj * obj, const tdoas_obj * tdoas, const deltas_obj * deltas, const pairs_obj * pairs, const unsigned int iPoint, xcorrs_obj * xcorrs) {

        unsigned int iSignal;

        /* Reject an invalid spatial point before indexing the flattened
         * [nPoints][nPairs] TDOA table. */
        if (iPoint >= tdoas->nPoints) {
            return;
        }

        for (iSignal = 0; iSignal < xcorrs->nSignals; iSignal++) {

            if (pairs->array[iSignal] == 0x01) {

                const unsigned int middle = tdoas->array[iPoint * tdoas->nPairs + iSignal];
                if (obj->frameSize == 0U || middle >= obj->frameSize) {
                    continue;
                }
                const unsigned int delta = deltas->array[iSignal];
                const unsigned int left = middle > delta ? middle - delta : 0U;
                const unsigned int right = delta < obj->frameSize - 1U - middle
                    ? middle + delta : obj->frameSize - 1U;

                /*
                 * Extend the mandatory +/-delta reset only along a
                 * descending shoulder, stopping at the first valley.
                 * A distant independent peak must survive, while a
                 * broad single-source shoulder should not be proposed
                 * repeatedly as another spatial source. This is an
                 * experimental hypothesis requiring paired A/B evidence.
                 */
                /* Preserve the endpoint bin: it may contain a separate peak or
                 * a correlation boundary, not a continuation of this shoulder. */
                unsigned int start = left;
                unsigned int end = right;
                /*
                 * Bound shoulder expansion to the local TDOA resolution.
                 * The unbounded valley walk erased weaker independent
                 * candidates on real two-speaker Acoustix T03. This cap is
                 * experimental and must pass the frozen three-way A/B.
                 */
                /* Test a two-resolution shoulder cap against the frozen real-speech A/B.
                 * A one-resolution cap left persistent ghost candidates on T02.
                 * The local-maximum guards still protect distinct secondary peaks.
                 * This is an experiment, not an accepted quality improvement. */
                const unsigned int extra = delta > 0U
                    ? (delta > obj->frameSize / 2U ? obj->frameSize : 2U * delta)
                    : 1U;
                unsigned int leftSteps = 0U;
                unsigned int rightSteps = 0U;
                /*
                 * Do not consume a distinct local maximum while following a
                 * shoulder. A weaker second-source peak can be lower than
                 * the selected peak yet higher than both its neighbours.
                 * This is a hypothesis; Acoustix A/B must reject it if
                 * false SST tracks increase.
                 */
                while (start > 1U && leftSteps < extra &&
                       xcorrs->array[iSignal][start - 1U] <=
                           xcorrs->array[iSignal][start] &&
                       (start <= 2U ||
                        xcorrs->array[iSignal][start - 1U] >=
                            xcorrs->array[iSignal][start - 2U])) {
                    --start;
                    ++leftSteps;
                }
                while (end + 1U < obj->frameSize && rightSteps < extra &&
                       xcorrs->array[iSignal][end + 1U] <=
                           xcorrs->array[iSignal][end] &&
                       (end + 2U >= obj->frameSize ||
                        xcorrs->array[iSignal][end + 1U] >=
                            xcorrs->array[iSignal][end + 2U])) {
                    ++end;
                    ++rightSteps;
                }
                memset(&(xcorrs->array[iSignal][start]), 0x00,
                       sizeof(float) * (end - start + 1U));

            }

        }

    }
