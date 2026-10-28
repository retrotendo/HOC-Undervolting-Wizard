from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

old = '''            if ((k & HidNpadButton_Y) && (g_configCheck.mask & (Config_Prepare | Config_LowUv | Config_LowVmin))) {
                g_autoSetMask = g_configCheck.mask;
                g_autoPrepError.clear();
                g_autoPrepConfirm = true;
                redraw = true;
'''
new = '''            if ((k & HidNpadButton_Y) && (g_configCheck.mask & (Config_Prepare | Config_LowUv | Config_LowVmin))) {
                g_autoSetMask = g_configCheck.mask;
                g_autoPrepError.clear();
                g_configPrompt = false;
                g_autoPrepConfirm = true;
                redraw = true;
'''
if old not in s:
    raise SystemExit('Y-button config prompt block not found')
s = s.replace(old, new, 1)

old = '''            } else if (k & HidNpadButton_B) {
                g_autoPrepConfirm = false;
                g_autoPrepError.clear();
                redraw = true;
            }
            svcSleepThread(20'000'000);
            continue;
        }

        if (g_rebootConfirm) {
'''
new = '''            } else if (k & HidNpadButton_B) {
                g_autoPrepConfirm = false;
                g_autoPrepError.clear();
                g_configPrompt = true;
                redraw = true;
            }
            svcSleepThread(20'000'000);
            continue;
        }

        if (g_rebootConfirm) {
'''
if old not in s:
    raise SystemExit('Auto-set cancel block not found')
s = s.replace(old, new, 1)

p.write_text(s)
print('beta31 Y-button flow fixed')
# trigger
