from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

def rep(old, new, label, count=1):
    global s
    if old not in s:
        raise SystemExit(f'{label} not found')
    s = s.replace(old, new, count)

# Persist a dedicated limit-notice state. stageReadyAfterBoot is also used for
# normal post-reboot quick tests, so it must not double as the UI notice flag.
rep('''    bool recoveryNeeded = false;\n    bool warningBelow590Seen = false;''',
    '''    bool recoveryNeeded = false;\n    bool warningBelow590Seen = false;\n    bool limitNoticePending = false;''',
    'state limit flag')
rep('''    f << "warningBelow590Seen=" << (g.warningBelow590Seen ? 1 : 0) << "\\n";''',
    '''    f << "warningBelow590Seen=" << (g.warningBelow590Seen ? 1 : 0) << "\\n";\n    f << "limitNoticePending=" << (g.limitNoticePending ? 1 : 0) << "\\n";''',
    'save limit flag')
rep('''    else if (key == "warningBelow590Seen") g.warningBelow590Seen = (v != 0);''',
    '''    else if (key == "warningBelow590Seen") g.warningBelow590Seen = (v != 0);\n    else if (key == "limitNoticePending") g.limitNoticePending = (v != 0);''',
    'load limit flag')

# Baseline at Low UV maximum: show the limit page before voltage-region scan.
rep('''    if (g.lowUvGood >= LOW_UV_MAX) {\n        g.stage = Stage::LowUvLong;\n        g.stageReadyAfterBoot = true;\n    } else {\n        g.stage = Stage::LowUvQuick;\n        g.lowUvTest = g.lowUvGood + 1;\n        g.stageReadyAfterBoot = false;\n    }''',
    '''    g.limitNoticePending = false;\n    if (g.lowUvGood >= LOW_UV_MAX) {\n        g.stage = Stage::LowUvQuick;\n        g.lowUvTest = g.lowUvGood;\n        g.stageReadyAfterBoot = true;\n        g.limitNoticePending = true;\n    } else {\n        g.stage = Stage::LowUvQuick;\n        g.lowUvTest = g.lowUvGood + 1;\n        g.stageReadyAfterBoot = false;\n    }''',
    'baseline Low UV limit')

