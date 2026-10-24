from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

repls = []
repls.append((
'''        case Stage::LowUvQuick: return "CPU Low UV - Boot Search";
        case Stage::LowUvValidateQuick: return "CPU Low UV - Quick Validation";''',
'''        case Stage::LowUvQuick: return "CPU Low UV - 1 Min Search";
        case Stage::LowUvValidateQuick: return "CPU Low UV - Legacy Quick Validation";'''))

repls.append((
'''    switch (s) {
        case Stage::LowUvValidateQuick:
        case Stage::LowVminQuick:''',
'''    switch (s) {
        case Stage::LowUvQuick:
        case Stage::LowUvValidateQuick:
        case Stage::LowVminQuick:'''))

repls.append((
'''        case Stage::LowUvQuick: return "CPU Low UV - Boot Search";
        case Stage::LowUvValidateQuick: return "CPU Low UV - Quick Test";''',
'''        case Stage::LowUvQuick: return "CPU Low UV - 1 Min Search";
        case Stage::LowUvValidateQuick: return "CPU Low UV - Legacy Quick Test";'''))

repls.append((
'''        case Stage::LowUvQuick:
            g.lowUvGood = g.lowUvTest;
            if (g.lowUvTest >= LOW_UV_MAX) {
                g.stage = Stage::LowUvValidateQuick;
                g.stageReadyAfterBoot = true;
            } else {
                ++g.lowUvTest;
                g.stageReadyAfterBoot = false;
            }
            break;''',
'''        case Stage::LowUvQuick:
            // Every candidate must both boot and pass the 1-minute CPU test
            // before it becomes the new last-known-good Low UV value.
            g.lowUvGood = g.lowUvTest;
            if (g.lowUvTest >= LOW_UV_MAX) {
                g.stage = Stage::LowUvLong;
                g.stageReadyAfterBoot = true;
            } else {
                ++g.lowUvTest;
                g.stageReadyAfterBoot = false;
            }
            break;'''))

repls.append((
'''        case Stage::LowUvQuick:
            g.stage = Stage::LowUvValidateQuick;
            g.recoveryNeeded = didNotBoot;
            g.pendingConfigMask = Config_LowUv;
            break;''',
'''        case Stage::LowUvQuick:
            // Candidate failed either to boot or to pass its 1-minute test.
            // Restore the previous last-known-good value, reboot, then run
            // the 1-hour validation on that recovered value.
            g.stage = Stage::LowUvLong;
            g.recoveryNeeded = didNotBoot;
            g.pendingConfigMask = Config_LowUv;
            break;'''))

repls.append((
'''                if (g.stage == Stage::Preparation) {
                    if (g.lowUvGood >= LOW_UV_MAX) {
                        g.stage = Stage::LowUvValidateQuick;
                        g.stageReadyAfterBoot = true;
                    } else {
                        g.stage = Stage::LowUvQuick;
                        g.lowUvTest = g.lowUvGood + 1;
                        g.stageReadyAfterBoot = false;
                    }
                } else if (g.stage == Stage::LowUvQuick) {
                    handlePass();
                } else {
                    g.stageReadyAfterBoot = true;
                }''',
'''                if (g.stage == Stage::Preparation) {
                    if (g.lowUvGood >= LOW_UV_MAX) {
                        g.stage = Stage::LowUvLong;
                        g.stageReadyAfterBoot = true;
                    } else {
                        g.stage = Stage::LowUvQuick;
                        g.lowUvTest = g.lowUvGood + 1;
                        g.stageReadyAfterBoot = false;
                    }
                } else if (g.stage == Stage::LowUvQuick) {
                    // Boot success alone is not a PASS. Stay on the same
                    // candidate and require the 1-minute CPU test next.
                    g.stageReadyAfterBoot = true;
                } else {
                    g.stageReadyAfterBoot = true;
                }'''))

repls.append((
'''    if (m & Config_LowUv)
        uiPrintf(11, "2. Lower Low UV by one step.");''',
'''    if (m & Config_LowUv)
        uiPrintf(11, "2. Restore previous Low UV (one step back).");'''))

for old, new in repls:
    if old not in s:
        raise SystemExit('anchor not found:\n' + old[:160])
    s = s.replace(old, new, 1)

p.write_text(s)

mk = Path('Makefile')
ms = mk.read_text()
if 'APP_VERSION := 0.4.0-beta.26' not in ms:
    raise SystemExit('beta26 Makefile version anchor not found')
mk.write_text(ms.replace('APP_VERSION := 0.4.0-beta.26', 'APP_VERSION := 0.4.0-beta.27', 1))

u = Path('UPDATE.txt')
us = u.read_text()
us = us.replace('version=0.4.0-beta.26', 'version=0.4.0-beta.27')
us = us.replace('/v0.4.0-beta.26/', '/v0.4.0-beta.27/')
u.write_text(us)
