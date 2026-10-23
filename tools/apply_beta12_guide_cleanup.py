from pathlib import Path


def must_replace(text, old, new, label):
    if old not in text:
        raise SystemExit(f'missing expected block: {label}')
    return text.replace(old, new, 1)

# ---------------------------------------------------------------------------
# source/main.cpp - presentation only
# ---------------------------------------------------------------------------
p = Path('source/main.cpp')
s = p.read_text()

s = must_replace(s, r'''void printSafeRecovery(const std::string& restoreText) {
    uiPrintf(5, "\\x1b[33mPrevious setting did not boot\\x1b[0m");
    uiPrintf(7, "Recovery:");
    uiPrintf(8, "1. Boot Hekate without hoc.kip");
    uiPrintf(9, "2. Open Horizon OC");
    uiPrintf(10, "3. Restore : %s", restoreText.c_str());
    uiPrintf(11, "4. Save KIP + Reboot");
}
''', r'''void printSafeRecovery(const char* menu, const std::string& restoreText) {
    uiPrintf(5, "\\x1b[33mPrevious setting did not boot\\x1b[0m");
    uiPrintf(7, "Recovery:");
    uiPrintf(8, "1. Boot Hekate without hoc.kip");
    uiPrintf(9, "2. Open Horizon OC");
    uiPrintf(10, "%s:", menu);
    uiPrintf(11, "Restore : %s", restoreText.c_str());
    uiPrintf(12, "3. Reboot CFW");
}
''', 'printSafeRecovery')

old_prep = r'''void renderPreparation() {
    title();
    uiPrintf(5, "Set in Horizon OC:");
    uiPrintf(6, "Uncapped Clocks : OFF");
    uiPrintf(7, "HP Mode         : OFF");
    uiPrintf(8, "RAM Max         : 1600 MHz");
    uiPrintf(9, "VDD2            : 1175 mV");
    uiPrintf(10, "VDDQ            : 600 mV");
    uiPrintf(11, "CPU Max         : Lowest selectable (1963)");
    uiPrintf(12, "CPU UV Table    : 1683 MHz Tbreak");
    uiPrintf(13, "Low / High UV   : 0 / 0");
    uiPrintf(14, "Low VMIN        : 620 mV");
    uiPrintf(15, "High VMIN       : 750 mV");
    uiPrintf(17, "HOC Toolkit:");
    uiPrintf(18, "CPU Boost       : Lowest selectable / 1785");
    uiPrintf(20, "Then:");
    uiPrintf(21, "Save Toolkit + Save KIP + Reboot CFW");
    uiPrintf(22, "Reopen Wizard after reboot");
    uiPrintf(24, "Keys:");
    uiPrintf(25, "A : Setup done / Start");
    uiPrintf(26, "B : Exit    - : Reset");
}
'''
new_prep = r'''void renderPreparation() {
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
'''
s = must_replace(s, old_prep, new_prep, 'renderPreparation')

# Remove the generic heading; each actual set point now carries its real menu heading.
s = must_replace(s, '    uiPrintf(row++, "Set in HOC:");\n\n', '', 'generic Set in HOC heading')

