#include "gui_console.hpp"

#include <switch.h>

#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <string>

namespace gui {
namespace {

constexpr int kContentOffset = 5;
constexpr int kLeftCol = 3;
constexpr int kLeftWidth = 50;
constexpr int kRightCol = 55;
constexpr int kRightInner = 23;

void at(int row, int col, const char* fmt, ...) {
    std::printf("\x1b[%d;%dH", row, col);
    va_list args;
    va_start(args, fmt);
    std::vprintf(fmt, args);
    va_end(args);
}

bool startsWith(const char* s, const char* prefix) {
    return s && prefix && std::strncmp(s, prefix, std::strlen(prefix)) == 0;
}

bool contains(const char* s, const char* needle) {
    return s && needle && std::strstr(s, needle) != nullptr;
}

void boxTop(int row, const char* color = "90") {
    at(row, kRightCol, "\x1b[%sm+-----------------------+\x1b[0m", color);
}

void boxBottom(int row, const char* color = "90") {
    at(row, kRightCol, "\x1b[%sm+-----------------------+\x1b[0m", color);
}

void boxText(int row, const std::string& text, const char* color = "37") {
    at(row, kRightCol, "\x1b[90m|\x1b[0m\x1b[%sm%-23.23s\x1b[0m\x1b[90m|\x1b[0m",
       color, text.c_str());
}

void drawProgress(const View& view) {
    static const char* labels[7] = {
        "Baseline", "Low UV", "Low VMIN", "VDDQ", "VDD2", "High UV", "Finalize"
    };
    static const int cols[7] = {3, 14, 25, 37, 47, 57, 69};

    for (int i = 0; i < 7; ++i) {
        const int step = i + 1;
        const bool active = step == view.activeStep;
        const bool done = step < view.activeStep;
        const char* color = active ? (view.pulse ? "97" : "96") : (done ? "36" : "90");
        at(3, cols[i], "\x1b[%sm[%d]\x1b[0m", color, step);
        at(4, cols[i] - 1, "\x1b[%sm%-9.9s\x1b[0m", color, labels[i]);
    }
}

void drawInstruction(const View& view) {
    boxTop(6, "36");
    boxText(7, "CURRENT INSTRUCTION", "96");
    boxText(8, view.instructionTitle.empty() ? "Continue Wizard" : view.instructionTitle, "97");
    boxText(9, view.instructionLine1, "37");
    boxText(10, view.instructionLine2, "96");
    boxBottom(11, "36");
}

void drawValues(const View& view) {
    boxTop(13, "90");
    boxText(14, "ACTUAL ACTIVE VALUES", "97");

    if (!view.haveActiveValues) {
        boxText(15, "Horizon OC unavailable", "31");
        for (int row = 16; row <= 19; ++row) boxText(row, "", "37");
        boxBottom(20, "90");
        return;
    }

    for (int i = 0; i < 5; ++i) {
        const ValueRow& v = view.values[i];
        char line[64];
        std::snprintf(line, sizeof(line), "%-12.12s %10.10s", v.label.c_str(), v.value.c_str());
        boxText(15 + i, line, v.mismatch ? "91" : "37");
    }
    boxBottom(20, "90");
}

const char* actionStyle(const char* text) {
    if (startsWith(text, "A :")) return "42;30";          // primary action
    if (startsWith(text, "Y :")) return "44;97";          // automatic action
    if (startsWith(text, "+ :")) return "44;97";          // known pass / skip
    if (startsWith(text, "X :")) {
        if (contains(text, "FAIL") || contains(text, "unstable") ||
            contains(text, "crash") || contains(text, "safer"))
            return "41;97";
        return "44;97";
    }
    if (startsWith(text, "B :") || startsWith(text, "- :")) return "100;37";
    return nullptr;
}

} // namespace

void draw(const View& view) {
    consoleClear();

    at(1, 2, "\x1b[1;97mHorizon \x1b[96mOC\x1b[0m  \x1b[90m|\x1b[0m  \x1b[1;97mUndervolting Wizard\x1b[0m");
    at(1, 67, "\x1b[90mv%-12.12s\x1b[0m", view.version.c_str());
    at(2, 2, "\x1b[90m------------------------------------------------------------------------------\x1b[0m");
    drawProgress(view);
    at(5, 2, "\x1b[90m---------------------------------------------------\x1b[0m");
    at(5, kRightCol, "\x1b[90m-------------------------\x1b[0m");

    drawInstruction(view);
    drawValues(view);
}

void printLeft(int logicalRow, const char* text) {
    if (!text) return;
    const int row = logicalRow + kContentOffset;
    if (row < 6 || row > 45) return;

    const char* style = actionStyle(text);
    if (style) {
        at(row, kLeftCol, "\x1b[%sm %-48.48s \x1b[0m", style, text);
        return;
    }

    at(row, kLeftCol, "%s", text);
}

} // namespace gui
