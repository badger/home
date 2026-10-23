MPY_DIR ?= ../../../../micropython
MOD = _gas_index
SRC = gas_index.c vendor/sensirion_gas_index_algorithm.c
ARCH ?= armv6m
CFLAGS_EXTRA += -Ivendor
LINK_RUNTIME = 1

include $(MPY_DIR)/py/dynruntime.mk
