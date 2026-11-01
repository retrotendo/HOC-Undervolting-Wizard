from pathlib import Path


def replace_once(text, old, new, name):
    if old not in text:
        raise SystemExit(f'missing block: {name}')
    return text.replace(old, new, 1)

main_path = Path('source/main.cpp')
make_path = Path('Makefile')
readme_path = Path('README.md')

main = main_path.read_text()
make = make_path.read_text()
readme = readme_path.read_text()

old_real = '''    if (!g_realWorldHelpPage) {\n        uiPrintf(5, "For final confirmation, play The Legend of Zelda: Tears of the Kingdom.");\n        uiPrintf(7, "Play for at least 1 hour.");\n        uiPrintf(9, "During the check:");\n        uiPrintf(10, "• Normal gameplay");\n        uiPrintf(11, "• Battles and fast travel");\n        uiPrintf(12, "• Loading screens");\n        uiPrintf(13, "• Sleep / Wake");\n        uiPrintf(15, "Watch for crashes, freezes or unexpected reboots.");\n        uiPrintf(19, "A : If instability occurs");\n        uiPrintf(20, "+ : Stable / Continue to results");\n        uiPrintf(21, "B : Exit");\n        printResetHint(21);\n        return;\n    }\n'''
new_real = '''    if (!g_realWorldHelpPage) {\n        uiPrintf(5, "Recommendation: Tears of the Kingdom");\n        uiPrintf(7, "Play for at least 1 hour.");\n        uiPrintf(9, "Use:");\n        uiPrintf(10, "• Normal gameplay");\n        uiPrintf(11, "• Fast travel / battles");\n        uiPrintf(12, "• Loading screens");\n        uiPrintf(13, "• Sleep / Wake");\n        uiPrintf(15, "Watch for crash, freeze or reboot.");\n        uiPrintf(19, "A : If instability occurs");\n        uiPrintf(20, "+ : Stable / Continue to results");\n        uiPrintf(21, "B : Exit");\n        printResetHint(21);\n        return;\n    }\n'''
main = replace_once(main, old_real, new_real, 'real world page')

old_prompt = '''    m.eyebrow = "PERFORMANCE MODES";\n    m.title = "Save Settings as Battery Profile in Performance Modes?";\n    m.body = {\n        "This performs the same save as Performance Modes -> Save Settings -> as Battery Mode.",\n        "The current Horizon OC config.ini, hoc.kip and ReverseNX-RT profile will be copied to the Performance Modes Battery profile.",\n        "The active Performance Modes profile will not be changed."\n    };\n'''
new_prompt = '''    m.eyebrow = "PERFORMANCE MODES";\n    m.title = "Save Settings to Performance Modes App?";\n    m.body = {\n        "Save the current settings as the Battery Profile.",\n        "The active profile will not be changed."\n    };\n'''
main = replace_once(main, old_prompt, new_prompt, 'performance modes prompt')

main = main.replace('m.primaryAction = "Save Settings as Battery Profile";', 'm.primaryAction = "Save Battery Profile";', 1)

make = make.replace('APP_VERSION := 0.4.0-beta.53', 'APP_VERSION := 0.4.0-beta.54', 1)
if 'APP_VERSION := 0.4.0-beta.54' not in make:
    raise SystemExit('version update failed')

readme = readme.replace('v0.4.0-beta.53', 'v0.4.0-beta.54')

main_path.write_text(main)
make_path.write_text(make)
readme_path.write_text(readme)
print('beta54 readability patch applied')