# Replace the beta41 Low-VMIN-only helper with consistent helpers for every
# search domain that has a Wizard boundary.
old_helper = '''void enterLowVminSearchOrMinimumNotice() {\n    clearVminSweepData();\n    g.pendingConfigMask = Config_None;\n    if (g.lowVminGood == LOW_VMIN_MIN_MV) {\n        g.stage = Stage::LowVminQuick;\n        g.lowVminTest = LOW_VMIN_MIN_MV;\n        g.stageReadyAfterBoot = true;\n    } else if (g.lowVminGood > LOW_VMIN_MIN_MV) {\n        g.stage = Stage::LowVminQuick;\n        g.lowVminTest = std::max(LOW_VMIN_MIN_MV, g.lowVminGood - LOW_VMIN_STEP_MV);\n        g.stageReadyAfterBoot = false;\n    } else {\n        restartVminSweep(false);\n        g.stageReadyAfterBoot = true;\n    }\n}\n'''
new_helper = '''void enterLowVminSearchOrMinimumNotice() {\n    clearVminSweepData();\n    g.pendingConfigMask = Config_None;\n    g.limitNoticePending = false;\n    if (g.lowVminGood <= LOW_VMIN_MIN_MV) {\n        g.stage = Stage::LowVminQuick;\n        g.lowVminTest = g.lowVminGood;\n        g.stageReadyAfterBoot = true;\n        g.limitNoticePending = true;\n    } else {\n        g.stage = Stage::LowVminQuick;\n        g.lowVminTest = std::max(LOW_VMIN_MIN_MV, g.lowVminGood - LOW_VMIN_STEP_MV);\n        g.stageReadyAfterBoot = false;\n    }\n}\n\nvoid enterVddqSearchOrMinimumNotice() {\n    g.pendingConfigMask = Config_None;\n    g.limitNoticePending = false;\n    g.stage = Stage::VddqQuick;\n    if (g.vddqGood <= VDDQ_MIN_MV) {\n        g.vddqTest = g.vddqGood;\n        g.stageReadyAfterBoot = true;\n        g.limitNoticePending = true;\n    } else {\n        g.vddqTest = g.vddqGood - VDDQ_STEP_MV;\n        g.stageReadyAfterBoot = false;\n    }\n}\n\nvoid enterVdd2SearchOrMinimumNotice() {\n    g.pendingConfigMask = Config_None;\n    g.limitNoticePending = false;\n    g.stage = Stage::Vdd2Quick;\n    if (g.vdd2GoodUv <= VDD2_MIN_UV) {\n        g.vdd2TestUv = g.vdd2GoodUv;\n        g.stageReadyAfterBoot = true;\n        g.limitNoticePending = true;\n    } else {\n        g.vdd2TestUv = g.vdd2GoodUv - VDD2_STEP_UV;\n        g.stageReadyAfterBoot = false;\n    }\n}\n\nvoid enterHighUvSearchOrMaximumNotice() {\n    g.pendingConfigMask = Config_None;\n    g.limitNoticePending = false;\n    g.stage = Stage::HighUvQuick;\n    if (g.highUvGood >= HIGH_UV_MAX) {\n        g.highUvTest = g.highUvGood;\n        g.stageReadyAfterBoot = true;\n        g.limitNoticePending = true;\n    } else {\n        g.highUvTest = g.highUvGood + 1;\n        g.stageReadyAfterBoot = false;\n    }\n}\n\nvoid confirmWizardLimitAndContinue() {\n    g.limitNoticePending = false;\n    g.pendingConfigMask = Config_None;\n    switch (g.stage) {\n        case Stage::LowUvQuick:\n            g.stage = Stage::LowUvLong;\n            g.stageReadyAfterBoot = true;\n            break;\n        case Stage::LowVminQuick:\n            restartVminSweep(false);\n            g.stageReadyAfterBoot = true;\n            g.pendingConfigMask = Config_None;\n            break;\n        case Stage::VddqQuick:\n            g.stage = Stage::VddqLong;\n            g.stageReadyAfterBoot = true;\n            break;\n        case Stage::Vdd2Quick:\n            g.ramPairRetryMode = 0;\n            g.stage = Stage::Vdd2Long;\n            g.stageReadyAfterBoot = true;\n            break;\n        case Stage::HighUvQuick:\n            g.stage = Stage::BoostCpuRamValidate;\n            g.stageReadyAfterBoot = true;\n            break;\n        default:\n            break;\n    }\n    saveState();\n}\n'''
rep(old_helper, new_helper, 'all limit helpers')

# Quick-search PASS at a boundary now stops on the explicit limit page.
rep('''        case Stage::LowUvQuick:\n            // Boot-stable candidate confirmed by the post-reboot check.\n            g.lowUvGood = g.lowUvTest;\n            if (g.lowUvTest >= LOW_UV_MAX) {\n                g.stage = Stage::LowUvLong;\n                g.stageReadyAfterBoot = true;\n            } else {\n                ++g.lowUvTest;\n                g.stageReadyAfterBoot = false;\n            }\n            break;''',
    '''        case Stage::LowUvQuick:\n            // Boot-stable candidate confirmed by the post-reboot check.\n            g.lowUvGood = g.lowUvTest;\n            if (g.lowUvTest >= LOW_UV_MAX) {\n                g.stageReadyAfterBoot = true;\n                g.limitNoticePending = true;\n            } else {\n                ++g.lowUvTest;\n                g.stageReadyAfterBoot = false;\n                g.limitNoticePending = false;\n            }\n            break;''',
    'Low UV pass limit')

rep('''        case Stage::LowVminQuick:\n            g.lowVminGood = g.lowVminTest;\n            if (g.lowVminTest <= LOW_VMIN_MIN_MV) {\n                restartVminSweep(false);\n                g.stageReadyAfterBoot = true; // 570 was already booted for quick test\n                return;\n            }\n            g.lowVminTest -= LOW_VMIN_STEP_MV;\n            g.stageReadyAfterBoot = false;\n            break;''',
    '''        case Stage::LowVminQuick:\n            g.lowVminGood = g.lowVminTest;\n            if (g.lowVminTest <= LOW_VMIN_MIN_MV) {\n                g.stageReadyAfterBoot = true;\n                g.limitNoticePending = true;\n            } else {\n                g.lowVminTest -= LOW_VMIN_STEP_MV;\n                g.stageReadyAfterBoot = false;\n                g.limitNoticePending = false;\n            }\n            break;''',
    'Low VMIN pass limit')

