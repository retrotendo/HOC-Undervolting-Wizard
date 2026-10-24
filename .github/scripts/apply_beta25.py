from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

# 1) Append a dedicated Low UV quick-validation stage without changing existing persisted stage numbers.
old = '''    HardwareDetection,\n    LowVminPlateauValidate\n};'''
new = '''    HardwareDetection,\n    LowVminPlateauValidate,\n    // beta.25: LowUvQuick is now boot-limit discovery; validation is separate.\n    LowUvValidateQuick\n};'''
if old not in s: raise SystemExit('enum anchor not found')
s = s.replace(old, new, 1)

# 2) LowUvQuick becomes boot discovery; the new stage owns the 60-second CPU validation.
old = '''        case Stage::LowUvQuick:\n        case Stage::LowVminQuick:\n        case Stage::HighUvQuick:\n            kind = stress::Kind::Cpu; seconds = 60; return true;'''
new = '''        case Stage::LowUvValidateQuick:\n        case Stage::LowVminQuick:\n        case Stage::HighUvQuick:\n            kind = stress::Kind::Cpu; seconds = 60; return true;'''
if old not in s: raise SystemExit('testPlan lowuv anchor not found')
s = s.replace(old, new, 1)

# Add validation stage to normal handheld override group.
old = '''        case Stage::LowUvQuick:\n        case Stage::LowUvLong:\n        case Stage::Ram1331Validate:'''
new = '''        case Stage::LowUvQuick:\n        case Stage::LowUvValidateQuick:\n        case Stage::LowUvLong:\n        case Stage::Ram1331Validate:'''
if old not in s: raise SystemExit('overridePlan lowuv anchor not found')
s = s.replace(old, new, 1)

# 3) Persistent target selection and mask for the new stage.
old = '''        case Stage::LowUvQuick:\n        case Stage::LowUvLong: return Config_LowUv;'''
new = '''        case Stage::LowUvQuick:\n        case Stage::LowUvValidateQuick:\n        case Stage::LowUvLong: return Config_LowUv;'''
if old not in s: raise SystemExit('defaultConfigMask lowuv anchor not found')
s = s.replace(old, new, 1)

old = '''int targetLowUv() {\n    return g.stage == Stage::LowUvQuick ? g.lowUvTest : g.lowUvGood;\n}'''
new = '''int targetLowUv() {\n    // LowUvQuick is the boot-limit search. Validation stages use the last\n    // value that actually booted.\n    return g.stage == Stage::LowUvQuick ? g.lowUvTest : g.lowUvGood;\n}'''
if old not in s: raise SystemExit('targetLowUv anchor not found')
s = s.replace(old, new, 1)

# 4) Current-settings baseline support. Structural Preparation controls still have to match.
anchor = '''    return sawValuesSection;\n}\n\nbool configMatchesCurrent(u32 mask, const HocMonConfig& c) {'''
insert = '''    return sawValuesSection;\n}\n\nbool preparationFixedSettingsMatch(const HocMonConfig& c) {\n    // These controls define the controlled test environment and are not\n    // adopted as tuning baselines. The tunable voltage/UV values may already\n    // be lower and are captured separately below.\n    return !c.uncappedClocks && !c.hpMode &&\n           c.ramMaxKHz == 1600000U &&\n           c.cpuMaxKHz == 1963500U &&\n           c.tableConf == 3 &&\n           c.cpuBoostKHz == 1785000U &&\n           c.vdd2Uv != 0 && c.vddqUv != 0 &&\n           c.lowVminMv != 0 && c.highVminMv != 0;\n}\n\nbool captureCurrentSettingsBaseline() {\n    g_configCheck = ConfigCheckState{};\n    g_configCheck.mask = Config_Prepare;\n    g_configCheck.readOk = readHocConfigIni(g_configCheck.current);\n    g_configCheck.rc = g_configCheck.readOk ? 0 : 0xF024;\n    if (!g_configCheck.readOk || !preparationFixedSettingsMatch(g_configCheck.current))\n        return false;\n\n    const HocMonConfig& c = g_configCheck.current;\n\n    g.lowUvGood = std::max(0, c.lowUv);\n    g.lowUvTest = (g.lowUvGood < LOW_UV_MAX) ? g.lowUvGood + 1 : g.lowUvGood;\n\n    g.lowVminGood = c.lowVminMv;\n    g.lowVminTest = (g.lowVminGood > LOW_VMIN_MIN_MV)\n        ? g.lowVminGood - LOW_VMIN_STEP_MV : g.lowVminGood;\n\n    g.vddqGood = (int)(c.vddqUv / 1000U);\n    g.vddqTest = (g.vddqGood > VDDQ_MIN_MV)\n        ? g.vddqGood - VDDQ_STEP_MV : g.vddqGood;\n\n    g.vdd2GoodUv = (int)c.vdd2Uv;\n    g.vdd2TestUv = (g.vdd2GoodUv > VDD2_MIN_UV)\n        ? g.vdd2GoodUv - VDD2_STEP_UV : g.vdd2GoodUv;\n\n    g.highUvGood = std::max(0, c.highUv);\n    g.highUvTest = (g.highUvGood < HIGH_UV_MAX) ? g.highUvGood + 1 : g.highUvGood;\n\n    g.stageReadyAfterBoot = false;\n    g.pendingConfigMask = Config_None;\n    saveState();\n    return true;\n}\n\nbool configMatchesCurrent(u32 mask, const HocMonConfig& c) {'''
if anchor not in s: raise SystemExit('baseline insertion anchor not found')
s = s.replace(anchor, insert, 1)

