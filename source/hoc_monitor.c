/*
 * HOC Undervolting Wizard - Horizon OC monitor.
 *
 * The IPC commands and context/config layouts are adapted from Horizon-OC
 * (common/include/hocclk/{clock_manager,config,ipc}.h and client/ipc.c).
 * Copyright (c) Souldbminer, Lightos_ and Horizon OC Contributors.
 * Horizon-OC distributes this interface under GNU GPL version 2.
 *
 * Modifications for HOC Undervolting Wizard, 2026:
 * - read-only clock/override/voltage access;
 * - read DRAM ID for automatic VDDQ starting-point selection;
 * - read persistent HOC/KIP settings so reboot steps can be verified first.
 *
 * SPDX-License-Identifier: GPL-2.0-only
 */

#define NX_SERVICE_ASSUME_NON_DOMAIN
#include <switch.h>
#include <stddef.h>
#include <string.h>

#include "hoc_monitor.h"

#define HOCCLK_IPC_SERVICE_NAME "hoc:clk"
#define HOCCLK_IPC_CMD_GET_API_VERSION 0
#define HOCCLK_IPC_CMD_GET_CURRENT_CONTEXT 2
#define HOCCLK_IPC_CMD_GET_CONFIG_VALUES 9
#define HOCCLK_API_VERSION_REQUIRED 2

#define HOCCLK_STABLE_MODULE_COUNT 5
#define HOCCLK_STABLE_THERMAL_COUNT 11
#define HOCCLK_STABLE_POWER_COUNT 2
#define HOCCLK_STABLE_PARTLOAD_COUNT 10
#define HOCCLK_STABLE_VOLTAGE_COUNT 7
#define HOCCLK_VOLTAGE_CPU_INDEX 2

/* Current API-v2 non-stable context counts. */
#define HOCCLK_CONTEXT_MODULE_COUNT 5
#define HOCCLK_CONTEXT_THERMAL_COUNT 12
#define HOCCLK_CONTEXT_POWER_COUNT 2
#define HOCCLK_CONTEXT_PARTLOAD_COUNT 10
#define HOCCLK_CONTEXT_VOLTAGE_COUNT 7
#define HOCCLK_CONTEXT_SPEEDO_COUNT 3

typedef struct {
    u32 freqs[HOCCLK_STABLE_MODULE_COUNT];
    u32 realFreqs[HOCCLK_STABLE_MODULE_COUNT];
    u32 overrideFreqs[HOCCLK_STABLE_MODULE_COUNT];
    s32 temps[HOCCLK_STABLE_THERMAL_COUNT];
    s32 power[HOCCLK_STABLE_POWER_COUNT];
    u32 partLoad[HOCCLK_STABLE_PARTLOAD_COUNT];
    u32 voltages[HOCCLK_STABLE_VOLTAGE_COUNT];
} HocMonStableContext;

/*
 * Prefix of Horizon OC's current HocClkContext through consoleType.
 * The first stable block is ABI-stable. The DRAM fields after it are API-v2
 * fields; hocmonGetHardware additionally validates API version and ID range.
 */
typedef struct {
    HocMonStableContext stable;
    u64 applicationId;
    s32 profile;
    u32 freqs[HOCCLK_CONTEXT_MODULE_COUNT];
    u32 realFreqs[HOCCLK_CONTEXT_MODULE_COUNT];
    u32 overrideFreqs[HOCCLK_CONTEXT_MODULE_COUNT];
    s32 temps[HOCCLK_CONTEXT_THERMAL_COUNT];
    s32 power[HOCCLK_CONTEXT_POWER_COUNT];
    u32 partLoad[HOCCLK_CONTEXT_PARTLOAD_COUNT];
    u32 voltages[HOCCLK_CONTEXT_VOLTAGE_COUNT];
    u16 speedos[HOCCLK_CONTEXT_SPEEDO_COUNT];
    u16 iddq[HOCCLK_CONTEXT_SPEEDO_COUNT];
    s16 waferX;
    s16 waferY;
    s32 gpuSchedulingMode;
    bool isSysDockInstalled;
    bool isSaltyNXInstalled;
    u8 maxDisplayFreq;
    u8 dramID;
    bool isDram8GB;
    s32 consoleType;
} HocMonContextPrefix;

typedef struct {
    HocMonStableContext stable;
    u8 reserved[0x500 - sizeof(HocMonStableContext)];
} HocMonRawContext;

_Static_assert(sizeof(HocMonRawContext) == 0x500, "Horizon OC context size mismatch");
_Static_assert(offsetof(HocMonContextPrefix, dramID) == 403, "Unexpected Horizon OC API-v2 context layout");

/* Relevant indexes from Horizon OC HocClkConfigValue. */
enum {
    CFG_UNCAPPED_CLOCKS = 5,
    CFG_HP_MODE = 40,
    CFG_VDD2_UV = 41,
    CFG_RAM_MAX_KHZ = 44,
    CFG_VDDQ_UV = 45,
    CFG_CPU_LOW_UV = 77,
    CFG_CPU_HIGH_UV = 78,
    CFG_CPU_TABLE = 79,
    CFG_CPU_LOW_VMIN_MV = 80,
    CFG_CPU_HIGH_VMIN_MV = 81,
    CFG_CPU_MAX_KHZ = 83,
    CFG_CPU_BOOST_KHZ = 85,
};

