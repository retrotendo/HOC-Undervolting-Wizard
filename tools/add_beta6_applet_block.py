from pathlib import Path

# --- main.cpp ---
p = Path('source/main.cpp')
s = p.read_text()
old = '''    padConfigureInput(1, HidNpadStyleSet_NpadStandard);\n    PadState pad;\n    padInitializeDefault(&pad);\n\n    ensureDir();\n'''
new = '''    padConfigureInput(1, HidNpadStyleSet_NpadStandard);\n    PadState pad;\n    padInitializeDefault(&pad);\n\n    // The built-in CPU/RAM/Combined/GPU stability tests require hbmenu to be\n    // launched with full application memory. Match nx-hbmenu's own Applet Mode\n    // detection: only Application/SystemApplication are accepted.\n    const AppletType appletType = appletGetAppletType();\n    const bool fullMemoryMode =\n        appletType == AppletType_Application || appletType == AppletType_SystemApplication;\n\n    if (!fullMemoryMode) {\n        while (appletMainLoop()) {\n            padUpdate(&pad);\n            const u64 k = padGetButtonsDown(&pad);\n\n            consoleClear();\n            std::printf("\\x1b[1;1H\\x1b[31mHOC Undervolting Wizard - CANNOT START\\x1b[0m\\n");\n            std::printf("------------------------------------------------------------\\n\\n");\n            std::printf("\\x1b[1mApplet Mode detected.\\x1b[0m\\n\\n");\n            std::printf("The Wizard's stability tests require Full Memory Mode.\\n");\n            std::printf("Applet Mode is therefore not supported.\\n\\n");\n            std::printf("Start hbmenu correctly:\\n");\n            std::printf("  1. Return to the HOME Menu.\\n");\n            std::printf("  2. Highlight any installed game.\\n");\n            std::printf("  3. Hold [R] while starting the game.\\n");\n            std::printf("  4. Keep holding [R] until hbmenu opens.\\n");\n            std::printf("  5. Start HOC Undervolting Wizard again.\\n\\n");\n            std::printf("Do NOT launch hbmenu from the Album for stability testing.\\n\\n");\n            std::printf("[B] Exit\\n");\n            consoleUpdate(nullptr);\n\n            if (k & HidNpadButton_B) break;\n            svcSleepThread(20'000'000);\n        }\n\n        consoleExit(nullptr);\n        return 0;\n    }\n\n    ensureDir();\n'''
if old not in s:
    raise SystemExit('main insertion point not found')
s = s.replace(old, new, 1)
p.write_text(s)

# --- Makefile version ---
p = Path('Makefile')
s = p.read_text().replace('APP_VERSION := 0.4.0-beta.5', 'APP_VERSION := 0.4.0-beta.6', 1)
p.write_text(s)

# --- README ---
p = Path('README.md')
s = p.read_text()
marker = '# New in v0.4.0-beta.5\n'
block = '''# Full Memory Mode required\n\nThe Wizard must be launched from hbmenu in **Full Memory / Application Mode**.\n\nIf it is started in **Applet Mode** (for example through Album), the Wizard stops immediately on a dedicated warning screen. The guide and tuning state are not opened and no built-in test can be started.\n\nTo launch correctly, hold **R** while starting an installed game and keep holding **R** until hbmenu opens, then start HOC Undervolting Wizard.\n\nThis check uses the same `appletGetAppletType()` distinction as nx-hbmenu: only `Application` and `SystemApplication` modes are accepted.\n\n---\n\n# New in v0.4.0-beta.6\n\n- hard startup block when Applet Mode is detected\n- clear on-screen Full Memory Mode launch instructions\n- no Wizard state/guide/test access until launched as an Application\n- beta.5 dynamic VMIN probe and known-result shortcuts retained\n\n---\n\n# New in v0.4.0-beta.5\n'''
if marker not in s:
    raise SystemExit('README beta5 marker not found')
s = s.replace(marker, block, 1)
p.write_text(s)

# --- CHANGELOG ---
p = Path('CHANGELOG.md')
s = p.read_text()
entry = '''## v0.4.0-beta.6\n\n- Block startup completely when hbmenu launches the Wizard in Applet Mode.\n- Detect Full Memory Mode using `appletGetAppletType()`; only Application/SystemApplication are accepted.\n- Show a dedicated warning with R-button title-takeover instructions instead of opening the guide.\n- Keep beta.5 dynamic VMIN probing and known PASS/FAIL shortcuts unchanged.\n\n'''
if '## v0.4.0-beta.6' not in s:
    first = s.find('## ')
    s = s[:first] + entry + s[first:] if first >= 0 else s + '\n' + entry
p.write_text(s)

# --- beta.6 release notes ---
Path('RELEASE_NOTES_v0.4.0-beta.6.md').write_text('''# HOC Undervolting Wizard v0.4.0-beta.6\n\nThis beta adds a hard **Full Memory Mode** requirement before the Wizard is allowed to open.\n\n## Applet Mode is blocked at startup\n\nThe Wizard now checks `appletGetAppletType()` immediately after initializing input. Only `AppletType_Application` and `AppletType_SystemApplication` are accepted, matching nx-hbmenu's own distinction for Applet Mode.\n\nIf the NRO is launched through Album/Applet Mode:\n\n- the Wizard does **not** load or modify its tuning state;\n- the guide is not shown;\n- no CPU, RAM, Combined or GPU stability test can be started;\n- a dedicated warning screen explains how to relaunch hbmenu in Full Memory Mode.\n\nCorrect launch:\n\n1. Return to HOME.\n2. Highlight an installed game.\n3. Hold **R** while starting the game.\n4. Keep holding **R** until hbmenu opens.\n5. Launch HOC Undervolting Wizard.\n\n## Retained from beta.5\n\n- dynamic measurement-only Low VMIN floor probing\n- 3 HOC voltage samples spaced 1.1 seconds apart\n- requested CPU clock must actually be applied before a VMIN sample is accepted\n- automatic CPU/GPU/RAM Temporary Override checks\n- known PASS / FAIL shortcuts for previously validated values\n- 570 mV Low VMIN lower bound\n- 10 mV VDDQ search interval\n- combined RAM-rail validation\n\nThis remains a **pre-release** until validated on real Mariko / Switch OLED hardware.\n''')

# --- release workflow cloned from beta.5 with version/file substitutions ---
src = Path('.github/workflows/release-v0.4.0-beta.5.yml').read_text()
src = src.replace('v0.4.0-beta.5', 'v0.4.0-beta.6')
src = src.replace('RELEASE_NOTES_v0.4.0-beta.5.md', 'RELEASE_NOTES_v0.4.0-beta.6.md')
Path('.github/workflows/release-v0.4.0-beta.6.yml').write_text(src)
