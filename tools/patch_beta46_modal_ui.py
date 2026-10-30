from pathlib import Path

# --- gui_console.hpp -------------------------------------------------------
p = Path('source/gui_console.hpp')
s = p.read_text()
s = s.replace('#include <string>\n', '#include <string>\n#include <vector>\n', 1)
anchor = '''struct StressView {\n'''
modal = '''enum class ModalTone { Cyan, Green, Amber, Red };\n\nstruct ModalView {\n    std::string version;\n    std::string eyebrow;\n    std::string title;\n    std::vector<std::string> body;\n    std::string primaryAction;\n    std::string secondaryAction;\n    ModalTone tone = ModalTone::Cyan;\n};\n\nstruct StressView {\n'''
if anchor not in s:
    raise SystemExit('gui header struct anchor missing')
s = s.replace(anchor, modal, 1)
anchor = '''// Dedicated graphical progress page used while built-in stress tests are running.\nvoid presentStress(const StressView& view);\n'''
new = '''// Full-width modal used for startup/update/disclaimer/reboot/error states.\nvoid presentModal(const ModalView& view);\n\n// Dedicated graphical progress page used while built-in stress tests are running.\nvoid presentStress(const StressView& view);\n'''
if anchor not in s:
    raise SystemExit('gui header api anchor missing')
s = s.replace(anchor, new, 1)
p.write_text(s)

# --- gui_console.cpp -------------------------------------------------------
p = Path('source/gui_console.cpp')
s = p.read_text()
anchor = '''void drawStressFrame(const StressView& s) {\n'''
insert = r'''u32 modalToneColor(ModalTone tone) {
    switch (tone) {
        case ModalTone::Green: return C_GREEN;
        case ModalTone::Amber: return C_AMBER;
        case ModalTone::Red: return C_RED;
        case ModalTone::Cyan:
        default: return C_CYAN;
    }
}

int drawWrappedText(int x, int y, int size, u32 color, const std::string& text,
                    int maxWidth, int lineHeight, int maxLines = 4) {
    if (text.empty()) return y;
    std::string line;
    std::string word;
    int lines = 0;
    auto flushWord = [&]() {
        if (word.empty()) return;
        const std::string candidate = line.empty() ? word : line + " " + word;
        if (!line.empty() && textWidth(candidate, size) > maxWidth) {
            drawText(x, y, size, color, line);
            y += lineHeight;
            ++lines;
            line = word;
        } else {
            line = candidate;
        }
        word.clear();
    };
    for (size_t i = 0; i <= text.size(); ++i) {
        const char c = i < text.size() ? text[i] : ' ';
        if (c == ' ' || c == '\n' || i == text.size()) {
            flushWord();
            if (c == '\n' && !line.empty() && lines < maxLines) {
                drawText(x, y, size, color, line);
                y += lineHeight;
                ++lines;
                line.clear();
            }
            if (lines >= maxLines) break;
        } else {
            word.push_back(c);
        }
    }
    if (!line.empty() && lines < maxLines) {
        drawText(x, y, size, color, fitText(line, size, maxWidth));
        y += lineHeight;
    }
    return y;
}

void drawModalFrame(const ModalView& m) {
    beginFrame();
    if (!g_pixels) return;

    // Same visual language as the Wizard, but without the two right-side cards.
    drawText(42, 24, 24, C_TEXT, "Horizon");
    drawText(134, 24, 24, C_CYAN, "OC");
    drawText(177, 24, 24, C_MUTED, "/");
    drawText(198, 24, 24, C_TEXT, "Undervolting Wizard");
    roundedRect(1085, 20, 150, 34, 17, C_PANEL_2);
    drawTextRight(1218, 26, 15, C_MUTED, "v" + m.version);
    fillRect(40, 70, 1200, 1, C_BORDER);

    // Quiet/dimmed guide backdrop behind the modal.
    roundedRect(40, 103, 1200, 557, 22, mix(C_BG, C_PANEL, 50));
    fillRect(72, 126, 1136, 2, mix(C_BG, C_BORDER, 65));
    for (int i = 0; i < 7; ++i) {
        const int x = 72 + 1136 * i / 6;
        fillCircle(x, 127, 5, mix(C_BG, C_BORDER, 70));
    }

    const int x = 145, y = 120, w = 990, h = 515;
    const u32 accent = modalToneColor(m.tone);
    roundedBorder(x, y, w, h, 22, mix(C_BORDER, accent, 52), C_PANEL, 2);
    drawText(x + 38, y + 28, 15, accent, m.eyebrow.empty() ? "HOC UNDERVOLTING WIZARD" : m.eyebrow);
    drawText(x + 38, y + 61, 34, C_TEXT, fitText(m.title, 34, w - 76));
    fillRect(x + 38, y + 111, w - 76, 1, C_BORDER);

    int yy = y + 136;
    for (const std::string& paragraph : m.body) {
        if (paragraph.empty()) { yy += 12; continue; }
        const bool warning = paragraph.rfind("If normal CFW", 0) == 0 ||
                             paragraph.rfind("Important:", 0) == 0;
        yy = drawWrappedText(x + 38, yy, 19, warning ? accent : C_TEXT, paragraph,
                             w - 76, 27, 3);
        yy += 8;
        if (yy > y + h - 135) break;
    }

    if (!m.primaryAction.empty()) {
        const int by = y + h - 78;
        if (!m.secondaryAction.empty()) {
            drawActionButton(x + 38, by, 445, 48, "A : " + m.primaryAction);
            drawActionButton(x + 507, by, 445, 48, "B : " + m.secondaryAction);
        } else {
            drawActionButton(x + 38, by, w - 76, 48, "A : " + m.primaryAction);
        }
    }

    endFrame();
}

void drawStressFrame(const StressView& s) {
'''
if anchor not in s:
    raise SystemExit('gui cpp stress anchor missing')
