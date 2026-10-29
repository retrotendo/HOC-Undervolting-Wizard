from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

def rep(old, new, label, count=1):
    global s
    if old not in s:
        raise SystemExit(f'{label} not found')
    s = s.replace(old, new, count)

# Present the two final anchor validations as CPU-memtester checks, mirroring
# the OC Part 1 workflow: critical low/normal point first, then final Boost.
rep('case Stage::NormalMatrixValidate: return "Final Normal - CPU";',
    'case Stage::NormalMatrixValidate: return "Handheld CPU + RAM Validation";',
    'stageName normal')
rep('case Stage::BoostCpuRamValidate: return "Boost CPU + RAM Validation";',
    'case Stage::BoostCpuRamValidate: return "Boost CPU + RAM Validation";',
    'stageName boost')

old_testplan = '''        case Stage::LowVminFinalLong:
        case Stage::HighUvLong:
        case Stage::NormalMatrixValidate:
        case Stage::BoostMatrixValidate:
            kind = stress::Kind::Cpu; seconds = 3600; return true;
        case Stage::VddqQuick:
        case Stage::Vdd2Quick:
            kind = stress::Kind::Ram; seconds = 60; return true;
        case Stage::VddqLong:
        case Stage::Vdd2Long:
        case Stage::RamBoostValidate:
        case Stage::Ram1331Validate:
        case Stage::NormalMemValidate:
        case Stage::BoostMemValidate:
            kind = stress::Kind::Ram; seconds = 3600; return true;
        case Stage::BoostCpuRamValidate:
        case Stage::BoostCpuMemValidate:
            kind = stress::Kind::Combined; seconds = 3600; return true;
'''
new_testplan = '''        case Stage::LowVminFinalLong:
        case Stage::HighUvLong:
        case Stage::BoostMatrixValidate:
            kind = stress::Kind::Cpu; seconds = 3600; return true;
        case Stage::VddqQuick:
        case Stage::Vdd2Quick:
            kind = stress::Kind::Ram; seconds = 60; return true;
        case Stage::VddqLong:
        case Stage::Vdd2Long:
        case Stage::RamBoostValidate:
        case Stage::Ram1331Validate:
        case Stage::NormalMatrixValidate:
        case Stage::NormalMemValidate:
        case Stage::BoostCpuRamValidate:
        case Stage::BoostMemValidate:
            kind = stress::Kind::Ram; seconds = 3600; return true;
        case Stage::BoostCpuMemValidate:
            kind = stress::Kind::Combined; seconds = 3600; return true;
'''
rep(old_testplan, new_testplan, 'testPlan Part1 anchors')

# UI names: the built-in RAM kind is the full CPU memtester sequence.
rep('case stress::Kind::Ram: return "RAM memtester";',
    'case stress::Kind::Ram: return "CPU memtester";',
    'compact test name')
rep('case Stage::NormalMatrixValidate: return "Final Handheld - CPU";',
    'case Stage::NormalMatrixValidate: return "Handheld CPU + RAM";',
    'compact normal')

rep('''        case Stage::BoostCpuRamValidate:
            uiPrintf(row++, "CPU + RAM Boost stability will be tested now.");
            break;
        case Stage::NormalMatrixValidate:
            uiPrintf(row++, "Final handheld CPU stability will be tested now.");
            break;
''', '''        case Stage::BoostCpuRamValidate:
            uiPrintf(row++, "Final High UV + RAM Boost stability");
            uiPrintf(row++, "will be tested now at 1785 / 1600.");
            break;
        case Stage::NormalMatrixValidate:
            uiPrintf(row++, "Critical Low CPU + RAM stability");
            uiPrintf(row++, "will be tested now at 1020 / 1331.");
            break;
''', 'validation objective')

# Part 1 style flow:
# final VDD2 candidate -> critical 1020/1331 CPU-memtester -> High UV quick search
# -> final 1785/1600 CPU-memtester -> real-world test.
rep('''        case Stage::Vdd2Long:
            g.recoveryNeeded = false;
            g.ramPairRetryMode = 0;
            g.stage = Stage::RamBoostValidate;
            break;
        case Stage::RamBoostValidate:
            g.ramPairRetryMode = 0;
            g.stage = Stage::Ram1331Validate;
            break;
        case Stage::Ram1331Validate:
            if (g.highUvGood >= HIGH_UV_MAX) {
                g.stage = Stage::HighUvLong;
                g.stageReadyAfterBoot = true;
            } else {
                g.stage = Stage::HighUvQuick;
                g.highUvTest = g.highUvGood + 1;
                g.stageReadyAfterBoot = false;
            }
            break;
''', '''        case Stage::Vdd2Long:
            g.recoveryNeeded = false;
            g.ramPairRetryMode = 0;
            g.stage = Stage::NormalMatrixValidate;
            break;
        case Stage::RamBoostValidate:
        case Stage::Ram1331Validate:
            // Legacy beta states now continue with the Part-1 critical low anchor.
            g.ramPairRetryMode = 0;
            g.stage = Stage::NormalMatrixValidate;
            break;
''', 'post VDD2 flow')