# 5) Labels for the new Low UV phases.
old = '''        case Stage::LowUvQuick: return "CPU Low UV - Quick Search";\n        case Stage::LowUvLong: return "CPU Low UV - 1 Hour Validation";'''
new = '''        case Stage::LowUvQuick: return "CPU Low UV - Boot Search";\n        case Stage::LowUvValidateQuick: return "CPU Low UV - Quick Validation";\n        case Stage::LowUvLong: return "CPU Low UV - 1 Hour Validation";'''
if old not in s: raise SystemExit('stageName anchor not found')
s = s.replace(old, new, 1)

old = '''        case Stage::LowUvQuick: return "CPU Low UV";\n        case Stage::LowUvLong: return "CPU Low UV - Validate";'''
new = '''        case Stage::LowUvQuick: return "CPU Low UV - Boot Search";\n        case Stage::LowUvValidateQuick: return "CPU Low UV - Quick Test";\n        case Stage::LowUvLong: return "CPU Low UV - Validate";'''
if old not in s: raise SystemExit('compactStepName anchor not found')
s = s.replace(old, new, 1)

# 6) Preparation UI: expose current-settings baseline option.
old = '''    uiPrintf(29, "A : Check settings");\n    uiPrintf(30, "+ : Known PASS / Skip");\n    uiPrintf(31, "B : Exit    - : Reset");'''
new = '''    uiPrintf(29, "A : Check settings");\n    uiPrintf(30, "X : Use current settings as baseline");\n    uiPrintf(31, "+ : Known PASS / Skip");\n    uiPrintf(32, "B : Exit    - : Reset");'''
if old not in s: raise SystemExit('renderPreparation keys anchor not found')
s = s.replace(old, new, 1)

# Preparation check page also exposes the baseline path and leaves debug available.
old = '''    if (g.stage == Stage::Preparation)\n        uiPrintf(4, "\\x1b[33mY : RAW CONFIG DEBUG\\x1b[0m");\n    if (!g_configCheck.readOk) {\n        uiPrintf(5, "Could not read Horizon OC config.ini");\n        uiPrintf(6, "Result : 0x%08X", g_configCheck.rc);\n        uiPrintf(9, "A : Check again");\n        uiPrintf(10, "B : Back");\n        consoleUpdate(nullptr);\n        return;\n    }\n\n    const u32 m = g_configCheck.mask;\n    int row = 5;'''
new = '''    if (g.stage == Stage::Preparation) {\n        uiPrintf(4, "X : Use current tuning as baseline");\n        uiPrintf(5, "\\x1b[33mY : RAW CONFIG DEBUG\\x1b[0m");\n    }\n    if (!g_configCheck.readOk) {\n        const int r = (g.stage == Stage::Preparation) ? 7 : 5;\n        uiPrintf(r, "Could not read Horizon OC config.ini");\n        uiPrintf(r + 1, "Result : 0x%08X", g_configCheck.rc);\n        uiPrintf(r + 4, "A : Check again");\n        uiPrintf(r + 5, "B : Back");\n        consoleUpdate(nullptr);\n        return;\n    }\n\n    const u32 m = g_configCheck.mask;\n    int row = (g.stage == Stage::Preparation) ? 7 : 5;'''
if old not in s: raise SystemExit('renderConfigPrompt header anchor not found')
s = s.replace(old, new, 1)

