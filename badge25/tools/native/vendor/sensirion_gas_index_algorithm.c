/*
 * Copyright (c) 2022, Sensirion AG
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * * Redistributions of source code must retain the above copyright notice, this
 *   list of conditions and the following disclaimer.
 *
 * * Redistributions in binary form must reproduce the above copyright notice,
 *   this list of conditions and the following disclaimer in the documentation
 *   and/or other materials provided with the distribution.
 *
 * * Neither the name of Sensirion AG nor the names of its
 *   contributors may be used to endorse or promote products derived from
 *   this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 */

#include "sensirion_gas_index_algorithm.h"

/*!< the maximum value of fix16_t */
#define FIX16_MAXIMUM 0x7FFFFFFF
/*!< the minimum value of fix16_t */
#define FIX16_MINIMUM 0x80000000
/*!< the value used to indicate overflows when FIXMATH_NO_OVERFLOW is not
 * specified */
#define FIX16_OVERFLOW 0x80000000
/*!< fix16_t value of 1 */
#define FIX16_ONE 0x00010000

static inline fix16_t fix16_from_int(int32_t a) {
    return a * FIX16_ONE;
}

static inline int32_t fix16_cast_to_int(fix16_t a) {
    return (a >= 0) ? (a >> 16) : -((-a) >> 16);
}

/*! Multiplies the two given fix16_t's and returns the result. */
static fix16_t fix16_mul(fix16_t inArg0, fix16_t inArg1);

/*! Divides the first given fix16_t by the second and returns the result. */
static fix16_t fix16_div(fix16_t inArg0, fix16_t inArg1);

/*! Returns the square root of the given fix16_t. */
static fix16_t fix16_sqrt(fix16_t inValue);

/*! Returns the exponent (e^) of the given fix16_t. */
static fix16_t fix16_exp(fix16_t inValue);

static fix16_t fix16_mul(fix16_t inArg0, fix16_t inArg1) {
    // Each argument is divided to 16-bit parts.
    //					AB
    //			*	 CD
    // -----------
    //					BD	16 * 16 -> 32 bit products
    //				 CB
    //				 AD
    //				AC
    //			 |----| 64 bit product
    uint32_t absArg0 = (uint32_t)((inArg0 >= 0) ? inArg0 : (-inArg0));
    uint32_t absArg1 = (uint32_t)((inArg1 >= 0) ? inArg1 : (-inArg1));
    uint32_t A = (absArg0 >> 16), C = (absArg1 >> 16);
    uint32_t B = (absArg0 & 0xFFFF), D = (absArg1 & 0xFFFF);

    uint32_t AC = A * C;
    uint32_t AD_CB = A * D + C * B;
    uint32_t BD = B * D;

    uint32_t product_hi = AC + (AD_CB >> 16);

    // Handle carry from lower 32 bits to upper part of result.
    uint32_t ad_cb_temp = AD_CB << 16;
    uint32_t product_lo = BD + ad_cb_temp;
    if (product_lo < BD)
        product_hi++;

#ifndef FIXMATH_NO_OVERFLOW
    // The upper 17 bits should all be zero.
    if (product_hi >> 15)
        return (fix16_t)FIX16_OVERFLOW;
#endif

#ifdef FIXMATH_NO_ROUNDING
    fix16_t result = (fix16_t)((product_hi << 16) | (product_lo >> 16));
    if ((inArg0 < 0) != (inArg1 < 0))
        result = -result;
    return result;
#else
    // Adding 0x8000 (= 0.5) and then using right shift
    // achieves proper rounding to result.
    // Handle carry from lower to upper part.
    uint32_t product_lo_tmp = product_lo;
    product_lo += 0x8000;
    if (product_lo < product_lo_tmp)
        product_hi++;

    // Discard the lowest 16 bits and convert back to signed result.
    fix16_t result = (fix16_t)((product_hi << 16) | (product_lo >> 16));
    if ((inArg0 < 0) != (inArg1 < 0))
        result = -result;
    return result;
#endif
}

static fix16_t fix16_div(fix16_t a, fix16_t b) {
    // This uses the basic binary restoring division algorithm.
    // It appears to be faster to do the whole division manually than
    // trying to compose a 64-bit divide out of 32-bit divisions on
    // platforms without hardware divide.

    if (b == 0)
        return (fix16_t)FIX16_MINIMUM;

    uint32_t remainder = (uint32_t)((a >= 0) ? a : (-a));
    uint32_t divider = (uint32_t)((b >= 0) ? b : (-b));

    uint32_t quotient = 0;
    uint32_t bit = 0x10000;

    /* The algorithm requires D >= R */
    while (divider < remainder) {
        divider <<= 1;
        bit <<= 1;
    }

#ifndef FIXMATH_NO_OVERFLOW
    if (!bit)
        return (fix16_t)FIX16_OVERFLOW;
#endif

    if (divider & 0x80000000) {
        // Perform one step manually to avoid overflows later.
        // We know that divider's bottom bit is 0 here.
        if (remainder >= divider) {
            quotient |= bit;
            remainder -= divider;
        }
        divider >>= 1;
        bit >>= 1;
    }

    /* Main division loop */
    while (bit && remainder) {
        if (remainder >= divider) {
            quotient |= bit;
            remainder -= divider;
        }

        remainder <<= 1;
        bit >>= 1;
    }

#ifndef FIXMATH_NO_ROUNDING
    if (remainder >= divider) {
        quotient++;
    }
#endif

    fix16_t result = (fix16_t)quotient;

    /* Figure out the sign of result */
    if ((a < 0) != (b < 0)) {
#ifndef FIXMATH_NO_OVERFLOW
        if (result == (fix16_t)FIX16_MINIMUM)
            return (fix16_t)FIX16_OVERFLOW;
#endif

        result = -result;
    }

    return result;
}

