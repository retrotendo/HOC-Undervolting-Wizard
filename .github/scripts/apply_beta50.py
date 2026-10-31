from pathlib import Path


def replace_once(text, old, new, name):
    if old not in text:
        raise SystemExit(f"missing block: {name}")
    return text.replace(old, new, 1)

# ---- source/main.cpp ----
p = Path("source/main.cpp")
s = p.read_text()

s = replace_once(
    s,
    'case Stage::RealWorldValidate: return "Final Real-World Test";',
    'case Stage::RealWorldValidate: return "Real-World Stability Check";',
    "real-world stage title",
)

old = '''    v.preparationLayout = (g.stage == Stage::Preparation && !g_autoPrepConfirm && !g_rebootConfirm);\n    v.hideValuesCard = (g.stage == Stage::HardwareDetection);'''
new = '''    v.preparationLayout = (g.stage == Stage::Preparation && !g_autoPrepConfirm && !g_rebootConfirm);\n    v.hideValuesCard = (g.stage == Stage::HardwareDetection);\n    v.fullWidthLayout = g_resultScreen || g.stage == Stage::RealWorldValidate || g.stage == Stage::Complete;'''
s = replace_once(s, old, new, "full-width view flag")

old = '''    } else if (g.stage == Stage::RealWorldValidate) {\n        v.instructionTitle = "Run the real-world test";\n        v.instructionLine1 = "Remove all overrides";\n        v.instructionLine2 = "Then run game test";\n    } else if (g.stage == Stage::Complete) {\n        v.instructionTitle = "Undervolting complete";\n        v.instructionLine1 = "Final values saved";\n        v.instructionLine2 = "B : Exit";'''
new = '''    } else if (g.stage == Stage::RealWorldValidate) {\n        v.instructionTitle = "Final stability recommendation";\n        v.instructionLine1 = "Optional real-world confirmation";\n        v.instructionLine2 = "A : Continue to results";\n    } else if (g.stage == Stage::Complete) {\n        v.instructionTitle = "Undervolting complete";\n        v.instructionLine1 = "Final values saved";\n        v.instructionLine2 = "B : Exit";'''
s = replace_once(s, old, new, "real-world instruction semantics")

start = s.index("void renderRealWorld() {")
end = s.index("\nvoid renderComplete() {", start)
real_world = r'''void renderRealWorld() {
    title();
    uiPrintf(5, "For final confirmation, play The Legend of Zelda: Tears of the Kingdom for at least 1 hour.");
    uiPrintf(7, "Use normal gameplay, fast travel, battles, loading screens and Sleep/Wake.");
    uiPrintf(9, "If a crash, freeze or reboot occurs, change only ONE setting by one step, then play again.");
    uiPrintf(11, "Recommended order:");
    uiPrintf(12, "Low VMIN -> VDDQ -> VDD2 -> CPU High UV -> CPU Low UV");
    uiPrintf(14, "Low VMIN / VDDQ / VDD2: raise the voltage by one step.");
    uiPrintf(15, "CPU High UV / CPU Low UV: move one step toward a less aggressive undervolt.");
    uiPrintf(17, "If it still fails, restore that setting to its previous value before trying the next one.");
    uiPrintf(18, "Never change more than one setting at a time.");
    uiPrintf(20, "A : Continue to results");
    uiPrintf(21, "B : Exit");
    printResetHint(21);
}
'''
s = s[:start] + real_world + s[end:]

p.write_text(s)

# ---- source/gui_console.hpp ----
p = Path("source/gui_console.hpp")
s = p.read_text()
s = replace_once(
    s,
    '''    bool preparationLayout = false;\n    bool hideValuesCard = false;''',
    '''    bool preparationLayout = false;\n    bool hideValuesCard = false;\n    bool fullWidthLayout = false;''',
    "View fullWidthLayout",
)
p.write_text(s)

# ---- source/gui_console.cpp ----
p = Path("source/gui_console.cpp")
s = p.read_text()

s = replace_once(
    s,
    '''    const int x = 40, y = 158, w = g_view.preparationLayout ? 650 : 765, h = 522;''',
    '''    const int x = 40, y = 158, w = g_view.fullWidthLayout ? 1200 : (g_view.preparationLayout ? 650 : 765), h = 522;''',
    "full-width main card",
)

marker = '''    if (g_view.preparationLayout) {\n        int by = y + 120;'''
insert = '''    // Old console pages sometimes split one sentence across several uiPrintf rows.\n    // Rejoin only obvious prose fragments, then let the graphical renderer wrap\n    // them to the actual card width. This removes unnecessary legacy line breaks\n    // without merging headings, values or numbered rows.\n    std::vector<std::string> compactBody;\n    auto isPlainFragment = [](const std::string& text) {\n        if (text.empty() || !std::isalpha(static_cast<unsigned char>(text[0]))) return false;\n        if (text.find(':') != std::string::npos || startsWith(text, "http")) return false;\n        return true;\n    };\n    for (const std::string& raw : body) {\n        if (!compactBody.empty() && isPlainFragment(compactBody.back()) && isPlainFragment(raw)) {\n            const char last = compactBody.back().empty() ? '\\0' : compactBody.back().back();\n            if (last != '.' && last != '!' && last != '?' && last != ':' && last != ';') {\n                compactBody.back() += " " + raw;\n                continue;\n            }\n        }\n        compactBody.push_back(raw);\n    }\n    body.swap(compactBody);\n\n    if (g_view.preparationLayout) {\n        int by = y + 120;'''
s = replace_once(s, marker, insert, "legacy line-break compaction")

old = '''    drawMainCard();\n    if (g_view.preparationLayout) {\n        drawPreparationCard();\n    } else {\n        drawInstructionCard();\n        if (!g_view.hideValuesCard) drawValuesCard();\n    }'''
new = '''    drawMainCard();\n    if (!g_view.fullWidthLayout) {\n        if (g_view.preparationLayout) {\n            drawPreparationCard();\n        } else {\n            drawInstructionCard();\n            if (!g_view.hideValuesCard) drawValuesCard();\n        }\n    }'''
s = replace_once(s, old, new, "skip right cards on full-width pages")

p.write_text(s)

# ---- Makefile ----
p = Path("Makefile")
s = p.read_text()
s = replace_once(s, "APP_VERSION := 0.4.0-beta.49", "APP_VERSION := 0.4.0-beta.50", "version bump")
p.write_text(s)

print("beta50 patch applied")
