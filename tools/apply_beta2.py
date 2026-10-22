from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
main_path = ROOT / "source" / "main.cpp"
text = main_path.read_text()


def replace_once(old: str, new: str):
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one match, got {count}: {old[:100]!r}")
    text = text.replace(old, new, 1)


replace_once(
    '#include "stress_tests.hpp"\n',
    '#include "stress_tests.hpp"\n#include "hoc_monitor.h"\n'
)

replace_once(
    'constexpr int STOCK_VDD2_UV = 1175000;\n',
    '''constexpr int STOCK_VDD2_UV = 1175000;\n\n// Horizon OC temporary-override targets used by the Battery guide.\nconstexpr u32 CLOCK_CPU_NORMAL_HZ = 1020000000U;\nconstexpr u32 CLOCK_CPU_LOW_HZ    = 510000000U;\nconstexpr u32 CLOCK_CPU_BOOST_HZ  = 1785000000U;\nconstexpr u32 CLOCK_GPU_NORMAL_HZ = 384000000U;\nconstexpr u32 CLOCK_GPU_BOOST_HZ  = 76800000U;\nconstexpr u32 CLOCK_RAM_NORMAL_HZ = 1331200000U;\nconstexpr u32 CLOCK_RAM_BOOST_HZ  = 1600000000U;\n'''
)

replace_once(
    'std::string g_resultAction;\n',
    '''std::string g_resultAction;\n\nstruct OverrideExpectation {\n    u32 cpuHz = 0;\n    u32 gpuHz = 0;\n    u32 ramHz = 0;\n};\n\nstruct OverrideCheckState {\n    bool readOk = false;\n    Result rc = 0;\n    OverrideExpectation expected;\n    HocMonClocks current{};\n    bool cpuOk = false;\n    bool gpuOk = false;\n    bool ramOk = false;\n};\n\nbool g_overridePrompt = false;\nOverrideCheckState g_overrideCheck;\n'''
)

needle = '''bool testPlan(Stage s, stress::Kind& kind, int& seconds) {\n    switch (s) {\n'''
if needle not in text:
    raise RuntimeError("testPlan marker missing")

# Insert helpers immediately before ensureDir(), after testPlan().
marker = '''void ensureDir() {\n'''
helpers = r'''bool overridePlan(Stage s, OverrideExpectation& e) {
    switch (s) {
        case Stage::LowUvQuick:
        case Stage::LowUvLong:
        case Stage::LowVminQuick:
        case Stage::Ram1331Validate:
        case Stage::NormalMatrixValidate:
        case Stage::NormalMemValidate:
        case Stage::NormalGpuValidate:
            e = {CLOCK_CPU_NORMAL_HZ, CLOCK_GPU_NORMAL_HZ, CLOCK_RAM_NORMAL_HZ};
            return true;

        case Stage::LowVminLong:
            e = {CLOCK_CPU_LOW_HZ, CLOCK_GPU_NORMAL_HZ, CLOCK_RAM_NORMAL_HZ};
            return true;

        case Stage::VddqQuick:
        case Stage::VddqLong:
        case Stage::Vdd2Quick:
        case Stage::Vdd2Long:
        case Stage::HighUvQuick:
        case Stage::HighUvLong:
        case Stage::BoostCpuRamValidate:
        case Stage::BoostMatrixValidate:
        case Stage::BoostMemValidate:
        case Stage::BoostCpuMemValidate:
            e = {CLOCK_CPU_BOOST_HZ, CLOCK_GPU_BOOST_HZ, CLOCK_RAM_BOOST_HZ};
            return true;

        default:
            return false;
    }
}

bool clockMatches(u32 current, u32 expected) {
    if (current == 0 || expected == 0) return false;
    const u32 tolerance = 2000000U; // tolerate display/list rounding such as 1331 vs 1331.2 MHz
    return current > expected ? (current - expected <= tolerance) : (expected - current <= tolerance);
}

std::string formatClock(u32 hz) {
    if (hz == 0) return "NOT SET";
    char buf[32];
    if (hz % 1000000U == 0)
        std::snprintf(buf, sizeof(buf), "%u MHz", hz / 1000000U);
    else
        std::snprintf(buf, sizeof(buf), "%.1f MHz", (double)hz / 1000000.0);
    return std::string(buf);
}

bool checkAllOverrides(Stage s) {
    g_overrideCheck = OverrideCheckState{};
    if (!overridePlan(s, g_overrideCheck.expected)) return true;

    g_overrideCheck.rc = hocmonGetClocks(&g_overrideCheck.current);
    if (R_FAILED(g_overrideCheck.rc)) {
        g_overrideCheck.readOk = false;
        return false;
    }

    g_overrideCheck.readOk = true;
    g_overrideCheck.cpuOk = clockMatches(g_overrideCheck.current.overrideHz[0], g_overrideCheck.expected.cpuHz);
    g_overrideCheck.gpuOk = clockMatches(g_overrideCheck.current.overrideHz[1], g_overrideCheck.expected.gpuHz);
    g_overrideCheck.ramOk = clockMatches(g_overrideCheck.current.overrideHz[2], g_overrideCheck.expected.ramHz);
    return g_overrideCheck.cpuOk && g_overrideCheck.gpuOk && g_overrideCheck.ramOk;
}

'''
replace_once(marker, helpers + marker)

