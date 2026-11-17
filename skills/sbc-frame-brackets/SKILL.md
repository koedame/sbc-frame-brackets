---
name: sbc-frame-brackets
description: Get or make a screwless, support-free 3D-printed bracket that clips a single-board computer (Raspberry Pi, Radxa, Khadas, Hardkernel ODROID, Orange Pi, NVIDIA Jetson Orin Nano, BeagleBone, LattePanda, Sipeed NanoKVM-Desk and NanoKVM Lite, and others) onto 20x20 or 40x40 aluminium extrusion or a TS35 DIN rail, as 3MF, STL and STEP. Use when someone wants to mount a board on an extrusion frame or a DIN rail, asks for a bracket, holder or mount for a single-board computer, or wants a board added to sbc-frame-brackets.
license: MIT
---

# SBC frame brackets

[sbc-frame-brackets](https://github.com/koedame/sbc-frame-brackets) makes L-shaped brackets that clip onto an aluminium extrusion (6 mm slot) or a DIN rail without screws and hold a board by its mounting holes. A board with none, such as the Sipeed NanoKVM Lite, snaps into a printed cradle that is screwed on in its place.
Every supported board already has ready-made files attached to the latest release. Build only for a board that is not supported yet.

Work through the steps in order. Steps 3 to 8 are only for a new board.

## 1. Find out what is wanted

Ask only for what the user has not said:

- **Board**: the exact model, and the revision if the manufacturer has several.
- **Mount** (`--mount`): `20` (20x20 extrusion), `40` (40x40 extrusion) or `DIN` (TS35 DIN rail). The extrusion needs 6 mm slots.
- **Orientation** (`--orient`), one of six:

  | `--orient` | File name suffix | Where the board sits |
  |---|---|---|
  | `upright-portrait` | none | Stands out from the frame at right angles to the rail, long side vertical. Takes the least rail |
  | `upright-landscape` | `_upright-landscape` | Stands out at right angles to the rail, long side pointing away from the frame |
  | `flat-portrait` | `_flat-portrait` | Parallel to the front of the frame, beside the grip, long side vertical. Closest to the frame |
  | `flat-landscape` | `_flat-landscape` | Parallel to the front of the frame, beside the grip, long side along the rail |
  | `shelf-portrait` | `_shelf-portrait` | Lies on a shelf level with the top of the grip, long side pointing away from the frame |
  | `shelf-landscape` | `_shelf-landscape` | Lies on a shelf level with the top of the grip, long side along the rail |

- **Standoffs**: only the two upright orientations come in a version with integrated standoffs (`_spacer`). Flat and shelf have no `_spacer` version, because standoffs growing sideways out of a standing plate cannot print without support; the user brings their own standoffs. In the flat orientations the back of the plate lies on the frame, so the holes are countersunk on the back and take flat head screws, put in from the back before the bracket goes on.
- **Format**: 3MF for a slicer (in print orientation on the build plate), STL, or STEP for CAD.

## 2. Is the board supported? Then hand over the download link

Read "Supported boards" in the README: `README.md` two directories above this file when the skill comes with the repository, otherwise <https://github.com/koedame/sbc-frame-brackets#supported-boards>.
If the board is listed, **do not build anything**. Give the link to the zip of the bracket the table names, from the README's "Download" table:

```
https://github.com/koedame/sbc-frame-brackets/releases/latest/download/<bracket>.zip
```

The zip holds every mount, orientation and format of that bracket in a folder named after it, so also tell the user which file in it to use. The `NanoKVMLite` zip also has `NanoKVMLite_cradle`, the cradle the board snaps into, which has to be printed too (one fits every bracket of that board). File names are `<bracket>_<2020|4040|DIN35>[_<orientation suffix>][_spacer].<3mf|stl|step>`, for example `PiB_2020.3mf`, `PiB_2020_upright-landscape_spacer.3mf` or `PiB_DIN35_flat-portrait.step`.
Point the user to "Printing" (PETG, no supports) and "Mounting" in the README, and to "Where the edges of the board end up" if they care which connector ends up where.

A board that is not listed may still share its outline, mounting holes and microSD position with a listed bracket; many boards copy the Raspberry Pi B layout. Only say so after comparing with the official drawing (step 3), and say which drawing you compared.

## 3. New board: take the dimensions from an official source

Use only the manufacturer's official mechanical drawing (PDF, DXF), 3D model (STEP) or manufacturing data (board outline and drill files).
**Never take a dimension from memory, a photo, a shop listing or a guess.** If you cannot find an official source, stop and ask the user for one.
Note where each number comes from; it goes into the definition's `notes`.

You need:

- the outline, L x S, and the PCB thickness
- the centre of every mounting hole, and the screw size
- the edge the microSD card comes out of, and whether the slot is on top or under the board
- every part that comes near the bracket: everything under the board and how far below it reaches, connectors that stick out past the edges, and the tall parts on top
- which edges the user wants where. In upright portrait one of the two edges along `l` (`frame_edge`) faces the back plate, 4 mm away. In upright landscape and shelf portrait one short end faces the frame; if the microSD slot is at that end, the bracket keeps 17 mm there for a finger

Never put the manufacturer's CAD files, or shapes converted from them, into the repository, the viewer or anything you hand over. Most of them are not licensed for redistribution.

## 4. Set up

Work in a clone of the repository: the current directory if it is one, otherwise:

```sh
git clone https://github.com/koedame/sbc-frame-brackets.git
cd sbc-frame-brackets
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Python 3.11 to 3.14. On a minimal Linux install, `ImportError: libGL.so.1` means libGL is missing (`sudo apt install libgl1` on Debian and Ubuntu).

## 5. Write the definition

A board is one JSON file, `boards/<Name>.json`; no code changes. `<Name>` is letters and digits only: it is what `--board` takes and the start of every output file name.
Copy the closest existing definition (`PiA.json` is the simplest, `VIM1S.json` has rows of windows and a notch, `BBB.json` has many parts) and read `boards/README.md`, which describes every field. The parts that are easy to get wrong:

- **Coordinates** are in mm in the board's top view, right-handed: `l` from 0 to L, `s` from 0 to S, `s` growing upwards when `l` grows to the right. If the drawing's y axis points down (KiCad), use `s = S - y`. Never mirror.
  Lay `l` along the edge that should face the back plate, usually the long side (the orientation names assume it is).
- **`frame_edge`** (`"s=0"` or `"s=S"`) is the edge along `l` that faces the back plate. Turn the drawing so that this edge is at the bottom: the end on the right is then at the top in upright portrait and faces the frame in upright landscape and shelf portrait.
- **`standoffs`**: `h` tall enough that the deepest part under the board clears the plate, `d` narrow enough to miss the nearest part around each hole. `pilot` is 1.7 for M2, 2.2 for M2.5, 2.6 for M3 (self-tapping). `screw` starts with the thread size (`M2`, `M2.5` or `M3`), which sizes the countersinks of the flat orientations. `--check` reports standoffs that are too short or too wide as a board overlap.
- **`openings`** and **`windows`** must stay clear of the standoffs. A microSD slot under the board usually needs a notch so that a finger reaches the card: an opening that starts 4 mm outside the edge (`-4`, or `L + 4`), so that it is open there, and reaches 11 to 15 mm in, as in the existing definitions. The same works for a connector under the board.
- **A board with no mounting holes** gets a `cradle` (`boards/README.md`, `NanoKVMLite.json`); `size`, `holes`, `hole_d` and `standoffs` are then the cradle's.
- **`parts`**: the PCB itself (`[0, L, 0, S, 0, <thickness>]`) and every part from step 3, as boxes, heights from the board's underside (negative below it): a part 8.5 mm tall on a 1.6 mm board is `1.6, 10.1`. They decide what `--check` tests the bracket against.

## 6. Build only what is needed, with `--check`

```sh
python build_all.py --board <Name> --mount 20 --orient flat-portrait --format 3mf stl step viewer --check
```

| Option | Values |
|---|---|
| `--board` | The definitions' names (file names in `boards/`), one or more |
| `--mount` | `20`, `40`, `DIN`, one or more |
| `--orient` | `upright-portrait`, `upright-landscape`, `flat-portrait`, `flat-landscape`, `shelf-portrait`, `shelf-landscape`, one or more |
| `--format` | `3mf`, `stl`, `step`, `viewer`, one or more. The upright orientations get both the version without and the version with standoffs |
| `--check` | Checks interference with the frame and the board, unsupported area, that the part is one solid, that it is held (moved 0.3 mm forward, up or down it hits the frame), that flat head screws stay below the back of the flat plates, and on DIN rail both a steel and an aluminium rail and that the leaf springs can bend far enough |
| `--board-step <file>` | Check against the manufacturer's 3D model instead of `parts` (the file's name must be in `official_models`) |
| `--out <dir>` | Output directory, `models/` by default |

The exit status is the result:

- **0**: every check passed. The last line says `Checks passed for all <n> models`.
- **1, after a line per model**: a check failed. The last line, `Checks failed for ...`, names the failed models; on each one's line, look for the number that is not 0 (`frame overlap`, `aluminium rail`, `board overlap`, `flat head screws overlap`, `unsupported ... mm2`, `separate solids`, `leaf spring ... overlap`), for `not held` or for `OCC and mesh disagree` (OpenCascade and the triangle meshes measured an overlap differently, or a shape could not be meshed; OpenCascade can miss overlaps between nearly parallel flat faces, DESIGN_NOTES section 6). Fix the definition (usually taller or narrower standoffs, or a notch for a part under the board) and build again. Never hand over files from a run that exited 1.
- **1, with only a line starting `boards/<Name>.json:`**: the definition itself is wrong, before anything was built. Fix what the line names.
- **2**: an option is wrong; the message lists the valid values.

Before handing over a new board, also build every mount and orientation once, `python build_all.py --board <Name> --format step --check --out models/all` (a few minutes; `--out` keeps these apart from the files you hand over). A definition that passes in one orientation can fail in another, for example a part that reaches the frame only in landscape.
If the manufacturer publishes a 3D model, add it to `official_models` and pass it with `--board-step <path>` as well; its board overlap must be 0.

## 7. Show the result

`--format viewer` writes `viewer.html` next to the models: one offline page with the brackets built in that run, the simplified board on them and the mount.
Open it for the user (`open` on macOS, `xdg-open` on Linux, `start` on Windows). If you can take a screenshot of it (a headless browser with WebGL), look at it yourself first: the board on its standoffs, nothing through the plate, the microSD slot and the connectors where the user wanted them. Tell the user what to look at.

## 8. Hand over the files

Give the user the files from the output directory, named as in step 2:

- **3MF**: ready to slice, in print orientation centred on a 256 mm build plate
- **STL**: the same, for slicers that do not read 3MF
- **STEP**: for changing the shape in CAD

Say what is not verified: a new board's bracket has never been printed, its board is simplified to boxes, and the dimensions are only as good as the official source you name.
Print it in PETG without supports (README "Printing").

The generated files are not committed (`models/` is in `.gitignore`). Release files are built by the repository's workflow when a maintainer pushes a version tag; never create tags or releases yourself.

## 9. Contributing the board

If the user wants the board in the project, open a pull request with `boards/<Name>.json`, its rows in the README's "Supported boards" and "Download" tables, and its source in section 7 of `DESIGN_NOTES.md`. The pull request runs `--check` for every model. The download links work once a maintainer has published the next release.
