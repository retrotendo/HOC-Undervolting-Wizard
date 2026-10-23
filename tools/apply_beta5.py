from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

s = s.replace('#include <cstdio>\n', '#include <algorithm>\n#include <cstdio>\n', 1)

s = s.replace(
'''bool g_overridePrompt = false;\nOverrideCheckState g_overrideCheck;\n''',
'''enum class PendingOverrideAction { StartTest, VminProbe };\nbool g_overridePrompt = false;\nPendingOverrideAction g_overrideAction = PendingOverrideAction::StartTest;\nOverrideCheckState g_overrideCheck;\n''', 1)

s = s.replace(
'''        case Stage::LowUvQuick:\n        case Stage::LowVminQuick:\n        case Stage::LowVminLong:\n        case Stage::LowVminSweep612:\n        case Stage::LowVminSweep714:\n        case Stage::LowVminValidate816:\n        case Stage::LowVminSweep918:\n        case Stage::LowVminValidate1020:\n        case Stage::HighUvQuick:\n            kind = stress::Kind::Cpu; seconds = 60; return true;\n''',
'''        case Stage::LowUvQuick:\n        case Stage::LowVminQuick:\n        case Stage::HighUvQuick:\n            kind = stress::Kind::Cpu; seconds = 60; return true;\n''', 1)

needle = '''bool checkAllOverrides(Stage s) {\n    g_overrideCheck = OverrideCheckState{};\n    if (!overridePlan(s, g_overrideCheck.expected)) return true;\n\n    g_overrideCheck.rc = hocmonGetClocks(&g_overrideCheck.current);\n    if (R_FAILED(g_overrideCheck.rc)) {\n        g_overrideCheck.readOk = false;\n        return false;\n    }\n\n    g_overrideCheck.readOk = true;\n    g_overrideCheck.cpuOk = clockMatches(g_overrideCheck.current.overrideHz[0], g_overrideCheck.expected.cpuHz);\n    g_overrideCheck.gpuOk = clockMatches(g_overrideCheck.current.overrideHz[1], g_overrideCheck.expected.gpuHz);\n    g_overrideCheck.ramOk = clockMatches(g_overrideCheck.current.overrideHz[2], g_overrideCheck.expected.ramHz);\n    return g_overrideCheck.cpuOk && g_overrideCheck.gpuOk && g_overrideCheck.ramOk;\n}\n'''
insert = needle + '''\n// VMIN floor probing is measurement-only. Read several HOC context samples so a\n// stale single poll cannot decide the floor crossover. The median CPU rail\n// voltage from matching override samples is used.\nbool sampleVminVoltage(Stage s) {\n    if (!checkAllOverrides(s)) return false;\n\n    u32 samples[7] = {};\n    int count = 0;\n    HocMonClocks latest = g_overrideCheck.current;\n\n    for (int i = 0; i < 7; ++i) {\n        HocMonClocks cur{};\n        Result rc = hocmonGetClocks(&cur);\n        if (R_SUCCEEDED(rc) &&\n            clockMatches(cur.overrideHz[0], g_overrideCheck.expected.cpuHz) &&\n            clockMatches(cur.overrideHz[1], g_overrideCheck.expected.gpuHz) &&\n            clockMatches(cur.overrideHz[2], g_overrideCheck.expected.ramHz) &&\n            cur.cpuVoltageUv != 0) {\n            samples[count++] = cur.cpuVoltageUv;\n            latest = cur;\n        }\n        svcSleepThread(120'000'000);\n    }\n\n    if (count < 3) {\n        // Preserve the latest context for the Expected/Current error screen.\n        g_overrideCheck.current = latest;\n        g_overrideCheck.readOk = true;\n        g_overrideCheck.cpuOk = clockMatches(latest.overrideHz[0], g_overrideCheck.expected.cpuHz);\n        g_overrideCheck.gpuOk = clockMatches(latest.overrideHz[1], g_overrideCheck.expected.gpuHz);\n        g_overrideCheck.ramOk = clockMatches(latest.overrideHz[2], g_overrideCheck.expected.ramHz);\n        return false;\n    }\n\n    std::sort(samples, samples + count);\n    latest.cpuVoltageUv = samples[count / 2];\n    g_overrideCheck.current = latest;\n    g_overrideCheck.readOk = true;\n    g_overrideCheck.cpuOk = g_overrideCheck.gpuOk = g_overrideCheck.ramOk = true;\n    return true;\n}\n'''
if needle not in s:
    raise SystemExit('checkAllOverrides block not found')
s = s.replace(needle, insert, 1)

# Forward declaration because renderTestStage needs to distinguish measurement-only stages.
marker = '''void renderTestStage() {\n'''
s = s.replace(marker, '''bool isVminSweepStage(Stage st);\n\n''' + marker, 1)

