# v0.4.0-beta.31

UI readability fix for the new guided CPU tuning flow.

- Shortened and reworded the beta30 Preparation, reboot, boot-check, recovery, voltage-scan, and automatic-validation text so the relevant single-line UI strings fit the Switch console width.
- Preparation reboot guidance now stays within the visible text area.
- Recovery wording was simplified and kept explicit: requested value, recovery result, and last good value remain clearly separated.
- Renamed `Use current settings as baseline` to `Use my current settings as baseline` for clearer user intent.
- Shortened the HOC Toolkit CPU Boost preparation line and several automatic-setting prompts to avoid right-edge clipping.
- No tuning logic, boot-search logic, automatic voltage scan logic, or stress-test behavior was changed from beta30.