s = s.replace(anchor, insert, 1)
anchor = '''void presentStress(const StressView& view) {\n    if (!g_initialized) return;\n    drawStressFrame(view);\n}\n'''
new = '''void presentModal(const ModalView& view) {\n    if (!g_initialized) return;\n    drawModalFrame(view);\n}\n\nvoid presentStress(const StressView& view) {\n    if (!g_initialized) return;\n    drawStressFrame(view);\n}\n'''
if anchor not in s:
    raise SystemExit('gui cpp public api anchor missing')
s = s.replace(anchor, new, 1)
p.write_text(s)

# --- updater.cpp -----------------------------------------------------------
p = Path('source/updater.cpp')
s = p.read_text()
if '#include "gui_console.hpp"' not in s:
    s = s.replace('#include "updater.hpp"\n', '#include "updater.hpp"\n#include "gui_console.hpp"\n', 1)

repls = {
'''void drawChecking() {\n    consoleClear();''': '''void drawChecking() {\n    if (gui::isInitialized()) {\n        gui::ModalView m{};\n        m.version = HOC_WIZARD_VERSION;\n        m.eyebrow = "UPDATE";\n        m.title = "Checking for updates";\n        m.body = {"Installed version: " HOC_WIZARD_VERSION, "Checking the latest Wizard release..."};\n        m.tone = gui::ModalTone::Cyan;\n        gui::presentModal(m);\n        return;\n    }\n    consoleClear();''',
'''void drawUpdatePrompt(const ReleaseInfo& release) {\n    consoleClear();''': '''void drawUpdatePrompt(const ReleaseInfo& release) {\n    if (gui::isInitialized()) {\n        gui::ModalView m{};\n        m.version = HOC_WIZARD_VERSION;\n        m.eyebrow = "UPDATE AVAILABLE";\n        m.title = "A newer build is available";\n        m.body = {"Installed: " + std::string(HOC_WIZARD_VERSION), "Available: " + release.version, "The downloaded NRO is verified with SHA256 before the current file is replaced."};\n        m.primaryAction = "Download & install";\n        m.secondaryAction = "Not now";\n        m.tone = gui::ModalTone::Green;\n        gui::presentModal(m);\n        return;\n    }\n    consoleClear();''',
'''void drawInstalling(const ReleaseInfo& release) {\n    consoleClear();''': '''void drawInstalling(const ReleaseInfo& release) {\n    if (gui::isInitialized()) {\n        gui::ModalView m{};\n        m.version = HOC_WIZARD_VERSION;\n        m.eyebrow = "INSTALLING UPDATE";\n        m.title = "Downloading " + release.version;\n        m.body = {"The existing NRO is kept until the new file has passed SHA256 verification.", "Do not close the application while the update is being installed."};\n        m.tone = gui::ModalTone::Cyan;\n        gui::presentModal(m);\n        return;\n    }\n    consoleClear();''',
'''void drawCheckFailed(const std::string& error) {\n    consoleClear();''': '''void drawCheckFailed(const std::string& error) {\n    if (gui::isInitialized()) {\n        gui::ModalView m{};\n        m.version = HOC_WIZARD_VERSION;\n        m.eyebrow = "UPDATE CHECK FAILED";\n        m.title = "Could not check for updates";\n        m.body = {error, "You can retry or continue with the currently installed version."};\n        m.primaryAction = "Retry";\n        m.secondaryAction = "Continue current version";\n        m.tone = gui::ModalTone::Red;\n        gui::presentModal(m);\n        return;\n    }\n    consoleClear();''',
'''void drawInstallFailed(const std::string& error) {\n    consoleClear();''': '''void drawInstallFailed(const std::string& error) {\n    if (gui::isInitialized()) {\n        gui::ModalView m{};\n        m.version = HOC_WIZARD_VERSION;\n        m.eyebrow = "UPDATE FAILED";\n        m.title = "The update could not be installed";\n        m.body = {error, "The current NRO was preserved."};\n        m.primaryAction = "Retry";\n        m.secondaryAction = "Continue current version";\n        m.tone = gui::ModalTone::Red;\n        gui::presentModal(m);\n        return;\n    }\n    consoleClear();''',
'''void drawInstalled(const ReleaseInfo& release) {\n    consoleClear();''': '''void drawInstalled(const ReleaseInfo& release) {\n    if (gui::isInitialized()) {\n        gui::ModalView m{};\n        m.version = HOC_WIZARD_VERSION;\n        m.eyebrow = "UPDATE INSTALLED";\n        m.title = release.version + " is ready";\n        m.body = {"The previous NRO was kept as .bak.", "The running copy is still the old version in memory.", "Exit now and launch HOC Undervolting Wizard again."};\n        m.primaryAction = "Exit";\n        m.secondaryAction = "Exit";\n        m.tone = gui::ModalTone::Green;\n        gui::presentModal(m);\n        return;\n    }\n    consoleClear();'''
}
for old, new in repls.items():
    if old not in s:
        raise SystemExit('updater draw anchor missing: ' + old.split('{')[0].strip())
    s = s.replace(old, new, 1)