repls = [
(r'''        case Stage::LowUvQuick:
            uiPrintf(row++, "Low UV : %d", g.lowUvTest);
            uiPrintf(row++, "Action : Save KIP + Reboot");
            break;
''', r'''        case Stage::LowUvQuick:
            uiPrintf(row++, "CPU UV:");
            uiPrintf(row++, "Low UV : %d", g.lowUvTest);
            uiPrintf(row++, "Action : Reboot CFW");
            break;
''', 'LowUvQuick'),
(r'''        case Stage::LowUvLong:
            if (g.recoveryNeeded) { printSafeRecovery("CPU Low UV = " + std::to_string(g.lowUvGood)); row = 13; }
            else {
                uiPrintf(row++, "Low UV : %d", g.lowUvGood);
                uiPrintf(row++, "Action : Save KIP + Reboot");
            }
            break;
''', r'''        case Stage::LowUvLong:
            if (g.recoveryNeeded) { printSafeRecovery("CPU UV", "Low UV = " + std::to_string(g.lowUvGood)); row = 14; }
            else {
                uiPrintf(row++, "CPU UV:");
                uiPrintf(row++, "Low UV : %d", g.lowUvGood);
                uiPrintf(row++, "Action : Reboot CFW");
            }
            break;
''', 'LowUvLong'),
(r'''        case Stage::LowVminQuick:
            uiPrintf(row++, "Low UV   : %d", g.lowUvGood);
            uiPrintf(row++, "Low VMIN : %d mV", g.lowVminTest);
            uiPrintf(row++, "Action   : Save KIP + Reboot");
            break;
''', r'''        case Stage::LowVminQuick:
            uiPrintf(row++, "CPU UV:");
            uiPrintf(row++, "Low UV   : %d", g.lowUvGood);
            uiPrintf(row++, "CPU Settings:");
            uiPrintf(row++, "Low VMIN : %d mV", g.lowVminTest);
            uiPrintf(row++, "Action   : Reboot CFW");
            break;
''', 'LowVminQuick'),
(r'''        case Stage::LowVminValidate1020:
            uiPrintf(row++, "Low VMIN : %d mV", g.lowVminGood);
            uiPrintf(row++, "Action   : Set Overrides below");
            break;
''', r'''        case Stage::LowVminValidate1020:
            uiPrintf(row++, "CPU Settings:");
            uiPrintf(row++, "Low VMIN : %d mV", g.lowVminGood);
            break;
''', 'LowVmin sweep'),
(r'''        case Stage::LowVminFinalLong:
            uiPrintf(row++, "Low VMIN : %d mV", g.lowVminGood);
            uiPrintf(row++, "Floor CPU: %s", formatClock(g.vminFloorHz ? g.vminFloorHz : CLOCK_CPU_VMIN_510_HZ).c_str());
            break;
''', r'''        case Stage::LowVminFinalLong:
            uiPrintf(row++, "CPU Settings:");
            uiPrintf(row++, "Low VMIN : %d mV", g.lowVminGood);
            uiPrintf(row++, "Floor CPU: %s", formatClock(g.vminFloorHz ? g.vminFloorHz : CLOCK_CPU_VMIN_510_HZ).c_str());
            break;
''', 'LowVminFinalLong'),
(r'''        case Stage::VddqQuick:
            uiPrintf(row++, "VDD2 : %s", formatVdd2(STOCK_VDD2_UV).c_str());
            uiPrintf(row++, "VDDQ : %d mV", g.vddqTest);
            uiPrintf(row++, "Action: Save KIP + Reboot");
            break;
''', r'''        case Stage::VddqQuick:
            uiPrintf(row++, "RAM Settings:");
            uiPrintf(row++, "VDD2 : %s", formatVdd2(STOCK_VDD2_UV).c_str());
            uiPrintf(row++, "VDDQ : %d mV", g.vddqTest);
            uiPrintf(row++, "Action: Reboot CFW");
            break;
''', 'VddqQuick'),
(r'''        case Stage::VddqLong:
            if (g.recoveryNeeded) { printSafeRecovery("RAM VDDQ = " + std::to_string(g.vddqGood) + " mV"); row = 13; }
            else {
                uiPrintf(row++, "VDDQ : %d mV", g.vddqGood);
                uiPrintf(row++, "Action: Save KIP + Reboot");
            }
            break;
''', r'''        case Stage::VddqLong:
            if (g.recoveryNeeded) { printSafeRecovery("RAM Settings", "VDDQ = " + std::to_string(g.vddqGood) + " mV"); row = 14; }
            else {
                uiPrintf(row++, "RAM Settings:");
                uiPrintf(row++, "VDDQ : %d mV", g.vddqGood);
                uiPrintf(row++, "Action: Reboot CFW");
            }
            break;
''', 'VddqLong'),
(r'''        case Stage::Vdd2Quick:
            uiPrintf(row++, "VDDQ : %d mV", g.vddqGood);
            uiPrintf(row++, "VDD2 : %s", formatVdd2(g.vdd2TestUv).c_str());
            uiPrintf(row++, "Action: Save KIP + Reboot");
            break;
''', r'''        case Stage::Vdd2Quick:
            uiPrintf(row++, "RAM Settings:");
            uiPrintf(row++, "VDDQ : %d mV", g.vddqGood);
            uiPrintf(row++, "VDD2 : %s", formatVdd2(g.vdd2TestUv).c_str());
            uiPrintf(row++, "Action: Reboot CFW");
            break;
''', 'Vdd2Quick'),
(r'''        case Stage::Vdd2Long:
            if (g.recoveryNeeded) { printSafeRecovery("RAM VDD2 = " + formatVdd2(g.vdd2GoodUv)); row = 13; }
            else {
                uiPrintf(row++, "VDDQ : %d mV", g.vddqGood);
                uiPrintf(row++, "VDD2 : %s", formatVdd2(g.vdd2GoodUv).c_str());
                uiPrintf(row++, "Action: Save KIP + Reboot");
            }
            break;
''', r'''        case Stage::Vdd2Long:
            if (g.recoveryNeeded) { printSafeRecovery("RAM Settings", "VDD2 = " + formatVdd2(g.vdd2GoodUv)); row = 14; }
            else {
                uiPrintf(row++, "RAM Settings:");
                uiPrintf(row++, "VDDQ : %d mV", g.vddqGood);
                uiPrintf(row++, "VDD2 : %s", formatVdd2(g.vdd2GoodUv).c_str());
                uiPrintf(row++, "Action: Reboot CFW");
            }
            break;
''', 'Vdd2Long'),
(r'''        case Stage::RamBoostValidate:
            uiPrintf(row++, "VDDQ : %d mV", g.vddqGood);
            uiPrintf(row++, "VDD2 : %s", formatVdd2(g.vdd2GoodUv).c_str());
''', r'''        case Stage::RamBoostValidate:
            uiPrintf(row++, "RAM Settings:");
            uiPrintf(row++, "VDDQ : %d mV", g.vddqGood);
            uiPrintf(row++, "VDD2 : %s", formatVdd2(g.vdd2GoodUv).c_str());
''', 'RamBoostValidate'),
(r'''        case Stage::Ram1331Validate:
            uiPrintf(row++, "VDDQ : %d mV", g.vddqGood);
            uiPrintf(row++, "VDD2 : %s", formatVdd2(g.vdd2GoodUv).c_str());
            break;
''', r'''        case Stage::Ram1331Validate:
            uiPrintf(row++, "RAM Settings:");
            uiPrintf(row++, "VDDQ : %d mV", g.vddqGood);
            uiPrintf(row++, "VDD2 : %s", formatVdd2(g.vdd2GoodUv).c_str());
            break;
''', 'Ram1331Validate'),
(r'''        case Stage::HighUvQuick:
            uiPrintf(row++, "High UV : %d", g.highUvTest);
            uiPrintf(row++, "Action  : Save KIP + Reboot");
            break;
''', r'''        case Stage::HighUvQuick:
            uiPrintf(row++, "CPU UV:");
            uiPrintf(row++, "High UV : %d", g.highUvTest);
            uiPrintf(row++, "Action  : Reboot CFW");
            break;
''', 'HighUvQuick'),
(r'''        case Stage::HighUvLong:
            if (g.recoveryNeeded) { printSafeRecovery("CPU High UV = " + std::to_string(g.highUvGood)); row = 13; }
            else {
                uiPrintf(row++, "High UV : %d", g.highUvGood);
                uiPrintf(row++, "Action  : Save KIP + Reboot");
            }
            break;
''', r'''        case Stage::HighUvLong:
            if (g.recoveryNeeded) { printSafeRecovery("CPU UV", "High UV = " + std::to_string(g.highUvGood)); row = 14; }
            else {
                uiPrintf(row++, "CPU UV:");
                uiPrintf(row++, "High UV : %d", g.highUvGood);
                uiPrintf(row++, "Action  : Reboot CFW");
            }
            break;
''', 'HighUvLong'),
(r'''        case Stage::BoostCpuRamValidate:
            uiPrintf(row++, "Low UV  : %d", g.lowUvGood);
            uiPrintf(row++, "High UV : %d", g.highUvGood);
            uiPrintf(row++, "VMIN    : %d mV", g.lowVminGood);
            break;
''', r'''        case Stage::BoostCpuRamValidate:
            uiPrintf(row++, "CPU UV:");
            uiPrintf(row++, "Low UV  : %d", g.lowUvGood);
            uiPrintf(row++, "High UV : %d", g.highUvGood);
            uiPrintf(row++, "CPU Settings:");
            uiPrintf(row++, "Low VMIN: %d mV", g.lowVminGood);
            break;
''', 'BoostCpuRamValidate'),
(r'''        case Stage::BoostCpuMemValidate:
            uiPrintf(row++, "Use final validated values");
            break;
''', r'''        case Stage::BoostCpuMemValidate:
            uiPrintf(row++, "HOC Settings:");
            uiPrintf(row++, "Use final validated values");
            break;
''', 'Final validated values')
]

