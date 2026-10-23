from pathlib import Path
import re


def sub_once(text, pattern, replacement, label):
    out, n = re.subn(pattern, lambda m: replacement, text, count=1, flags=re.S)
    if n != 1:
        raise SystemExit(f'could not replace {label}: {n} matches')
    return out

# ---------------------------------------------------------------------------
# source/main.cpp - presentation only; no tuning/test logic changes
# ---------------------------------------------------------------------------
p = Path('source/main.cpp')
s = p.read_text()

safe_recovery = r'''void printSafeRecovery(const char* menu, const std::string& restoreText) {
    uiPrintf(5, "\x1b[33mPrevious setting did not boot\x1b[0m");
    uiPrintf(7, "Recovery:");
    uiPrintf(8, "1. Boot Hekate without hoc.kip");
    uiPrintf(9, "2. Open Horizon OC");
    uiPrintf(10, "%s:", menu);
    uiPrintf(11, "Restore : %s", restoreText.c_str());
    uiPrintf(12, "3. Reboot CFW");
}

const char* compactTestName'''
s = sub_once(s,
    r'void printSafeRecovery\(const std::string& restoreText\) \{.*?\n\}\n\nconst char\* compactTestName',
    safe_recovery,
    'printSafeRecovery')

prep = r'''void renderPreparation() {
    title();
    uiPrintf(5, "General:");
    uiPrintf(6, "Uncapped Clocks : OFF");

    uiPrintf(8, "RAM Settings:");
    uiPrintf(9, "HP Mode         : OFF");
    uiPrintf(10, "RAM Max         : 1600 MHz");
    uiPrintf(11, "VDD2            : 1175 mV");
    uiPrintf(12, "VDDQ            : 600 mV");

    uiPrintf(14, "CPU Settings:");
    uiPrintf(15, "CPU Max         : Lowest selectable (1963)");
    uiPrintf(16, "Low VMIN        : 620 mV");
    uiPrintf(17, "High VMIN       : 750 mV");

    uiPrintf(19, "CPU UV:");
    uiPrintf(20, "UV Table        : 1683 MHz Tbreak");
    uiPrintf(21, "Low / High UV   : 0 / 0");

    uiPrintf(23, "HOC Toolkit:");
    uiPrintf(24, "CPU Boost       : Lowest selectable / 1785");

    uiPrintf(26, "Then:");
    uiPrintf(27, "Reboot CFW and reopen Wizard");
    uiPrintf(29, "Keys:");
    uiPrintf(30, "A : Setup done / Start");
    uiPrintf(31, "B : Exit    - : Reset");
}

bool isVminSweepStage'''
s = sub_once(s,
    r'void renderPreparation\(\) \{.*?\n\}\n\nbool isVminSweepStage',
    prep,
    'renderPreparation')

