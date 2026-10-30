from pathlib import Path

# gui_console.hpp
p = Path('source/gui_console.hpp')
s = p.read_text()
s = s.replace(
'''struct ValueRow {\n    std::string label;\n    std::string value;\n    bool mismatch = false;\n};\n\nstruct View {''',
'''struct ValueRow {\n    std::string label;\n    std::string value;\n    bool mismatch = false;\n};\n\nstruct PreparationRow {\n    std::string group;\n    std::string label;\n    std::string setValue;\n    std::string activeValue;\n    bool mismatch = false;\n};\n\nstruct View {''', 1)
s = s.replace(
'''    bool haveActiveValues = false;\n    ValueRow values[5];\n};''',
'''    bool haveActiveValues = false;\n    ValueRow values[5];\n\n    bool preparationLayout = false;\n    bool havePreparationActiveValues = false;\n    std::vector<PreparationRow> preparationRows;\n};''', 1)
p.write_text(s)

# gui_console.cpp
p = Path('source/gui_console.cpp')
s = p.read_text()
anchor = 'void drawValuesCard() {\n'
if anchor not in s:
    raise SystemExit('drawValuesCard anchor missing')
prep = r'''void drawPreparationCard() {
    const int x = 715, y = 158, w = 525, h = 522;
    drawCard(x, y, w, h, true);
    drawLabel(x + 24, y + 20, "CURRENT INSTRUCTION");
    drawText(x + 24, y + 48, 27, C_TEXT, "Preparation");

    const int setRight = x + 393;
    const int activeRight = x + w - 24;
    drawTextRight(setRight, y + 80, 13, C_MUTED, "SET");
    drawTextRight(activeRight, y + 80, 13, C_MUTED, "ACTIVE");
    fillRect(x + 24, y + 105, w - 48, 1, C_BORDER);

    int yy = y + 119;
    std::string currentGroup;
    for (const PreparationRow& r : g_view.preparationRows) {
        if (r.group != currentGroup) {
            if (!currentGroup.empty()) {
                fillRect(x + 24, yy + 1, w - 48, 1, C_BORDER);
                yy += 13;
            }
            drawText(x + 24, yy, 14, C_CYAN, r.group);
            yy += 24;
            currentGroup = r.group;
        }

        if (r.mismatch)
            roundedRect(x + 18, yy - 3, w - 36, 26, 8, mix(C_PANEL_2, C_RED, 10));
        drawText(x + 28, yy, 14, C_MUTED, fitText(r.label, 14, 235));
        drawTextRight(setRight, yy, 14, C_TEXT, fitText(r.setValue, 14, 104));
        const u32 activeColor = !g_view.havePreparationActiveValues ? C_MUTED : (r.mismatch ? C_RED : C_TEXT);
        drawTextRight(activeRight, yy, 14, activeColor, fitText(r.activeValue, 14, 105));
        yy += 23;
    }
}

'''
s = s.replace(anchor, prep + anchor, 1)

