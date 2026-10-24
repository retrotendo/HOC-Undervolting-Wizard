# v0.4.0-beta.16

- Detects the installed Mariko DRAM module before Preparation and selects the 600/640 mV VDDQ starting point from the Horizon OC RAM table.
- Persistent HOC changes now use a guided verify -> green confirmation -> user-confirmed system reboot flow.
- After every app-requested reboot, the Wizard asks whether the console booted normally before testing.
- Already validated persistent settings are no longer repeated on later test pages.
- CPU Low VMIN mapping is automatic: the Wizard controls temporary CPU/GPU/RAM overrides and scans 510/612/714/816/918/1020 MHz with a visible progress bar.
- Distinct measured CPU voltage plateaus are detected and the highest frequency of every plateau is scheduled for 1-hour CPU validation.
- Temporary overrides used by the automatic mapper/plateau tests are restored afterwards.
