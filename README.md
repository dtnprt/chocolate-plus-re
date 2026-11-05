# Chocolate Plus (M-VAVE FootCtrlPlus) â€“ reverse engineering & custom firmware

Modded Firmware for the M-VAVE Chocolate Plus MIDI Controller.

```
firmware/     custom firmware build (build.py, patch sources, CHANGELOG.md, README.md)
```

The website (https://dtnprt.github.io/chocolate/), the Web Bluetooth flasher and the Android app are kept in the
private parent repository. This repository is meant to live inside it:

```
chocolate-re/
  public-repo/   this repository (git@github.com:dtnprt/chocolate-plus-re.git)
  pages/         working copy of the GitHub Pages repo (git@github.com:dtnprt/dtnprt.github.io.git)
  website/ tools/ flasher/ android/ restore/ firmware/   private: website + deploy, flasher, Android app, stock restore, local builds
  third-party/   vendor apps, SDK + toolchains, stock firmware, decompiled/disassembled material (private)
```

## Workflow
- Work on branch `dev`; `main` holds releases. The website is deployed from the parent repo (`tools/deploy_site.py`).
- Build: `python -I firmware/build.py <FootCtrlPlus_012.fwsc> [-o <folder>] [--extras]` -> `FootCtrlPlus_<VERSION>-dtnprt.fwsc`.
  The input must be the original M-VAVE firmware 012 (https://www.cuvave.com/product?id=chocolate-plus), checked by SHA-256.
  Local builds go to the parent repo: `python -I firmware/build.py ../third-party/stock_firmware/FootCtrlPlus_012.ufw -o ../firmware/out --extras`.
  No firmware binaries in this repo or on the website. Flash with SincoOTA, pedal not paired.

## Version numbers
Three digits `<version><build>`, numbers only (SincoOTA/CubeSuite parse digits). Every build gets a new number.
- **Release** versions have an **even** version number: 140â€“149, then 160â€“169, 180â€“189 â€¦
- **Dev** versions have an **odd** version number: 150â€“159, then 170â€“179, 190â€“199 â€¦
- The last digit is the build. After x9 the next number of the same kind follows (149 -> 160, 159 -> 170).