# 7) Low UV state machine: boot to the limit first, then quick test, then long test.
old = '''        case Stage::LowUvQuick:\n            g.lowUvGood = g.lowUvTest;\n            if (g.lowUvTest >= LOW_UV_MAX) {\n                g.stage = Stage::LowUvLong;\n                g.stageReadyAfterBoot = true; // same already-booted value\n            } else {\n                ++g.lowUvTest;\n                g.stageReadyAfterBoot = false;\n            }\n            break;\n        case Stage::LowUvLong:\n            g.recoveryNeeded = false;\n            g.stage = Stage::LowVminQuick;\n            g.lowVminTest = g.lowVminGood - LOW_VMIN_STEP_MV;\n            g.stageReadyAfterBoot = false;\n            break;'''
new = '''        case Stage::LowUvQuick:\n            // Boot succeeded: remember this as the last bootable value and keep\n            // walking downward (higher UV index) without stress testing yet.\n            g.lowUvGood = g.lowUvTest;\n            if (g.lowUvTest >= LOW_UV_MAX) {\n                g.stage = Stage::LowUvValidateQuick;\n                g.stageReadyAfterBoot = true; // same already-booted value\n            } else {\n                ++g.lowUvTest;\n                g.stageReadyAfterBoot = false;\n            }\n            break;\n        case Stage::LowUvValidateQuick:\n            // First stress test only after the boot limit has been found.\n            g.stage = Stage::LowUvLong;\n            g.stageReadyAfterBoot = true;\n            break;\n        case Stage::LowUvLong:\n            g.recoveryNeeded = false;\n            if (g.lowVminGood <= LOW_VMIN_MIN_MV) {\n                restartVminSweep(false);\n                g.stageReadyAfterBoot = true;\n            } else {\n                g.stage = Stage::LowVminQuick;\n                g.lowVminTest = g.lowVminGood - LOW_VMIN_STEP_MV;\n                g.stageReadyAfterBoot = false;\n            }\n            break;'''
if old not in s: raise SystemExit('handlePass lowuv anchor not found')
s = s.replace(old, new, 1)

# Preserve adopted VDDQ baseline instead of returning to hardware starting value.
old = '''            if (g.vminValidateIndex >= g.vminValidateCount) {\n                g.stage = Stage::VddqQuick;\n                g.vddqTest = g.vddqStartMv - VDDQ_STEP_MV;\n                g.stageReadyAfterBoot = false;\n            }'''
new = '''            if (g.vminValidateIndex >= g.vminValidateCount) {\n                if (g.vddqGood <= VDDQ_MIN_MV) {\n                    g.stage = Stage::VddqLong;\n                    g.stageReadyAfterBoot = true;\n                } else {\n                    g.stage = Stage::VddqQuick;\n                    g.vddqTest = g.vddqGood - VDDQ_STEP_MV;\n                    g.stageReadyAfterBoot = false;\n                }\n            }'''
if old not in s: raise SystemExit('VDDQ baseline transition anchor not found')
s = s.replace(old, new, 1)

# Preserve adopted VDD2 baseline.
old = '''        case Stage::VddqLong:\n            g.recoveryNeeded = false;\n            g.stage = Stage::Vdd2Quick;\n            g.vdd2TestUv = STOCK_VDD2_UV - VDD2_STEP_UV;\n            g.stageReadyAfterBoot = false;\n            break;'''
new = '''        case Stage::VddqLong:\n            g.recoveryNeeded = false;\n            if (g.vdd2GoodUv <= VDD2_MIN_UV) {\n                g.stage = Stage::Vdd2Long;\n                g.stageReadyAfterBoot = true;\n            } else {\n                g.stage = Stage::Vdd2Quick;\n                g.vdd2TestUv = g.vdd2GoodUv - VDD2_STEP_UV;\n                g.stageReadyAfterBoot = false;\n            }\n            break;'''
if old not in s: raise SystemExit('VDD2 baseline transition anchor not found')
s = s.replace(old, new, 1)

# Preserve adopted High UV baseline.
old = '''        case Stage::Ram1331Validate:\n            g.stage = Stage::HighUvQuick;\n            g.highUvTest = 1;\n            g.stageReadyAfterBoot = false;\n            break;'''
new = '''        case Stage::Ram1331Validate:\n            if (g.highUvGood >= HIGH_UV_MAX) {\n                g.stage = Stage::HighUvLong;\n                g.stageReadyAfterBoot = true;\n            } else {\n                g.stage = Stage::HighUvQuick;\n                g.highUvTest = g.highUvGood + 1;\n                g.stageReadyAfterBoot = false;\n            }\n            break;'''
if old not in s: raise SystemExit('High UV baseline transition anchor not found')
s = s.replace(old, new, 1)

