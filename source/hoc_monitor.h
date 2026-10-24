/*
 * HOC Undervolting Wizard - Horizon OC monitor.
 *
 * Uses the public Horizon-OC hoc:clk IPC service. The stable context fields are
 * used for clocks/voltages; current API-v2 context/config fields are used for
 * DRAM identification and persistent-setting verification. Temporary CPU/GPU/
 * MEM overrides can also be written through HOC's public SetOverride IPC.
 *
 * SPDX-License-Identifier: GPL-2.0-only
 */

#pragma once

#include <switch.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    u32 targetHz[3];
    u32 realHz[3];
    u32 overrideHz[3];
    /* Current CPU rail voltage reported by Horizon OC, in microvolts. */
    u32 cpuVoltageUv;
} HocMonClocks;

typedef struct {
    u8 dramId;
    bool isDram8GB;
    u32 consoleType;
} HocMonHardware;

typedef struct {
    bool uncappedClocks;
    bool hpMode;
    u32 ramMaxKHz;
    u32 vdd2Uv;
    u32 vddqUv;
    int lowUv;
    int highUv;
    int tableConf;
    int lowVminMv;
    int highVminMv;
    u32 cpuMaxKHz;
    u32 cpuBoostKHz;
} HocMonConfig;

enum {
    HocMonModule_CPU = 0,
    HocMonModule_GPU = 1,
    HocMonModule_MEM = 2,
};

/* Read CPU/GPU/MEM target, real and temporary override clocks + CPU voltage. */
Result hocmonGetClocks(HocMonClocks* out);

/* Set one Horizon OC Temporary Override. hz=0 clears that module override. */
Result hocmonSetOverride(u32 module, u32 hz);

/* Read DRAM identity from Horizon OC API-v2 current context. */
Result hocmonGetHardware(HocMonHardware* out);

/* Read the persistent Horizon OC/KIP values used by the Battery Wizard. */
Result hocmonGetConfig(HocMonConfig* out);

#ifdef __cplusplus
}
#endif