# Replace preparation screen with the Battery-guide baseline.
start = text.index('void renderPreparation() {')
end = text.index('void renderTestStage() {', start)
new_prep = r'''void renderPreparation() {
    title();
    std::printf("Before tuning, prepare the Battery profile exactly once.\n\n");
    std::printf("HOC Toolkit / stock clock limits:\n");
    std::printf("  CPU Max Clock   : 1785 MHz\n");
    std::printf("  CPU Boost Clock : 1785 MHz\n");
    std::printf("  GPU Max Clock   : 384 MHz\n");
    std::printf("  RAM Max Clock   : 1600 MHz\n\n");
    std::printf("Horizon OC:\n");
    std::printf("  Safety -> Uncapped Clocks : OFF\n");
    std::printf("  RAM -> HP Mode             : OFF\n");
    std::printf("  RAM Max Clock              : 1600 MHz\n");
    std::printf("  Overwrite Boost Mode       : OFF\n");
    std::printf("  Auto CPU RAM OC            : OFF\n");
    std::printf("  CPU UV Table               : Normal\n");
    std::printf("  Low UV / High UV           : 0 / 0\n");
    std::printf("  Low VMIN / High VMIN       : %d / %d mV\n", STOCK_LOW_VMIN_MV, STOCK_HIGH_VMIN_MV);
    std::printf("  RAM VDD2 / VDDQ            : %s / %d mV\n", formatVdd2(STOCK_VDD2_UV).c_str(), STOCK_VDDQ_MV);
    std::printf("  Per-game CPU/GPU/RAM       : STOCK / default\n\n");
    std::printf("Save/apply the Toolkit values, Save KIP, then REBOOT CFW.\n");
    std::printf("After reboot reopen this Wizard and press [A].\n\n");
    std::printf("[A] Setup done - start tuning   [B] Exit   [-] Reset\n");
}

'''
text = text[:start] + new_prep + text[end:]

replace_once(
    '    std::printf("Errors/mismatches are detected automatically.\\n");\n',
    '    std::printf("Errors/mismatches are detected automatically.\\n");\n    std::printf("CPU + GPU + RAM Overrides are verified before EVERY test.\\n");\n'
)