p.write_text(s)

# --- main.cpp --------------------------------------------------------------
p = Path('source/main.cpp')
s = p.read_text()
s = s.replace('constexpr const char* RESULTS   = "sdmc:/switch/HOC-Undervolting-Wizard/results.txt";\n',
              'constexpr const char* RESULTS   = "sdmc:/switch/HOC-Undervolting-Wizard/results.txt";\nconstexpr const char* DISCLAIMER_ACK = "sdmc:/switch/HOC-Undervolting-Wizard/disclaimer.accepted";\n', 1)

# Add the reboot modal before render().
anchor = '''void render() {\n'''
reboot = r'''std::string rebootSavedValueText() {
    const u32 mask = g_configCheck.mask;
    if (mask & Config_Prepare) return "Preparation values were saved successfully.";
    if (mask & Config_LowUv) return "Low UV " + std::to_string(targetLowUv()) + " was saved successfully.";
    if (mask & Config_LowVmin) return "Low VMIN " + std::to_string(targetLowVmin()) + " mV was saved successfully.";
    if ((mask & Config_Vddq) && (mask & Config_Vdd2)) return "VDDQ and VDD2 were saved successfully.";
    if (mask & Config_Vddq) return "VDDQ " + std::to_string(targetVddqMv()) + " mV was saved successfully.";
    if (mask & Config_Vdd2) return "VDD2 " + formatVdd2(targetVdd2Uv()) + " was saved successfully.";
    if (mask & Config_HighUv) return "High UV " + std::to_string(targetHighUv()) + " was saved successfully.";
    return "The requested value was saved successfully.";
}

void renderRebootModal() {
    gui::ModalView m{};
    m.version = HOC_WIZARD_VERSION;
    m.eyebrow = "REBOOT REQUIRED";
    m.title = "Apply the new setting";
    m.body = {
        rebootSavedValueText(),
        "A reboot is required to apply this setting.",
        "After normal CFW has booted, open HOC Undervolting Wizard again to continue.",
        "If normal CFW does not boot, freezes or crashes:",
        "Boot CFW No OC, restore the previous known-good value, reboot normal CFW and open the Wizard again."
    };
    m.primaryAction = "Reboot now";
    m.secondaryAction = "Back";
    m.tone = gui::ModalTone::Amber;
    gui::presentModal(m);
}

void render() {
'''
if anchor not in s:
    raise SystemExit('main render anchor missing')
