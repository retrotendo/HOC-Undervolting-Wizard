from pathlib import Path


def repl(text, old, new, name):
    if old not in text:
        raise SystemExit(f"missing block: {name}")
    return text.replace(old, new, 1)

p = Path('source/main.cpp')
s = p.read_text()

s = repl(s,
'''bool g_configPrompt = false;\nbool g_configDebugScreen = false;''',
'''bool g_configPrompt = false;\nbool g_configPromptSafetyOnly = false;\nbool g_configDebugScreen = false;''',
'config safety flag')

insert_after = '''bool verifyPersistentSettings(u32 mask) {\n    g_configCheck = ConfigCheckState{};\n    g_configCheck.mask = mask;\n    g_configCheck.readOk = readHocConfigIni(g_configCheck.current);\n    g_configCheck.rc = g_configCheck.readOk ? 0 : 0xF024;\n    return g_configCheck.readOk && configMatchesCurrent(mask, g_configCheck.current);\n}\n'''
helper = insert_after + r'''

u32 wizardTunableMismatchMask(const HocMonConfig& c) {
    u32 mask = Config_None;
    if (c.lowUv != targetLowUv()) mask |= Config_LowUv;
    if (c.lowVminMv != targetLowVmin()) mask |= Config_LowVmin;
    if (c.vddqUv != (u32)targetVddqMv() * 1000U) mask |= Config_Vddq;
    if (c.vdd2Uv != (u32)targetVdd2Uv()) mask |= Config_Vdd2;
    if (c.highUv != targetHighUv()) mask |= Config_HighUv;
    return mask;
}

bool guardWizardTunableState() {
    // During the active guide, all five tunable values must match the exact
    // state the Wizard expects. The one setting currently being changed is
    // already represented by target*(); every other setting remains at its
    // last known-good (or imported baseline) value.
    HocMonConfig current{};
    bool readOk = R_SUCCEEDED(hocmonGetConfig251(&current));
    if (!readOk) readOk = readHocConfigIni(current);

    if (!readOk) {
        g_configCheck = ConfigCheckState{};
        g_configCheck.readOk = false;
        g_configCheck.rc = 0xF024;
        g_configCheck.mask = Config_None;
        g_configPromptSafetyOnly = true;
        g_configPrompt = true;
        return false;
    }

    const u32 mismatch = wizardTunableMismatchMask(current);
    if (mismatch == Config_None) return true;

    g_configCheck = ConfigCheckState{};
    g_configCheck.readOk = true;
    g_configCheck.current = current;
    g_configCheck.mask = mismatch;
    g_configPromptSafetyOnly = true;
    g_configPrompt = true;
    return false;
}
'''
s = repl(s, insert_after, helper, 'wizard state guard helpers')

old = '''    const u32 mask = guiInstructionMask();\n    if (mask & Config_Prepare) {'''
new = '''    const u32 mask = guiInstructionMask();\n    if (g_configPromptSafetyOnly) {\n        v.instructionTitle = "Unexpected setting change";\n        v.instructionLine1 = "Restore the red values";\n        v.instructionLine2 = "A : Check again";\n    } else if (mask & Config_Prepare) {'''
s = repl(s, old, new, 'safety instruction card')

old = '''        if (mask & Config_Prepare) {\n            v.values[0].mismatch = c.lowUv != STOCK_LOW_UV;\n            v.values[1].mismatch = c.lowVminMv != STOCK_LOW_VMIN_MV;\n            v.values[2].mismatch = (int)(c.vddqUv / 1000U) != g.vddqStartMv;\n            v.values[3].mismatch = (int)c.vdd2Uv != STOCK_VDD2_UV;\n            v.values[4].mismatch = c.highUv != STOCK_HIGH_UV;\n        } else {\n            if (mask & Config_LowUv) v.values[0].mismatch = c.lowUv != targetLowUv();\n            if (mask & Config_LowVmin) v.values[1].mismatch = c.lowVminMv != targetLowVmin();\n            if (mask & Config_Vddq) v.values[2].mismatch = (int)(c.vddqUv / 1000U) != targetVddqMv();\n            if (mask & Config_Vdd2) v.values[3].mismatch = (int)c.vdd2Uv != targetVdd2Uv();\n            if (mask & Config_HighUv) v.values[4].mismatch = c.highUv != targetHighUv();\n        }'''
new = '''        if (mask & Config_Prepare) {\n            v.values[0].mismatch = c.lowUv != STOCK_LOW_UV;\n            v.values[1].mismatch = c.lowVminMv != STOCK_LOW_VMIN_MV;\n            v.values[2].mismatch = (int)(c.vddqUv / 1000U) != g.vddqStartMv;\n            v.values[3].mismatch = (int)c.vdd2Uv != STOCK_VDD2_UV;\n            v.values[4].mismatch = c.highUv != STOCK_HIGH_UV;\n        } else {\n            // Always compare every tunable value against the current Wizard\n            // state, not just the setting being changed on this page. This\n            // immediately exposes accidental changes in another domain.\n            v.values[0].mismatch = c.lowUv != targetLowUv();\n            v.values[1].mismatch = c.lowVminMv != targetLowVmin();\n            v.values[2].mismatch = c.vddqUv != (u32)targetVddqMv() * 1000U;\n            v.values[3].mismatch = c.vdd2Uv != (u32)targetVdd2Uv();\n            v.values[4].mismatch = c.highUv != targetHighUv();\n        }'''
s = repl(s, old, new, 'global actual-value mismatch highlighting')

