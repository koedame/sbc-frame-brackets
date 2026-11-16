# Board definitions

One JSON file per board. `build_all.py` reads every file in this directory, so adding a board means adding a file; no code changes.
The file name is the board's name: `PiB.json` is what `--board PiB` builds, and every output file starts with it (`PiB_2020_spacer.3mf`). Use letters and digits only.

The simplest complete example is [`PiA.json`](PiA.json). [`VIM1S.json`](VIM1S.json) has rows of windows and a notch, [`BBB.json`](BBB.json) has many parts, [`N2Plus.json`](N2Plus.json) is held by its heatsink rather than the board.

## Coordinates

All lengths are in mm, in the board's own **top view**: you look at the side that faces away from the bracket, as on most manufacturers' drawings.

- `l` runs along one side, from 0 to `L`: the side whose edge should face the back plate, usually the long side (the orientation names assume it is). The plate is `L` tall in upright portrait.
- `s` runs along the other side, from 0 to `S`.
- The axes are right-handed: with `l` growing to the right, `s` grows upwards. Never mirror them. If the drawing's y axis points down, as in KiCad, use `s = S - y`.
- `frame_edge` is the edge along `l` that faces the back plate (the frame), either `"s=0"` or `"s=S"`.
  Turn the drawing so that this edge is at the bottom. The end now on the right is at the top in upright portrait, and faces the frame in upright landscape and shelf portrait.
- Heights `h` start from the top of the standoffs, which is the underside of the board for a board on standoffs. Parts under the board have negative heights; a part 8.5 mm tall on top of a 1.6 mm board is `1.6, 10.1`.

## Fields

| Field | Required | What it is |
|---|---|---|
| `title` | yes | The boards it fits, as shown in the viewer, e.g. `"Raspberry Pi 3 A+ / 1 A+"` |
| `notes` | no | List of strings. Where each dimension comes from (which official drawing or 3D model, and its revision), and why the standoffs, notches and openings are what they are. JSON has no comments, so they go here |
| `size` | yes | `[L, S]`, the board outline |
| `frame_edge` | yes | `"s=0"` or `"s=S"`, see above |
| `microsd_edge` | no | The edge the microSD card comes out of: `"l=0"`, `"l=L"`, `"s=0"` or `"s=S"`. Leave it out if there is no slot. When it is the end that faces the frame in upright landscape and shelf portrait, those brackets keep the board 17 mm (`SD_GAP`) off the back plate so that a finger reaches the card |
| `holes` | yes | `[[l, s], ...]`, the mounting holes. Every one must be on the board |
| `hole_d` | yes | Diameter of the through holes in the version without standoffs (3.0 for M2.5 and M3 screws, 2.4 for M2 as on `NanoKVMDesk`) |
| `standoffs` | yes | Integrated standoffs (bosses) of the `_spacer` version, see below |
| `openings` | no | `[[l0, l1, s0, s1], ...]`, rectangles cut through the plate, with 3 mm corner radius. Let one start 4 mm outside the outline (`-4`, or `L + 4`) to make a notch open at that edge, for example 11 to 15 mm deep so that a finger reaches a microSD card under the board, or for a connector under the board. Keep openings clear of the standoffs |
| `windows` | no | `{"rows": [[s0, s1], ...], "per_row": 3}`: rows of lightening windows. Each row has `per_row` windows between `l = 6` and `l = L - 6`, 6 mm apart. Keep the rows clear of the standoffs |
| `parts` | yes | `[{"name": "...", "box": [l0, l1, s0, s1, h0, h1]}, ...]`: the board, simplified to boxes. Include the PCB itself, `[0, L, 0, S, 0, <thickness>]`, and everything that comes near the bracket: parts under the board, connectors that stick out past the edges, the microSD card. The parts do not change the bracket; `--check` reports any overlap with it as a failure, and the viewer shows them |
| `official_models` | no | The manufacturer's 3D models this board fits, used by `--board-step` instead of `parts`, see below |

### `standoffs`

| Field | Required | What it is |
|---|---|---|
| `h` | yes | Height above the plate. The board sits at this height in every version, for display and the checks |
| `d` | yes | Outer diameter |
| `pilot` | yes | Pilot hole diameter for a self-tapping screw (2.2 for M2.5, 2.6 for M3, 1.7 for M2) |
| `screw` | yes | Screw shown in the viewer, e.g. `"M2.5"` |
| `foot` | no | `[height, diameter]` of a wider base under a standoff that has to be slim further up |
| `through` | no | For screws that go from under the plate through the standoffs, what they screw into (shown in the viewer), e.g. `"heatsink"` |
| `at` | no | `[[l, s], ...]`, the holes that get standoffs, when not all of them do. Each one must be in `holes` |

Make the standoffs tall enough that the deepest part under the board clears the plate, and narrow enough to miss the nearest part around each hole. The `notes` of the existing definitions say how they chose theirs.

### `official_models`

```json
"official_models": {
  "<file name>": {"rotate": 0, "centre": [41.5, 28.0], "underside": 0.0}
}
```

The key is the file name as the manufacturer publishes it; `--board-step <path>` recognises the file by that name. All numbers are in the file's own coordinates:

| Field | What it is |
|---|---|
| `tilt` | Optional. Degrees about the file's x axis, applied first, for a model whose z axis is not up |
| `rotate` | Degrees about z, counter-clockwise seen from above, that turn the file's x and y axes into the `l` and `s` directions |
| `centre` | The point (after `tilt`) that goes to the centre of the outline, `(L/2, S/2)` |
| `underside` | z (after `tilt`) of what sits on the standoffs: the PCB's underside, or for a board held by its heatsink, the underside of the heatsink's base |
| `exclude` | Optional. `["<name>", ...]`, top-level parts of the file to leave out because they are not on the board when it is on a bracket, such as the case base a developer kit comes screwed to and its screws. Each name is a top-level part's name in the STEP file and must be in it |

Check the placement with `python build_all.py --board <board> --format step --check --board-step <file>`: every model must report a board overlap of 0. Never commit the manufacturer's files, or anything converted from them.
