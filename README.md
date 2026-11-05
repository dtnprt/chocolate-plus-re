# Chocolate Plus (M-VAVE FootCtrlPlus) â€“ reverse engineering & custom firmware

Modded Firmware for the M-VAVE Chocolate Plus MIDI Controller.

```
firmware/     custom firmware build (build.py, patch sources, CHANGELOG.md, README.md)
website/      website source: release page + Web Config  -> https://dtnprt.github.io/chocolate/
tools/        make_site.py (release page), deploy_site.py (Pages deploy), hooks/pre-push
flasher/      Bluetooth OTA protocol notes + Web Bluetooth flasher (experimental)
android/      Android wrapper for the Web Config
restore/      USB restore runbook (tools in ../third-party/restore_kit)
```

This repository is meant to live next to two sibling folders (not part of it):

```
chocolate-re/
  public-repo/   this repository (git@github.com:dtnprt/chocolate-plus-re.git)
  pages/         working copy of the GitHub Pages repo (git@github.com:dtnprt/dtnprt.github.io.git)
  third-party/   vendor apps, SDK + toolchains, stock firmware, decompiled/disassembled material (private)
```

## Workflow
- Work on branch `dev`; `main` holds releases. Pushing `main` to `origin` also deploys `website/` into
  `../pages/chocolate/` and pushes the Pages repo (needs `git config core.hooksPath tools/hooks` once per clone).
- Build: `python -I firmware/build.py` -> `firmware/out/FootCtrlPlus_<VERSION>-dtnprt.fwsc`
  (needs `../third-party/stock_firmware/FootCtrlPlus_012.ufw`). Flash with SincoOTA, pedal not paired.

## Version numbers
Three digits `<version><build>`, numbers only (SincoOTA/CubeSuite parse digits). Every build gets a new number.
- **Release** versions have an **even** version number: 140â€“149, then 160â€“169, 180â€“189 â€¦
- **Dev** versions have an **odd** version number: 150â€“159, then 170â€“179, 190â€“199 â€¦
- The last digit is the build. After x9 the next number of the same kind follows (149 -> 160, 159 -> 170).
