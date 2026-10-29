from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

def rep(old, new, label, count=1):
    global s
    if old not in s:
        raise SystemExit(f'{label} not found')
    s = s.replace(old, new, count)

# Labels: first RAM rail gets a shorter confirmation; the second-rail final
# stage is the one-hour pair validation because both final rails are active.
rep('case Stage::VddqLong: return "VDDQ - 1 Hour Validation";',
    'case Stage::VddqLong: return "VDDQ - 30 Minute Validation";',
    'stageName VDDQ long')
rep('case Stage::Vdd2Long: return "VDD2 - 1 Hour Validation";',
    'case Stage::Vdd2Long: return "RAM Rails - Final Pair Validation";',
    'stageName VDD2 long')
rep('case Stage::BoostCpuRamValidate: return "Boost CPU + RAM Validation";',
    'case Stage::BoostCpuRamValidate: return "High UV - CPU Memtester";',
    'stageName high uv cpu memtester')
rep('case Stage::BoostCpuMemValidate: return "Final Boost - CPU + RAM";',
    'case Stage::BoostCpuMemValidate: return "High UV + RAM Combined";',
    'stageName combined')

rep('case Stage::VddqLong: return "RAM VDDQ - Validate";',
    'case Stage::VddqLong: return "RAM VDDQ - 30 min Validate";',
    'compact VDDQ long')
rep('case Stage::Vdd2Long: return "RAM VDD2 - Validate";',
    'case Stage::Vdd2Long: return "RAM Rails - Final Pair";',
    'compact VDD2 long')
rep('case Stage::BoostCpuRamValidate: return "Boost CPU + RAM";',
    'case Stage::BoostCpuRamValidate: return "High UV - CPU Memtester";',
    'compact high uv cpu memtester')
rep('case Stage::BoostCpuMemValidate: return "Final Boost - CPU + RAM";',
    'case Stage::BoostCpuMemValidate: return "High UV + RAM Combined";',
    'compact combined')

# Test plan: VDDQ final gets 30 minutes. VDD2Long is deliberately kept as a
# one-hour RAM test, but now represents the final VDDQ+VDD2 pair with both
# tuned rails active. High UV then gets CPU-memtester followed by Combined.
old_test = '''        case Stage::VddqLong:\n        case Stage::Vdd2Long:\n        case Stage::RamBoostValidate:\n        case Stage::Ram1331Validate:\n        case Stage::NormalMatrixValidate:\n        case Stage::NormalMemValidate:\n        case Stage::BoostCpuRamValidate:\n        case Stage::BoostMemValidate:\n            kind = stress::Kind::Ram; seconds = 3600; return true;'''
new_test = '''        case Stage::VddqLong:\n            kind = stress::Kind::Ram; seconds = 1800; return true;\n        case Stage::Vdd2Long:\n        case Stage::RamBoostValidate:\n        case Stage::Ram1331Validate:\n        case Stage::NormalMatrixValidate:\n        case Stage::NormalMemValidate:\n        case Stage::BoostCpuRamValidate:\n        case Stage::BoostMemValidate:\n            kind = stress::Kind::Ram; seconds = 3600; return true;'''
rep(old_test, new_test, 'testPlan RAM durations')

# VDD2Long objective is no longer an individual VDD2 test: by this point both
# final rail values are active, so make the pair validation explicit.
old_obj = '''        case Stage::Vdd2Quick:\n        case Stage::Vdd2Long: {\n            const int value = g.stage == Stage::Vdd2Quick ? g.vdd2TestUv : g.vdd2GoodUv;\n            uiPrintf(row++, "VDD2 %s will be tested now.", formatVdd2(value).c_str());\n            uiPrintf(row++, "Current VDD2 : %s", haveCurrent ? formatVdd2((int)current.vdd2Uv).c_str() : "unavailable");\n            break;\n        }'''
new_obj = '''        case Stage::Vdd2Quick: {\n            uiPrintf(row++, "VDD2 %s will be tested now.", formatVdd2(g.vdd2TestUv).c_str());\n            uiPrintf(row++, "Current VDD2 : %s", haveCurrent ? formatVdd2((int)current.vdd2Uv).c_str() : "unavailable");\n            break;\n        }\n        case Stage::Vdd2Long:\n            uiPrintf(row++, "Final VDDQ + VDD2 pair will be tested now.");\n            if (haveCurrent) {\n                uiPrintf(row++, "Current VDDQ : %s", formatMv((int)(current.vddqUv / 1000U)).c_str());\n                uiPrintf(row++, "Current VDD2 : %s", formatVdd2((int)current.vdd2Uv).c_str());\n            }\n            break;'''
rep(old_obj, new_obj, 'VDD2 pair objective')

# Rename final High-UV objectives to show the two distinct one-hour workloads.
old_boost_obj = '''        case Stage::BoostCpuRamValidate:\n            uiPrintf(row++, "Final High UV + RAM Boost stability");\n            uiPrintf(row++, "will be tested now at 1785 / 1600.");\n            break;'''
new_boost_obj = '''        case Stage::BoostCpuRamValidate:\n            uiPrintf(row++, "Final High UV CPU-memtester");\n            uiPrintf(row++, "will run at 1785 / 76.8 / 1600.");\n            break;'''
rep(old_boost_obj, new_boost_obj, 'Boost CPU memtester objective')