rep('''        case Stage::VddqQuick:\n            g.vddqGood = g.vddqTest;\n            if (g.vddqTest <= VDDQ_MIN_MV) {\n                g.stage = Stage::VddqLong;\n                g.stageReadyAfterBoot = true;\n            } else {\n                g.vddqTest -= VDDQ_STEP_MV;\n                g.stageReadyAfterBoot = false;\n            }\n            break;''',
    '''        case Stage::VddqQuick:\n            g.vddqGood = g.vddqTest;\n            if (g.vddqTest <= VDDQ_MIN_MV) {\n                g.stageReadyAfterBoot = true;\n                g.limitNoticePending = true;\n            } else {\n                g.vddqTest -= VDDQ_STEP_MV;\n                g.stageReadyAfterBoot = false;\n                g.limitNoticePending = false;\n            }\n            break;''',
    'VDDQ pass limit')

rep('''        case Stage::Vdd2Quick:\n            g.vdd2GoodUv = g.vdd2TestUv;\n            if (g.vdd2TestUv <= VDD2_MIN_UV) {\n                g.ramPairRetryMode = 0;\n                g.stage = Stage::Vdd2Long;\n                g.stageReadyAfterBoot = true;\n            } else {\n                g.vdd2TestUv -= VDD2_STEP_UV;\n                g.stageReadyAfterBoot = false;\n            }\n            break;''',
    '''        case Stage::Vdd2Quick:\n            g.vdd2GoodUv = g.vdd2TestUv;\n            if (g.vdd2TestUv <= VDD2_MIN_UV) {\n                g.stageReadyAfterBoot = true;\n                g.limitNoticePending = true;\n            } else {\n                g.vdd2TestUv -= VDD2_STEP_UV;\n                g.stageReadyAfterBoot = false;\n                g.limitNoticePending = false;\n            }\n            break;''',
    'VDD2 pass limit')

rep('''        case Stage::HighUvQuick:\n            g.highUvGood = g.highUvTest;\n            if (g.highUvTest >= HIGH_UV_MAX) {\n                g.stage = Stage::BoostCpuRamValidate;\n                g.stageReadyAfterBoot = true;\n            } else {\n                ++g.highUvTest;\n                g.stageReadyAfterBoot = false;\n            }\n            break;''',
    '''        case Stage::HighUvQuick:\n            g.highUvGood = g.highUvTest;\n            if (g.highUvTest >= HIGH_UV_MAX) {\n                g.stageReadyAfterBoot = true;\n                g.limitNoticePending = true;\n            } else {\n                ++g.highUvTest;\n                g.stageReadyAfterBoot = false;\n                g.limitNoticePending = false;\n            }\n            break;''',
    'High UV pass limit')

# Baseline/previous-stage transitions use the same limit-aware entry helpers.
rep('''            if (g.vddqGood <= VDDQ_MIN_MV) {\n                g.stage = Stage::VddqLong;\n                g.stageReadyAfterBoot = true;\n            } else {\n                g.stage = Stage::VddqQuick;\n                g.vddqTest = g.vddqGood - VDDQ_STEP_MV;\n                g.stageReadyAfterBoot = false;\n            }''',
    '''            enterVddqSearchOrMinimumNotice();''',
    'plateau to VDDQ helper', 1)
rep('''        if (g.vddqGood <= VDDQ_MIN_MV) {\n            g.stage = Stage::VddqLong;\n            g.stageReadyAfterBoot = true;\n        } else {\n            g.stage = Stage::VddqQuick;\n            g.vddqTest = g.vddqGood - VDDQ_STEP_MV;\n            g.stageReadyAfterBoot = false;\n        }''',
    '''        enterVddqSearchOrMinimumNotice();''',
    'skip to VDDQ helper', 1)
