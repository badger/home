#include "py/dynruntime.h"
#include "sensirion_gas_index_algorithm.h"

GasIndexAlgorithmParams voc_params;
GasIndexAlgorithmParams nox_params;

static mp_obj_t reset(void) {
    GasIndexAlgorithm_init(&voc_params, GasIndexAlgorithm_ALGORITHM_TYPE_VOC);
    GasIndexAlgorithm_init(&nox_params, GasIndexAlgorithm_ALGORITHM_TYPE_NOX);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(reset_obj, reset);

static mp_obj_t process(mp_obj_t voc_raw_obj, mp_obj_t nox_raw_obj) {
    mp_int_t voc_raw = mp_obj_get_int(voc_raw_obj);
    mp_int_t nox_raw = mp_obj_get_int(nox_raw_obj);
    if (voc_raw <= 0 || voc_raw >= 65000 || nox_raw <= 0 || nox_raw >= 65000) {
        mp_raise_ValueError(MP_ERROR_TEXT("Invalid SGP41 raw signal"));
    }
    int32_t voc_index;
    int32_t nox_index;
    GasIndexAlgorithm_process(&voc_params, voc_raw, &voc_index);
    GasIndexAlgorithm_process(&nox_params, nox_raw, &nox_index);
    mp_obj_t values[2] = {mp_obj_new_int(voc_index), mp_obj_new_int(nox_index)};
    return mp_obj_new_tuple(2, values);
}
static MP_DEFINE_CONST_FUN_OBJ_2(process_obj, process);

mp_obj_t mpy_init(mp_obj_fun_bc_t *self, size_t n_args, size_t n_kw, mp_obj_t *args) {
    MP_DYNRUNTIME_INIT_ENTRY
    reset();
    mp_store_global(MP_QSTR_reset, MP_OBJ_FROM_PTR(&reset_obj));
    mp_store_global(MP_QSTR_process, MP_OBJ_FROM_PTR(&process_obj));
    MP_DYNRUNTIME_INIT_EXIT
}