# Low UV failure behavior: boot failure restores last bootable value for quick validation;
# quick-test failure backs off one more step and retries quick validation.
old = '''        case Stage::LowUvQuick:\n            g.stage = Stage::LowUvLong;\n            g.recoveryNeeded = didNotBoot;\n            g.pendingConfigMask = Config_LowUv;\n            break;\n        case Stage::LowUvLong:\n            if (g.lowUvGood > 0) --g.lowUvGood;\n            g.pendingConfigMask = Config_LowUv;\n            break;'''
new = '''        case Stage::LowUvQuick:\n            g.stage = Stage::LowUvValidateQuick;\n            g.recoveryNeeded = didNotBoot;\n            g.pendingConfigMask = Config_LowUv;\n            break;\n        case Stage::LowUvValidateQuick:\n            if (g.lowUvGood > 0) --g.lowUvGood;\n            g.recoveryNeeded = false;\n            g.pendingConfigMask = Config_LowUv;\n            break;\n        case Stage::LowUvLong:\n            if (g.lowUvGood > 0) --g.lowUvGood;\n            g.pendingConfigMask = Config_LowUv;\n            break;'''
if old not in s: raise SystemExit('handleFail lowuv anchor not found')
s = s.replace(old, new, 1)

# 8) Boot success during LowUvQuick means continue the boot search, not start a test.
old = '''                if (g.stage == Stage::Preparation) {\n                    g.stage = Stage::LowUvQuick;\n                    g.stageReadyAfterBoot = false;\n                } else {\n                    g.stageReadyAfterBoot = true;\n                }\n                saveState();'''
new = '''                if (g.stage == Stage::Preparation) {\n                    if (g.lowUvGood >= LOW_UV_MAX) {\n                        g.stage = Stage::LowUvValidateQuick;\n                        g.stageReadyAfterBoot = true;\n                    } else {\n                        g.stage = Stage::LowUvQuick;\n                        g.lowUvTest = g.lowUvGood + 1;\n                        g.stageReadyAfterBoot = false;\n                    }\n                } else if (g.stage == Stage::LowUvQuick) {\n                    handlePass();\n                } else {\n                    g.stageReadyAfterBoot = true;\n                }\n                saveState();'''
if old not in s: raise SystemExit('boot success anchor not found')
s = s.replace(old, new, 1)

# 9) Baseline option on Preparation check page.
old = '''        if (g_configPrompt) {\n            if ((k & HidNpadButton_Y) && g.stage == Stage::Preparation) {\n                openConfigDebug();\n                redraw = true;\n            } else if (k & HidNpadButton_A) {'''
new = '''        if (g_configPrompt) {\n            if ((k & HidNpadButton_X) && g.stage == Stage::Preparation) {\n                if (captureCurrentSettingsBaseline()) {\n                    g_configPrompt = false;\n                    g_rebootConfirm = true;\n                }\n                redraw = true;\n            } else if ((k & HidNpadButton_Y) && g.stage == Stage::Preparation) {\n                openConfigDebug();\n                redraw = true;\n            } else if (k & HidNpadButton_A) {'''
if old not in s: raise SystemExit('config prompt input anchor not found')
s = s.replace(old, new, 1)

# Baseline option directly on Preparation page, before generic X/fail handling.
old = '''        } else if (k & HidNpadButton_Plus) {\n            if (isVminSweepStage(g.stage)) {'''
new = '''        } else if (g.stage == Stage::Preparation && (k & HidNpadButton_X)) {\n            if (captureCurrentSettingsBaseline()) g_rebootConfirm = true;\n            else g_configPrompt = true;\n            redraw = true;\n        } else if (k & HidNpadButton_Plus) {\n            if (isVminSweepStage(g.stage)) {'''
if old not in s: raise SystemExit('main preparation baseline input anchor not found')
s = s.replace(old, new, 1)

# Interrupted-test stage range includes the appended LowUvValidateQuick stage.
s = s.replace('static_cast<int>(Stage::LowVminPlateauValidate))\n                    g.stage = static_cast<Stage>(g.testStage);',
              'static_cast<int>(Stage::LowUvValidateQuick))\n                    g.stage = static_cast<Stage>(g.testStage);')

# Version bump.
mk = Path('Makefile')
ms = mk.read_text()
if 'APP_VERSION := 0.4.0-beta.24' not in ms: raise SystemExit('Makefile beta24 anchor not found')
mk.write_text(ms.replace('APP_VERSION := 0.4.0-beta.24', 'APP_VERSION := 0.4.0-beta.25', 1))

u = Path('UPDATE.txt')
us = u.read_text()
us = us.replace('version=0.4.0-beta.24', 'version=0.4.0-beta.25')
us = us.replace('/v0.4.0-beta.24/', '/v0.4.0-beta.25/')
u.write_text(us)

p.write_text(s)
