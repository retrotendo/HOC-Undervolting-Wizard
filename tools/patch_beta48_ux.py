from pathlib import Path


def rep(text, old, new, label):
    if old not in text:
        raise SystemExit(f"missing pattern: {label}")
    return text.replace(old, new, 1)

# --- gui_console.hpp ---
p = Path('source/gui_console.hpp')
s = p.read_text()
s = rep(s,
'''    bool preparationLayout = false;\n    bool havePreparationActiveValues = false;\n''',
'''    bool preparationLayout = false;\n    bool hideValuesCard = false;\n    bool havePreparationActiveValues = false;\n''', 'view hide values')
p.write_text(s)

# --- gui_console.cpp ---
p = Path('source/gui_console.cpp')
s = p.read_text()
s = rep(s,
'''void drawInstructionCard() {\n    const int x = 835, y = 158, w = 405, h = 205;\n    drawCard(x, y, w, h, true);\n    drawLabel(x + 24, y + 20, "CURRENT INSTRUCTION");\n''',
'''void drawInstructionCard() {\n    const int x = 835, y = 158, w = 405, h = 205;\n    drawCard(x, y, w, h, true);\n    drawLabel(x + 24, y + 20, "YOUR TASK");\n''', 'instruction eyebrow')

s = rep(s,
'''    drawCard(x, y, w, h, true);\n    drawLabel(x + 24, y + 20, "CURRENT INSTRUCTION");\n    drawText(x + 24, y + 48, 27, C_TEXT, "Preparation");\n\n    const int setRight = x + 393;\n    const int activeRight = x + w - 24;\n    drawTextRight(setRight, y + 80, 13, C_MUTED, "SET");\n    drawTextRight(activeRight, y + 80, 13, C_MUTED, "ACTIVE");\n    fillRect(x + 24, y + 105, w - 48, 1, C_BORDER);\n\n    int yy = y + 119;\n''',
'''    drawCard(x, y, w, h, true);\n    drawLabel(x + 24, y + 20, "YOUR TASK");\n    drawText(x + 24, y + 48, 25, C_TEXT, "Set the Preparation values");\n    drawText(x + 24, y + 80, 14, C_MUTED, "Open Horizon OC / HOC Toolkit and match SET.");\n\n    const int setRight = x + 393;\n    const int activeRight = x + w - 24;\n    drawTextRight(setRight, y + 107, 13, C_MUTED, "SET");\n    drawTextRight(activeRight, y + 107, 13, C_MUTED, "ACTIVE");\n    fillRect(x + 24, y + 130, w - 48, 1, C_BORDER);\n\n    int yy = y + 143;\n''', 'preparation task card')

# Forward declare wrapper before main card.
s = rep(s,
'''void drawMainCard() {\n''',
'''int drawWrappedText(int x, int y, int size, u32 color, const std::string& text,\n                    int maxWidth, int lineHeight, int maxLines);\n\nvoid drawMainCard() {\n''', 'wrap forward declaration')