render_test = r'''void renderTestStage() {
    title();

    stress::Kind kind;
    int seconds = 0;
    const bool hasTest = testPlan(g.stage, kind, seconds);
    OverrideExpectation expected{};
    const bool hasOverrides = overridePlan(g.stage, expected);

    int row = 5;

    switch (g.stage) {
        case Stage::LowUvQuick:
            uiPrintf(row++, "CPU UV:");
            uiPrintf(row++, "Low UV : %d", g.lowUvTest);
            uiPrintf(row++, "Action : Reboot CFW");
            break;
        case Stage::LowUvLong:
            if (g.recoveryNeeded) { printSafeRecovery("CPU UV", "Low UV = " + std::to_string(g.lowUvGood)); row = 14; }
            else {
                uiPrintf(row++, "CPU UV:");
                uiPrintf(row++, "Low UV : %d", g.lowUvGood);
                uiPrintf(row++, "Action : Reboot CFW");
            }
            break;
        case Stage::LowVminQuick:
            uiPrintf(row++, "CPU UV:");
            uiPrintf(row++, "Low UV   : %d", g.lowUvGood);
            uiPrintf(row++, "CPU Settings:");
            uiPrintf(row++, "Low VMIN : %d mV", g.lowVminTest);
            uiPrintf(row++, "Action   : Reboot CFW");
            break;
        case Stage::LowVminLong:
        case Stage::LowVminSweep612:
        case Stage::LowVminSweep714:
        case Stage::LowVminValidate816:
        case Stage::LowVminSweep918:
        case Stage::LowVminValidate1020:
            uiPrintf(row++, "CPU Settings:");
            uiPrintf(row++, "Low VMIN : %d mV", g.lowVminGood);
            break;
        case Stage::LowVminFinalLong:
            uiPrintf(row++, "CPU Settings:");
            uiPrintf(row++, "Low VMIN : %d mV", g.lowVminGood);
            uiPrintf(row++, "Floor CPU: %s", formatClock(g.vminFloorHz ? g.vminFloorHz : CLOCK_CPU_VMIN_510_HZ).c_str());
            break;
        case Stage::VddqQuick:
            uiPrintf(row++, "RAM Settings:");
            uiPrintf(row++, "VDD2 : %s", formatVdd2(STOCK_VDD2_UV).c_str());
            uiPrintf(row++, "VDDQ : %d mV", g.vddqTest);
            uiPrintf(row++, "Action: Reboot CFW");
            break;
        case Stage::VddqLong:
            if (g.recoveryNeeded) { printSafeRecovery("RAM Settings", "VDDQ = " + std::to_string(g.vddqGood) + " mV"); row = 14; }
            else {
                uiPrintf(row++, "RAM Settings:");
                uiPrintf(row++, "VDDQ : %d mV", g.vddqGood);
                uiPrintf(row++, "Action: Reboot CFW");
            }
            break;
        case Stage::Vdd2Quick:
            uiPrintf(row++, "RAM Settings:");
            uiPrintf(row++, "VDDQ : %d mV", g.vddqGood);
            uiPrintf(row++, "VDD2 : %s", formatVdd2(g.vdd2TestUv).c_str());
            uiPrintf(row++, "Action: Reboot CFW");
            break;
        case Stage::Vdd2Long:
            if (g.recoveryNeeded) { printSafeRecovery("RAM Settings", "VDD2 = " + formatVdd2(g.vdd2GoodUv)); row = 14; }
            else {
                uiPrintf(row++, "RAM Settings:");
                uiPrintf(row++, "VDDQ : %d mV", g.vddqGood);
                uiPrintf(row++, "VDD2 : %s", formatVdd2(g.vdd2GoodUv).c_str());
                uiPrintf(row++, "Action: Reboot CFW");
            }
            break;
        case Stage::RamBoostValidate:
            uiPrintf(row++, "RAM Settings:");
            uiPrintf(row++, "VDDQ : %d mV", g.vddqGood);
            uiPrintf(row++, "VDD2 : %s", formatVdd2(g.vdd2GoodUv).c_str());
            if (g.ramPairRetryMode == 1) uiPrintf(row++, "Retry: VDDQ +10 mV");
            if (g.ramPairRetryMode == 2) uiPrintf(row++, "Retry: VDD2 +12.5 mV");
            break;
        case Stage::Ram1331Validate:
            uiPrintf(row++, "RAM Settings:");
            uiPrintf(row++, "VDDQ : %d mV", g.vddqGood);
            uiPrintf(row++, "VDD2 : %s", formatVdd2(g.vdd2GoodUv).c_str());
            break;
        case Stage::HighUvQuick:
            uiPrintf(row++, "CPU UV:");
            uiPrintf(row++, "High UV : %d", g.highUvTest);
            uiPrintf(row++, "Action  : Reboot CFW");
            break;
        case Stage::HighUvLong:
            if (g.recoveryNeeded) { printSafeRecovery("CPU UV", "High UV = " + std::to_string(g.highUvGood)); row = 14; }
            else {
                uiPrintf(row++, "CPU UV:");
                uiPrintf(row++, "High UV : %d", g.highUvGood);
                uiPrintf(row++, "Action  : Reboot CFW");
            }
            break;
        case Stage::BoostCpuRamValidate:
            uiPrintf(row++, "CPU UV:");
            uiPrintf(row++, "Low UV  : %d", g.lowUvGood);
            uiPrintf(row++, "High UV : %d", g.highUvGood);
            uiPrintf(row++, "CPU Settings:");
            uiPrintf(row++, "Low VMIN: %d mV", g.lowVminGood);
            break;
        case Stage::NormalMatrixValidate:
        case Stage::NormalMemValidate:
        case Stage::NormalGpuValidate:
        case Stage::BoostMatrixValidate:
        case Stage::BoostMemValidate:
        case Stage::BoostCpuMemValidate:
            uiPrintf(row++, "HOC Settings:");
            uiPrintf(row++, "Use final validated values");
            break;
        default:
            break;
    }

    row++;
    if (hasOverrides) {
        printOverrides(row, expected);
        row += 5;
    }

    if (isVminSweepStage(g.stage)) {
        uiPrintf(row++, "Next:");
        uiPrintf(row++, "A : Continue");
        uiPrintf(row++, "    (CPU voltage checked automatically)");
        uiPrintf(row++, "B : Exit");
        return;
    }

    if (hasTest) {
        uiPrintf(row++, "Test:");
        uiPrintf(row++, "%s - %s", seconds == 60 ? "1 min" : "1 hour", compactTestName(kind));
        footerTest(row + 1);
    }
}

void renderRealWorld'''
s = sub_once(s,
    r'void renderTestStage\(\) \{.*?\n\}\n\nvoid renderRealWorld',
    render_test,
    'renderTestStage')