static fix16_t fix16_sqrt(fix16_t x) {
    // It is assumed that x is not negative

    uint32_t num = (uint32_t)x;
    uint32_t result = 0;
    uint32_t bit;
    uint8_t n;

    bit = (uint32_t)1 << 30;
    while (bit > num)
        bit >>= 2;

    // The main part is executed twice, in order to avoid
    // using 64 bit values in computations.
    for (n = 0; n < 2; n++) {
        // First we get the top 24 bits of the answer.
        while (bit) {
            if (num >= result + bit) {
                num -= result + bit;
                result = (result >> 1) + bit;
            } else {
                result = (result >> 1);
            }
            bit >>= 2;
        }

        if (n == 0) {
            // Then process it again to get the lowest 8 bits.
            if (num > 65535) {
                // The remainder 'num' is too large to be shifted left
                // by 16, so we have to add 1 to result manually and
                // adjust 'num' accordingly.
                // num = a - (result + 0.5)^2
                //	 = num + result^2 - (result + 0.5)^2
                //	 = num - result - 0.5
                num -= result;
                num = (num << 16) - 0x8000;
                result = (result << 16) + 0x8000;
            } else {
                num <<= 16;
                result <<= 16;
            }

            bit = 1 << 14;
        }
    }

#ifndef FIXMATH_NO_ROUNDING
    // Finally, if next bit would have been 1, round the result upwards.
    if (num > result) {
        result++;
    }
#endif

    return (fix16_t)result;
}

static fix16_t fix16_exp(fix16_t x) {
    // Function to approximate exp(); optimized more for code size than speed

    // exp(x) for x = +/- {1, 1/8, 1/64, 1/512}
#define NUM_EXP_VALUES 4
    static const fix16_t exp_pos_values[NUM_EXP_VALUES] = {
        F16(2.7182818), F16(1.1331485), F16(1.0157477), F16(1.0019550)};
    static const fix16_t exp_neg_values[NUM_EXP_VALUES] = {
        F16(0.3678794), F16(0.8824969), F16(0.9844964), F16(0.9980488)};
    const fix16_t* exp_values;

    fix16_t res, arg;
    uint16_t i;

    if (x >= F16(10.3972))
        return FIX16_MAXIMUM;
    if (x <= F16(-11.7835))
        return 0;

    if (x < 0) {
        x = -x;
        exp_values = exp_neg_values;
    } else {
        exp_values = exp_pos_values;
    }

    res = FIX16_ONE;
    arg = FIX16_ONE;
    for (i = 0; i < NUM_EXP_VALUES; i++) {
        while (x >= arg) {
            res = fix16_mul(res, exp_values[i]);
            x -= arg;
        }
        arg >>= 3;
    }
    return res;
}

static void GasIndexAlgorithm__init_instances(GasIndexAlgorithmParams* params);
static void GasIndexAlgorithm__mean_variance_estimator__set_parameters(
    GasIndexAlgorithmParams* params);
static void GasIndexAlgorithm__mean_variance_estimator__set_states(
    GasIndexAlgorithmParams* params, fix16_t mean, fix16_t std,
    fix16_t uptime_gamma);
static fix16_t GasIndexAlgorithm__mean_variance_estimator__get_std(
    const GasIndexAlgorithmParams* params);
static fix16_t GasIndexAlgorithm__mean_variance_estimator__get_mean(
    const GasIndexAlgorithmParams* params);
static bool GasIndexAlgorithm__mean_variance_estimator__is_initialized(
    GasIndexAlgorithmParams* params);
static void GasIndexAlgorithm__mean_variance_estimator___calculate_gamma(
    GasIndexAlgorithmParams* params);
static void GasIndexAlgorithm__mean_variance_estimator__process(
    GasIndexAlgorithmParams* params, fix16_t sraw);
static void
GasIndexAlgorithm__mean_variance_estimator___sigmoid__set_parameters(
    GasIndexAlgorithmParams* params, fix16_t X0, fix16_t K);
static fix16_t GasIndexAlgorithm__mean_variance_estimator___sigmoid__process(
    GasIndexAlgorithmParams* params, fix16_t sample);
static void GasIndexAlgorithm__mox_model__set_parameters(
    GasIndexAlgorithmParams* params, fix16_t SRAW_STD, fix16_t SRAW_MEAN);