# Replace the generic test footer with a measurement-only footer for the dynamic VMIN sweep.
needle = '''    std::printf("\\nBuilt-in test: \\x1b[1m%s\\x1b[0m\\n", stress::kindName(kind));\n    std::printf("Duration: \\x1b[1m%s\\x1b[0m\\n", seconds == 60 ? "1 minute" : "1 hour");\n    std::printf("Errors/mismatches are detected automatically.\\n");\n    std::printf("CPU + GPU + RAM Overrides are verified before EVERY test.\\n");\n    if (kind == stress::Kind::Ram || kind == stress::Kind::Combined)\n        std::printf("Do not install/update/copy files while testing unstable RAM.\\n");\n    footerTest();\n'''
replacement = '''    if (isVminSweepStage(g.stage)) {\n        std::printf("\\n\\x1b[36mVMIN FLOOR PROBE - NO STRESS TEST\\x1b[0m\\n");\n        std::printf("CPU + GPU + RAM Overrides are verified first.\\n");\n        std::printf("The Wizard then samples the live CPU rail several times\\n");\n        std::printf("and uses the median voltage to detect the floor crossover.\\n\\n");\n        std::printf("\\x1b[32m[A] VERIFY OVERRIDES + MEASURE\\x1b[0m   [B] Exit\\n");\n        return;\n    }\n\n    std::printf("\\nBuilt-in test: \\x1b[1m%s\\x1b[0m\\n", stress::kindName(kind));\n    std::printf("Duration: \\x1b[1m%s\\x1b[0m\\n", seconds == 60 ? "1 minute" : "1 hour");\n    std::printf("Errors/mismatches are detected automatically.\\n");\n    std::printf("CPU + GPU + RAM Overrides are verified before EVERY test.\\n");\n    if (kind == stress::Kind::Ram || kind == stress::Kind::Combined)\n        std::printf("Do not install/update/copy files while testing unstable RAM.\\n");\n    footerTest();\n'''
if needle not in s:
    raise SystemExit('render footer block not found')
s = s.replace(needle, replacement, 1)

# Override-block wording must also cover a VMIN measurement request.
s = s.replace(
'''    std::printf("\\nThe stability test has NOT started and no result was recorded.\\n\\n");\n    std::printf("[A] Check again + start when correct   [B] Back\\n");\n''',
'''    if (g_overrideAction == PendingOverrideAction::VminProbe) {\n        std::printf("\\nThe VMIN measurement has NOT started.\\n\\n");\n        std::printf("[A] Check again + measure when correct   [B] Back\\n");\n    } else {\n        std::printf("\\nThe stability test has NOT started and no result was recorded.\\n\\n");\n        std::printf("[A] Check again + start when correct   [B] Back\\n");\n    }\n''', 1)

# Dynamic sweep decisions must always use the measured floor state; a manual-pass bypass is no longer needed there.
s = s.replace('if (!g_manualPass && !g_lastVminAtFloor)', 'if (!g_lastVminAtFloor)')

# Insert the measurement runner before the regular stress-test runner.
needle = '''void runCurrentTest() {\n'''
runner = '''void runVminProbe() {\n    if (!isVminSweepStage(g.stage)) return;\n\n    g_overrideAction = PendingOverrideAction::VminProbe;\n    if (!sampleVminVoltage(g.stage)) {\n        g_overridePrompt = true;\n        return;\n    }\n    g_overridePrompt = false;\n\n    const Stage probedStage = g.stage;\n    recordVminObservation(probedStage);\n    handlePass();\n}\n\n'''
s = s.replace(needle, runner + needle, 1)

# Regular test preflight should explicitly set its pending action.
s = s.replace(
'''    // Hard pre-flight: every built-in test requires all three expected\n    // Horizon OC Temporary Overrides. A missing/wrong override blocks the test.\n    if (!checkAllOverrides(g.stage)) {\n''',
'''    // Hard pre-flight: every built-in test requires all three expected\n    // Horizon OC Temporary Overrides. A missing/wrong override blocks the test.\n    g_overrideAction = PendingOverrideAction::StartTest;\n    if (!checkAllOverrides(g.stage)) {\n''', 1)

# Retry the correct pending action from the override screen.
s = s.replace(
'''            if (k & HidNpadButton_A) {\n                g_overridePrompt = false;\n                runCurrentTest();\n                redraw = true;\n''',
'''            if (k & HidNpadButton_A) {\n                g_overridePrompt = false;\n                if (g_overrideAction == PendingOverrideAction::VminProbe) runVminProbe();\n                else runCurrentTest();\n                redraw = true;\n''', 1)

# Plus remains a true known-pass shortcut on test stages. On VMIN floor-probe stages it performs the required measurement instead.
s = s.replace(
'''        } else if (k & HidNpadButton_Plus) {\n            stress::Kind skipKind;\n            int skipSeconds = 0;\n            if (testPlan(g.stage, skipKind, skipSeconds)) {\n                g_manualPass = true;\n                g_lastVminAtFloor = true;\n                handlePass();\n                g_manualPass = false;\n                redraw = true;\n            }\n        } else if (k & HidNpadButton_X) {\n            if (g.stage != Stage::Preparation && g.stage != Stage::Complete) {\n                handleFail(false);\n                redraw = true;\n            }\n        } else if (k & HidNpadButton_A) {\n            stress::Kind kind;\n            int seconds = 0;\n            if (testPlan(g.stage, kind, seconds)) {\n                runCurrentTest();\n            } else {\n                handlePass();\n            }\n            redraw = true;\n''',
'''        } else if (k & HidNpadButton_Plus) {\n            if (isVminSweepStage(g.stage)) {\n                runVminProbe();\n                redraw = true;\n            } else {\n                stress::Kind skipKind;\n                int skipSeconds = 0;\n                if (testPlan(g.stage, skipKind, skipSeconds)) {\n                    g_manualPass = true;\n                    handlePass();\n                    g_manualPass = false;\n                    redraw = true;\n                }\n            }\n        } else if (k & HidNpadButton_X) {\n            if (!isVminSweepStage(g.stage) && g.stage != Stage::Preparation && g.stage != Stage::Complete) {\n                handleFail(false);\n                redraw = true;\n            }\n        } else if (k & HidNpadButton_A) {\n            if (isVminSweepStage(g.stage)) {\n                runVminProbe();\n            } else {\n                stress::Kind kind;\n                int seconds = 0;\n                if (testPlan(g.stage, kind, seconds)) runCurrentTest();\n                else handlePass();\n            }\n            redraw = true;\n''', 1)

p.write_text(s)