# Insert the blocking override-check screen before renderResultScreen().
marker = 'void renderResultScreen() {\n'
override_screen = r'''void renderOverridePrompt() {
    consoleClear();
    std::printf("\x1b[1;1H\x1b[31mHOC Undervolting Wizard - TEST BLOCKED\x1b[0m\n");
    std::printf("------------------------------------------------------------\n\n");

    if (!g_overrideCheck.readOk) {
        std::printf("Could not read Horizon OC service 'hoc:clk'.\n");
        std::printf("Result: 0x%08X\n\n", g_overrideCheck.rc);
        std::printf("Boot normal CFW with Horizon OC / hoc.kip loaded, then retry.\n");
    } else {
        const char* ok = "\x1b[32mOK\x1b[0m";
        const char* bad = "\x1b[31mWRONG\x1b[0m";
        std::printf("All three Temporary Overrides must match the test target.\n\n");
        std::printf("       Expected       Current        Status\n");
        std::printf("CPU    %-13s  %-13s  %s\n",
                    formatClock(g_overrideCheck.expected.cpuHz).c_str(),
                    formatClock(g_overrideCheck.current.overrideHz[0]).c_str(),
                    g_overrideCheck.cpuOk ? ok : bad);
        std::printf("GPU    %-13s  %-13s  %s\n",
                    formatClock(g_overrideCheck.expected.gpuHz).c_str(),
                    formatClock(g_overrideCheck.current.overrideHz[1]).c_str(),
                    g_overrideCheck.gpuOk ? ok : bad);
        std::printf("RAM    %-13s  %-13s  %s\n\n",
                    formatClock(g_overrideCheck.expected.ramHz).c_str(),
                    formatClock(g_overrideCheck.current.overrideHz[2]).c_str(),
                    g_overrideCheck.ramOk ? ok : bad);
        std::printf("Open Horizon OC -> Temporary Overrides and correct ALL red values.\n");
    }

    std::printf("\nThe stability test has NOT started and no result was recorded.\n\n");
    std::printf("[A] Check again + start when correct   [B] Back\n");
    consoleUpdate(nullptr);
}

'''
replace_once(marker, override_screen + marker)

replace_once(
    '    if (g_interruptedPrompt) { renderInterruptedPrompt(); return; }\n    if (g_resultScreen) { renderResultScreen(); return; }\n',
    '    if (g_interruptedPrompt) { renderInterruptedPrompt(); return; }\n    if (g_overridePrompt) { renderOverridePrompt(); return; }\n    if (g_resultScreen) { renderResultScreen(); return; }\n'
)

replace_once(
    '''void runCurrentTest() {\n    stress::Kind kind;\n    int seconds = 0;\n    if (!testPlan(g.stage, kind, seconds)) return;\n\n    const Stage testedStage = g.stage;\n''',
    '''void runCurrentTest() {\n    stress::Kind kind;\n    int seconds = 0;\n    if (!testPlan(g.stage, kind, seconds)) return;\n\n    // Hard pre-flight: every built-in test requires all three expected\n    // Horizon OC Temporary Overrides. A missing/wrong override blocks the test.\n    if (!checkAllOverrides(g.stage)) {\n        g_overridePrompt = true;\n        return;\n    }\n    g_overridePrompt = false;\n\n    const Stage testedStage = g.stage;\n'''
)

# Handle the blocking screen before normal input handling.
replace_once(
    '''        if (g_resultScreen) {\n            if (k & HidNpadButton_A || k & HidNpadButton_B) {\n                g_resultScreen = false;\n                redraw = true;\n            }\n            svcSleepThread(20'000'000);\n            continue;\n        }\n\n        if (g_resetConfirm) {\n''',
    '''        if (g_overridePrompt) {\n            if (k & HidNpadButton_A) {\n                g_overridePrompt = false;\n                runCurrentTest();\n                redraw = true;\n            } else if (k & HidNpadButton_B) {\n                g_overridePrompt = false;\n                redraw = true;\n            }\n            svcSleepThread(20'000'000);\n            continue;\n        }\n\n        if (g_resultScreen) {\n            if (k & HidNpadButton_A || k & HidNpadButton_B) {\n                g_resultScreen = false;\n                redraw = true;\n            }\n            svcSleepThread(20'000'000);\n            continue;\n        }\n\n        if (g_resetConfirm) {\n'''
)

main_path.write_text(text)

# Version metadata.
makefile = ROOT / "Makefile"
m = makefile.read_text()
if 'APP_VERSION := 0.4.0-beta.1' in m:
    m = m.replace('APP_VERSION := 0.4.0-beta.1', 'APP_VERSION := 0.4.0-beta.2')
