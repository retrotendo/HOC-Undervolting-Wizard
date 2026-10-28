from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

def rep(old, new, label):
    global s
    if old not in s:
        raise SystemExit(f'{label} not found')
    s = s.replace(old, new, 1)

# If a Boot Search candidate is being checked, never let stageReadyAfterBoot
# suppress the config mask. A successful check of a new candidate must always
# lead into the reboot-confirm flow before it can be judged boot-stable.
rep('''            } else if (k & HidNpadButton_A) {\n                const u32 mask = activeConfigMask();\n                if (verifyPersistentSettings(mask)) {\n                    g_configPrompt = false;\n                    g_rebootConfirm = true;\n                }\n                redraw = true;\n''', '''            } else if (k & HidNpadButton_A) {\n                u32 mask = g_configCheck.mask;\n                if (g.stage == Stage::LowUvQuick || g.stage == Stage::LowVminQuick)\n                    mask = defaultConfigMaskForStage(g.stage);\n                if (verifyPersistentSettings(mask)) {\n                    g.stageReadyAfterBoot = false;\n                    g.pendingConfigMask = mask;\n                    g_configCheck.mask = mask;\n                    g_configPrompt = false;\n                    g_rebootConfirm = true;\n                    saveState();\n                }\n                redraw = true;\n''', 'config prompt A reboot enforcement')

rep('''        } else if (k & HidNpadButton_A) {\n            const u32 cfgMask = activeConfigMask();\n            if (cfgMask != Config_None) {\n                if (verifyPersistentSettings(cfgMask)) g_rebootConfirm = true;\n                else g_configPrompt = true;\n''', '''        } else if (k & HidNpadButton_A) {\n            const bool bootSearch = g.stage == Stage::LowUvQuick || g.stage == Stage::LowVminQuick;\n            const u32 cfgMask = bootSearch ? defaultConfigMaskForStage(g.stage) : activeConfigMask();\n            if (cfgMask != Config_None) {\n                if (verifyPersistentSettings(cfgMask)) {\n                    if (bootSearch) g.stageReadyAfterBoot = false;\n                    g.pendingConfigMask = cfgMask;\n                    g_configCheck.mask = cfgMask;\n                    g_rebootConfirm = true;\n                    saveState();\n                } else {\n                    g_configPrompt = true;\n                }\n''', 'main A reboot enforcement')

# Same guarantee after automatic Low UV/Low VMIN set.
rep('''                if (applyAutomaticCurrentSetting(g_autoSetMask)) {\n                    g_autoPrepConfirm = false;\n                    g_configPrompt = false;\n                    g_configCheck.mask = g_autoSetMask;\n                    g_rebootConfirm = true;\n                }\n''', '''                if (applyAutomaticCurrentSetting(g_autoSetMask)) {\n                    if (g_autoSetMask & (Config_LowUv | Config_LowVmin))\n                        g.stageReadyAfterBoot = false;\n                    g.pendingConfigMask = g_autoSetMask;\n                    g_autoPrepConfirm = false;\n                    g_configPrompt = false;\n                    g_configCheck.mask = g_autoSetMask;\n                    g_rebootConfirm = true;\n                    saveState();\n                }\n''', 'automatic set reboot enforcement')

p.write_text(s)
print('beta36 reboot enforcement applied')
