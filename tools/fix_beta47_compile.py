from pathlib import Path
p=Path('source/main.cpp')
s=p.read_text()
s=s.replace('''        addPrep("@ HORIZON OC", "RAM · VDDQ", formatMv(g.vddqStartMv), have ? formatMv((int)(c.vddqUv / 1000U)) : "", have && c.vddqUv != (u32)g.vddqStartMv * 1000U);''','''        addPrep("@ HORIZON OC", "RAM · VDDQ", std::to_string(g.vddqStartMv) + " mV", have ? std::to_string((int)(c.vddqUv / 1000U)) + " mV" : "", have && c.vddqUv != (u32)g.vddqStartMv * 1000U);''',1)
s=s.replace('''        addPrep("@ HORIZON OC", "CPU · Low VMIN", formatMv(STOCK_LOW_VMIN_MV), have ? formatMv(c.lowVminMv) : "", have && c.lowVminMv != STOCK_LOW_VMIN_MV);''','''        addPrep("@ HORIZON OC", "CPU · Low VMIN", std::to_string(STOCK_LOW_VMIN_MV) + " mV", have ? std::to_string(c.lowVminMv) + " mV" : "", have && c.lowVminMv != STOCK_LOW_VMIN_MV);''',1)
s=s.replace('''        addPrep("@ HORIZON OC", "CPU · High VMIN", formatMv(STOCK_HIGH_VMIN_MV), have ? formatMv(c.highVminMv) : "", have && c.highVminMv != STOCK_HIGH_VMIN_MV);''','''        addPrep("@ HORIZON OC", "CPU · High VMIN", std::to_string(STOCK_HIGH_VMIN_MV) + " mV", have ? std::to_string(c.highVminMv) + " mV" : "", have && c.highVminMv != STOCK_HIGH_VMIN_MV);''',1)
s=s.replace('''        addPrep("@ HORIZON OC", "CPU · UV Table", "1683 Tbreak", have ? std::string(cpuTableLabel(c.tableConf)) : "", have && c.tableConf != 3);''','''        const std::string activeTable = !have ? "" :
            (c.tableConf == 1 ? "Default" : c.tableConf == 2 ? "1581 Tbreak" :
             c.tableConf == 3 ? "1683 Tbreak" : c.tableConf == 4 ? "Extreme UV" : "Unknown");
        addPrep("@ HORIZON OC", "CPU · UV Table", "1683 Tbreak", activeTable, have && c.tableConf != 3);''',1)
p.write_text(s)