for old, new, label in repls:
    s = must_replace(s, old, new, label)

# Real-world page: make the location of the setting explicit.
s = must_replace(s, r'''    uiPrintf(5, "Set in HOC:");
    uiPrintf(6, "Remove all Temporary Overrides");
''', r'''    uiPrintf(5, "Temporary Overrides:");
    uiPrintf(6, "Remove all Overrides");
''', 'renderRealWorld')

# Sanity: no manual-save prompts should survive in the app source.
if 'Save KIP' in s or 'Save Toolkit' in s:
    raise SystemExit('manual save wording still present in source/main.cpp')
p.write_text(s)

# ---------------------------------------------------------------------------
# README - current guide wording and menu structure
# ---------------------------------------------------------------------------
p = Path('README.md')
r = p.read_text()

r = r.replace('- `Save KIP + Reboot` is shown only on stages where the persistent HOC value has actually changed.\n',
              '- `Reboot CFW` is shown only on stages where the persistent HOC value has actually changed.\n')

r = must_replace(r, '''5. Save KIP.\n6. Reboot normally.\n7. Continue validation.\n''',
                    '''5. Reboot normally.\n6. Continue validation.\n''', 'README recovery')

old_setup = '''### Safety\n\n- **Uncapped Clocks: OFF**\n\n### RAM\n\n- **HP Mode: OFF**\n- **RAM Max Clock: 1600 MHz**\n- **VDD2: 1175 mV**\n- **VDDQ: 600 mV**\n\n### CPU\n\n- **CPU Max Clock: lowest selectable value**\n  - current Mariko HOC builds show **1963 MHz** as the lowest selectable CPU Max Clock\n- **CPU UV Table: 1683 MHz Tbreak**\n- **Low UV: 0**\n- **High UV: 0**\n- **Low VMIN: 620 mV**\n- **High VMIN: 750 mV**\n\n## HOC Toolkit\n\n- **CPU Boost Clock: lowest selectable value**\n  - stock Nintendo Boost target used by this workflow is **1785 MHz**\n\nAfter changing persistent HOC/Toolkit settings:\n\n**Save KIP -> reboot CFW -> reopen the Wizard**\n'''
new_setup = '''### General\n\n- **Uncapped Clocks: OFF**\n\n### RAM Settings\n\n- **HP Mode: OFF**\n- **RAM Max Clock: 1600 MHz**\n- **VDD2: 1175 mV**\n- **VDDQ: 600 mV**\n\n### CPU Settings\n\n- **CPU Max Clock: lowest selectable value**\n  - current Mariko HOC builds show **1963 MHz** as the lowest selectable CPU Max Clock\n- **Low VMIN: 620 mV**\n- **High VMIN: 750 mV**\n\n### CPU UV\n\n- **CPU UV Table: 1683 MHz Tbreak**\n- **Low UV: 0**\n- **High UV: 0**\n\n## HOC Toolkit\n\n- **CPU Boost Clock: lowest selectable value**\n  - stock Nintendo Boost target used by this workflow is **1785 MHz**\n\nAfter changing persistent HOC/Toolkit settings:\n\n**Reboot CFW -> reopen the Wizard**\n'''
r = must_replace(r, old_setup, new_setup, 'README starting setup')