static fix16_t
GasIndexAlgorithm__mox_model__process(GasIndexAlgorithmParams* params,
                                      fix16_t sraw);
static void GasIndexAlgorithm__sigmoid_scaled__set_parameters(
    GasIndexAlgorithmParams* params, fix16_t X0, fix16_t K,
    fix16_t offset_default);
static fix16_t
GasIndexAlgorithm__sigmoid_scaled__process(GasIndexAlgorithmParams* params,
                                           fix16_t sample);
static void GasIndexAlgorithm__adaptive_lowpass__set_parameters(
    GasIndexAlgorithmParams* params);
static fix16_t
GasIndexAlgorithm__adaptive_lowpass__process(GasIndexAlgorithmParams* params,
                                             fix16_t sample);

void GasIndexAlgorithm_init(GasIndexAlgorithmParams* params,
                            int32_t algorithm_type) {

    params->mAlgorithm_Type = algorithm_type;
    if ((algorithm_type == GasIndexAlgorithm_ALGORITHM_TYPE_NOX)) {
        params->mIndex_Offset = F16(GasIndexAlgorithm_NOX_INDEX_OFFSET_DEFAULT);
        params->mSraw_Minimum = GasIndexAlgorithm_NOX_SRAW_MINIMUM;
        params->mGating_Max_Duration_Minutes =
            F16(GasIndexAlgorithm_GATING_NOX_MAX_DURATION_MINUTES);
        params->mInit_Duration_Mean =
            F16(GasIndexAlgorithm_INIT_DURATION_MEAN_NOX);
        params->mInit_Duration_Variance =
            F16(GasIndexAlgorithm_INIT_DURATION_VARIANCE_NOX);
        params->mGating_Threshold = F16(GasIndexAlgorithm_GATING_THRESHOLD_NOX);
    } else {
        params->mIndex_Offset = F16(GasIndexAlgorithm_VOC_INDEX_OFFSET_DEFAULT);
        params->mSraw_Minimum = GasIndexAlgorithm_VOC_SRAW_MINIMUM;
        params->mGating_Max_Duration_Minutes =
            F16(GasIndexAlgorithm_GATING_VOC_MAX_DURATION_MINUTES);
        params->mInit_Duration_Mean =
            F16(GasIndexAlgorithm_INIT_DURATION_MEAN_VOC);
        params->mInit_Duration_Variance =
            F16(GasIndexAlgorithm_INIT_DURATION_VARIANCE_VOC);
        params->mGating_Threshold = F16(GasIndexAlgorithm_GATING_THRESHOLD_VOC);
    }
    params->mIndex_Gain = F16(GasIndexAlgorithm_INDEX_GAIN);
    params->mTau_Mean_Hours = F16(GasIndexAlgorithm_TAU_MEAN_HOURS);
    params->mTau_Variance_Hours = F16(GasIndexAlgorithm_TAU_VARIANCE_HOURS);
    params->mSraw_Std_Initial = F16(GasIndexAlgorithm_SRAW_STD_INITIAL);
    GasIndexAlgorithm_reset(params);
}

void GasIndexAlgorithm_reset(GasIndexAlgorithmParams* params) {
    params->mUptime = F16(0.);
    params->mSraw = F16(0.);
    params->mGas_Index = 0;
    GasIndexAlgorithm__init_instances(params);
}

static void GasIndexAlgorithm__init_instances(GasIndexAlgorithmParams* params) {

    GasIndexAlgorithm__mean_variance_estimator__set_parameters(params);
    GasIndexAlgorithm__mox_model__set_parameters(
        params, GasIndexAlgorithm__mean_variance_estimator__get_std(params),
        GasIndexAlgorithm__mean_variance_estimator__get_mean(params));
    if ((params->mAlgorithm_Type == GasIndexAlgorithm_ALGORITHM_TYPE_NOX)) {
        GasIndexAlgorithm__sigmoid_scaled__set_parameters(
            params, F16(GasIndexAlgorithm_SIGMOID_X0_NOX),
            F16(GasIndexAlgorithm_SIGMOID_K_NOX),
            F16(GasIndexAlgorithm_NOX_INDEX_OFFSET_DEFAULT));
    } else {
        GasIndexAlgorithm__sigmoid_scaled__set_parameters(
            params, F16(GasIndexAlgorithm_SIGMOID_X0_VOC),
            F16(GasIndexAlgorithm_SIGMOID_K_VOC),
            F16(GasIndexAlgorithm_VOC_INDEX_OFFSET_DEFAULT));
    }
    GasIndexAlgorithm__adaptive_lowpass__set_parameters(params);
}

void GasIndexAlgorithm_get_states(const GasIndexAlgorithmParams* params,
                                  int32_t* state0, int32_t* state1) {

    *state0 = GasIndexAlgorithm__mean_variance_estimator__get_mean(params);
    *state1 = GasIndexAlgorithm__mean_variance_estimator__get_std(params);
    return;
}