old_legacy_obj = '''        case Stage::BoostCpuMemValidate:\n            uiPrintf(row++, "Final Boost CPU + RAM stability will be tested now.");\n            break;'''
new_legacy_obj = '''        case Stage::BoostCpuMemValidate:\n            uiPrintf(row++, "High UV + high RAM combined stability");\n            uiPrintf(row++, "will run at 1785 / 76.8 / 1600.");\n            break;'''
rep(old_legacy_obj, new_legacy_obj, 'Combined objective')

# After the High-UV CPU-memtester, always run the separate Combined workload.
rep('case Stage::BoostCpuRamValidate: g.stage = Stage::RealWorldValidate; break;',
    'case Stage::BoostCpuRamValidate: g.stage = Stage::BoostCpuMemValidate; break;',
    'High UV CPU memtester transition')

# Combined failure lowers High UV, then repeats the CPU-memtester first so the
# replacement High-UV value is validated in the same order before Combined.
old_fail = '''        case Stage::BoostMatrixValidate:\n        case Stage::BoostCpuMemValidate:\n            if (g.highUvGood > 0) --g.highUvGood;\n            g.pendingConfigMask = Config_HighUv;\n            break;'''
new_fail = '''        case Stage::BoostMatrixValidate:\n            if (g.highUvGood > 0) --g.highUvGood;\n            g.pendingConfigMask = Config_HighUv;\n            break;\n        case Stage::BoostCpuMemValidate:\n            if (g.highUvGood > 0) --g.highUvGood;\n            g.stage = Stage::BoostCpuRamValidate;\n            g.pendingConfigMask = Config_HighUv;\n            break;'''
rep(old_fail, new_fail, 'Combined fail retry order')

# Pair validation failure should use the same two-rail retry logic that was
# already used by RamBoostValidate, instead of assuming VDD2 alone caused it.
old_vdd2_fail = '''        case Stage::Vdd2Long:\n            g.vdd2GoodUv += VDD2_STEP_UV;\n            g.pendingConfigMask = Config_Vdd2;\n            break;\n        case Stage::RamBoostValidate:\n            if (g.ramPairRetryMode == 0) {'''
new_vdd2_fail = '''        case Stage::Vdd2Long:\n        case Stage::RamBoostValidate:\n            if (g.ramPairRetryMode == 0) {'''
rep(old_vdd2_fail, new_vdd2_fail, 'pair fail shared retry')

# Start pair retry bookkeeping before entering the final pair stage.
old_vdd2_quick_fail = '''        case Stage::Vdd2Quick:\n            g.stage = Stage::Vdd2Long;\n            g.recoveryNeeded = didNotBoot;\n            g.pendingConfigMask = Config_Vdd2;\n            break;'''
new_vdd2_quick_fail = '''        case Stage::Vdd2Quick:\n            g.stage = Stage::Vdd2Long;\n            g.recoveryNeeded = didNotBoot;\n            g.ramPairRetryMode = 0;\n            g.pendingConfigMask = Config_Vdd2;\n            break;'''
rep(old_vdd2_quick_fail, new_vdd2_quick_fail, 'VDD2 quick fail pair mode')

# When VDD2 reaches the minimum through PASS rather than first FAIL, also reset
# pair retry state before the one-hour pair validation.
old_min = '''            if (g.vdd2TestUv <= VDD2_MIN_UV) {\n                g.stage = Stage::Vdd2Long;\n                g.stageReadyAfterBoot = true;\n            } else {'''
new_min = '''            if (g.vdd2TestUv <= VDD2_MIN_UV) {\n                g.ramPairRetryMode = 0;\n                g.stage = Stage::Vdd2Long;\n                g.stageReadyAfterBoot = true;\n            } else {'''
rep(old_min, new_min, 'VDD2 min pair mode')

# 30-minute duration must render correctly both on the start page and after an
# interrupted reboot/crash.
rep('uiPrintf(row++, "%s - %s", seconds == 60 ? "1 min" : "1 hour", compactTestName(kind));',
    'uiPrintf(row++, "%s - %s", seconds == 60 ? "1 min" : (seconds == 1800 ? "30 min" : "1 hour"), compactTestName(kind));',
    'test duration UI')
rep('std::printf("Time : %s\\n\\n", g.testDurationSec == 60 ? "1 minute" : "1 hour");',
    'std::printf("Time : %s\\n\\n", g.testDurationSec == 60 ? "1 minute" : (g.testDurationSec == 1800 ? "30 minutes" : "1 hour"));',
    'interrupted duration UI')

rep('f << "Built-in CPU/RAM/combined/GPU validation completed.\\n";',
    'f << "Built-in CPU-memtester, RAM-rail and combined validation completed.\\n";',
    'results validation summary')

p.write_text(s)

m = Path('Makefile')
ms = m.read_text()
if 'APP_VERSION := 0.4.0-beta.39' not in ms:
    raise SystemExit('beta39 Makefile version not found')
ms = ms.replace('APP_VERSION := 0.4.0-beta.39', 'APP_VERSION := 0.4.0-beta.40', 1)
m.write_text(ms)