old = '''    if (!g_configCheck.readOk) {\n        const int r = 5;\n        uiPrintf(r, "Could not read Horizon OC config.ini");\n        uiPrintf(r + 1, "Result : 0x%08X", g_configCheck.rc);\n        uiPrintf(r + 4, "A : Check again");\n        uiPrintf(r + 5, "B : Back");\n        uiPresent();\n        return;\n    }\n\n    const u32 m = g_configCheck.mask;'''
new = '''    if (!g_configCheck.readOk) {\n        const int r = 5;\n        uiPrintf(r, "Could not read Horizon OC config.ini");\n        uiPrintf(r + 1, "Result : 0x%08X", g_configCheck.rc);\n        uiPrintf(r + 4, "A : Check again");\n        uiPrintf(r + 5, "B : Back");\n        uiPresent();\n        return;\n    }\n\n    if (g_configPromptSafetyOnly) {\n        uiPrintf(5, "One or more active values no longer match the Wizard state.");\n        uiPrintf(7, "Restore the red values shown on the right.");\n        uiPrintf(9, "Only change the setting the Wizard currently asks you to change.");\n        uiPrintf(12, "A : Check again");\n        uiPrintf(13, "B : Back");\n        uiPresent();\n        return;\n    }\n\n    const u32 m = g_configCheck.mask;'''
s = repl(s, old, new, 'safety prompt copy')

s = repl(s,
'''void runAutomaticRegionValidation(bool forLowUv) {\n    if (g.vminValidateCount <= 0) {''',
'''void runAutomaticRegionValidation(bool forLowUv) {\n    if (!guardWizardTunableState()) return;\n    if (g.vminValidateCount <= 0) {''',
'region validation guard')

s = repl(s,
'''void runAutomaticVoltageScan(bool forLowUv) {\n    static const u32 cpuHz[6] = {''',
'''void runAutomaticVoltageScan(bool forLowUv) {\n    if (!guardWizardTunableState()) return;\n    static const u32 cpuHz[6] = {''',
'voltage scan guard')

s = repl(s,
'''void runCurrentTest() {\n    stress::Kind kind;''',
'''void runCurrentTest() {\n    if (!guardWizardTunableState()) return;\n    stress::Kind kind;''',
'built-in test guard')

old = '''        if (g_configPrompt) {\n            if ((k & HidNpadButton_Y) && (g_configCheck.mask & (Config_Prepare | Config_LowUv | Config_LowVmin))) {'''
new = '''        if (g_configPrompt) {\n            if (g_configPromptSafetyOnly) {\n                if (k & HidNpadButton_A) {\n                    if (guardWizardTunableState()) {\n                        g_configPromptSafetyOnly = false;\n                        g_configPrompt = false;\n                    }\n                    redraw = true;\n                } else if (k & HidNpadButton_B) {\n                    g_configPromptSafetyOnly = false;\n                    g_configPrompt = false;\n                    redraw = true;\n                }\n                svcSleepThread(20'000'000);\n                continue;\n            }\n            if ((k & HidNpadButton_Y) && (g_configCheck.mask & (Config_Prepare | Config_LowUv | Config_LowVmin))) {'''
s = repl(s, old, new, 'safety prompt input handling')

old = '''        if (g_rebootConfirm) {\n            if (k & HidNpadButton_A) {\n                g.pendingConfigMask = g_configCheck.mask;'''
new = '''        if (g_rebootConfirm) {\n            if (k & HidNpadButton_A) {\n                const bool safeToReboot = (g.stage == Stage::Preparation)\n                    ? verifyPersistentSettings(Config_Prepare)\n                    : guardWizardTunableState();\n                if (!safeToReboot) {\n                    g_rebootConfirm = false;\n                    if (g.stage == Stage::Preparation) g_configPrompt = true;\n                    redraw = true;\n                    svcSleepThread(20'000'000);\n                    continue;\n                }\n                g.pendingConfigMask = g_configCheck.mask;'''
s = repl(s, old, new, 'reboot final guard')

old = '''                if (cfgMask != Config_None) {\n                if (verifyPersistentSettings(cfgMask)) {\n                    if (bootSearch) g.stageReadyAfterBoot = false;\n                    g.pendingConfigMask = cfgMask;\n                    g_configCheck.mask = cfgMask;\n                    g_rebootConfirm = true;\n                    saveState();\n                } else {\n                    g_configPrompt = true;\n                }'''
new = '''                if (cfgMask != Config_None) {\n                if (verifyPersistentSettings(cfgMask) && guardWizardTunableState()) {\n                    if (bootSearch) g.stageReadyAfterBoot = false;\n                    g.pendingConfigMask = cfgMask;\n                    g_configCheck.mask = cfgMask;\n                    g_rebootConfirm = true;\n                    saveState();\n                } else {\n                    g_configPrompt = true;\n                }'''
s = repl(s, old, new, 'pre-reboot all-domain guard')

p.write_text(s)

p = Path('Makefile')
s = p.read_text()
s = repl(s, 'APP_VERSION := 0.4.0-beta.50', 'APP_VERSION := 0.4.0-beta.51', 'version bump')
p.write_text(s)

print('beta51 safety guard patch applied')