void GasIndexAlgorithm_set_states(GasIndexAlgorithmParams* params,
                                  int32_t state0, int32_t state1) {

    GasIndexAlgorithm__mean_variance_estimator__set_states(
        params, state0, state1,
        F16(GasIndexAlgorithm_PERSISTENCE_UPTIME_GAMMA));
    GasIndexAlgorithm__mox_model__set_parameters(
        params, GasIndexAlgorithm__mean_variance_estimator__get_std(params),
        GasIndexAlgorithm__mean_variance_estimator__get_mean(params));
    params->mSraw = state0;
}

void GasIndexAlgorithm_set_tuning_parameters(
    GasIndexAlgorithmParams* params, int32_t index_offset,
    int32_t learning_time_offset_hours, int32_t learning_time_gain_hours,
    int32_t gating_max_duration_minutes, int32_t std_initial,
    int32_t gain_factor) {

    params->mIndex_Offset = (fix16_from_int(index_offset));
    params->mTau_Mean_Hours = (fix16_from_int(learning_time_offset_hours));
    params->mTau_Variance_Hours = (fix16_from_int(learning_time_gain_hours));
    params->mGating_Max_Duration_Minutes =
        (fix16_from_int(gating_max_duration_minutes));
    params->mSraw_Std_Initial = (fix16_from_int(std_initial));
    params->mIndex_Gain = (fix16_from_int(gain_factor));
    GasIndexAlgorithm__init_instances(params);
}

void GasIndexAlgorithm_get_tuning_parameters(
    const GasIndexAlgorithmParams* params, int32_t* index_offset,
    int32_t* learning_time_offset_hours, int32_t* learning_time_gain_hours,
    int32_t* gating_max_duration_minutes, int32_t* std_initial,
    int32_t* gain_factor) {

    *index_offset = (fix16_cast_to_int(params->mIndex_Offset));
    *learning_time_offset_hours = (fix16_cast_to_int(params->mTau_Mean_Hours));
    *learning_time_gain_hours =
        (fix16_cast_to_int(params->mTau_Variance_Hours));
    *gating_max_duration_minutes =
        (fix16_cast_to_int(params->mGating_Max_Duration_Minutes));
    *std_initial = (fix16_cast_to_int(params->mSraw_Std_Initial));
    *gain_factor = (fix16_cast_to_int(params->mIndex_Gain));
    return;
}

void GasIndexAlgorithm_process(GasIndexAlgorithmParams* params, int32_t sraw,
                               int32_t* gas_index) {

    if ((params->mUptime <= F16(GasIndexAlgorithm_INITIAL_BLACKOUT))) {
        params->mUptime =
            (params->mUptime + F16(GasIndexAlgorithm_SAMPLING_INTERVAL));
    } else {
        if (((sraw > 0) && (sraw < 65000))) {
            if ((sraw < (params->mSraw_Minimum + 1))) {
                sraw = (params->mSraw_Minimum + 1);
            } else if ((sraw > (params->mSraw_Minimum + 32767))) {
                sraw = (params->mSraw_Minimum + 32767);
            }
            params->mSraw = (fix16_from_int((sraw - params->mSraw_Minimum)));
        }
        if (((params->mAlgorithm_Type ==
              GasIndexAlgorithm_ALGORITHM_TYPE_VOC) ||
             GasIndexAlgorithm__mean_variance_estimator__is_initialized(
                 params))) {
            params->mGas_Index =
                GasIndexAlgorithm__mox_model__process(params, params->mSraw);
            params->mGas_Index = GasIndexAlgorithm__sigmoid_scaled__process(
                params, params->mGas_Index);
        } else {
            params->mGas_Index = params->mIndex_Offset;
        }
        params->mGas_Index = GasIndexAlgorithm__adaptive_lowpass__process(
            params, params->mGas_Index);
        if ((params->mGas_Index < F16(0.5))) {
            params->mGas_Index = F16(0.5);
        }
        if ((params->mSraw > F16(0.))) {
            GasIndexAlgorithm__mean_variance_estimator__process(params,
                                                                params->mSraw);
            GasIndexAlgorithm__mox_model__set_parameters(
                params,
                GasIndexAlgorithm__mean_variance_estimator__get_std(params),
                GasIndexAlgorithm__mean_variance_estimator__get_mean(params));
        }
    }
    *gas_index = (fix16_cast_to_int((params->mGas_Index + F16(0.5))));
    return;
}