old_block = '''    if (g_view.preparationLayout) {\n        drawText(x + 28, y + 120, 18, C_TEXT,\n                 g_view.stageTitle.find("not ready") != std::string::npos\n                    ? "Some Preparation values do not match yet."\n                    : "Set the Preparation values shown on the right.");\n        drawText(x + 28, y + 151, 16, C_MUTED, "SET = required value");\n        drawText(x + 28, y + 178, 16, C_MUTED, "ACTIVE = value currently reported by Horizon OC");\n        drawText(x + 28, y + 205, 16, C_RED, "Red ACTIVE values still need attention.");\n    } else {\n        const int bodyMax = actions.empty() ? 15 : (actions.size() >= 5 ? 7 : 10);\n        const int bodySize = body.size() > size_t(bodyMax) ? 16 : 18;\n        const int bodyStep = bodySize + 7;\n        int by = y + 116;\n        int shown = 0;\n        for (const std::string& raw : body) {\n            if (shown >= bodyMax) break;\n            const bool heading = raw == "Objective:" || raw == "Test:" || raw == "Keys:" ||\n                                 raw == "Required test clocks:" || raw == "Current Temporary Overrides:" ||\n                                 raw == "Final values:" || raw == "Temporary Overrides:";\n            drawText(x + 28, by, heading ? 15 : bodySize, heading ? C_CYAN : C_TEXT,\n                     fitText(raw, heading ? 15 : bodySize, w - 56));\n            by += heading ? 24 : bodyStep;\n            ++shown;\n        }\n        if (shown < int(body.size())) drawText(x + 28, by, 15, C_MUTED, "More details continue in this step...");\n    }\n'''
new_block = '''    if (g_view.preparationLayout) {\n        int by = y + 120;\n        if (g_view.stageTitle.find("not ready") != std::string::npos) {\n            by = drawWrappedText(x + 28, by, 18, C_TEXT,\n                "Some required Preparation values still do not match.", w - 56, 27, 2);\n            by += 12;\n            drawWrappedText(x + 28, by, 17, C_MUTED,\n                "Correct the red ACTIVE values shown on the right, then check again.", w - 56, 25, 3);\n        } else {\n            by = drawWrappedText(x + 28, by, 18, C_TEXT,\n                "Before tuning starts, the Wizard needs a known baseline.", w - 56, 27, 3);\n            by += 12;\n            drawWrappedText(x + 28, by, 17, C_MUTED,\n                "You can set the recommended values manually, use your current settings as the baseline, or let the Wizard apply the recommended values automatically.",\n                w - 56, 25, 5);\n        }\n    } else {\n        const int bodyMax = actions.empty() ? 15 : (actions.size() >= 5 ? 8 : 11);\n        int by = y + 116;\n        int shown = 0;\n        for (const std::string& raw : body) {\n            if (shown >= bodyMax || by > y + h - 190) break;\n            const bool heading = raw == "Objective:" || raw == "Test:" || raw == "Keys:" ||\n                                 raw == "Required test clocks:" || raw == "Current Temporary Overrides:" ||\n                                 raw == "Final values:" || raw == "Temporary Overrides:";\n            if (heading) {\n                drawText(x + 28, by, 15, C_CYAN, raw);\n                by += 26;\n                ++shown;\n                continue;\n            }\n\n            const size_t colon = raw.find(':');\n            const bool valueRow = colon != std::string::npos && colon > 0 && colon < raw.size() - 1 &&\n                                  raw.find("http") != 0;\n            if (valueRow) {\n                const std::string label = trim(raw.substr(0, colon));\n                const std::string value = trim(raw.substr(colon + 1));\n                if (shown) fillRect(x + 28, by - 7, w - 56, 1, mix(C_PANEL, C_BORDER, 65));\n                drawText(x + 28, by, 16, C_MUTED, fitText(label, 16, (w - 70) / 2));\n                drawTextRight(x + w - 28, by, 17, C_TEXT, fitText(value, 17, (w - 70) / 2));\n                by += 31;\n            } else {\n                by = drawWrappedText(x + 28, by, 17, C_TEXT, raw, w - 56, 25, 3);\n                by += 5;\n            }\n            ++shown;\n        }\n        if (shown < int(body.size()) && by < y + h - 175)\n            drawText(x + 28, by, 15, C_MUTED, "More details continue in this step...");\n    }\n'''
s = rep(s, old_block, new_block, 'main card typography')

s = rep(s,
'''    if (g_view.preparationLayout) {\n        drawPreparationCard();\n    } else {\n        drawInstructionCard();\n        drawValuesCard();\n    }\n''',
'''    if (g_view.preparationLayout) {\n        drawPreparationCard();\n    } else {\n        drawInstructionCard();\n        if (!g_view.hideValuesCard) drawValuesCard();\n    }\n''', 'hide values card')
p.write_text(s)

# --- main.cpp ---
p = Path('source/main.cpp')
s = p.read_text()

