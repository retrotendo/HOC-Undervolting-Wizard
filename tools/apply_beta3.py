from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "source" / "main.cpp"
text = path.read_text()


def rep(old, new):
    global text
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f"expected 1 match, got {n}: {old[:120]!r}")
    text = text.replace(old, new, 1)

# Constants and stage IDs. Existing IDs remain unchanged for state.ini compatibility.
rep(
'''constexpr u32 CLOCK_CPU_NORMAL_HZ = 1020000000U;
constexpr u32 CLOCK_CPU_LOW_HZ    = 510000000U;
constexpr u32 CLOCK_CPU_BOOST_HZ  = 1785000000U;
''',
'''constexpr u32 CLOCK_CPU_NORMAL_HZ = 1020000000U;
constexpr u32 CLOCK_CPU_LOW_HZ    = 612000000U;
constexpr u32 CLOCK_CPU_VMIN_MID_HZ = 816000000U;
constexpr u32 CLOCK_CPU_BOOST_HZ  = 1785000000U;
''')
rep('constexpr int LOW_VMIN_MIN_MV = 550;\n', 'constexpr int LOW_VMIN_MIN_MV = 570;\n')
rep(
'''    RealWorldValidate,
    Complete
};
''',
'''    RealWorldValidate,
    Complete,
    // Appended to preserve all existing beta.2 stage numbers in state.ini.
    LowVminValidate816,
    LowVminValidate1020
};
''')

# Stage labels.
rep(
'''        case Stage::LowVminQuick: return "CPU Low VMIN - Quick Search";
        case Stage::LowVminLong: return "CPU Low VMIN - 1 Hour Validation";
''',
'''        case Stage::LowVminQuick: return "CPU Low VMIN - Quick Search @ 612";
        case Stage::LowVminLong: return "CPU Low VMIN - Validation 1/3 @ 612";
        case Stage::LowVminValidate816: return "CPU Low VMIN - Validation 2/3 @ 816";
        case Stage::LowVminValidate1020: return "CPU Low VMIN - Validation 3/3 @ 1020";
''')

# Test plan: all three final VMIN validation stages are one-hour CPU tests.
rep(
'''        case Stage::LowUvLong:
        case Stage::LowVminLong:
        case Stage::HighUvLong:
''',
'''        case Stage::LowUvLong:
        case Stage::LowVminLong:
        case Stage::LowVminValidate816:
        case Stage::LowVminValidate1020:
        case Stage::HighUvLong:
''')

# Override plan: quick VMIN search now runs at 612, then 612/816/1020 validation.
rep(
'''        case Stage::LowUvQuick:
        case Stage::LowUvLong:
        case Stage::LowVminQuick:
        case Stage::Ram1331Validate:
''',
'''        case Stage::LowUvQuick:
        case Stage::LowUvLong:
        case Stage::LowVminValidate1020:
        case Stage::Ram1331Validate:
''')
rep(
'''        case Stage::LowVminLong:
            e = {CLOCK_CPU_LOW_HZ, CLOCK_GPU_NORMAL_HZ, CLOCK_RAM_NORMAL_HZ};
            return true;

        case Stage::VddqQuick:
''',
'''        case Stage::LowVminQuick:
        case Stage::LowVminLong:
            e = {CLOCK_CPU_LOW_HZ, CLOCK_GPU_NORMAL_HZ, CLOCK_RAM_NORMAL_HZ};
            return true;

        case Stage::LowVminValidate816:
            e = {CLOCK_CPU_VMIN_MID_HZ, CLOCK_GPU_NORMAL_HZ, CLOCK_RAM_NORMAL_HZ};
            return true;

        case Stage::VddqQuick:
''')

