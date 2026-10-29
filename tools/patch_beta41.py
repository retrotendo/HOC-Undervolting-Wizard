from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

def rep(old, new, label, count=1):
    global s
    if old not in s:
        raise SystemExit(f'{label} not found')
    s = s.replace(old, new, count)

anchor = '''void restartVminSweep(bool recovery) {\n    const u32 keepMask = g.pendingConfigMask;\n    g.stage = Stage::LowVminLong;\n    g.recoveryNeeded = recovery;\n    clearVminSweepData();\n    g.pendingConfigMask = keepMask;\n    saveState();\n}\n\n\nvoid handlePass() {'''
replacement = '''void restartVminSweep(bool recovery) {\n    const u32 keepMask = g.pendingConfigMask;\n    g.stage = Stage::LowVminLong;\n    g.recoveryNeeded = recovery;\n    clearVminSweepData();\n    g.pendingConfigMask = keepMask;\n    saveState();\n}\n\nvoid enterLowVminSearchOrMinimumNotice() {\n    clearVminSweepData();\n    g.pendingConfigMask = Config_None;\n    if (g.lowVminGood == LOW_VMIN_MIN_MV) {\n        g.stage = Stage::LowVminQuick;\n        g.lowVminTest = LOW_VMIN_MIN_MV;\n        g.stageReadyAfterBoot = true;\n    } else if (g.lowVminGood > LOW_VMIN_MIN_MV) {\n        g.stage = Stage::LowVminQuick;\n        g.lowVminTest = std::max(LOW_VMIN_MIN_MV, g.lowVminGood - LOW_VMIN_STEP_MV);\n        g.stageReadyAfterBoot = false;\n    } else {\n        restartVminSweep(false);\n        g.stageReadyAfterBoot = true;\n    }\n}\n\n\nvoid handlePass() {'''
rep(anchor, replacement, 'insert Low VMIN minimum helper')

old = '''        case Stage::LowUvLong:\n            g.recoveryNeeded = false;\n            if (g.lowVminGood <= LOW_VMIN_MIN_MV) {\n                restartVminSweep(false);\n                g.stageReadyAfterBoot = true;\n            } else {\n                g.stage = Stage::LowVminQuick;\n                g.lowVminTest = g.lowVminGood - LOW_VMIN_STEP_MV;\n                g.stageReadyAfterBoot = false;\n            }\n            break;'''
new = '''        case Stage::LowUvLong:\n            g.recoveryNeeded = false;\n            enterLowVminSearchOrMinimumNotice();\n            break;'''
rep(old, new, 'LowUvLong transition')

old_skip = '''    if (forLowUv) {\n        if (g.lowVminGood <= LOW_VMIN_MIN_MV) {\n            g.stage = Stage::LowVminLong;\n            g.stageReadyAfterBoot = true;\n        } else {\n            g.stage = Stage::LowVminQuick;\n            g.lowVminTest = std::max(LOW_VMIN_MIN_MV, g.lowVminGood - LOW_VMIN_STEP_MV);\n            g.stageReadyAfterBoot = false;\n        }\n    } else {'''
new_skip = '''    if (forLowUv) {\n        enterLowVminSearchOrMinimumNotice();\n    } else {'''
rep(old_skip, new_skip, 'skip region transition')

old_auto = '''        if (forLowUv) {\n            clearVminSweepData();\n            if (g.lowVminGood <= LOW_VMIN_MIN_MV) {\n                g.stage = Stage::LowVminLong;\n                g.stageReadyAfterBoot = true;\n            } else {\n                g.stage = Stage::LowVminQuick;\n                g.lowVminTest = std::max(LOW_VMIN_MIN_MV, g.lowVminGood - LOW_VMIN_STEP_MV);\n                g.stageReadyAfterBoot = false;\n            }\n            g_resultAction = "All CPU voltage regions passed. CPU Low UV is confirmed; continuing to Low VMIN boot search.";'''
new_auto = '''        if (forLowUv) {\n            enterLowVminSearchOrMinimumNotice();\n            g_resultAction = "All CPU voltage regions passed. CPU Low UV is confirmed; continuing to Low VMIN boot search.";'''
rep(old_auto, new_auto, 'automatic region transition')

old_render = '''void renderTestStage() {\n    title();\n\n    const u32 configMask = activeConfigMask();'''
new_render = '''void renderTestStage() {\n    title();\n\n    if (g.stage == Stage::LowVminQuick &&\n        g.stageReadyAfterBoot &&\n        g.lowVminGood == LOW_VMIN_MIN_MV &&\n        g.lowVminTest == LOW_VMIN_MIN_MV) {\n        uiPrintf(5, "Objective:");\n        uiPrintf(6, "Current Low VMIN : %d mV", g.lowVminGood);\n        uiPrintf(8, "570 mV is the minimum recommended");\n        uiPrintf(9, "value used by this Wizard.");\n        uiPrintf(11, "Going lower is not recommended.");\n        uiPrintf(12, "Very low VMIN values may cause");\n        uiPrintf(13, "Sleep / Standby / Wake problems.");\n        uiPrintf(15, "No lower value will be tested.");\n        uiPrintf(18, "A : Confirm 570 mV and continue");\n        uiPrintf(19, "B : Exit");\n        printResetHint(19);\n        return;\n    }\n\n    const u32 configMask = activeConfigMask();'''
rep(old_render, new_render, 'minimum notice UI')

old_input = '''        } else if (k & HidNpadButton_A) {\n            const bool bootSearch = g.stage == Stage::LowUvQuick || g.stage == Stage::LowVminQuick;\n            const u32 cfgMask = bootSearch ? defaultConfigMaskForStage(g.stage) : activeConfigMask();\n            if (cfgMask != Config_None) {'''
new_input = '''        } else if (k & HidNpadButton_A) {\n            const bool lowVminMinimumNotice =\n                g.stage == Stage::LowVminQuick &&\n                g.stageReadyAfterBoot &&\n                g.lowVminGood == LOW_VMIN_MIN_MV &&\n                g.lowVminTest == LOW_VMIN_MIN_MV;\n            if (lowVminMinimumNotice) {\n                restartVminSweep(false);\n                g.stageReadyAfterBoot = true;\n                saveState();\n            } else {\n                const bool bootSearch = g.stage == Stage::LowUvQuick || g.stage == Stage::LowVminQuick;\n                const u32 cfgMask = bootSearch ? defaultConfigMaskForStage(g.stage) : activeConfigMask();\n                if (cfgMask != Config_None) {'''
rep(old_input, new_input, 'A input minimum notice')

old_close = '''                if (testPlan(g.stage, kind, seconds)) runCurrentTest();\n                else handlePass();\n            }\n            redraw = true;\n        }\n\n        svcSleepThread(20'000'000);'''
new_close = '''                if (testPlan(g.stage, kind, seconds)) runCurrentTest();\n                else handlePass();\n            }\n            }\n            redraw = true;\n        }\n\n        svcSleepThread(20'000'000);'''
rep(old_close, new_close, 'close A input minimum notice')

p.write_text(s)

m = Path('Makefile')
ms = m.read_text()
if 'APP_VERSION := 0.4.0-beta.40' not in ms:
    raise SystemExit('beta40 Makefile version not found')
ms = ms.replace('APP_VERSION := 0.4.0-beta.40', 'APP_VERSION := 0.4.0-beta.41', 1)
m.write_text(ms)