static void GasIndexAlgorithm__mean_variance_estimator__set_parameters(
    GasIndexAlgorithmParams* params) {

    params->m_Mean_Variance_Estimator___Initialized = false;
    params->m_Mean_Variance_Estimator___Mean = F16(0.);
    params->m_Mean_Variance_Estimator___Sraw_Offset = F16(0.);
    params->m_Mean_Variance_Estimator___Std = params->mSraw_Std_Initial;
    params->m_Mean_Variance_Estimator___Gamma_Mean = (fix16_div(
        F16((
            (GasIndexAlgorithm_MEAN_VARIANCE_ESTIMATOR__ADDITIONAL_GAMMA_MEAN_SCALING *
             GasIndexAlgorithm_MEAN_VARIANCE_ESTIMATOR__GAMMA_SCALING) *
            (GasIndexAlgorithm_SAMPLING_INTERVAL / 3600.))),
        (params->mTau_Mean_Hours +
         F16((GasIndexAlgorithm_SAMPLING_INTERVAL / 3600.)))));
    params->m_Mean_Variance_Estimator___Gamma_Variance = (fix16_div(
        F16((GasIndexAlgorithm_MEAN_VARIANCE_ESTIMATOR__GAMMA_SCALING *
             (GasIndexAlgorithm_SAMPLING_INTERVAL / 3600.))),
        (params->mTau_Variance_Hours +
         F16((GasIndexAlgorithm_SAMPLING_INTERVAL / 3600.)))));
    if ((params->mAlgorithm_Type == GasIndexAlgorithm_ALGORITHM_TYPE_NOX)) {
        params->m_Mean_Variance_Estimator___Gamma_Initial_Mean = F16((
            ((GasIndexAlgorithm_MEAN_VARIANCE_ESTIMATOR__ADDITIONAL_GAMMA_MEAN_SCALING *
              GasIndexAlgorithm_MEAN_VARIANCE_ESTIMATOR__GAMMA_SCALING) *
             GasIndexAlgorithm_SAMPLING_INTERVAL) /
            (GasIndexAlgorithm_TAU_INITIAL_MEAN_NOX +
             GasIndexAlgorithm_SAMPLING_INTERVAL)));
    } else {
        params->m_Mean_Variance_Estimator___Gamma_Initial_Mean = F16((
            ((GasIndexAlgorithm_MEAN_VARIANCE_ESTIMATOR__ADDITIONAL_GAMMA_MEAN_SCALING *
              GasIndexAlgorithm_MEAN_VARIANCE_ESTIMATOR__GAMMA_SCALING) *
             GasIndexAlgorithm_SAMPLING_INTERVAL) /
            (GasIndexAlgorithm_TAU_INITIAL_MEAN_VOC +
             GasIndexAlgorithm_SAMPLING_INTERVAL)));
    }
    params->m_Mean_Variance_Estimator___Gamma_Initial_Variance =
        F16(((GasIndexAlgorithm_MEAN_VARIANCE_ESTIMATOR__GAMMA_SCALING *
              GasIndexAlgorithm_SAMPLING_INTERVAL) /
             (GasIndexAlgorithm_TAU_INITIAL_VARIANCE +
              GasIndexAlgorithm_SAMPLING_INTERVAL)));
    params->m_Mean_Variance_Estimator__Gamma_Mean = F16(0.);
    params->m_Mean_Variance_Estimator__Gamma_Variance = F16(0.);
    params->m_Mean_Variance_Estimator___Uptime_Gamma = F16(0.);
    params->m_Mean_Variance_Estimator___Uptime_Gating = F16(0.);
    params->m_Mean_Variance_Estimator___Gating_Duration_Minutes = F16(0.);
}

static void GasIndexAlgorithm__mean_variance_estimator__set_states(
    GasIndexAlgorithmParams* params, fix16_t mean, fix16_t std,
    fix16_t uptime_gamma) {

    params->m_Mean_Variance_Estimator___Mean = mean;
    params->m_Mean_Variance_Estimator___Std = std;
    params->m_Mean_Variance_Estimator___Uptime_Gamma = uptime_gamma;
    params->m_Mean_Variance_Estimator___Initialized = true;
}

static fix16_t GasIndexAlgorithm__mean_variance_estimator__get_std(
    const GasIndexAlgorithmParams* params) {

    return params->m_Mean_Variance_Estimator___Std;
}

static fix16_t GasIndexAlgorithm__mean_variance_estimator__get_mean(
    const GasIndexAlgorithmParams* params) {

    return (params->m_Mean_Variance_Estimator___Mean +
            params->m_Mean_Variance_Estimator___Sraw_Offset);
}

static bool GasIndexAlgorithm__mean_variance_estimator__is_initialized(
    GasIndexAlgorithmParams* params) {

    return params->m_Mean_Variance_Estimator___Initialized;
}