rep('''            clearVminSweepData();\n            if (g.vddqGood <= VDDQ_MIN_MV) {\n                g.stage = Stage::VddqLong;\n                g.stageReadyAfterBoot = true;\n            } else {\n                g.stage = Stage::VddqQuick;\n                g.vddqTest = g.vddqGood - VDDQ_STEP_MV;\n                g.stageReadyAfterBoot = false;\n            }''',
    '''            enterVddqSearchOrMinimumNotice();''',
    'auto validate to VDDQ helper', 1)

rep('''        case Stage::VddqLong:\n            g.recoveryNeeded = false;\n            if (g.vdd2GoodUv <= VDD2_MIN_UV) {\n                g.stage = Stage::Vdd2Long;\n                g.stageReadyAfterBoot = true;\n            } else {\n                g.stage = Stage::Vdd2Quick;\n                g.vdd2TestUv = g.vdd2GoodUv - VDD2_STEP_UV;\n                g.stageReadyAfterBoot = false;\n            }\n            break;''',
    '''        case Stage::VddqLong:\n            g.recoveryNeeded = false;\n            enterVdd2SearchOrMinimumNotice();\n            break;''',
    'VDDQ long to VDD2 helper')

rep('''        case Stage::NormalMatrixValidate:\n            if (g.highUvGood >= HIGH_UV_MAX) {\n                g.stage = Stage::BoostCpuRamValidate;\n                g.stageReadyAfterBoot = true;\n            } else {\n                g.stage = Stage::HighUvQuick;\n                g.highUvTest = g.highUvGood + 1;\n                g.stageReadyAfterBoot = false;\n            }\n            break;''',
    '''        case Stage::NormalMatrixValidate:\n            enterHighUvSearchOrMaximumNotice();\n            break;''',
    'normal anchor to High UV helper')

# Replace the beta41 Low-VMIN-only page with one common limit page.
old_notice = '''    if (g.stage == Stage::LowVminQuick &&\n        g.stageReadyAfterBoot &&\n        g.lowVminGood == LOW_VMIN_MIN_MV &&\n        g.lowVminTest == LOW_VMIN_MIN_MV) {\n        uiPrintf(5, "Objective:");\n        uiPrintf(6, "Current Low VMIN : %d mV", g.lowVminGood);\n        uiPrintf(8, "570 mV is the minimum recommended");\n        uiPrintf(9, "value used by this Wizard.");\n        uiPrintf(11, "Going lower is not recommended.");\n        uiPrintf(12, "Very low VMIN values may cause");\n        uiPrintf(13, "Sleep / Standby / Wake problems.");\n        uiPrintf(15, "No lower value will be tested.");\n        uiPrintf(18, "A : Confirm 570 mV and continue");\n        uiPrintf(19, "B : Exit");\n        printResetHint(19);\n        return;\n    }\n'''
new_notice = '''    if (g.limitNoticePending) {\n        uiPrintf(5, "\\x1b[33mWizard search limit reached.\\x1b[0m");\n        switch (g.stage) {\n            case Stage::LowUvQuick:\n                uiPrintf(7, "Current Low UV : %d", g.lowUvGood);\n                uiPrintf(8, "Wizard maximum : %d", LOW_UV_MAX);\n                uiPrintf(10, "No higher Low UV level will be tested.");\n                uiPrintf(13, "A : Confirm Low UV %d and continue", g.lowUvGood);\n                break;\n            case Stage::LowVminQuick:\n                uiPrintf(7, "Current Low VMIN : %d mV", g.lowVminGood);\n                uiPrintf(8, "Wizard minimum   : %d mV", LOW_VMIN_MIN_MV);\n                uiPrintf(10, "Going lower is not recommended.");\n                uiPrintf(11, "Very low VMIN values may cause");\n                uiPrintf(12, "Sleep / Standby / Wake problems.");\n                uiPrintf(14, "No lower value will be tested.");\n                uiPrintf(17, "A : Confirm %d mV and continue", g.lowVminGood);\n                break;\n            case Stage::VddqQuick:\n                uiPrintf(7, "Current VDDQ    : %d mV", g.vddqGood);\n                uiPrintf(8, "Wizard minimum  : %d mV", VDDQ_MIN_MV);\n                uiPrintf(10, "The Wizard will not search below");\n                uiPrintf(11, "%d mV VDDQ.", VDDQ_MIN_MV);\n                uiPrintf(13, "No lower value will be tested.");\n                uiPrintf(16, "A : Confirm %d mV and continue", g.vddqGood);\n                break;\n            case Stage::Vdd2Quick:\n                uiPrintf(7, "Current VDD2   : %s", formatVdd2(g.vdd2GoodUv).c_str());\n                uiPrintf(8, "Wizard minimum : %s", formatVdd2(VDD2_MIN_UV).c_str());\n                uiPrintf(10, "The Wizard will not search below");\n                uiPrintf(11, "%s VDD2.", formatVdd2(VDD2_MIN_UV).c_str());\n                uiPrintf(13, "No lower value will be tested.");\n                uiPrintf(16, "A : Confirm %s and continue", formatVdd2(g.vdd2GoodUv).c_str());\n                break;\n            case Stage::HighUvQuick:\n                uiPrintf(7, "Current High UV : %d", g.highUvGood);\n                uiPrintf(8, "Wizard maximum  : %d", HIGH_UV_MAX);\n                uiPrintf(10, "No higher High UV level will be tested.");\n                uiPrintf(13, "A : Confirm High UV %d and continue", g.highUvGood);\n                break;\n            default:\n                uiPrintf(7, "The configured Wizard limit was reached.");\n                uiPrintf(10, "A : Confirm and continue");\n                break;\n        }\n        uiPrintf(19, "B : Exit");\n        printResetHint(19);\n        return;\n    }\n'''
rep(old_notice, new_notice, 'generic limit notice UI')

