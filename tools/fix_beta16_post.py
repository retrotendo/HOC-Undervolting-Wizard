from pathlib import Path
p=Path('source/main.cpp')
s=p.read_text()

# UI_COL is needed by the voltage progress screen before uiPrintf is defined.
s=s.replace('constexpr int VDD2_STEP_UV = 12500;\n', 'constexpr int VDD2_STEP_UV = 12500;\nconstexpr int UI_COL = 36;\n')
s=s.replace('\nconstexpr int UI_COL = 36;\n\nvoid uiPrintf', '\nvoid uiPrintf', 1)

# Did-not-boot is now handled immediately after the guided reboot.
s=s.replace('''void footerTest(int row) {\n    uiPrintf(row,     "Keys:");\n    uiPrintf(row + 1, "A : Start Test");\n    uiPrintf(row + 2, "+ : Known PASS / Skip");\n    uiPrintf(row + 3, "X : Known FAIL / Skip");\n    if (isQuickStage(g.stage)) uiPrintf(row + 4, "Y : Did Not Boot");\n    uiPrintf(row + 5, "B : Exit    - : Reset");\n}''', '''void footerTest(int row) {\n    uiPrintf(row,     "Keys:");\n    uiPrintf(row + 1, "A : Start Test");\n    uiPrintf(row + 2, "+ : Known PASS / Skip");\n    uiPrintf(row + 3, "X : Known FAIL / Skip");\n    uiPrintf(row + 4, "B : Exit    - : Reset");\n}''')

# Allow a retry to ask for VDDQ and VDD2 together without overwriting one row.
old='''        uiPrintf(5, "@ Horizon OC");\n        uiPrintf(7, (configMask & (Config_Vddq | Config_Vdd2)) ? "RAM Settings:" : "CPU Settings:");\n        if (configMask & Config_LowUv) uiPrintf(8, " - Low UV   : %d", targetLowUv());\n        if (configMask & Config_LowVmin) uiPrintf(8, " - Low VMIN : %d mV", targetLowVmin());\n        if (configMask & Config_Vddq) uiPrintf(8, " - VDDQ     : %d mV", targetVddqMv());\n        if (configMask & Config_Vdd2) uiPrintf(8, " - VDD2     : %s", formatVdd2(targetVdd2Uv()).c_str());\n        if (configMask & Config_HighUv) uiPrintf(8, " - High UV  : %d", targetHighUv());\n        uiPrintf(11, "A : Check setting");\n        uiPrintf(12, "+ : Known PASS / Skip");\n        uiPrintf(13, "B : Exit    - : Reset");'''
new='''        uiPrintf(5, "@ Horizon OC");\n        uiPrintf(7, (configMask & (Config_Vddq | Config_Vdd2)) ? "RAM Settings:" : "CPU Settings:");\n        int setRow = 8;\n        if (configMask & Config_LowUv) uiPrintf(setRow++, " - Low UV   : %d", targetLowUv());\n        if (configMask & Config_LowVmin) uiPrintf(setRow++, " - Low VMIN : %d mV", targetLowVmin());\n        if (configMask & Config_Vddq) uiPrintf(setRow++, " - VDDQ     : %d mV", targetVddqMv());\n        if (configMask & Config_Vdd2) uiPrintf(setRow++, " - VDD2     : %s", formatVdd2(targetVdd2Uv()).c_str());\n        if (configMask & Config_HighUv) uiPrintf(setRow++, " - High UV  : %d", targetHighUv());\n        setRow += 2;\n        uiPrintf(setRow++, "A : Check setting");\n        uiPrintf(setRow++, "+ : Known PASS / Skip");\n        uiPrintf(setRow++, "B : Exit    - : Reset");'''
if old not in s: raise SystemExit('config page block not found')
s=s.replace(old,new,1)

old='''    } else if (m & Config_Vddq) {\n        printSingleConfigCheck(row, "RAM VDDQ", formatMv(targetVddqMv()), formatMv((int)(g_configCheck.current.vddqUv / 1000U)), g_configCheck.current.vddqUv == (u32)targetVddqMv() * 1000U);\n        row += 5;\n    } else if (m & Config_Vdd2) {'''
new='''    } else if ((m & Config_Vddq) && (m & Config_Vdd2)) {\n        printSingleConfigCheck(row, "RAM VDDQ", formatMv(targetVddqMv()), formatMv((int)(g_configCheck.current.vddqUv / 1000U)), g_configCheck.current.vddqUv == (u32)targetVddqMv() * 1000U);\n        row += 5;\n        printSingleConfigCheck(row, "RAM VDD2", formatVdd2(targetVdd2Uv()), formatVdd2((int)g_configCheck.current.vdd2Uv), g_configCheck.current.vdd2Uv == (u32)targetVdd2Uv());\n        row += 5;\n    } else if (m & Config_Vddq) {\n        printSingleConfigCheck(row, "RAM VDDQ", formatMv(targetVddqMv()), formatMv((int)(g_configCheck.current.vddqUv / 1000U)), g_configCheck.current.vddqUv == (u32)targetVddqMv() * 1000U);\n        row += 5;\n    } else if (m & Config_Vdd2) {'''
if old not in s: raise SystemExit('combined config prompt marker not found')
s=s.replace(old,new,1)

old='''    else if (m & Config_Vddq)\n        uiPrintf(6, "\\x1b[32mVDDQ %d mV is set.\\x1b[0m", targetVddqMv());\n    else if (m & Config_Vdd2)'''
new='''    else if ((m & Config_Vddq) && (m & Config_Vdd2))\n        uiPrintf(6, "\\x1b[32mVDDQ %d mV + VDD2 %s are set.\\x1b[0m", targetVddqMv(), formatVdd2(targetVdd2Uv()).c_str());\n    else if (m & Config_Vddq)\n        uiPrintf(6, "\\x1b[32mVDDQ %d mV is set.\\x1b[0m", targetVddqMv());\n    else if (m & Config_Vdd2)'''
if old not in s: raise SystemExit('reboot combined marker not found')
s=s.replace(old,new,1)

p.write_text(s)
print('beta16 post cleanup applied')