rep('''        case Stage::HighUvQuick:
            g.highUvGood = g.highUvTest;
            if (g.highUvTest >= HIGH_UV_MAX) {
                g.stage = Stage::HighUvLong;
                g.stageReadyAfterBoot = true;
            } else {
                ++g.highUvTest;
                g.stageReadyAfterBoot = false;
            }
            break;
        case Stage::HighUvLong:
            g.recoveryNeeded = false;
            g.stage = Stage::BoostCpuRamValidate;
            break;
        case Stage::BoostCpuRamValidate: g.stage = Stage::NormalMatrixValidate; break;
        case Stage::NormalMatrixValidate: g.stage = Stage::RealWorldValidate; break;
''', '''        case Stage::HighUvQuick:
            g.highUvGood = g.highUvTest;
            if (g.highUvTest >= HIGH_UV_MAX) {
                g.stage = Stage::BoostCpuRamValidate;
                g.stageReadyAfterBoot = true;
            } else {
                ++g.highUvTest;
                g.stageReadyAfterBoot = false;
            }
            break;
        case Stage::HighUvLong:
            // Legacy beta state: the Boost CPU-memtester now replaces this
            // standalone High UV one-hour CPU test.
            g.recoveryNeeded = false;
            g.stage = Stage::BoostCpuRamValidate;
            break;
        case Stage::NormalMatrixValidate:
            if (g.highUvGood >= HIGH_UV_MAX) {
                g.stage = Stage::BoostCpuRamValidate;
                g.stageReadyAfterBoot = true;
            } else {
                g.stage = Stage::HighUvQuick;
                g.highUvTest = g.highUvGood + 1;
                g.stageReadyAfterBoot = false;
            }
            break;
        case Stage::BoostCpuRamValidate: g.stage = Stage::RealWorldValidate; break;
''', 'high UV and final anchors')

# First failed High UV quick candidate: restore the previous known-good High UV
# and go straight to the one-hour Boost CPU-memtester. No duplicate one-hour CPU test.
rep('''        case Stage::HighUvQuick:
            g.stage = Stage::HighUvLong;
            g.recoveryNeeded = didNotBoot;
            g.pendingConfigMask = Config_HighUv;
            break;
''', '''        case Stage::HighUvQuick:
            g.stage = Stage::BoostCpuRamValidate;
            g.recoveryNeeded = didNotBoot;
            g.pendingConfigMask = Config_HighUv;
            break;
''', 'High UV fail transition')

# Old saved states from beta38/beta39 drafts are migrated into the new flow.
needle = '''    const bool removedFinalValidationStage =
        g.stage == Stage::NormalMemValidate || g.stage == Stage::NormalGpuValidate ||
        g.stage == Stage::BoostMatrixValidate || g.stage == Stage::BoostMemValidate ||
        g.stage == Stage::BoostCpuMemValidate;
    if (removedFinalValidationStage) {
        g.stage = Stage::RealWorldValidate;
        g.stageReadyAfterBoot = true;
        g.pendingConfigMask = Config_None;
    }
'''
replacement = '''    if (g.stage == Stage::RamBoostValidate || g.stage == Stage::Ram1331Validate) {
        g.stage = Stage::NormalMatrixValidate;
        g.stageReadyAfterBoot = true;
        g.pendingConfigMask = Config_None;
    } else if (g.stage == Stage::HighUvLong) {
        g.stage = Stage::BoostCpuRamValidate;
        g.stageReadyAfterBoot = true;
        g.pendingConfigMask = Config_None;
    }

    const bool removedFinalValidationStage =
        g.stage == Stage::NormalMemValidate || g.stage == Stage::NormalGpuValidate ||
        g.stage == Stage::BoostMatrixValidate || g.stage == Stage::BoostMemValidate ||
        g.stage == Stage::BoostCpuMemValidate;
    if (removedFinalValidationStage) {
        g.stage = Stage::RealWorldValidate;
        g.stageReadyAfterBoot = true;
        g.pendingConfigMask = Config_None;
    }
'''
rep(needle, replacement, 'state migration')

rep('f << "Built-in CPU/RAM/combined/GPU validation completed.\\n";',
    'f << "Part-1-style critical CPU/RAM validation completed.\\n";',
    'results wording')

p.write_text(s)