real_world = r'''void renderRealWorld() {
    title();
    uiPrintf(5, "Temporary Overrides:");
    uiPrintf(6, "Remove all Overrides");
    uiPrintf(8, "Test:");
    uiPrintf(9, "1 hour Tears of the Kingdom");
    uiPrintf(10, "Fast travel / battles / loading");
    uiPrintf(11, "Home + Sleep/Wake");
    uiPrintf(13, "Keys:");
    uiPrintf(14, "A : PASS");
    uiPrintf(15, "X : FAIL");
    uiPrintf(16, "B : Exit");
}

void renderComplete'''
s = sub_once(s,
    r'void renderRealWorld\(\) \{.*?\n\}\n\nvoid renderComplete',
    real_world,
    'renderRealWorld')

if 'Save KIP' in s or 'Save Toolkit' in s:
    raise SystemExit('manual save wording still present in source/main.cpp')
p.write_text(s)

# ---------------------------------------------------------------------------
# README current guide
# ---------------------------------------------------------------------------
p = Path('README.md')
r = p.read_text()
r = r.replace('- `Save KIP + Reboot` is shown only on stages where the persistent HOC value has actually changed.\n',
              '- `Reboot CFW` is shown only on stages where the persistent HOC value has actually changed.\n')
r = r.replace('5. Save KIP.\n6. Reboot normally.\n7. Continue validation.\n',
              '5. Reboot normally.\n6. Continue validation.\n')

