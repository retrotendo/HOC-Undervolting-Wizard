/*
 * HOC Undervolting Wizard - Horizon OC monitor.
 *
 * The IPC commands and context/config layouts are adapted from Horizon-OC
 * (common/include/hocclk/{clock_manager,config,ipc}.h and client/ipc.c).
 * Copyright (c) Souldbminer, Lightos_ and Horizon OC Contributors.
 * Horizon-OC distributes this interface under GNU GPL version 2.
 *
 * Modifications for HOC Undervolting Wizard, 2026:
 * - clock/override/voltage context access;
 * - Temporary Override writes through HOC's public SetOverride IPC;
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
#define HOCCLK_IPC_CMD_SET_OVERRIDE 8
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

typedef struct {
    s32 module;
    u32 hz;
} HocMonSetOverrideArgs;

_Static_assert(sizeof(HocMonRawContext) == 0x500, "Horizon OC context size mismatch");
_Static_assert(sizeof(HocMonSetOverrideArgs) == 8, "Unexpected Horizon OC SetOverride args layout");

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

Result hocmonSetOverride(u32 module, u32 hz)
{
    if (module > HocMonModule_MEM)
        return 1;

    Service srv = {0};
    u32 api = 0;
    Result rc = hocmonOpen(&srv, &api);
    if (R_FAILED(rc))
        return rc;
    if (api < HOCCLK_API_VERSION_REQUIRED) {
        serviceClose(&srv);
        return 2;
    }

    const HocMonSetOverrideArgs args = {
        .module = (s32)module,
        .hz = hz,
    };
    rc = serviceDispatchIn(&srv, HOCCLK_IPC_CMD_SET_OVERRIDE, args);
    serviceClose(&srv);
    return rc;
}

static bool hocmonIsKnownMarikoDramId(u8 id)
{
    switch (id) {
        case 3: case 5: case 6:
        case 8: case 9: case 10: case 11: case 12: case 13: case 14: case 15:
        case 17: case 18: case 19: case 20: case 21: case 22: case 23: case 24:
        case 25: case 26: case 27: case 28: case 29: case 30: case 31:
        case 32: case 33: case 34:
            return true;
        default:
            return false;
    }
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

    /*
     * HOC 2.6.0 and current HOC use the same 0x500 context size but differ by
     * one byte before maxDisplayFreq/dramID:
     *
     *   current main : [402]=maxDisplayFreq [403]=dramID [404]=isDram8GB
     *   HOC 2.6.0   : [402]=isUsingRetroSuper [403]=maxDisplayFreq
     *                  [404]=dramID [405]=isDram8GB
     *
     * consoleType remains 32-bit aligned at byte 408 in both layouts. Do not
     * guess from maxDisplayFreq; validate both layouts against HOC's known
     * Mariko DRAM IDs and the adjacent boolean instead.
     */
    const u8* bytes = (const u8*)&raw;
    s32 consoleType = -1;
    memcpy(&consoleType, bytes + 408, sizeof(consoleType));
    if (consoleType < 0 || consoleType > 3)
        return 3;

    const u8 currentId = bytes[403];
    const u8 currentIs8GB = bytes[404];
    const bool currentValid =
        hocmonIsKnownMarikoDramId(currentId) && currentIs8GB <= 1;

    const u8 hoc260Id = bytes[404];
    const u8 hoc260Is8GB = bytes[405];
    const bool hoc260Valid =
        hocmonIsKnownMarikoDramId(hoc260Id) && hoc260Is8GB <= 1;

    /* Exactly one known layout must validate. Ambiguous/unknown future layouts
       deliberately fail instead of selecting a RAM family by accident. */
    if (currentValid == hoc260Valid)
        return 3;

    if (currentValid) {
        out->dramId = currentId;
        out->isDram8GB = currentIs8GB != 0;
    } else {
        out->dramId = hoc260Id;
        out->isDram8GB = hoc260Is8GB != 0;
    }
    out->consoleType = (u32)consoleType;
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
