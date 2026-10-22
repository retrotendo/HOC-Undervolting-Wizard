/*
 * HOC Undervolting Wizard - Horizon OC clock/override monitor.
 *
 * The IPC command and stable HocClkContext layout are adapted from
 * Horizon-OC (common/include/hocclk/clock_manager.h and common/src/client/ipc.c).
 * Copyright (c) Souldbminer, Lightos_ and Horizon OC Contributors.
 * Horizon-OC distributes this interface under GNU GPL version 2.
 *
 * Modifications for HOC Undervolting Wizard, 2026:
 * - reduced the client to read-only GetCurrentContext access;
 * - expose only CPU/GPU/MEM target, real and temporary override clocks.
 *
 * SPDX-License-Identifier: GPL-2.0-only
 */

#define NX_SERVICE_ASSUME_NON_DOMAIN
#include <switch.h>
#include <string.h>

#include "hoc_monitor.h"

#define HOCCLK_IPC_SERVICE_NAME "hoc:clk"
#define HOCCLK_IPC_CMD_GET_CURRENT_CONTEXT 2

#define HOCCLK_STABLE_MODULE_COUNT 5
#define HOCCLK_STABLE_THERMAL_COUNT 11
#define HOCCLK_STABLE_POWER_COUNT 2
#define HOCCLK_STABLE_PARTLOAD_COUNT 10
#define HOCCLK_STABLE_VOLTAGE_COUNT 7

typedef struct {
    u32 freqs[HOCCLK_STABLE_MODULE_COUNT];
    u32 realFreqs[HOCCLK_STABLE_MODULE_COUNT];
    u32 overrideFreqs[HOCCLK_STABLE_MODULE_COUNT];
    s32 temps[HOCCLK_STABLE_THERMAL_COUNT];
    s32 power[HOCCLK_STABLE_POWER_COUNT];
    u32 partLoad[HOCCLK_STABLE_PARTLOAD_COUNT];
    u32 voltages[HOCCLK_STABLE_VOLTAGE_COUNT];
} HocMonStableContext;

typedef struct {
    HocMonStableContext stable;
    u8 reserved[0x500 - sizeof(HocMonStableContext)];
} HocMonRawContext;

_Static_assert(sizeof(HocMonRawContext) == 0x500, "Horizon OC context size mismatch");

Result hocmonGetClocks(HocMonClocks* out)
{
    if (!out)
        return 1;

    memset(out, 0, sizeof(*out));

    Service srv = {0};
    Result rc = smGetService(&srv, HOCCLK_IPC_SERVICE_NAME);
    if (R_FAILED(rc))
        return rc;

    HocMonRawContext ctx;
    memset(&ctx, 0, sizeof(ctx));

    rc = serviceDispatch(&srv, HOCCLK_IPC_CMD_GET_CURRENT_CONTEXT,
        .buffer_attrs = { SfBufferAttr_HipcAutoSelect | SfBufferAttr_Out },
        .buffers = {{ &ctx, sizeof(ctx) }},
    );

    serviceClose(&srv);

    if (R_FAILED(rc))
        return rc;

    /* Horizon-OC module order: CPU=0, GPU=1, MEM=2. */
    for (int i = 0; i < 3; ++i) {
        out->targetHz[i] = ctx.stable.freqs[i];
        out->realHz[i] = ctx.stable.realFreqs[i];
        out->overrideHz[i] = ctx.stable.overrideFreqs[i];
    }

    return 0;
}