old_setup = '''### Safety\n\n- **Uncapped Clocks: OFF**\n\n### RAM\n\n- **HP Mode: OFF**\n- **RAM Max Clock: 1600 MHz**\n- **VDD2: 1175 mV**\n- **VDDQ: 600 mV**\n\n### CPU\n\n- **CPU Max Clock: lowest selectable value**\n  - current Mariko HOC builds show **1963 MHz** as the lowest selectable CPU Max Clock\n- **CPU UV Table: 1683 MHz Tbreak**\n- **Low UV: 0**\n- **High UV: 0**\n- **Low VMIN: 620 mV**\n- **High VMIN: 750 mV**\n\n## HOC Toolkit\n\n- **CPU Boost Clock: lowest selectable value**\n  - stock Nintendo Boost target used by this workflow is **1785 MHz**\n\nAfter changing persistent HOC/Toolkit settings:\n\n**Save KIP -> reboot CFW -> reopen the Wizard**\n'''
new_setup = '''### General\n\n- **Uncapped Clocks: OFF**\n\n### RAM Settings\n\n- **HP Mode: OFF**\n- **RAM Max Clock: 1600 MHz**\n- **VDD2: 1175 mV**\n- **VDDQ: 600 mV**\n\n### CPU Settings\n\n- **CPU Max Clock: lowest selectable value**\n  - current Mariko HOC builds show **1963 MHz** as the lowest selectable CPU Max Clock\n- **Low VMIN: 620 mV**\n- **High VMIN: 750 mV**\n\n### CPU UV\n\n- **CPU UV Table: 1683 MHz Tbreak**\n- **Low UV: 0**\n- **High UV: 0**\n\n## HOC Toolkit\n\n- **CPU Boost Clock: lowest selectable value**\n  - stock Nintendo Boost target used by this workflow is **1785 MHz**\n\nAfter changing persistent HOC/Toolkit settings:\n\n**Reboot CFW -> reopen the Wizard**\n'''
if old_setup not in r:
    raise SystemExit('README starting setup block not found')
r = r.replace(old_setup, new_setup, 1)
r = r.replace('For beta.8 this is the final required manual update; later builds can be installed by the in-app updater.',
              'Once an updater-capable build is installed, later builds can be installed by the in-app updater.')

entry = '''# New in v0.4.0-beta.12\n\n- Remove all manual **Save KIP / Save Toolkit** instructions from the active Wizard guide.\n- Persistent setting changes now simply tell the user when a **CFW reboot** is required.\n- Group every HOC set point under its actual menu area: **General**, **RAM Settings**, **CPU Settings**, **CPU UV**, **HOC Toolkit**, and **Temporary Overrides**.\n- Keep the beta.11 tuning/test logic unchanged.\n- Expand the GitHub Releases API fallback from 5 to 100 entries; the lightweight `UPDATE.txt` manifest remains the primary update source.\n\n---\n\n'''
if '# New in v0.4.0-beta.12' not in r:
    r = r.replace('# New in v0.4.0-beta.11\n', entry + '# New in v0.4.0-beta.11\n', 1)

# Historical release notes can describe old builds, but the active guide sections below
# must no longer instruct the user to save KIP/toolkit manually.
p.write_text(r)

# ---------------------------------------------------------------------------
# Version/update metadata
# ---------------------------------------------------------------------------
p = Path('Makefile')
m = p.read_text().replace('APP_VERSION := 0.4.0-beta.11', 'APP_VERSION := 0.4.0-beta.12')
p.write_text(m)

p = Path('source/updater.cpp')
u = p.read_text().replace('releases?per_page=5', 'releases?per_page=100')
p.write_text(u)

Path('UPDATE.txt').write_text('''version=0.4.0-beta.12\nnro_url=https://github.com/retrotendo/HOC-Undervolting-Wizard/releases/download/v0.4.0-beta.12/HOC-Undervolting-Wizard.nro\nsha_url=https://github.com/retrotendo/HOC-Undervolting-Wizard/releases/download/v0.4.0-beta.12/HOC-Undervolting-Wizard.nro.sha256\n''')

p = Path('CHANGELOG.md')
c = p.read_text()
entry = '''## v0.4.0-beta.12\n\n- Remove manual Save KIP / Save Toolkit prompts from the active Wizard flow and documentation.\n- Keep required CFW reboot instructions where persistent settings change.\n- Label set points by their HOC menu area: General, RAM Settings, CPU Settings, CPU UV, HOC Toolkit and Temporary Overrides.\n- Preserve beta.11 tuning, stress-test, VMIN, skip and recovery logic.\n- Increase the GitHub Releases API fallback window from 5 to 100 releases.\n\n'''
if '## v0.4.0-beta.12' not in c:
    c = c.replace('# Changelog\n\n', '# Changelog\n\n' + entry, 1)
p.write_text(c)
