# MSY Rip

A desktop RIP tool that turns TIF files into **.PRT** print files for DTF printers.
Drop your TIF files in, choose a spot choke, and get a ready-to-print file.

## Features

- **Drag & drop** TIF files — rip many files in one go
- **Spot choke**: 0 / 1 / 2 px white-layer contraction per file
- **CMYK + White** channel output (8-channel PRT)
- **ICC profile support** for RGB inputs (import once, the profile is stored inside
  the application folder so it keeps working if you delete the original)
- **Printer profiles**: pick your machine from a list and every parameter
  (pass count, band width, halftone cell, channel order, spot name) is applied
  automatically; a manual profile is available for custom setups
- **Fully adjustable**: channel order, ink percentages, spot name, pass count,
  ink limit
- **Large files**: tested with jobs up to 58 × 200 cm (~4.7 GB PRT)
- **Persistent settings** — configure once, it stays
- **Automatic updates** from GitHub Releases

## How it works

```
TIF (CMYK or RGB)  →  colour conversion / direct channel read
                   →  ink limits and spot generation
                   →  tone encoding per ink channel
                   →  .PRT file (8 planes, 16-bit big-endian)
```

The `.PRT` body is organised in eight vertical blocks; each ink channel is written
to its own plane position and the per-pixel 16-bit value carries the dot pattern.
The writer streams plane by plane, which keeps memory use low and allows very tall
designs.

## Tested on

Validated on **Audley Malina** DTF printers with 58 cm media width (6-pass mode),
printing at 1800 dpi vertical resolution. Output files match the reference RIP byte
layout, plane structure and channel mapping; colour, white layer and geometry were
verified with physical test prints.

## Install (end user)

1. Download `MSYRip-Setup.exe` from the latest release
2. Run it — installs to `C:\Program Files\MSYRip`
3. A **MSY Rip** shortcut is created on the desktop
4. Open Settings (⚙) → pick your printer profile, import your ICC profile if you use
   RGB files, choose an output folder → Save
5. Drag your TIF files onto the window → choose 0/1/2 choke → **spot + rip**

## Development

```bash
pip install -r requirements.txt
python main.py
```

## Requirements

- Windows 10/11 (64-bit)
- 300 dpi TIF input recommended
- Free disk space: roughly 20 MB of PRT per 1000 cm² of design, more for tall jobs

## License

Open source — MIT