# Update old installation note so it does not imply beta.8 is still the required manual bridge.
r = r.replace('For beta.8 this is the final required manual update; later builds can be installed by the in-app updater.',
              'Once an updater-capable build is installed, later builds can be installed by the in-app updater.')

# Document beta.12 behavior near the top.
entry = '''# New in v0.4.0-beta.12\n\n- Remove all manual **Save KIP / Save Toolkit** instructions from the active Wizard guide.\n- Persistent setting changes now simply tell the user when a **CFW reboot** is required.\n- Group every HOC set point under its actual menu area: **General**, **RAM Settings**, **CPU Settings**, **CPU UV**, **HOC Toolkit**, and **Temporary Overrides**.\n- Keep the beta.11 tuning/test logic unchanged.\n- Expand the GitHub Releases API fallback from 5 to 100 entries; the lightweight `UPDATE.txt` manifest remains the primary update source.\n\n---\n\n'''
if '# New in v0.4.0-beta.12' not in r:
    r = r.replace('# New in v0.4.0-beta.11\n', entry + '# New in v0.4.0-beta.11\n', 1)

# The active README guide should not contain manual-save instructions anymore.
if 'Save KIP' in r or 'Save Toolkit' in r:
    raise SystemExit('manual save wording still present in README.md')
p.write_text(r)

