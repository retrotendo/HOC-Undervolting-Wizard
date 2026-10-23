from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

old = '#include "hoc_monitor.h"\n'
new = '#include "hoc_monitor.h"\n#include "updater.hpp"\n'
if old not in s:
    raise SystemExit('include marker not found')
s = s.replace(old, new, 1)

old = 'int main() {'
new = 'int main(int argc, char** argv) {'
if old not in s:
    raise SystemExit('main signature marker not found')
s = s.replace(old, new, 1)

old = '''        consoleExit(nullptr);\n        return 0;\n    }\n\n    ensureDir();\n'''
new = '''        consoleExit(nullptr);\n        return 0;\n    }\n\n    // Full Application Mode only: check the public GitHub releases before\n    // touching Wizard state. Network/update failures are non-fatal and simply\n    // continue with the currently installed build.\n    if (updater::startupCheckAndPrompt(pad, argc, argv)) {\n        consoleExit(nullptr);\n        return 0;\n    }\n\n    ensureDir();\n'''
if old not in s:
    raise SystemExit('startup insertion marker not found')
s = s.replace(old, new, 1)

p.write_text(s)
