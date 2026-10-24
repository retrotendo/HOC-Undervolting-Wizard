from pathlib import Path

p = Path('tools/apply_beta16_flow.py')
s = p.read_text()

old = '''    depth = 0\n    in_str = False\n    in_char = False\n    esc = False\n    i = brace\n    while i < len(s):\n        c = s[i]\n        if esc:\n            esc = False\n        elif c == '\\\\' and (in_str or in_char):\n            esc = True\n        elif c == '\"' and not in_char:\n            in_str = not in_str\n        elif c == "'" and not in_str:\n            in_char = not in_char\n        elif not in_str and not in_char:\n            if c == '{': depth += 1\n            elif c == '}':\n'''
new = '''    depth = 0\n    in_str = False\n    esc = False\n    i = brace\n    while i < len(s):\n        c = s[i]\n        if esc:\n            esc = False\n        elif c == '\\\\' and in_str:\n            esc = True\n        elif c == '\"':\n            in_str = not in_str\n        elif not in_str:\n            if c == '{': depth += 1\n            elif c == '}':\n'''
if old not in s:
    raise SystemExit('parser pattern not found')
s = s.replace(old, new, 1)

needle = "helpers = r'''\nstruct DesiredConfig {"
replacement = "helpers = r'''\nbool saveState();\n\nstruct DesiredConfig {"
if needle not in s:
    raise SystemExit('helpers insertion point not found')
s = s.replace(needle, replacement, 1)

p.write_text(s)
print('beta16 patch helper repaired')
