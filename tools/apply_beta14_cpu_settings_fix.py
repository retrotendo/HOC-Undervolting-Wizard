from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

old = '''    uiPrintf(16, "CPU Settings:");
    uiPrintf(17, " - CPU Max         : Lowest selectable (1963)");
    uiPrintf(18, " - Low VMIN        : 620 mV");
    uiPrintf(19, " - High VMIN       : 750 mV");

    uiPrintf(21, "CPU UV:");
    uiPrintf(22, " - UV Table        : 1683 MHz Tbreak");
    uiPrintf(23, " - Low UV          : 0");
    uiPrintf(24, " - High UV         : 0");

    uiPrintf(26, "@ HOC Toolkit");
    uiPrintf(28, " - CPU Boost       : Lowest selectable / 1785");

    uiPrintf(30, "Then:");
    uiPrintf(31, " - Reboot CFW and reopen Wizard");
    uiPrintf(33, "Keys:");
    uiPrintf(34, "A : Setup done / Start");
    uiPrintf(35, "B : Exit    - : Reset");
'''
new = '''    uiPrintf(16, "CPU Settings:");
    uiPrintf(17, " - CPU Max         : Lowest selectable (1963)");
    uiPrintf(18, " - Low VMIN        : 620 mV");
    uiPrintf(19, " - High VMIN       : 750 mV");
    uiPrintf(20, " - UV Table        : 1683 MHz Tbreak");
    uiPrintf(21, " - Low UV          : 0");
    uiPrintf(22, " - High UV         : 0");

    uiPrintf(24, "@ HOC Toolkit");
    uiPrintf(26, " - CPU Boost       : Lowest selectable / 1785");

    uiPrintf(28, "Then:");
    uiPrintf(29, " - Reboot CFW and reopen Wizard");
    uiPrintf(31, "Keys:");
    uiPrintf(32, "A : Setup done / Start");
    uiPrintf(33, "B : Exit    - : Reset");
'''
if old not in s:
    raise SystemExit('Preparation CPU block not found')
s = s.replace(old, new, 1)

# All CPU UV controls live inside Horizon OC -> CPU Settings.
s = s.replace('"CPU UV:"', '"CPU Settings:"')
s = s.replace('printSafeRecovery("CPU UV",', 'printSafeRecovery("CPU Settings",')

# Combined CPU validation already has all of these controls in the same submenu;
# remove the duplicate CPU Settings heading between UV and VMIN values.
old = '''        case Stage::BoostCpuRamValidate:
            uiPrintf(row++, "CPU Settings:");
            uiPrintf(row++, " - Low UV  : %d", g.lowUvGood);
            uiPrintf(row++, " - High UV : %d", g.highUvGood);
            uiPrintf(row++, "CPU Settings:");
            uiPrintf(row++, " - Low VMIN: %d mV", g.lowVminGood);
            break;
'''
new = '''        case Stage::BoostCpuRamValidate:
            uiPrintf(row++, "CPU Settings:");
            uiPrintf(row++, " - Low UV   : %d", g.lowUvGood);
            uiPrintf(row++, " - High UV  : %d", g.highUvGood);
            uiPrintf(row++, " - Low VMIN : %d mV", g.lowVminGood);
            break;
'''
if old not in s:
    raise SystemExit('Boost CPU Settings block not found')
s = s.replace(old, new, 1)

p.write_text(s)

# Version/update metadata.
p = Path('Makefile')
s = p.read_text().replace('APP_VERSION := 0.4.0-beta.13', 'APP_VERSION := 0.4.0-beta.14')
p.write_text(s)

Path('UPDATE.txt').write_text('''version=0.4.0-beta.14\nnro_url=https://github.com/retrotendo/HOC-Undervolting-Wizard/releases/download/v0.4.0-beta.14/HOC-Undervolting-Wizard.nro\nsha_url=https://github.com/retrotendo/HOC-Undervolting-Wizard/releases/download/v0.4.0-beta.14/HOC-Undervolting-Wizard.nro.sha256\n''')

p = Path('README.md')
s = p.read_text()
marker = '# New in v0.4.0-beta.13\n'
section = '''# New in v0.4.0-beta.14\n\n- Correct the Horizon OC menu hierarchy: there is no separate **CPU UV** menu.\n- CPU Max, Low/High VMIN, UV Table, Low UV and High UV are all shown under **CPU Settings**.\n- Preparation and tuning/recovery screens now use the same real Horizon OC menu path.\n- No tuning, reboot, stress-test, VMIN, override or updater logic changes.\n\n---\n\n'''
if marker not in s:
    raise SystemExit('README beta13 marker not found')
s = s.replace(marker, section + marker, 1)
p.write_text(s)

p = Path('CHANGELOG.md')
s = p.read_text()
p.write_text('''## v0.4.0-beta.14\n- Fix Horizon OC menu naming: CPU UV controls are part of CPU Settings.\n- Merge CPU Max / VMIN / UV controls into one CPU Settings block in Preparation.\n- Use CPU Settings on all Low UV / High UV / recovery screens.\n- No tuning/test logic changes.\n\n''' + s)
