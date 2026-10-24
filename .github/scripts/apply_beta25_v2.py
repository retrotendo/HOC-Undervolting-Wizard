from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

def rep(old, new, name):
    global s
    if old not in s:
        raise SystemExit(f'{name} anchor not found')
    s = s.replace(old, new, 1)

rep('''    HardwareDetection,\n    LowVminPlateauValidate\n};''', '''    HardwareDetection,\n    LowVminPlateauValidate,\n    // beta.25: LowUvQuick is boot-limit discovery; validation is separate.\n    LowUvValidateQuick\n};''', 'enum')

rep('''        case Stage::LowUvQuick:\n        case Stage::LowVminQuick:\n        case Stage::HighUvQuick:\n            kind = stress::Kind::Cpu; seconds = 60; return true;''', '''        case Stage::LowUvValidateQuick:\n        case Stage::LowVminQuick:\n        case Stage::HighUvQuick:\n            kind = stress::Kind::Cpu; seconds = 60; return true;''', 'testPlan')

rep('''        case Stage::LowUvQuick:\n        case Stage::LowUvLong:\n        case Stage::Ram1331Validate:''', '''        case Stage::LowUvQuick:\n        case Stage::LowUvValidateQuick:\n        case Stage::LowUvLong:\n        case Stage::Ram1331Validate:''', 'overridePlan')

rep('''        case Stage::LowUvQuick:\n        case Stage::LowUvLong: return Config_LowUv;''', '''        case Stage::LowUvQuick:\n        case Stage::LowUvValidateQuick:\n        case Stage::LowUvLong: return Config_LowUv;''', 'config mask')

rep('''int targetLowUv() {\n    return g.stage == Stage::LowUvQuick ? g.lowUvTest : g.lowUvGood;\n}''', '''int targetLowUv() {\n    // LowUvQuick is the boot-limit search. Validation uses the last value\n    // that actually booted.\n    return g.stage == Stage::LowUvQuick ? g.lowUvTest : g.lowUvGood;\n}''', 'targetLowUv')

rep('''    return sawValuesSection;\n}\n\nbool configMatchesCurrent(u32 mask, const HocMonConfig& c) {''', '''    return sawValuesSection;\n}\n\nbool preparationFixedSettingsMatch(const HocMonConfig& c) {\n    return !c.uncappedClocks && !c.hpMode &&\n           c.ramMaxKHz == 1600000U &&\n           c.cpuMaxKHz == 1963500U &&\n           c.tableConf == 3 &&\n           c.cpuBoostKHz == 1785000U &&\n           c.vdd2Uv != 0 && c.vddqUv != 0 &&\n           c.lowVminMv != 0 && c.highVminMv != 0;\n}\n\nbool captureCurrentSettingsBaseline() {\n    g_configCheck = ConfigCheckState{};\n    g_configCheck.mask = Config_Prepare;\n    g_configCheck.readOk = readHocConfigIni(g_configCheck.current);\n    g_configCheck.rc = g_configCheck.readOk ? 0 : 0xF024;\n    if (!g_configCheck.readOk || !preparationFixedSettingsMatch(g_configCheck.current))\n        return false;\n\n    const HocMonConfig& c = g_configCheck.current;\n    g.lowUvGood = std::max(0, c.lowUv);\n    g.lowUvTest = (g.lowUvGood < LOW_UV_MAX) ? g.lowUvGood + 1 : g.lowUvGood;\n    g.lowVminGood = c.lowVminMv;\n    g.lowVminTest = (g.lowVminGood > LOW_VMIN_MIN_MV) ? g.lowVminGood - LOW_VMIN_STEP_MV : g.lowVminGood;\n    g.vddqGood = (int)(c.vddqUv / 1000U);\n    g.vddqTest = (g.vddqGood > VDDQ_MIN_MV) ? g.vddqGood - VDDQ_STEP_MV : g.vddqGood;\n    g.vdd2GoodUv = (int)c.vdd2Uv;\n    g.vdd2TestUv = (g.vdd2GoodUv > VDD2_MIN_UV) ? g.vdd2GoodUv - VDD2_STEP_UV : g.vdd2GoodUv;\n    g.highUvGood = std::max(0, c.highUv);\n    g.highUvTest = (g.highUvGood < HIGH_UV_MAX) ? g.highUvGood + 1 : g.highUvGood;\n    g.stageReadyAfterBoot = false;\n    g.pendingConfigMask = Config_None;\n    saveState();\n    return true;\n}\n\nbool configMatchesCurrent(u32 mask, const HocMonConfig& c) {''', 'baseline functions')

rep('''        case Stage::LowUvQuick: return "CPU Low UV - Quick Search";\n        case Stage::LowUvLong: return "CPU Low UV - 1 Hour Validation";''', '''        case Stage::LowUvQuick: return "CPU Low UV - Boot Search";\n        case Stage::LowUvValidateQuick: return "CPU Low UV - Quick Validation";\n        case Stage::LowUvLong: return "CPU Low UV - 1 Hour Validation";''', 'stageName')

