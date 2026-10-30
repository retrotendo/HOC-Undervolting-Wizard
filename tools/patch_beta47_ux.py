from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"missing pattern: {label}")
    return text.replace(old, new, 1)

# --- source/main.cpp ---
p = Path("source/main.cpp")
s = p.read_text()

start = s.index("void renderBootPrompt() {")
end = s.index("void printSingleConfigCheck", start)
boot = r'''void renderBootPrompt() {
    int active = 0;
    const BootInference state = inferBootState(&active);

    gui::ModalView m{};
    m.version = HOC_WIZARD_VERSION;
    m.eyebrow = "BOOT CHECK";

    if (state == BootInference::RequestedActive) {
        if (g.stage == Stage::LowUvQuick)
            m.title = "Did Low UV " + std::to_string(g.lowUvTest) + " boot normally?";
        else if (g.stage == Stage::LowVminQuick)
            m.title = "Did Low VMIN " + std::to_string(g.lowVminTest) + " mV boot normally?";
        else
            m.title = "Did normal CFW boot successfully?";

        m.body = {
            "Choose Yes only if normal CFW started successfully.",
            "No freeze.",
            "No crash.",
            "No unexpected reboot or system failure."
        };
        m.primaryAction = "Yes - boot was stable";
        m.tertiaryAction = "No - boot was unstable";
        m.secondaryAction = "Exit and decide later";
        m.tone = gui::ModalTone::Cyan;
    } else if (state == BootInference::SaferActive) {
        if (g_bootRecoveryCandidate < 0) g_bootRecoveryCandidate = active;

        if (g.stage == Stage::LowUvQuick) {
            m.title = "Low UV " + std::to_string(g.lowUvTest) + " did not boot";
            m.body = {
                "The console is currently running a safer value.",
                "Last known good value: Low UV " + std::to_string(g_bootRecoveryCandidate) + ".",
                "Use the last good value, or choose one safer value."
            };
        } else if (g.stage == Stage::LowVminQuick) {
            m.title = "Low VMIN " + std::to_string(g.lowVminTest) + " mV did not boot";
            m.body = {
                "The console is currently running a safer value.",
                "Last known good value: Low VMIN " + std::to_string(g_bootRecoveryCandidate) + " mV.",
                "Use the last good value, or choose one safer value."
            };
        } else {
            m.title = "The requested setting did not boot";
            m.body = {"The console is currently running a safer value."};
        }
        m.primaryAction = "Use last good value";
        m.tertiaryAction = "Try one safer value";
        m.secondaryAction = "Exit and decide later";
        m.tone = gui::ModalTone::Amber;
    } else {
        m.title = "Active value could not be confirmed";
        m.body = {
            "The Wizard could not verify the requested value in the running Horizon OC configuration.",
            "Check Horizon OC or the recovery state, then try again.",
            "If the boot was not stable, choose No to recover to the safer value."
        };
        m.primaryAction = "Check again";
        m.tertiaryAction = "No - treat as unstable";
        m.secondaryAction = "Exit and decide later";
        m.tone = gui::ModalTone::Red;
    }

    gui::presentModal(m);
}

'''
s = s[:start] + boot + s[end:]

startup_start = s.index("    ensureDir();\n\n    // The disclaimer is a one-time acknowledgement")
startup_end = s.index("    // Identify Mariko DRAM", startup_start)
startup = r'''    ensureDir();

    // Load Wizard progress before deciding whether the safety notice is needed.
    // Existing tuning runs must never be interrupted by a newly introduced
    // disclaimer, but a deliberate Wizard reset starts a fresh run and clears
    // the acknowledgement below.
    migrateLegacyState();
    const bool hadStateBeforeLoad = access(STATE, F_OK) == 0;
    if (!loadState()) saveState();

    const bool tuningAlreadyStarted =
        g.stage != Stage::HardwareDetection && g.stage != Stage::Preparation;
    bool riskAccepted = access(DISCLAIMER_ACK, F_OK) == 0;

    // Upgrade compatibility: an older installation already beyond Baseline has
    // necessarily been using the Wizard. Mark it accepted silently so a reboot
    // during tuning never inserts the disclaimer into the active workflow.
    if (!riskAccepted && hadStateBeforeLoad && tuningAlreadyStarted) {
        std::ofstream ack(DISCLAIMER_ACK, std::ios::trunc);
        if (ack) {
            ack << "accepted=1\n";
            ack.flush();
            ack.close();
            fsdevCommitDevice("sdmc");
            riskAccepted = true;
        }
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
s = s[:startup_start] + startup + s[startup_end:]

s = replace_once(
    s,
    """                resetState();\n                detectRamHardware();\n                g_resetConfirm = false;""",
    """                resetState();\n                // A reset starts a new tuning run. Show the safety notice again\n                // on the next app start while the Wizard is back at Baseline.\n                unlink(DISCLAIMER_ACK);\n                fsdevCommitDevice(\"sdmc\");\n                detectRamHardware();\n                g_resetConfirm = false;""",
    "reset disclaimer acknowledgement"
)

p.write_text(s)

# --- source/gui_console.hpp ---
p = Path("source/gui_console.hpp")
s = p.read_text()
s = replace_once(
    s,
    """    std::string primaryAction;\n    std::string secondaryAction;""",
    """    std::string primaryAction;\n    std::string tertiaryAction;  // X button, optional\n    std::string secondaryAction; // B button, optional""",
    "modal third action"
)
p.write_text(s)

# --- source/gui_console.cpp ---
p = Path("source/gui_console.cpp")
s = p.read_text()
old = r'''    if (!m.primaryAction.empty()) {
        const int by = y + h - 78;
        if (!m.secondaryAction.empty()) {
            drawActionButton(x + 38, by, 445, 48, "A : " + m.primaryAction);
            drawActionButton(x + 507, by, 445, 48, "B : " + m.secondaryAction);
        } else {
            drawActionButton(x + 38, by, w - 76, 48, "A : " + m.primaryAction);
        }
    }
'''
new = r'''    if (!m.primaryAction.empty()) {
        const int by = y + h - 78;
        if (!m.tertiaryAction.empty()) {
            // Decision modal: one clear Yes / No / Exit row.
            drawActionButton(x + 38,  by, 296, 48, "A : " + m.primaryAction);
            drawActionButton(x + 347, by, 296, 48, "X : " + m.tertiaryAction);
            if (!m.secondaryAction.empty())
                drawActionButton(x + 656, by, 296, 48, "B : " + m.secondaryAction);
        } else if (!m.secondaryAction.empty()) {
            drawActionButton(x + 38, by, 445, 48, "A : " + m.primaryAction);
            drawActionButton(x + 507, by, 445, 48, "B : " + m.secondaryAction);
        } else {
            drawActionButton(x + 38, by, w - 76, 48, "A : " + m.primaryAction);
        }
    }
'''
s = replace_once(s, old, new, "modal action layout")
p.write_text(s)