# Never allow an old beta.2 state to continue below the new 570 mV floor.
rep(
'''    while (std::getline(f, line)) {
        const auto p = line.find('=');
        if (p != std::string::npos) assignKV(line.substr(0, p), line.substr(p + 1));
    }
    return true;
}
''',
'''    while (std::getline(f, line)) {
        const auto p = line.find('=');
        if (p != std::string::npos) assignKV(line.substr(0, p), line.substr(p + 1));
    }
    if (g.lowVminGood < LOW_VMIN_MIN_MV) g.lowVminGood = LOW_VMIN_MIN_MV;
    if (g.lowVminTest < LOW_VMIN_MIN_MV) g.lowVminTest = LOW_VMIN_MIN_MV;
    return true;
}
''')

# UI for VMIN stages.
rep(
'''        case Stage::LowVminQuick:
            std::printf("Keep CPU Low UV = %d.\\n", g.lowUvGood);
            std::printf("Set CPU Low VMIN = \\x1b[1m%d mV\\x1b[0m, Save KIP and reboot.\\n", g.lowVminTest);
            if (g.lowVminTest < 590) std::printf("\\x1b[33mNote: HOC recommends >=590 mV.\\x1b[0m\\n");
            std::printf("Overrides: CPU 1020 / GPU 384 / RAM 1331\\n");
            break;
        case Stage::LowVminLong:
            if (g.recoveryNeeded) printSafeRecovery("CPU Low VMIN = " + std::to_string(g.lowVminGood) + " mV");
            else std::printf("Restore CPU Low VMIN = \\x1b[1m%d mV\\x1b[0m, Save KIP and reboot.\\n", g.lowVminGood);
            std::printf("Overrides: CPU 510 / GPU 384 / RAM 1331\\n");
            std::printf("After validation also check normal Sleep/Wake transitions.\\n");
            break;
''',
'''        case Stage::LowVminQuick:
            std::printf("Keep CPU Low UV = %d.\\n", g.lowUvGood);
            std::printf("Set CPU Low VMIN = \\x1b[1m%d mV\\x1b[0m, Save KIP and reboot.\\n", g.lowVminTest);
            if (g.lowVminTest < 590) std::printf("\\x1b[33mAdvanced low-VMIN range. Wizard floor: 570 mV.\\x1b[0m\\n");
            std::printf("Quick-search Overrides: CPU 612 / GPU 384 / RAM 1331\\n");
            break;
        case Stage::LowVminLong:
            if (g.recoveryNeeded) printSafeRecovery("CPU Low VMIN = " + std::to_string(g.lowVminGood) + " mV");
            else std::printf("Use CPU Low VMIN = \\x1b[1m%d mV\\x1b[0m, Save KIP and reboot.\\n", g.lowVminGood);
            std::printf("Final VMIN validation 1/3.\\n");
            std::printf("Overrides: CPU 612 / GPU 384 / RAM 1331\\n");
            break;
        case Stage::LowVminValidate816:
            std::printf("Keep CPU Low VMIN = \\x1b[1m%d mV\\x1b[0m.\\n", g.lowVminGood);
            std::printf("Final VMIN validation 2/3. No KIP change required.\\n");
            std::printf("Overrides: CPU 816 / GPU 384 / RAM 1331\\n");
            break;
        case Stage::LowVminValidate1020:
            std::printf("Keep CPU Low VMIN = \\x1b[1m%d mV\\x1b[0m.\\n", g.lowVminGood);
            std::printf("Final VMIN validation 3/3. No KIP change required.\\n");
            std::printf("Overrides: CPU 1020 / GPU 384 / RAM 1331\\n");
            std::printf("After PASS also check normal Sleep/Wake transitions.\\n");
            break;
''')

# Pass progression: 612 -> 816 -> 1020, then move to VDDQ.
rep(
'''        case Stage::LowVminLong:
            g.recoveryNeeded = false; g.stage = Stage::VddqQuick;
            g.vddqTest = STOCK_VDDQ_MV - VDDQ_STEP_MV; break;
''',
'''        case Stage::LowVminLong:
            g.recoveryNeeded = false; g.stage = Stage::LowVminValidate816; break;
        case Stage::LowVminValidate816:
            g.stage = Stage::LowVminValidate1020; break;
        case Stage::LowVminValidate1020:
            g.stage = Stage::VddqQuick;
            g.vddqTest = STOCK_VDDQ_MV - VDDQ_STEP_MV; break;
''')

