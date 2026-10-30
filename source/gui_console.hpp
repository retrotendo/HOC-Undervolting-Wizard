#pragma once

#include <string>

namespace gui {

// Presentation-only layer for the first 1.0.0 graphical beta.
struct ValueRow {
    std::string label;
    std::string value;
    bool mismatch = false;
};

struct View {
    std::string version;
    int activeStep = 1;
    bool pulse = false;

    std::string instructionTitle;
    std::string instructionLine1;
    std::string instructionLine2;

    bool haveActiveValues = false;
    ValueRow values[5];
};

// Clears the console and paints the static full-screen shell, progress strip,
// current instruction panel and live active-value panel.
void draw(const View& view);

// Prints one logical content row into the left pane. Controller-action lines
// are automatically styled as compact colored panels while keeping their text.
void printLeft(int logicalRow, const char* text);

} // namespace gui