s = s.replace(anchor, reboot, 1)
s = s.replace('if (g_rebootConfirm) { renderRebootConfirm(); return; }',
              'if (g_rebootConfirm) { renderRebootModal(); return; }', 1)

# Replace the full startup block: initialize GUI before updater and make disclaimer persistent.
start = s.find('    if (updater::startupCheckAndPrompt(pad, argc, argv)) {')
end_marker = '    ensureDir();\n    migrateLegacyState();\n'
end = s.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit('main startup block anchors missing')
end += len('    ensureDir();\n')
new_startup = r'''    // Full-memory mode can use the graphical backend for every startup screen.
    consoleExit(nullptr);
    if (!gui::init()) {
        consoleInit(nullptr);
        while (appletMainLoop()) {
            padUpdate(&pad);
            consoleClear();
            std::printf("\x1b[1;1H\x1b[31mHOC Undervolting Wizard - GUI ERROR\x1b[0m\n");
            std::printf("------------------------------------------------------------\n\n");
            std::printf("Could not initialize the graphical interface.\n");
            std::printf("The Switch shared font / framebuffer backend is unavailable.\n\n");
            std::printf("[B] Exit\n");
            consoleUpdate(nullptr);
            if (padGetButtonsDown(&pad) & HidNpadButton_B) break;
            svcSleepThread(20'000'000);
        }
        consoleExit(nullptr);
        return 0;
    }

    if (updater::startupCheckAndPrompt(pad, argc, argv)) {
        gui::shutdown();
        return 0;
    }

    ensureDir();

    // The disclaimer is a one-time acknowledgement, independent of Wizard reset.
    // Existing installations with a state file have necessarily already passed it.
    bool riskAccepted = access(DISCLAIMER_ACK, F_OK) == 0 || access(STATE, F_OK) == 0;
    if (riskAccepted && access(DISCLAIMER_ACK, F_OK) != 0) {
        std::ofstream ack(DISCLAIMER_ACK, std::ios::trunc);
        if (ack) { ack << "accepted=1\n"; ack.close(); fsdevCommitDevice("sdmc"); }
    }

    while (appletMainLoop() && !riskAccepted) {
        padUpdate(&pad);
        const u64 k = padGetButtonsDown(&pad);

        gui::ModalView m{};
        m.version = HOC_WIZARD_VERSION;
        m.eyebrow = "SAFETY NOTICE";
        m.title = "Use at your own risk";
        m.body = {
            "This Wizard changes CPU and RAM voltage settings and runs stability tests.",
            "Unstable settings can cause crashes, boot failures, save/data corruption or data loss.",
            "In extreme cases, hardware damage may also be possible.",
            "The author and contributors provide no warranty and accept no liability for resulting software, data or hardware damage.",
            "By continuing, you accept all risk and responsibility."
        };
        m.primaryAction = "I understand - continue";
        m.secondaryAction = "Exit";
        m.tone = gui::ModalTone::Amber;
        gui::presentModal(m);

        if (k & HidNpadButton_A) {
            std::ofstream ack(DISCLAIMER_ACK, std::ios::trunc);
            if (ack) {
                ack << "accepted=1\n";
                ack.flush();
                ack.close();
                fsdevCommitDevice("sdmc");
                riskAccepted = true;
            }
        } else if (k & HidNpadButton_B) {
            gui::shutdown();
            return 0;
        }
        svcSleepThread(20'000'000);
    }

    if (!riskAccepted) {
        gui::shutdown();
        return 0;
    }

'''
s = s[:start] + new_startup + s[end:]

# The old startup block contained a second consoleExit/gui::init section; assert it is gone.
if 'bool riskAccepted = false;' in s:
    raise SystemExit('old disclaimer block still present')

p.write_text(s)

# --- Makefile --------------------------------------------------------------
p = Path('Makefile')
s = p.read_text()
old = 'APP_VERSION := 0.4.0-beta.45\n'
if old not in s:
    raise SystemExit('version anchor missing')
s = s.replace(old, 'APP_VERSION := 0.4.0-beta.46\n', 1)
p.write_text(s)