for old in [
    'case Stage::LowVminLong: return "CPU Low VMIN - Floor Sweep @ 510";',
    'case Stage::LowVminSweep612: return "CPU Low VMIN - Floor Sweep @ 612";',
    'case Stage::LowVminSweep714: return "CPU Low VMIN - Floor Sweep @ 714";',
    'case Stage::LowVminValidate816: return "CPU Low VMIN - Floor Sweep @ 816";',
    'case Stage::LowVminSweep918: return "CPU Low VMIN - Floor Sweep @ 918";',
    'case Stage::LowVminValidate1020: return "CPU Low VMIN - Floor Sweep @ 1020";',
]:
    s = s.replace(old, old.split(': return')[0] + ': return "CPU Low VMIN - Voltage Floor Scan";')

s = rep(s,
'''    v.preparationLayout = (g.stage == Stage::Preparation && !g_autoPrepConfirm && !g_rebootConfirm);\n''',
'''    v.preparationLayout = (g.stage == Stage::Preparation && !g_autoPrepConfirm && !g_rebootConfirm);\n    v.hideValuesCard = (g.stage == Stage::HardwareDetection);\n''', 'hide hardware values')

s = rep(s,
'''    if (mask & Config_Prepare) {\n        v.instructionTitle = "Set values @ Horizon OC";\n        v.instructionLine1 = "Preparation";\n        v.instructionLine2 = "Use values shown left";\n''',
'''    if (mask & Config_Prepare) {\n        v.instructionTitle = "Set the Preparation values";\n        v.instructionLine1 = "Horizon OC + HOC Toolkit";\n        v.instructionLine2 = "Match the SET values below";\n''', 'prep task instruction')

s = rep(s,
'''    } else if (g.stage == Stage::HardwareDetection) {\n        v.instructionTitle = "Hardware detection";\n        v.instructionLine1 = g.ramDetected ? "RAM detected" : "Detect RAM module";\n        v.instructionLine2 = g.ramDetected ? "A : Continue" : "A : Retry";\n''',
'''    } else if (g.stage == Stage::HardwareDetection) {\n        v.instructionTitle = g.ramDetected ? "Continue to Preparation" : "Retry hardware detection";\n        v.instructionLine1 = g.ramDetected ? "Memory profile detected successfully" : "The memory profile could not be identified";\n        v.instructionLine2 = g.ramDetected ? "A : Continue" : "A : Retry";\n''', 'hardware task')

# Hardware detection content: remove redundant RAM detected / DRAM ID and use clean key/value rows.
old = '''    if (g.ramDetected) {\n        const RamProfile rp = ramProfileForId(g.dramId);\n        uiPrintf(6, "\\x1b[32mRAM detected\\x1b[0m");\n        uiPrintf(8, "Module     : %s", rp.name);\n        uiPrintf(9, "DRAM ID    : %d", g.dramId);\n        uiPrintf(11, "VDDQ start : %d mV", g.vddqStartMv);\n        uiPrintf(12, "OC range   : %s", rp.ocRange);\n        uiPrintf(13, "             Guide estimate - silicon varies");\n        uiPrintf(16, "A : Continue to Preparation");\n        uiPrintf(17, "B : Exit");\n        printResetHint(17);\n        return;\n    }\n'''
new = '''    if (g.ramDetected) {\n        const RamProfile rp = ramProfileForId(g.dramId);\n        uiPrintf(6, "The Wizard detected the memory profile used for RAM tuning.");\n        uiPrintf(9, "Memory Module : %s", rp.name);\n        uiPrintf(10, "VDDQ Start : %d mV", g.vddqStartMv);\n        uiPrintf(11, "Expected OC Range : %s", rp.ocRange);\n        uiPrintf(13, "The OC range is only a guide estimate; silicon quality varies.");\n        uiPrintf(16, "A : Continue to Preparation");\n        uiPrintf(17, "B : Exit");\n        printResetHint(17);\n        return;\n    }\n'''
s = rep(s, old, new, 'hardware content')

