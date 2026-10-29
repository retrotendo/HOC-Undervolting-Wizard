from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

old = '''        } else if ((k & HidNpadButton_Y) && g.stage != Stage::Preparation) {
            const u32 cfgMask = activeConfigMask();'''
new = '''        } else if (g.limitNoticePending) {
            // A limit page is informational/confirmational only. Do not let
            // Y / + / X fall through into normal search actions.
            if (k & HidNpadButton_A) {
                confirmWizardLimitAndContinue();
                redraw = true;
            }
        } else if ((k & HidNpadButton_Y) && g.stage != Stage::Preparation) {
            const u32 cfgMask = activeConfigMask();'''
if old not in s:
    raise SystemExit('input gate insertion point not found')
s = s.replace(old, new, 1)

old_late = '''        } else if (g.limitNoticePending) {
            if (k & HidNpadButton_A) {
                confirmWizardLimitAndContinue();
                redraw = true;
            }
        } else if (k & HidNpadButton_A) {'''
new_late = '''        } else if (k & HidNpadButton_A) {'''
if old_late not in s:
    raise SystemExit('late limit input gate not found')
s = s.replace(old_late, new_late, 1)

p.write_text(s)
