from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()
start = s.find('    bool riskAccepted = false;')
end = s.find('    ensureDir();', start)
if start < 0 or end < 0:
    raise SystemExit('disclaimer block not found')

block = r'''    bool riskAccepted = false;
    while (appletMainLoop() && !riskAccepted) {
        padUpdate(&pad);
        const u64 k = padGetButtonsDown(&pad);
        consoleClear();
        std::printf("\x1b[1;1H\x1b[31mHOC Undervolting Wizard - WARNING\x1b[0m\n");
        std::printf("------------------------------------------------------------\n\n");
        std::printf("\x1b[1mUSE AT YOUR OWN RISK\x1b[0m\n\n");
        std::printf("This Wizard changes CPU/RAM voltage settings and runs\n");
        std::printf("stability tests. Unstable settings can cause crashes,\n");
        std::printf("boot failures, data/save corruption or data loss.\n\n");
        std::printf("In extreme cases, hardware damage may also be possible.\n\n");
        std::printf("The author and contributors provide no warranty and accept\n");
        std::printf("no liability for data loss, software damage, hardware\n");
        std::printf("damage or any other consequences of using this Wizard.\n\n");
        std::printf("By continuing, you accept all risk and responsibility.\n\n");
        std::printf("[A] I understand - Continue\n");
        std::printf("[B] Exit\n");
        consoleUpdate(nullptr);

        if (k & HidNpadButton_A) riskAccepted = true;
        else if (k & HidNpadButton_B) {
            consoleExit(nullptr);
            return 0;
        }
        svcSleepThread(20'000'000);
    }

    if (!riskAccepted) {
        consoleExit(nullptr);
        return 0;
    }

'''
s = s[:start] + block + s[end:]
p.write_text(s)
