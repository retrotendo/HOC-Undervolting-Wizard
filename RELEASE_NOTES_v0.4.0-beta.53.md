# HOC Undervolting Wizard v0.4.0-beta.53

Optional Performance Modes Battery-profile export.

- After the final real-world guidance, the Wizard now asks: **Save Settings as Battery Profile in Performance Modes?**
- **A = Save Settings as Battery Profile** performs the same profile copy as `Performance Modes -> Save Settings -> as Battery Mode`.
- **X = Skip** leaves Performance Modes unchanged and continues to the normal Complete/results page.
- **B = Back** returns to the final real-world guidance page.
- Nothing is exported without explicit user confirmation.
- The confirmed save copies the current Horizon OC `config.ini`, `hoc.kip`, and ReverseNX-RT profile into `/switch/.packages/Performance Modes/Battery/`.
- The active Performance Modes profile/state is never switched or marked by the Wizard.
- A successful save is shown on the Complete page as `Saved to Performance Modes -> Battery Mode`.
- If Performance Modes or required Horizon OC files are missing, the Wizard reports the problem and keeps the save decision open.
- The save/skip decision is persisted so an already completed decision is not repeatedly prompted after reopening the Wizard.
- README updated for the new optional export flow.
- No tuning limits, search logic, validation durations, voltage sampling, or safety-state guard behavior changed.
