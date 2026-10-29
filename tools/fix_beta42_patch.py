from pathlib import Path

p = Path('tools/patch_beta42.py')
s = p.read_text()
start = s.index('# Baseline/previous-stage transitions use the same limit-aware entry helpers.')
end = s.index("rep('''        case Stage::VddqLong:", start)
replacement = r'''# Baseline/previous-stage transitions use the same limit-aware entry helpers.
block12 = """            if (g.vddqGood <= VDDQ_MIN_MV) {\n                g.stage = Stage::VddqLong;\n                g.stageReadyAfterBoot = true;\n            } else {\n                g.stage = Stage::VddqQuick;\n                g.vddqTest = g.vddqGood - VDDQ_STEP_MV;\n                g.stageReadyAfterBoot = false;\n            }"""
count12 = s.count(block12)
if count12 < 2:
    raise SystemExit(f'expected at least two indented VDDQ transition blocks, found {count12}')
s = s.replace(block12, """            enterVddqSearchOrMinimumNotice();""")

block8 = """        if (g.vddqGood <= VDDQ_MIN_MV) {\n            g.stage = Stage::VddqLong;\n            g.stageReadyAfterBoot = true;\n        } else {\n            g.stage = Stage::VddqQuick;\n            g.vddqTest = g.vddqGood - VDDQ_STEP_MV;\n            g.stageReadyAfterBoot = false;\n        }"""
if block8 not in s:
    raise SystemExit('skip VDDQ transition block not found')
s = s.replace(block8, """        enterVddqSearchOrMinimumNotice();""", 1)

'''
s = s[:start] + replacement + s[end:]
p.write_text(s)