# ---------------------------------------------------------------------------
# Version/update metadata + fallback query size
# ---------------------------------------------------------------------------
p = Path('Makefile')
m = p.read_text()
m = must_replace(m, 'APP_VERSION := 0.4.0-beta.11', 'APP_VERSION := 0.4.0-beta.12', 'Makefile version')
p.write_text(m)

p = Path('source/updater.cpp')
u = p.read_text()
u = must_replace(u, 'releases?per_page=5', 'releases?per_page=100', 'updater release page size')
p.write_text(u)

Path('UPDATE.txt').write_text('''version=0.4.0-beta.12\nnro_url=https://github.com/retrotendo/HOC-Undervolting-Wizard/releases/download/v0.4.0-beta.12/HOC-Undervolting-Wizard.nro\nsha_url=https://github.com/retrotendo/HOC-Undervolting-Wizard/releases/download/v0.4.0-beta.12/HOC-Undervolting-Wizard.nro.sha256\n''')

p = Path('CHANGELOG.md')
c = p.read_text()
entry = '''## v0.4.0-beta.12\n\n- Remove manual Save KIP / Save Toolkit prompts from the active Wizard flow and documentation.\n- Keep required CFW reboot instructions where persistent settings change.\n- Label set points by their HOC menu area: General, RAM Settings, CPU Settings, CPU UV, HOC Toolkit and Temporary Overrides.\n- Preserve beta.11 tuning, stress-test, VMIN, skip and recovery logic.\n- Increase the GitHub Releases API fallback window from 5 to 100 releases.\n\n'''
if '## v0.4.0-beta.12' not in c:
    c = c.replace('# Changelog\n\n', '# Changelog\n\n' + entry, 1)
p.write_text(c)