# Preparation left side is informational only; right side owns the concrete task/table.
start = s.index('void renderPreparation() {')
end = s.index('\n\n\n\nbool isVminSweepStage', start)
newprep = '''void renderPreparation() {\n    title();\n    uiPrintf(5, "Before tuning starts, the Wizard needs a known baseline.");\n    uiPrintf(7, "You can set the recommended values manually, use your current settings as the baseline, or let the Wizard apply the recommended values automatically.");\n\n    uiPrintf(18, "A : Check settings");\n    uiPrintf(19, "X : Use my current settings as baseline");\n    uiPrintf(20, "Y : Set recommended values automatically + reboot");\n    uiPrintf(21, "B : Exit");\n    printResetHint(21);\n}\n'''
s = s[:start] + newprep + s[end:]

# Search button wording follows actual search direction.
old = '''        uiPrintf(row++, "A : Check setting");\n        if (configMask & (Config_LowUv | Config_LowVmin))\n            uiPrintf(row++, "Y : Set value automatically");\n        uiPrintf(row++, "+ : Known stable / Skip to next value");\n        uiPrintf(row++, "X : Known unstable / Use last good value");\n        uiPrintf(row++, "B : Exit");\n'''
new = '''        uiPrintf(row++, "A : Check setting");\n        if (configMask & (Config_LowUv | Config_LowVmin))\n            uiPrintf(row++, "Y : Set value automatically");\n        const bool stepDownSearch = g.stage == Stage::LowVminQuick || g.stage == Stage::VddqQuick || g.stage == Stage::Vdd2Quick;\n        if (stepDownSearch) {\n            uiPrintf(row++, "+ : Known stable / Lower to next value");\n            uiPrintf(row++, "X : Known unstable / Raise to last good value");\n        } else {\n            uiPrintf(row++, "+ : Known stable / Continue to next value");\n            uiPrintf(row++, "X : Known unstable / Lower to last good value");\n        }\n        uiPrintf(row++, "B : Exit");\n'''
s = rep(s, old, new, 'search action wording')

# Graphical modal for voltage-floor/region measurement scans.
insert_at = s.index('bool sampleVminVoltage(Stage s, int sweepIndex = -1, int sweepTotal = 0) {')
helper = '''void renderVoltageScanModal(u32 cpuHz, int index, int total, const std::string& phase) {\n    gui::ModalView m{};\n    m.version = HOC_WIZARD_VERSION;\n    m.eyebrow = "AUTOMATIC CPU VOLTAGE SCAN";\n    m.title = "Finding the CPU voltage floor";\n    std::string context = "CPU " + formatClock(cpuHz);\n    if (index >= 0 && total > 0)\n        context += "  |  Frequency " + std::to_string(index + 1) + " of " + std::to_string(total);\n    m.body = {\n        context,\n        "GPU 384 MHz  |  RAM 1331.2 MHz",\n        phase,\n        "The Wizard is measuring automatically. No input is required."\n    };\n    m.tone = gui::ModalTone::Cyan;\n    gui::presentModal(m);\n}\n\n'''
s = s[:insert_at] + helper + s[insert_at:]

old_settle = '''            consoleClear();\n            std::printf("\\x1b[1;%dH\\x1b[36mBattery Wizard\\x1b[0m", UI_COL);\n            std::printf("\\x1b[2;%dHStep : CPU Low VMIN - AUTO SCAN", UI_COL);\n            std::printf("\\x1b[3;%dH----------------------------------------", UI_COL);\n            if (sweepIndex >= 0 && sweepTotal > 0)\n                std::printf("\\x1b[5;%dHFrequency : %d / %d", UI_COL, sweepIndex + 1, sweepTotal);\n            std::printf("\\x1b[7;%dHCPU       : %s", UI_COL, formatClock(g_overrideCheck.expected.cpuHz).c_str());\n            std::printf("\\x1b[8;%dHGPU / RAM : 384 / 1331.2 MHz", UI_COL);\n            std::printf("\\x1b[10;%dHSettling voltage %d / %d...", UI_COL, settle + 1, kSettleReads);\n            uiPresent();\n'''
new_settle = '''            renderVoltageScanModal(g_overrideCheck.expected.cpuHz, sweepIndex, sweepTotal,\n                "Settling measurement " + std::to_string(settle + 1) + " of " + std::to_string(kSettleReads));\n'''
s = rep(s, old_settle, new_settle, 'legacy floor scan settle')