old = r'''void drawMainCard() {
    const int x = 40, y = 158, w = 765, h = 522;
    drawCard(x, y, w, h, false);
    drawLabel(x + 26, y + 20, "GUIDED TUNING");
    drawText(x + 26, y + 49, 29, C_TEXT, fitText(g_view.stageTitle, 29, w - 52));
    fillRect(x + 26, y + 94, w - 52, 1, C_BORDER);

    std::vector<std::string> body;
    std::vector<std::string> actions;
    std::string reset;
    for (const auto& ln : g_lines) {
        std::string s = trim(ln.text);
        if (s.empty() || startsWith(s, "Step :") || isSeparator(s)) continue;
        if (startsWith(s, "- :")) { reset = s; continue; }
        if (isAction(s)) actions.push_back(s);
        else body.push_back(s);
    }

    const int bodyMax = actions.empty() ? 15 : (actions.size() >= 5 ? 7 : 10);
    const int bodySize = body.size() > size_t(bodyMax) ? 16 : 18;
    const int bodyStep = bodySize + 7;
    int by = y + 116;
    int shown = 0;
    for (const std::string& raw : body) {
        if (shown >= bodyMax) break;
        const bool heading = raw == "Objective:" || raw == "Test:" || raw == "Keys:" ||
                             raw == "Required test clocks:" || raw == "Current Temporary Overrides:" ||
                             raw == "Final values:" || raw == "Temporary Overrides:";
        drawText(x + 28, by, heading ? 15 : bodySize, heading ? C_CYAN : C_TEXT,
                 fitText(raw, heading ? 15 : bodySize, w - 56));
        by += heading ? 24 : bodyStep;
        ++shown;
    }
    if (shown < int(body.size())) drawText(x + 28, by, 15, C_MUTED, "More details continue in this step...");

    if (!actions.empty()) {
        const int gap = 8;
        const int ah = actions.size() >= 5 ? 35 : 39;
        const int total = int(actions.size()) * ah + (int(actions.size()) - 1) * gap;
        int ay = y + h - 24 - total - (reset.empty() ? 0 : 28);
        ay = std::max(ay, y + 260);
        for (const auto& a : actions) {
            drawActionButton(x + 26, ay, w - 52, ah, a);
            ay += ah + gap;
        }
    }
    if (!reset.empty()) drawText(x + 28, y + h - 24, 14, C_MUTED, reset);
}
'''
new = r'''void drawMainCard() {
    const int x = 40, y = 158, w = g_view.preparationLayout ? 650 : 765, h = 522;
    drawCard(x, y, w, h, false);
    drawLabel(x + 26, y + 20, "GUIDED TUNING");
    drawText(x + 26, y + 49, 29, C_TEXT, fitText(g_view.stageTitle, 29, w - 52));
    fillRect(x + 26, y + 94, w - 52, 1, C_BORDER);

    std::vector<std::string> body;
    std::vector<std::string> actions;
    std::string reset;
    for (const auto& ln : g_lines) {
        std::string s = trim(ln.text);
        if (s.empty() || startsWith(s, "Step :") || isSeparator(s)) continue;
        if (startsWith(s, "- :")) { reset = s; continue; }
        if (isAction(s)) actions.push_back(s);
        else body.push_back(s);
    }

    if (g_view.preparationLayout) {
        drawText(x + 28, y + 120, 18, C_TEXT,
                 g_view.stageTitle.find("not ready") != std::string::npos
                    ? "Some Preparation values do not match yet."
                    : "Set the Preparation values shown on the right.");
        drawText(x + 28, y + 151, 16, C_MUTED, "SET = required value");
        drawText(x + 28, y + 178, 16, C_MUTED, "ACTIVE = value currently reported by Horizon OC");
        drawText(x + 28, y + 205, 16, C_RED, "Red ACTIVE values still need attention.");
    } else {
        const int bodyMax = actions.empty() ? 15 : (actions.size() >= 5 ? 7 : 10);
        const int bodySize = body.size() > size_t(bodyMax) ? 16 : 18;
        const int bodyStep = bodySize + 7;
        int by = y + 116;
        int shown = 0;
        for (const std::string& raw : body) {
            if (shown >= bodyMax) break;
            const bool heading = raw == "Objective:" || raw == "Test:" || raw == "Keys:" ||
                                 raw == "Required test clocks:" || raw == "Current Temporary Overrides:" ||
                                 raw == "Final values:" || raw == "Temporary Overrides:";
            drawText(x + 28, by, heading ? 15 : bodySize, heading ? C_CYAN : C_TEXT,
                     fitText(raw, heading ? 15 : bodySize, w - 56));
            by += heading ? 24 : bodyStep;
            ++shown;
        }
        if (shown < int(body.size())) drawText(x + 28, by, 15, C_MUTED, "More details continue in this step...");
    }

    if (!actions.empty()) {
        const int gap = 8;
        const int ah = actions.size() >= 5 ? 35 : 39;
        const int total = int(actions.size()) * ah + (int(actions.size()) - 1) * gap;
        int ay = y + h - 24 - total - (reset.empty() ? 0 : 28);
        ay = std::max(ay, y + (g_view.preparationLayout ? 255 : 260));
        for (const auto& a : actions) {
            drawActionButton(x + 26, ay, w - 52, ah, a);
            ay += ah + gap;
        }
    }
    if (!reset.empty()) drawText(x + 28, y + h - 24, 14, C_MUTED, reset);
}
'''
if old not in s:
    raise SystemExit('drawMainCard block missing')
s = s.replace(old, new, 1)

old = '''    drawHeader();\n    drawProgress();\n    drawMainCard();\n    drawInstructionCard();\n    drawValuesCard();\n    endFrame();'''
new = '''    drawHeader();\n    drawProgress();\n    drawMainCard();\n    if (g_view.preparationLayout) {\n        drawPreparationCard();\n    } else {\n        drawInstructionCard();\n        drawValuesCard();\n    }\n    endFrame();'''
if old not in s:
    raise SystemExit('present layout anchor missing')
s = s.replace(old, new, 1)
p.write_text(s)

