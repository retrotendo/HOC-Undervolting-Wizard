from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()
old = '''            } else if (k & HidNpadButton_X) {
                g.rebootPending = false;
                g_bootPrompt = false;
                handleFail(true);
                redraw = true;
            } else if (k & HidNpadButton_B) {'''
new = '''            } else if (k & HidNpadButton_X) {
                const bool lowUvCandidateNoBoot = (g.stage == Stage::LowUvQuick);
                g.rebootPending = false;
                g_bootPrompt = false;
                handleFail(true);

                // After a Low UV no-boot, the documented recovery path is:
                // Hekate CFW No OC -> restore previous Low UV -> normal CFW ->
                // reopen Wizard. If that last-known-good value is already active,
                // do not demand another redundant reboot before the 1-hour test.
                if (lowUvCandidateNoBoot && verifyPersistentSettings(Config_LowUv)) {
                    g.pendingConfigMask = Config_None;
                    g.stageReadyAfterBoot = true;
                    saveState();
                }
                redraw = true;
            } else if (k & HidNpadButton_B) {'''
if old not in s:
    raise SystemExit('boot NO handler anchor not found')
p.write_text(s.replace(old, new, 1))
