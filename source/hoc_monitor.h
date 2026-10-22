/*
 * HOC Undervolting Wizard - Horizon OC clock/override monitor.
 *
 * Uses the public Horizon-OC hoc:clk IPC GetCurrentContext command and the
 * stable context layout documented by Horizon-OC. This file is part of
 * HOC Undervolting Wizard and is distributed under GNU GPL version 2 only.
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
} HocMonClocks;

/*
 * Reads CPU/GPU/MEM target, real and temporary override frequencies from
 * Horizon OC. Returns a libnx/Horizon-OC Result code on failure.
 */
Result hocmonGetClocks(HocMonClocks* out);

#ifdef __cplusplus
}
#endif
