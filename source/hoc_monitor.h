/*
 * HOC Undervolting Wizard - Horizon OC monitor/control.
 *
 * Uses the public Horizon-OC hoc:clk IPC service. Persistent tuning settings
 * are read-only here; only temporary CPU/GPU/RAM overrides are changed by the
 * Wizard for controlled tests.
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

/* Read CPU/GPU/MEM target, real and temporary override clocks + CPU voltage. */
Result hocmonGetClocks(HocMonClocks* out);

/* Read DRAM identity from Horizon OC API-v2 current context. */
Result hocmonGetHardware(HocMonHardware* out);

/* Read the persistent Horizon OC/KIP values used by the Battery Wizard. */
Result hocmonGetConfig(HocMonConfig* out);

/* Set Horizon OC temporary overrides. Pass 0 to remove an override. */
Result hocmonSetOverride(int module, u32 hz); /* module: CPU=0, GPU=1, RAM=2 */
Result hocmonSetOverrides(u32 cpuHz, u32 gpuHz, u32 ramHz);

#ifdef __cplusplus
}
#endif
