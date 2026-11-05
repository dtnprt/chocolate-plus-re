# Chocolate Plus (M-VAVE FootCtrlPlus) – reverse engineering & custom firmware

```
firmware/     custom firmware build (build.py, patch sources, CHANGELOG.md, README.md)
website/      GitHub Pages site: release page + Web Config  -> https://dtnprt.github.io/chocolate/
tools/        make_site.py (release page), deploy_site.py (Pages deploy), hooks/pre-push
flasher/      Bluetooth OTA protocol notes + Web Bluetooth flasher (experimental)
android/      Android wrapper for the Web Config
restore/      USB restore runbook (tools in thirdparty/restore_kit)
thirdparty/   vendor apps, SDK, stock firmware, decompiled/disassembled material - NOT in git
```

## Workflow
- Work on branch `dev`; `main` holds releases. Pushing `main` to `origin` also deploys `website/`
  (needs `git config core.hooksPath tools/hooks` once per clone).
- Build: `python -I firmware/build.py` -> `firmware/out/FootCtrlPlus_<VERSION>-dtnprt.fwsc`
  (needs `thirdparty/stock_firmware/FootCtrlPlus_012.ufw`). Flash with SincoOTA, pedal not paired.

## Version numbers
Three digits `<version><build>`, numbers only (SincoOTA/CubeSuite parse digits). Every build gets a new number.
- **Release** versions have an **even** version number: 140–149, then 160–169, 180–189 …
- **Dev** versions have an **odd** version number: 150–159, then 170–179, 190–199 …
- The last digit is the build. After x9 the next number of the same kind follows (149 -> 160, 159 -> 170).