# Consume all input on a limit page except B/Minus, and A explicitly advances.
old_special_a = '''        } else if (k & HidNpadButton_A) {\n            const bool lowVminMinimumNotice =\n                g.stage == Stage::LowVminQuick &&\n                g.stageReadyAfterBoot &&\n                g.lowVminGood == LOW_VMIN_MIN_MV &&\n                g.lowVminTest == LOW_VMIN_MIN_MV;\n            if (lowVminMinimumNotice) {\n                restartVminSweep(false);\n                g.stageReadyAfterBoot = true;\n                saveState();\n            } else {\n                const bool bootSearch = g.stage == Stage::LowUvQuick || g.stage == Stage::LowVminQuick;'''
new_special_a = '''        } else if (g.limitNoticePending) {\n            if (k & HidNpadButton_A) {\n                confirmWizardLimitAndContinue();\n                redraw = true;\n            }\n        } else if (k & HidNpadButton_A) {\n            const bool bootSearch = g.stage == Stage::LowUvQuick || g.stage == Stage::LowVminQuick;'''
rep(old_special_a, new_special_a, 'limit input gate')

# Remove the extra brace that beta41 needed around its special A case.
rep('''                if (testPlan(g.stage, kind, seconds)) runCurrentTest();\n                else handlePass();\n            }\n            }\n            redraw = true;''',
    '''                if (testPlan(g.stage, kind, seconds)) runCurrentTest();\n                else handlePass();\n            }\n            redraw = true;''',
    'remove beta41 extra brace')

# Failed candidates must never leave a stale limit screen pending.
rep('''void handleFail(bool didNotBoot) {\n    g.stageReadyAfterBoot = false;''',
    '''void handleFail(bool didNotBoot) {\n    g.stageReadyAfterBoot = false;\n    g.limitNoticePending = false;''',
    'clear notice on fail')

# Reset helpers used when starting fresh/baseline preparation.
rep('''    g.recoveryNeeded = false;\n    g.stageReadyAfterBoot = false;\n    g.pendingConfigMask = Config_None;''',
    '''    g.recoveryNeeded = false;\n    g.stageReadyAfterBoot = false;\n    g.limitNoticePending = false;\n    g.pendingConfigMask = Config_None;''',
    'reset baseline notice', 1)

p.write_text(s)

m = Path('Makefile')
ms = m.read_text()
if 'APP_VERSION := 0.4.0-beta.41' not in ms:
    raise SystemExit('beta41 Makefile version not found')
ms = ms.replace('APP_VERSION := 0.4.0-beta.41', 'APP_VERSION := 0.4.0-beta.42', 1)
m.write_text(ms)