rep('''        case Stage::LowUvQuick: return "CPU Low UV";\n        case Stage::LowUvLong: return "CPU Low UV - Validate";''', '''        case Stage::LowUvQuick: return "CPU Low UV - Boot Search";\n        case Stage::LowUvValidateQuick: return "CPU Low UV - Quick Test";\n        case Stage::LowUvLong: return "CPU Low UV - Validate";''', 'compactStepName')

rep('''    uiPrintf(29, "A : Check settings");\n    uiPrintf(30, "+ : Known PASS / Skip");\n    uiPrintf(31, "B : Exit    - : Reset");''', '''    uiPrintf(29, "A : Check settings");\n    uiPrintf(30, "X : Use current settings as baseline");\n    uiPrintf(31, "+ : Known PASS / Skip");\n    uiPrintf(32, "B : Exit    - : Reset");''', 'Preparation UI')

# Replace the Preparation-specific header of renderConfigPrompt without depending on ANSI byte spelling.
func = s.index('void renderConfigPrompt()')
start = s.index('    if (g.stage == Stage::Preparation)', func)
end = s.index('    if (m & Config_Prepare) {', start)
header = '''    if (g.stage == Stage::Preparation) {\n        uiPrintf(4, "X : Use current tuning as baseline");\n        uiPrintf(5, "\\x1b[33mY : RAW CONFIG DEBUG\\x1b[0m");\n    }\n    if (!g_configCheck.readOk) {\n        const int r = (g.stage == Stage::Preparation) ? 7 : 5;\n        uiPrintf(r, "Could not read Horizon OC config.ini");\n        uiPrintf(r + 1, "Result : 0x%08X", g_configCheck.rc);\n        uiPrintf(r + 4, "A : Check again");\n        uiPrintf(r + 5, "B : Back");\n        consoleUpdate(nullptr);\n        return;\n    }\n\n    const u32 m = g_configCheck.mask;\n    int row = (g.stage == Stage::Preparation) ? 7 : 5;\n'''
s = s[:start] + header + s[end:]

rep('''        case Stage::LowUvQuick:\n            g.lowUvGood = g.lowUvTest;\n            if (g.lowUvTest >= LOW_UV_MAX) {\n                g.stage = Stage::LowUvLong;\n                g.stageReadyAfterBoot = true; // same already-booted value\n            } else {\n                ++g.lowUvTest;\n                g.stageReadyAfterBoot = false;\n            }\n            break;\n        case Stage::LowUvLong:\n            g.recoveryNeeded = false;\n            g.stage = Stage::LowVminQuick;\n            g.lowVminTest = g.lowVminGood - LOW_VMIN_STEP_MV;\n            g.stageReadyAfterBoot = false;\n            break;''', '''        case Stage::LowUvQuick:\n            g.lowUvGood = g.lowUvTest;\n            if (g.lowUvTest >= LOW_UV_MAX) {\n                g.stage = Stage::LowUvValidateQuick;\n                g.stageReadyAfterBoot = true;\n            } else {\n                ++g.lowUvTest;\n                g.stageReadyAfterBoot = false;\n            }\n            break;\n        case Stage::LowUvValidateQuick:\n            g.stage = Stage::LowUvLong;\n            g.stageReadyAfterBoot = true;\n            break;\n        case Stage::LowUvLong:\n            g.recoveryNeeded = false;\n            if (g.lowVminGood <= LOW_VMIN_MIN_MV) {\n                restartVminSweep(false);\n                g.stageReadyAfterBoot = true;\n            } else {\n                g.stage = Stage::LowVminQuick;\n                g.lowVminTest = g.lowVminGood - LOW_VMIN_STEP_MV;\n                g.stageReadyAfterBoot = false;\n            }\n            break;''', 'Low UV pass flow')

rep('''            if (g.vminValidateIndex >= g.vminValidateCount) {\n                g.stage = Stage::VddqQuick;\n                g.vddqTest = g.vddqStartMv - VDDQ_STEP_MV;\n                g.stageReadyAfterBoot = false;\n            }''', '''            if (g.vminValidateIndex >= g.vminValidateCount) {\n                if (g.vddqGood <= VDDQ_MIN_MV) {\n                    g.stage = Stage::VddqLong;\n                    g.stageReadyAfterBoot = true;\n                } else {\n                    g.stage = Stage::VddqQuick;\n                    g.vddqTest = g.vddqGood - VDDQ_STEP_MV;\n                    g.stageReadyAfterBoot = false;\n                }\n            }''', 'VDDQ baseline')

rep('''        case Stage::VddqLong:\n            g.recoveryNeeded = false;\n            g.stage = Stage::Vdd2Quick;\n            g.vdd2TestUv = STOCK_VDD2_UV - VDD2_STEP_UV;\n            g.stageReadyAfterBoot = false;\n            break;''', '''        case Stage::VddqLong:\n            g.recoveryNeeded = false;\n            if (g.vdd2GoodUv <= VDD2_MIN_UV) {\n                g.stage = Stage::Vdd2Long;\n                g.stageReadyAfterBoot = true;\n            } else {\n                g.stage = Stage::Vdd2Quick;\n                g.vdd2TestUv = g.vdd2GoodUv - VDD2_STEP_UV;\n                g.stageReadyAfterBoot = false;\n            }\n            break;''', 'VDD2 baseline')