# main.cpp
p = Path('source/main.cpp')
s = p.read_text()
old = '''    v.activeStep = guiProgressStep(g.stage);\n    v.pulse = g_guiPulse;\n\n    const u32 mask = guiInstructionMask();'''
new = '''    v.activeStep = guiProgressStep(g.stage);\n    v.pulse = g_guiPulse;\n    v.preparationLayout = (g.stage == Stage::Preparation && !g_autoPrepConfirm && !g_rebootConfirm);\n    if (v.preparationLayout && g_configPrompt && (g_configCheck.mask & Config_Prepare))\n        v.stageTitle = "Preparation - Setting not ready";\n\n    const u32 mask = guiInstructionMask();'''
if old not in s:
    raise SystemExit('buildGuiView anchor missing')
s = s.replace(old, new, 1)

old = '''    v.haveActiveValues = have;\n\n    v.values[0].label = "CPU Low UV";'''
new = '''    v.haveActiveValues = have;\n    v.havePreparationActiveValues = have;\n\n    if (v.preparationLayout) {\n        auto addPrep = [&](const char* group, const char* label, const std::string& setValue,\n                           const std::string& activeValue, bool mismatch) {\n            gui::PreparationRow r{};\n            r.group = group;\n            r.label = label;\n            r.setValue = setValue;\n            r.activeValue = have ? activeValue : "unavailable";\n            r.mismatch = have && mismatch;\n            v.preparationRows.push_back(r);\n        };\n\n        addPrep("@ HORIZON OC", "General · Uncapped Clocks", "OFF", have ? (c.uncappedClocks ? "ON" : "OFF") : "", have && c.uncappedClocks);\n        addPrep("@ HORIZON OC", "RAM · HP Mode", "OFF", have ? (c.hpMode ? "ON" : "OFF") : "", have && c.hpMode);\n        addPrep("@ HORIZON OC", "RAM · RAM Max", "1600 MHz", have ? std::to_string(c.ramMaxKHz / 1000U) + " MHz" : "", have && c.ramMaxKHz != 1600000U);\n        addPrep("@ HORIZON OC", "RAM · VDD2", formatVdd2(STOCK_VDD2_UV), have ? formatVdd2((int)c.vdd2Uv) : "", have && c.vdd2Uv != (u32)STOCK_VDD2_UV);\n        addPrep("@ HORIZON OC", "RAM · VDDQ", formatMv(g.vddqStartMv), have ? formatMv((int)(c.vddqUv / 1000U)) : "", have && c.vddqUv != (u32)g.vddqStartMv * 1000U);\n        addPrep("@ HORIZON OC", "CPU · CPU Max", "1963 MHz", have ? std::to_string(c.cpuMaxKHz / 1000U) + " MHz" : "", have && c.cpuMaxKHz != 1963500U);\n        addPrep("@ HORIZON OC", "CPU · Low VMIN", formatMv(STOCK_LOW_VMIN_MV), have ? formatMv(c.lowVminMv) : "", have && c.lowVminMv != STOCK_LOW_VMIN_MV);\n        addPrep("@ HORIZON OC", "CPU · High VMIN", formatMv(STOCK_HIGH_VMIN_MV), have ? formatMv(c.highVminMv) : "", have && c.highVminMv != STOCK_HIGH_VMIN_MV);\n        addPrep("@ HORIZON OC", "CPU · UV Table", "1683 Tbreak", have ? std::string(cpuTableLabel(c.tableConf)) : "", have && c.tableConf != 3);\n        addPrep("@ HORIZON OC", "CPU · Low UV", "0", have ? std::to_string(c.lowUv) : "", have && c.lowUv != STOCK_LOW_UV);\n        addPrep("@ HORIZON OC", "CPU · High UV", "0", have ? std::to_string(c.highUv) : "", have && c.highUv != STOCK_HIGH_UV);\n        addPrep("@ HOC TOOLKIT", "CPU Boost", "1785 MHz", have ? std::to_string(c.cpuBoostKHz / 1000U) + " MHz" : "", have && c.cpuBoostKHz != 1785000U);\n    }\n\n    v.values[0].label = "CPU Low UV";'''
if old not in s:
    raise SystemExit('preparation values anchor missing')
s = s.replace(old, new, 1)
p.write_text(s)

# version
p = Path('Makefile')
s = p.read_text()
if 'APP_VERSION := 0.4.0-beta.46' not in s:
    raise SystemExit('version anchor missing')
s = s.replace('APP_VERSION := 0.4.0-beta.46', 'APP_VERSION := 0.4.0-beta.47', 1)
p.write_text(s)