static void GasIndexAlgorithm__mean_variance_estimator___calculate_gamma(
    GasIndexAlgorithmParams* params) {

    fix16_t uptime_limit;
    fix16_t sigmoid_gamma_mean;
    fix16_t gamma_mean;
    fix16_t gating_threshold_mean;
    fix16_t sigmoid_gating_mean;
    fix16_t sigmoid_gamma_variance;
    fix16_t gamma_variance;
    fix16_t gating_threshold_variance;
    fix16_t sigmoid_gating_variance;

    uptime_limit = F16((GasIndexAlgorithm_MEAN_VARIANCE_ESTIMATOR__FIX16_MAX -
                        GasIndexAlgorithm_SAMPLING_INTERVAL));
    if ((params->m_Mean_Variance_Estimator___Uptime_Gamma < uptime_limit)) {
        params->m_Mean_Variance_Estimator___Uptime_Gamma =
            (params->m_Mean_Variance_Estimator___Uptime_Gamma +
             F16(GasIndexAlgorithm_SAMPLING_INTERVAL));
    }
    if ((params->m_Mean_Variance_Estimator___Uptime_Gating < uptime_limit)) {
        params->m_Mean_Variance_Estimator___Uptime_Gating =
            (params->m_Mean_Variance_Estimator___Uptime_Gating +
             F16(GasIndexAlgorithm_SAMPLING_INTERVAL));
    }
    GasIndexAlgorithm__mean_variance_estimator___sigmoid__set_parameters(
        params, params->mInit_Duration_Mean,
        F16(GasIndexAlgorithm_INIT_TRANSITION_MEAN));
    sigmoid_gamma_mean =
        GasIndexAlgorithm__mean_variance_estimator___sigmoid__process(
            params, params->m_Mean_Variance_Estimator___Uptime_Gamma);
    gamma_mean =
        (params->m_Mean_Variance_Estimator___Gamma_Mean +
         (fix16_mul((params->m_Mean_Variance_Estimator___Gamma_Initial_Mean -
                     params->m_Mean_Variance_Estimator___Gamma_Mean),
                    sigmoid_gamma_mean)));
    gating_threshold_mean =
        (params->mGating_Threshold +
         (fix16_mul(
             (F16(GasIndexAlgorithm_GATING_THRESHOLD_INITIAL) -
              params->mGating_Threshold),
             GasIndexAlgorithm__mean_variance_estimator___sigmoid__process(
                 params, params->m_Mean_Variance_Estimator___Uptime_Gating))));
    GasIndexAlgorithm__mean_variance_estimator___sigmoid__set_parameters(
        params, gating_threshold_mean,
        F16(GasIndexAlgorithm_GATING_THRESHOLD_TRANSITION));
    sigmoid_gating_mean =
        GasIndexAlgorithm__mean_variance_estimator___sigmoid__process(
            params, params->mGas_Index);
    params->m_Mean_Variance_Estimator__Gamma_Mean =
        (fix16_mul(sigmoid_gating_mean, gamma_mean));
    GasIndexAlgorithm__mean_variance_estimator___sigmoid__set_parameters(
        params, params->mInit_Duration_Variance,
        F16(GasIndexAlgorithm_INIT_TRANSITION_VARIANCE));
    sigmoid_gamma_variance =
        GasIndexAlgorithm__mean_variance_estimator___sigmoid__process(
            params, params->m_Mean_Variance_Estimator___Uptime_Gamma);
    gamma_variance =
        (params->m_Mean_Variance_Estimator___Gamma_Variance +
         (fix16_mul(
             (params->m_Mean_Variance_Estimator___Gamma_Initial_Variance -
              params->m_Mean_Variance_Estimator___Gamma_Variance),
             (sigmoid_gamma_variance - sigmoid_gamma_mean))));
    gating_threshold_variance =
        (params->mGating_Threshold +
         (fix16_mul(
             (F16(GasIndexAlgorithm_GATING_THRESHOLD_INITIAL) -
              params->mGating_Threshold),
             GasIndexAlgorithm__mean_variance_estimator___sigmoid__process(
                 params, params->m_Mean_Variance_Estimator___Uptime_Gating))));
    GasIndexAlgorithm__mean_variance_estimator___sigmoid__set_parameters(
        params, gating_threshold_variance,
        F16(GasIndexAlgorithm_GATING_THRESHOLD_TRANSITION));
    sigmoid_gating_variance =
        GasIndexAlgorithm__mean_variance_estimator___sigmoid__process(
            params, params->mGas_Index);
    params->m_Mean_Variance_Estimator__Gamma_Variance =
        (fix16_mul(sigmoid_gating_variance, gamma_variance));
    params->m_Mean_Variance_Estimator___Gating_Duration_Minutes =
        (params->m_Mean_Variance_Estimator___Gating_Duration_Minutes +
         (fix16_mul(
             F16((GasIndexAlgorithm_SAMPLING_INTERVAL / 60.)),
             ((fix16_mul((F16(1.) - sigmoid_gating_mean),
                         F16((1. + GasIndexAlgorithm_GATING_MAX_RATIO)))) -
              F16(GasIndexAlgorithm_GATING_MAX_RATIO)))));
    if ((params->m_Mean_Variance_Estimator___Gating_Duration_Minutes <
         F16(0.))) {
        params->m_Mean_Variance_Estimator___Gating_Duration_Minutes = F16(0.);
    }
    if ((params->m_Mean_Variance_Estimator___Gating_Duration_Minutes >
         params->mGating_Max_Duration_Minutes)) {
        params->m_Mean_Variance_Estimator___Uptime_Gating = F16(0.);
    }
}