old_sample = '''            consoleClear();\n            std::printf("\\x1b[1;%dH\\x1b[36mBattery Wizard\\x1b[0m", UI_COL);\n            std::printf("\\x1b[2;%dHStep : CPU Low VMIN - AUTO SCAN", UI_COL);\n            std::printf("\\x1b[3;%dH----------------------------------------", UI_COL);\n            if (sweepIndex >= 0 && sweepTotal > 0)\n                std::printf("\\x1b[5;%dHFrequency : %d / %d", UI_COL, sweepIndex + 1, sweepTotal);\n            std::printf("\\x1b[7;%dHCPU       : %s", UI_COL, formatClock(g_overrideCheck.expected.cpuHz).c_str());\n            std::printf("\\x1b[8;%dHGPU / RAM : 384 / 1331.2 MHz", UI_COL);\n            std::printf("\\x1b[10;%dHReading CPU voltage sample %d / %d...", UI_COL, i + 1, kSamples);\n            if (attempt > 0) std::printf("\\x1b[12;%dHRetrying noisy measurement...", UI_COL);\n            uiPresent();\n'''
new_sample = '''            std::string scanPhase = "Reading voltage sample " + std::to_string(i + 1) + " of " + std::to_string(kSamples);\n            if (attempt > 0) scanPhase += "  |  retrying noisy measurement";\n            renderVoltageScanModal(g_overrideCheck.expected.cpuHz, sweepIndex, sweepTotal, scanPhase);\n'''
s = rep(s, old_sample, new_sample, 'legacy floor scan samples')

# The newer six-frequency scanner uses the same modal.
old2 = '''            guiPageClear();\n            uiPrintf(1, "\\x1b[36mBattery Wizard - CPU VOLTAGE SCAN\\x1b[0m");\n            uiPrintf(3, "----------------------------------------");\n            uiPrintf(5, "Frequency : %d / %d", index + 1, total);\n            uiPrintf(7, "CPU       : %s", formatClock(cpuHz).c_str());\n            uiPrintf(8, "GPU / RAM : 384 / 1331.2 MHz");\n            uiPrintf(10, "Settling voltage %d / %d...", settle + 1, kSettleReads);\n            uiPresent();\n'''
new2 = '''            renderVoltageScanModal(cpuHz, index, total,\n                "Settling measurement " + std::to_string(settle + 1) + " of " + std::to_string(kSettleReads));\n'''
s = rep(s, old2, new2, 'region scan settle')

old3 = '''            guiPageClear();\n            uiPrintf(1, "\\x1b[36mBattery Wizard - CPU VOLTAGE SCAN\\x1b[0m");\n            uiPrintf(3, "----------------------------------------");\n            uiPrintf(5, "Frequency : %d / %d", index + 1, total);\n            uiPrintf(7, "CPU       : %s", formatClock(cpuHz).c_str());\n            uiPrintf(8, "GPU / RAM : 384 / 1331.2 MHz");\n            uiPrintf(10, "Reading CPU voltage sample %d / %d...", sample + 1, kSamples);\n            if (attempt > 0) uiPrintf(12, "Retrying noisy measurement...");\n            uiPresent();\n'''
new3 = '''            std::string scanPhase = "Reading voltage sample " + std::to_string(sample + 1) + " of " + std::to_string(kSamples);\n            if (attempt > 0) scanPhase += "  |  retrying noisy measurement";\n            renderVoltageScanModal(cpuHz, index, total, scanPhase);\n'''
s = rep(s, old3, new3, 'region scan samples')

p.write_text(s)

# --- Makefile ---
p = Path('Makefile')
s = p.read_text().replace('APP_VERSION := 0.4.0-beta.47', 'APP_VERSION := 0.4.0-beta.48')
p.write_text(s)