# Any long-validation failure makes VMIN +5 mV safer and restarts at 612.
rep(
'''        case Stage::LowVminQuick: enterLowVminLong(didNotBoot); return;
        case Stage::LowVminLong: g.lowVminGood += LOW_VMIN_STEP_MV; g.recoveryNeeded = false; break;
''',
'''        case Stage::LowVminQuick: enterLowVminLong(didNotBoot); return;
        case Stage::LowVminLong:
        case Stage::LowVminValidate816:
        case Stage::LowVminValidate1020:
            if (g.lowVminGood < STOCK_LOW_VMIN_MV) g.lowVminGood += LOW_VMIN_STEP_MV;
            g.recoveryNeeded = false;
            g.stage = Stage::LowVminLong;
            break;
''')

# Interrupted-test stage validation must include the two appended stages.
text = text.replace(
    'g.testStage <= static_cast<int>(Stage::Complete)',
    'g.testStage <= static_cast<int>(Stage::LowVminValidate1020)'
)
if 'g.testStage <= static_cast<int>(Stage::Complete)' in text:
    raise RuntimeError('not all interrupted-stage bounds were updated')

path.write_text(text)

# Version metadata.
mk = ROOT / "Makefile"
m = mk.read_text()
if 'APP_VERSION := 0.4.0-beta.2' not in m:
    raise RuntimeError('unexpected Makefile version')
mk.write_text(m.replace('APP_VERSION := 0.4.0-beta.2', 'APP_VERSION := 0.4.0-beta.3'))

# README updates.
readme = ROOT / "README.md"
r = readme.read_text()
r = r.replace(
    '- CPU Low VMIN: 620 mV\n',
    '- CPU Low VMIN: 620 mV baseline; Wizard searches downward in 5 mV steps to a hard floor of **570 mV**\n'
)
r = r.replace(
    '- CPU Low VMIN: -5 mV\n',
    '- CPU Low VMIN: -5 mV, minimum **570 mV**\n'
)
workflow_marker = 'Quick searches run for **1 minute**. At the first failure, the previous working value becomes the candidate for a **1-hour validation**. If the long validation fails, the Wizard moves one step safer and repeats the validation.\n'
workflow_new = '''Quick searches run for **1 minute**. At the first failure, the previous working value becomes the candidate for long validation. If a long validation fails, the Wizard moves one step safer and repeats the validation.\n\nFor **CPU Low VMIN**, the quick search is intentionally run at **612 / 384 / 1331.2 MHz** so the voltage floor is actually exercised. The selected VMIN is then validated for **1 hour each at CPU 612 -> 816 -> 1020 MHz** (GPU 384 / RAM 1331.2 throughout). Any failure makes VMIN **+5 mV safer** and restarts the three-stage validation at 612 MHz. The Wizard never searches below **570 mV**.\n'''
if workflow_marker not in r:
    raise RuntimeError('README workflow marker missing')
r = r.replace(workflow_marker, workflow_new, 1)
readme.write_text(r)

# Changelog.
chg = ROOT / "CHANGELOG.md"
c = chg.read_text()
entry = '''## v0.4.0-beta.3\n\n- Changed CPU Low VMIN hard floor from 550 mV to **570 mV**.\n- Moved Low VMIN quick search to **612 / 384 / 1331.2 MHz** so the floor is exercised directly.\n- Added sequential 1-hour Low VMIN validation at **612 -> 816 -> 1020 MHz**.\n- CPU/GPU/RAM Temporary Overrides are verified before every one of those validation runs.\n- Any failure in the three-stage VMIN validation raises Low VMIN by **5 mV** and restarts validation at 612 MHz.\n- Existing beta.2 state files are clamped to the new 570 mV minimum on load.\n\n'''
if '## v0.4.0-beta.3' not in c:
    pos = c.find('\n\n', len('# Changelog'))
    c = c[:pos+2] + entry + c[pos+2:]
chg.write_text(c)

print('beta3 patch applied')
