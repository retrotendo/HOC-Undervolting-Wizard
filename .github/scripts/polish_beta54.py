from pathlib import Path
p=Path('source/main.cpp')
s=p.read_text()
old='''    uiPrintf(5, "Change only ONE setting at a time. Change it by one step, then play again.");\n    uiPrintf(7, "Recommended order:");\n    uiPrintf(9, "1. Low VMIN - raise voltage one step");\n    uiPrintf(10, "2. VDDQ - raise voltage one step");\n    uiPrintf(11, "3. VDD2 - raise voltage one step");\n    uiPrintf(12, "4. CPU High UV - one step less aggressive");\n    uiPrintf(13, "5. CPU Low UV - one step less aggressive");\n    uiPrintf(15, "If it still fails, restore that setting to its previous value before trying the next one.");\n    uiPrintf(17, "Never change multiple settings at the same time.");\n'''
new='''    uiPrintf(5, "Change only ONE setting at a time.");\n    uiPrintf(6, "Change one step, then play again.");\n    uiPrintf(8, "Recommended order:");\n    uiPrintf(10, "1. Low VMIN - raise one step");\n    uiPrintf(11, "2. VDDQ - raise one step");\n    uiPrintf(12, "3. VDD2 - raise one step");\n    uiPrintf(13, "4. CPU High UV - one step less aggressive");\n    uiPrintf(14, "5. CPU Low UV - one step less aggressive");\n    uiPrintf(16, "Still unstable? Restore the previous value.");\n    uiPrintf(17, "Then try the next setting.");\n'''
if old not in s: raise SystemExit('second real-world page block not found')
s=s.replace(old,new,1)
old2='''    m.body = {\n        "Saved to Performance Modes -> Battery Mode.",\n        "Horizon OC config.ini, hoc.kip and ReverseNX-RT were copied.",\n        "The active Performance Modes profile was not changed."\n    };\n'''
new2='''    m.body = {\n        "Battery Profile saved to Performance Modes.",\n        "The active profile was not changed."\n    };\n'''
if old2 not in s: raise SystemExit('save notice block not found')
s=s.replace(old2,new2,1)
p.write_text(s)
print('beta54 polish applied')