rep('''        case Stage::Ram1331Validate:\n            g.stage = Stage::HighUvQuick;\n            g.highUvTest = 1;\n            g.stageReadyAfterBoot = false;\n            break;''', '''        case Stage::Ram1331Validate:\n            if (g.highUvGood >= HIGH_UV_MAX) {\n                g.stage = Stage::HighUvLong;\n                g.stageReadyAfterBoot = true;\n            } else {\n                g.stage = Stage::HighUvQuick;\n                g.highUvTest = g.highUvGood + 1;\n                g.stageReadyAfterBoot = false;\n            }\n            break;''', 'High UV baseline')

rep('''        case Stage::LowUvQuick:\n            g.stage = Stage::LowUvLong;\n            g.recoveryNeeded = didNotBoot;\n            g.pendingConfigMask = Config_LowUv;\n            break;\n        case Stage::LowUvLong:\n            if (g.lowUvGood > 0) --g.lowUvGood;\n            g.pendingConfigMask = Config_LowUv;\n            break;''', '''        case Stage::LowUvQuick:\n            g.stage = Stage::LowUvValidateQuick;\n            g.recoveryNeeded = didNotBoot;\n            g.pendingConfigMask = Config_LowUv;\n            break;\n        case Stage::LowUvValidateQuick:\n            if (g.lowUvGood > 0) --g.lowUvGood;\n            g.recoveryNeeded = false;\n            g.pendingConfigMask = Config_LowUv;\n            break;\n        case Stage::LowUvLong:\n            if (g.lowUvGood > 0) --g.lowUvGood;\n            g.pendingConfigMask = Config_LowUv;\n            break;''', 'Low UV fail flow')

rep('''                if (g.stage == Stage::Preparation) {\n                    g.stage = Stage::LowUvQuick;\n                    g.stageReadyAfterBoot = false;\n                } else {\n                    g.stageReadyAfterBoot = true;\n                }\n                saveState();''', '''                if (g.stage == Stage::Preparation) {\n                    if (g.lowUvGood >= LOW_UV_MAX) {\n                        g.stage = Stage::LowUvValidateQuick;\n                        g.stageReadyAfterBoot = true;\n                    } else {\n                        g.stage = Stage::LowUvQuick;\n                        g.lowUvTest = g.lowUvGood + 1;\n                        g.stageReadyAfterBoot = false;\n                    }\n                } else if (g.stage == Stage::LowUvQuick) {\n                    handlePass();\n                } else {\n                    g.stageReadyAfterBoot = true;\n                }\n                saveState();''', 'boot success flow')

rep('''        if (g_configPrompt) {\n            if ((k & HidNpadButton_Y) && g.stage == Stage::Preparation) {\n                openConfigDebug();\n                redraw = true;\n            } else if (k & HidNpadButton_A) {''', '''        if (g_configPrompt) {\n            if ((k & HidNpadButton_X) && g.stage == Stage::Preparation) {\n                if (captureCurrentSettingsBaseline()) {\n                    g_configPrompt = false;\n                    g_rebootConfirm = true;\n                }\n                redraw = true;\n            } else if ((k & HidNpadButton_Y) && g.stage == Stage::Preparation) {\n                openConfigDebug();\n                redraw = true;\n            } else if (k & HidNpadButton_A) {''', 'configPrompt input')

rep('''        } else if (k & HidNpadButton_Plus) {\n            if (isVminSweepStage(g.stage)) {''', '''        } else if (g.stage == Stage::Preparation && (k & HidNpadButton_X)) {\n            if (captureCurrentSettingsBaseline()) g_rebootConfirm = true;\n            else g_configPrompt = true;\n            redraw = true;\n        } else if (k & HidNpadButton_Plus) {\n            if (isVminSweepStage(g.stage)) {''', 'Preparation baseline input')

s = s.replace('static_cast<int>(Stage::LowVminPlateauValidate))\n                    g.stage = static_cast<Stage>(g.testStage);', 'static_cast<int>(Stage::LowUvValidateQuick))\n                    g.stage = static_cast<Stage>(g.testStage);')

p.write_text(s)

mk = Path('Makefile')
ms = mk.read_text()
if 'APP_VERSION := 0.4.0-beta.24' not in ms: raise SystemExit('Makefile version anchor not found')
mk.write_text(ms.replace('APP_VERSION := 0.4.0-beta.24', 'APP_VERSION := 0.4.0-beta.25', 1))

u = Path('UPDATE.txt')
us = u.read_text()
us = us.replace('version=0.4.0-beta.24', 'version=0.4.0-beta.25')
us = us.replace('/v0.4.0-beta.24/', '/v0.4.0-beta.25/')
u.write_text(us)