static void GasIndexAlgorithm__mean_variance_estimator__process(
    GasIndexAlgorithmParams* params, fix16_t sraw) {

    fix16_t delta_sgp;
    fix16_t c;
    fix16_t additional_scaling;

    if ((params->m_Mean_Variance_Estimator___Initialized == false)) {
        params->m_Mean_Variance_Estimator___Initialized = true;
        params->m_Mean_Variance_Estimator___Sraw_Offset = sraw;
        params->m_Mean_Variance_Estimator___Mean = F16(0.);
    } else {
        if (((params->m_Mean_Variance_Estimator___Mean >= F16(100.)) ||
             (params->m_Mean_Variance_Estimator___Mean <= F16(-100.)))) {
            params->m_Mean_Variance_Estimator___Sraw_Offset =
                (params->m_Mean_Variance_Estimator___Sraw_Offset +
                 params->m_Mean_Variance_Estimator___Mean);
            params->m_Mean_Variance_Estimator___Mean = F16(0.);
        }
        sraw = (sraw - params->m_Mean_Variance_Estimator___Sraw_Offset);
        GasIndexAlgorithm__mean_variance_estimator___calculate_gamma(params);
        delta_sgp = (fix16_div(
            (sraw - params->m_Mean_Variance_Estimator___Mean),
            F16(GasIndexAlgorithm_MEAN_VARIANCE_ESTIMATOR__GAMMA_SCALING)));
        if ((delta_sgp < F16(0.))) {
            c = (params->m_Mean_Variance_Estimator___Std - delta_sgp);
        } else {
            c = (params->m_Mean_Variance_Estimator___Std + delta_sgp);
        }
        additional_scaling = F16(1.);
        if ((c > F16(1440.))) {
            additional_scaling = (fix16_mul((fix16_div(c, F16(1440.))),
                                            (fix16_div(c, F16(1440.)))));
        }
        params->m_Mean_Variance_Estimator___Std = (fix16_mul(
            fix16_sqrt((fix16_mul(
                additional_scaling,
                (F16(GasIndexAlgorithm_MEAN_VARIANCE_ESTIMATOR__GAMMA_SCALING) -
                 params->m_Mean_Variance_Estimator__Gamma_Variance)))),
            fix16_sqrt((
                (fix16_mul(
                    params->m_Mean_Variance_Estimator___Std,
                    (fix16_div(
                        params->m_Mean_Variance_Estimator___Std,
                        (fix16_mul(
                            F16(GasIndexAlgorithm_MEAN_VARIANCE_ESTIMATOR__GAMMA_SCALING),
                            additional_scaling)))))) +
                (fix16_mul(
                    (fix16_div(
                        (fix16_mul(
                            params->m_Mean_Variance_Estimator__Gamma_Variance,
                            delta_sgp)),
                        additional_scaling)),
                    delta_sgp))))));
        params->m_Mean_Variance_Estimator___Mean =
            (params->m_Mean_Variance_Estimator___Mean +
             (fix16_div(
                 (fix16_mul(params->m_Mean_Variance_Estimator__Gamma_Mean,
                            delta_sgp)),
                 F16(GasIndexAlgorithm_MEAN_VARIANCE_ESTIMATOR__ADDITIONAL_GAMMA_MEAN_SCALING))));
    }
}

static void
GasIndexAlgorithm__mean_variance_estimator___sigmoid__set_parameters(
    GasIndexAlgorithmParams* params, fix16_t X0, fix16_t K) {

    params->m_Mean_Variance_Estimator___Sigmoid__K = K;
    params->m_Mean_Variance_Estimator___Sigmoid__X0 = X0;
}

static fix16_t GasIndexAlgorithm__mean_variance_estimator___sigmoid__process(
    GasIndexAlgorithmParams* params, fix16_t sample) {

    fix16_t x;

    x = (fix16_mul(params->m_Mean_Variance_Estimator___Sigmoid__K,
                   (sample - params->m_Mean_Variance_Estimator___Sigmoid__X0)));
    if ((x < F16(-50.))) {
        return F16(1.);
    } else if ((x > F16(50.))) {
        return F16(0.);
    } else {
        return (fix16_div(F16(1.), (F16(1.) + fix16_exp(x))));
    }
}

static void GasIndexAlgorithm__mox_model__set_parameters(
    GasIndexAlgorithmParams* params, fix16_t SRAW_STD, fix16_t SRAW_MEAN) {

    params->m_Mox_Model__Sraw_Std = SRAW_STD;
    params->m_Mox_Model__Sraw_Mean = SRAW_MEAN;
}

static fix16_t
GasIndexAlgorithm__mox_model__process(GasIndexAlgorithmParams* params,
                                      fix16_t sraw) {

    if ((params->mAlgorithm_Type == GasIndexAlgorithm_ALGORITHM_TYPE_NOX)) {
        return (fix16_mul((fix16_div((sraw - params->m_Mox_Model__Sraw_Mean),
                                     F16(GasIndexAlgorithm_SRAW_STD_NOX))),
                          params->mIndex_Gain));
    } else {
        return (fix16_mul(
            (fix16_div((sraw - params->m_Mox_Model__Sraw_Mean),
                       (-(params->m_Mox_Model__Sraw_Std +
                          F16(GasIndexAlgorithm_SRAW_STD_BONUS_VOC))))),
            params->mIndex_Gain));
    }
}