/* Oversized read-only buffer. The HOC service only requires >= its current list size. */
typedef struct {
    u64 values[256];
} HocMonRawConfig;

static Result hocmonOpen(Service* srv, u32* apiVersion)
{
    Result rc = smGetService(srv, HOCCLK_IPC_SERVICE_NAME);
    if (R_FAILED(rc))
        return rc;

    u32 api = 0;
    rc = serviceDispatchOut(srv, HOCCLK_IPC_CMD_GET_API_VERSION, api);
    if (R_FAILED(rc)) {
        serviceClose(srv);
        return rc;
    }

    if (apiVersion)
        *apiVersion = api;
    return 0;
}

static Result hocmonReadRawContext(Service* srv, HocMonRawContext* ctx)
{
    memset(ctx, 0, sizeof(*ctx));
    return serviceDispatch(srv, HOCCLK_IPC_CMD_GET_CURRENT_CONTEXT,
        .buffer_attrs = { SfBufferAttr_HipcAutoSelect | SfBufferAttr_Out },
        .buffers = {{ ctx, sizeof(*ctx) }},
    );
}

Result hocmonGetClocks(HocMonClocks* out)
{
    if (!out)
        return 1;
    memset(out, 0, sizeof(*out));

    Service srv = {0};
    Result rc = hocmonOpen(&srv, NULL);
    if (R_FAILED(rc))
        return rc;

    HocMonRawContext ctx;
    rc = hocmonReadRawContext(&srv, &ctx);
    serviceClose(&srv);
    if (R_FAILED(rc))
        return rc;

    /* Horizon-OC stable module order: CPU=0, GPU=1, MEM=2. */
    for (int i = 0; i < 3; ++i) {
        out->targetHz[i] = ctx.stable.freqs[i];
        out->realHz[i] = ctx.stable.realFreqs[i];
        out->overrideHz[i] = ctx.stable.overrideFreqs[i];
    }

    /* Stable voltage order: SOC, VDD2, CPU, GPU, VDDQ, display, battery. */
    out->cpuVoltageUv = ctx.stable.voltages[HOCCLK_VOLTAGE_CPU_INDEX];
    return 0;
}

Result hocmonGetHardware(HocMonHardware* out)
{
    if (!out)
        return 1;
    memset(out, 0, sizeof(*out));

    Service srv = {0};
    u32 api = 0;
    Result rc = hocmonOpen(&srv, &api);
    if (R_FAILED(rc))
        return rc;
    if (api < HOCCLK_API_VERSION_REQUIRED) {
        serviceClose(&srv);
        return 2;
    }

    HocMonRawContext raw;
    rc = hocmonReadRawContext(&srv, &raw);
    serviceClose(&srv);
    if (R_FAILED(rc))
        return rc;

    const HocMonContextPrefix* ctx = (const HocMonContextPrefix*)&raw;
    /* Current HOC IDs are 0..34 and console types 0..3. Reject layout garbage. */
    if (ctx->dramID > 34 || ctx->consoleType < 0 || ctx->consoleType > 3)
        return 3;

    out->dramId = ctx->dramID;
    out->isDram8GB = ctx->isDram8GB;
    out->consoleType = (u32)ctx->consoleType;
    return 0;
}

Result hocmonGetConfig(HocMonConfig* out)
{
    if (!out)
        return 1;
    memset(out, 0, sizeof(*out));

    Service srv = {0};
    u32 api = 0;
    Result rc = hocmonOpen(&srv, &api);
    if (R_FAILED(rc))
        return rc;
    if (api < HOCCLK_API_VERSION_REQUIRED) {
        serviceClose(&srv);
        return 2;
    }

    HocMonRawConfig cfg;
    memset(&cfg, 0, sizeof(cfg));
    rc = serviceDispatch(&srv, HOCCLK_IPC_CMD_GET_CONFIG_VALUES,
        .buffer_attrs = { SfBufferAttr_HipcAutoSelect | SfBufferAttr_Out },
        .buffers = {{ &cfg, sizeof(cfg) }},
    );
    serviceClose(&srv);
    if (R_FAILED(rc))
        return rc;

    out->uncappedClocks = cfg.values[CFG_UNCAPPED_CLOCKS] != 0;
    out->hpMode = cfg.values[CFG_HP_MODE] != 0;
    out->vdd2Uv = (u32)cfg.values[CFG_VDD2_UV];
    out->ramMaxKHz = (u32)cfg.values[CFG_RAM_MAX_KHZ];
    out->vddqUv = (u32)cfg.values[CFG_VDDQ_UV];
    out->lowUv = (int)cfg.values[CFG_CPU_LOW_UV];
    out->highUv = (int)cfg.values[CFG_CPU_HIGH_UV];
    out->tableConf = (int)cfg.values[CFG_CPU_TABLE];
    out->lowVminMv = (int)cfg.values[CFG_CPU_LOW_VMIN_MV];
    out->highVminMv = (int)cfg.values[CFG_CPU_HIGH_VMIN_MV];
    out->cpuMaxKHz = (u32)cfg.values[CFG_CPU_MAX_KHZ];
    out->cpuBoostKHz = (u32)cfg.values[CFG_CPU_BOOST_KHZ];
    return 0;
}
