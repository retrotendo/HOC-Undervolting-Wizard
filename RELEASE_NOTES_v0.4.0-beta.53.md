# HOC Undervolting Wizard v0.4.0-beta.53

Optional Performance Modes Battery-profile export.

- The Complete page no longer claims that the profile was saved automatically.
- Adds an explicit **Save Settings as Battery Profile in Performance Modes** option.
- Nothing is exported without the user's confirmation.
- Choosing the save option mirrors `Performance Modes -> Save Settings -> as Battery Mode` and copies the current Horizon OC `config.ini`, `hoc.kip`, and ReverseNX-RT profile into the Performance Modes Battery folder.
- The active Performance Modes profile/state is not switched or marked.
- **X = Skip** leaves Performance Modes unchanged and exits the completed Wizard; reopening the completed Wizard offers the save option again.
- If Performance Modes or required Horizon OC files are missing, the Wizard reports the problem instead of creating a fake installation.
- README updated for the new optional export flow.
- No tuning limits, search logic, validation durations, voltage sampling, or safety-state guard behavior changed.