elif 'APP_VERSION := 0.4.0' in m:
    m = m.replace('APP_VERSION := 0.4.0', 'APP_VERSION := 0.4.0-beta.2')
else:
    raise RuntimeError('Unexpected APP_VERSION')
makefile.write_text(m)

# README: document setup baseline and hard override preflight.
readme = ROOT / "README.md"
r = readme.read_text()
r = r.replace(
    'Quick boundary tests run for **1 minute** and long validation tests run for **1 hour**, with an on-screen timer, progress information and automatic PASS/FAIL handling.\n',
    'Quick boundary tests run for **1 minute** and long validation tests run for **1 hour**, with an on-screen timer, progress information and automatic PASS/FAIL handling.\n\nBefore **every built-in test**, the Wizard reads Horizon OC\'s live `hoc:clk` context and verifies **all three Temporary Overrides (CPU + GPU + RAM)**. A missing or incorrect override blocks the test and shows Expected vs Current values; no tuning result is recorded until all three match.\n'
)
insert_marker = '# Normal workflow\n'
setup = '''# Battery starting setup\n\nBefore Step 1, prepare the Battery profile once:\n\n- HOC Toolkit / stock clock limits: **CPU Max 1785 MHz**, **CPU Boost 1785 MHz**, **GPU Max 384 MHz**, **RAM Max 1600 MHz**.\n- Horizon OC: **Uncapped Clocks OFF**, **HP Mode OFF**, **RAM Max Clock 1600 MHz**, **Overwrite Boost Mode OFF**, **Auto CPU RAM OC OFF**.\n- CPU baseline: **UV Table Normal**, **Low UV 0**, **High UV 0**, **Low VMIN 620 mV**, **High VMIN 750 mV**.\n- RAM baseline: **VDD2 1175 mV**, **VDDQ 600 mV**.\n- Per-game CPU/GPU/RAM clocks: **stock/default**.\n\nSave/apply the Toolkit values, **Save KIP**, then **reboot CFW** before starting the tuning sequence. These are starting limits/baselines, not the final undervolted values the Wizard will discover.\n\n---\n\n'''
if setup not in r:
    if insert_marker not in r:
        raise RuntimeError('README normal workflow marker missing')
    r = r.replace(insert_marker, setup + insert_marker, 1)
readme.write_text(r)

# Third-party notice: record the read-only Horizon-OC IPC/context adaptation.
third = ROOT / "THIRD_PARTY_LICENSES.md"
t = third.read_text()
notice = '''\n### Horizon OC live-context IPC used by override pre-flight\n\n`source/hoc_monitor.c` uses the public `hoc:clk` `GetCurrentContext` IPC command and the stable context layout documented by Horizon-OC to read CPU/GPU/RAM Temporary Overrides before a test. The implementation is a reduced read-only adaptation of Horizon-OC's GPLv2 client/context definitions. No Horizon OC configuration is written by this code.\n'''
if notice not in t:
    t += notice
third.write_text(t)

# Changelog beta.2 entry.
changelog = ROOT / "CHANGELOG.md"
c = changelog.read_text()
entry = '''## v0.4.0-beta.2\n\n- Added the full Battery-guide starting setup to the Wizard preparation screen.\n- Added CPU Max/Boost 1785 MHz, GPU Max 384 MHz and RAM Max 1600 MHz stock limits.\n- Added Uncapped Clocks OFF, HP Mode OFF, Overwrite Boost Mode OFF and Auto CPU RAM OC OFF preparation guidance.\n- Added a hard Horizon OC pre-flight before every built-in test.\n- CPU, GPU and RAM Temporary Overrides are all read from `hoc:clk` and compared with the exact test target.\n- A missing/wrong override blocks the test and shows Expected vs Current values; no PASS/FAIL is recorded.\n\n'''
if not c.startswith('# Changelog'):
    raise RuntimeError('Unexpected changelog format')
if '## v0.4.0-beta.2' not in c:
    split = c.find('\n\n', len('# Changelog'))
    c = c[:split+2] + entry + c[split+2:]
changelog.write_text(c)

print('beta.2 patch applied')