static void GasIndexAlgorithm__sigmoid_scaled__set_parameters(
    GasIndexAlgorithmParams* params, fix16_t X0, fix16_t K,
    fix16_t offset_default) {

    params->m_Sigmoid_Scaled__K = K;
    params->m_Sigmoid_Scaled__X0 = X0;
    params->m_Sigmoid_Scaled__Offset_Default = offset_default;
}

static fix16_t
GasIndexAlgorithm__sigmoid_scaled__process(GasIndexAlgorithmParams* params,
                                           fix16_t sample) {

    fix16_t x;
    fix16_t shift;

    x = (fix16_mul(params->m_Sigmoid_Scaled__K,
                   (sample - params->m_Sigmoid_Scaled__X0)));
    if ((x < F16(-50.))) {
        return F16(GasIndexAlgorithm_SIGMOID_L);
    } else if ((x > F16(50.))) {
        return F16(0.);
    } else {
        if ((sample >= F16(0.))) {
            if ((params->m_Sigmoid_Scaled__Offset_Default == F16(1.))) {
                shift = (fix16_mul(F16((500. / 499.)),
                                   (F16(1.) - params->mIndex_Offset)));
            } else {
                shift =
                    (fix16_div((F16(GasIndexAlgorithm_SIGMOID_L) -
                                (fix16_mul(F16(5.), params->mIndex_Offset))),
                               F16(4.)));
            }
            return ((fix16_div((F16(GasIndexAlgorithm_SIGMOID_L) + shift),
                               (F16(1.) + fix16_exp(x)))) -
                    shift);
        } else {
            return (
                fix16_mul((fix16_div(params->mIndex_Offset,
                                     params->m_Sigmoid_Scaled__Offset_Default)),
                          (fix16_div(F16(GasIndexAlgorithm_SIGMOID_L),
                                     (F16(1.) + fix16_exp(x))))));
        }
    }
}

static void GasIndexAlgorithm__adaptive_lowpass__set_parameters(
    GasIndexAlgorithmParams* params) {

    params->m_Adaptive_Lowpass__A1 = F16((
        GasIndexAlgorithm_SAMPLING_INTERVAL /
        (GasIndexAlgorithm_LP_TAU_FAST + GasIndexAlgorithm_SAMPLING_INTERVAL)));
    params->m_Adaptive_Lowpass__A2 = F16((
        GasIndexAlgorithm_SAMPLING_INTERVAL /
        (GasIndexAlgorithm_LP_TAU_SLOW + GasIndexAlgorithm_SAMPLING_INTERVAL)));
    params->m_Adaptive_Lowpass___Initialized = false;
}

static fix16_t
GasIndexAlgorithm__adaptive_lowpass__process(GasIndexAlgorithmParams* params,
                                             fix16_t sample) {

    fix16_t abs_delta;
    fix16_t F1;
    fix16_t tau_a;
    fix16_t a3;

    if ((params->m_Adaptive_Lowpass___Initialized == false)) {
        params->m_Adaptive_Lowpass___X1 = sample;
        params->m_Adaptive_Lowpass___X2 = sample;
        params->m_Adaptive_Lowpass___X3 = sample;
        params->m_Adaptive_Lowpass___Initialized = true;
    }
    params->m_Adaptive_Lowpass___X1 =
        ((fix16_mul((F16(1.) - params->m_Adaptive_Lowpass__A1),
                    params->m_Adaptive_Lowpass___X1)) +
         (fix16_mul(params->m_Adaptive_Lowpass__A1, sample)));
    params->m_Adaptive_Lowpass___X2 =
        ((fix16_mul((F16(1.) - params->m_Adaptive_Lowpass__A2),
                    params->m_Adaptive_Lowpass___X2)) +
         (fix16_mul(params->m_Adaptive_Lowpass__A2, sample)));
    abs_delta =
        (params->m_Adaptive_Lowpass___X1 - params->m_Adaptive_Lowpass___X2);
    if ((abs_delta < F16(0.))) {
        abs_delta = (-abs_delta);
    }
    F1 = fix16_exp((fix16_mul(F16(GasIndexAlgorithm_LP_ALPHA), abs_delta)));
    tau_a = ((fix16_mul(F16((GasIndexAlgorithm_LP_TAU_SLOW -
                             GasIndexAlgorithm_LP_TAU_FAST)),
                        F1)) +
             F16(GasIndexAlgorithm_LP_TAU_FAST));
    a3 = (fix16_div(F16(GasIndexAlgorithm_SAMPLING_INTERVAL),
                    (F16(GasIndexAlgorithm_SAMPLING_INTERVAL) + tau_a)));
    params->m_Adaptive_Lowpass___X3 =
        ((fix16_mul((F16(1.) - a3), params->m_Adaptive_Lowpass___X3)) +
         (fix16_mul(a3, sample)));
    return params->m_Adaptive_Lowpass___X3;
}
