
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

        for (iSignal = 0; iSignal < xcorrs->nSignals; iSignal++) {

            if (pairs->array[iSignal] == 0x01) {

                delta = deltas->array[iSignal];
                iSampleMaxLeft = tdoas->min[iSignal];
                iSampleMaxRight = tdoas->max[iSignal];

                for (iSampleMax = iSampleMaxLeft; iSampleMax <= iSampleMaxRight; iSampleMax++) {

                    maxValue = xcorrs->array[iSignal][iSampleMax];

                    for (iSample = (iSampleMax-delta); iSample <= (iSampleMax+delta); iSample++) {

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

        for (iSignal = 0; iSignal < xcorrs->nSignals; iSignal++) {

            if (pairs->array[iSignal] == 0x01) {

                const unsigned int middle = tdoas->array[iPoint * tdoas->nPairs + iSignal];
                if (obj->frameSize == 0U || middle >= obj->frameSize) {\n                    continue;\n                }\n                const unsigned int delta = deltas->array[iSignal];
                const unsigned int left = middle > delta ? middle - delta : 0U;
                const unsigned int right = delta < obj->frameSize - 1U - middle
                    ? middle + delta : obj->frameSize - 1U;

                memset(&(xcorrs->array[iSignal][left]), 0x00,
                       sizeof(float) * (right - left + 1U));

            }

        }

    }
