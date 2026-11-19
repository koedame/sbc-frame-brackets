"""Arrange the files build_all.py wrote into the files attached to a release.

  python build_all.py --coupons --out models
  python pack_release.py --models models --out dist --version v0.11.0

What a release holds, and why it is cut this way:

  <bracket>.zip          one per bracket, because the board you have picks the bracket and nothing else does
    <bracket>/
      README.txt         what is in the zip and how to pick a file
      LICENSE.txt        CC BY 4.0
      <mount>/           2020, 4040, DIN35: what you mount it on, which you also know before you look
        3mf/ stl/ step/  the format your slicer or CAD program reads
          <bracket>_<mount>_<orientation>[_standoffs].<format>
                         what is left to choose: how the board sits, and whether the standoffs are printed with it
      cradle/            only for a board that snaps into a printed cradle: the cradle, the same for every mount
  fit-test-coupons.zip   the coupons for trying a clearance on your own extrusion before changing the fit
  viewer.html            every model in 3D, to look before downloading

Every file in --models has to end up in exactly one of these, and every model build_all.py makes has to be there, or nothing is
written (exit 1). layout() is the one place the folders are decided.
"""
import argparse, os, sys, zipfile
import sbc_brackets as sb
import build_all as ba

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = "https://github.com/koedame/sbc-frame-brackets"
MODEL_FORMATS = ("3mf", "stl", "step")
FORMAT_NOTES = {"3mf": "for slicers, already oriented and centred on the plate",
                "stl": "the same, for slicers that do not read 3MF",
                "step": "for CAD programs, to change the shape"}
ORIENT_NOTES = {"upright-portrait": "stands out from the frame, long side vertical (takes the least rail)",
                "upright-landscape": "stands out from the frame, long side pointing away from it",
                "flat-portrait": "parallel to the front of the frame, long side vertical",
                "flat-landscape": "parallel to the front of the frame, long side along the rail",
                "shelf-portrait": "lies on a shelf above the frame, long side pointing away from it",
                "shelf-landscape": "lies on a shelf above the frame, long side along the rail"}
COUPONS = "fit-test-coupons"
CREDIT = f"""License: CC BY 4.0, see LICENSE.txt. You can print, change and share these
files, also commercially, as long as you give credit: write
"SBC Frame Brackets by koedame, CC BY 4.0", link to
{REPO} and say if you changed anything."""


def layout():
    """-> {archive name: {path inside the archive: file name in the models directory}}, for every file build_all.py writes
    except viewer.html. README.txt and LICENSE.txt are added when the archives are written"""
    archives = {}
    for B in sb.BOARDS:
        files = {}
        for series in sb.SERIES:
            for orient in sb.ORIENTS:
                for spacer in (False, True):
                    if spacer and orient not in sb.SPACER_ORIENTS:
                        continue
                    n = ba.model_id(B, series, spacer, orient)
                    for fmt in MODEL_FORMATS:
                        files[f"{sb.mount_tag(series)}/{fmt}/{n}.{fmt}"] = f"{n}.{fmt}"
        if B.cradle_def:
            for fmt in MODEL_FORMATS:
                files[f"cradle/{B.name}_cradle.{fmt}"] = f"{B.name}_cradle.{fmt}"
        archives[B.name] = files
    archives[COUPONS] = {f: f for f in (f"fit_test_{sb.mount_tag(s)}_{i + 1}.stl"
                                        for s in sb.SERIES if s != "DIN" for i in range(len(sb.COUPON_FITS)))}
    return archives


def bracket_readme(B, version):
    name = B.name
    rows = lambda d: "\n".join(f"     {k:<{max(map(len, d))}}  {v}" for k, v in d.items())
    cradle = "" if not B.cradle_def else f"""
The board has no mounting holes: it snaps into the cradle in cradle/
({name}_cradle), which is screwed onto the bracket. Print one
cradle too. The same cradle fits every bracket in this zip.
"""
    return f"""SBC Frame Brackets {version} - {name}
{REPO}

Bracket for: {B.title}

Pick a file in three steps:

  1. The folder for what you mount it on
{rows({sb.mount_tag(s) + "/": sb.mount_label(s) for s in sb.SERIES})}

  2. In it, the folder for the format
{rows({f + "/": FORMAT_NOTES[f] for f in MODEL_FORMATS})}

  3. In it, the file for how the board sits
     {name}_<mount>_<orientation>[_standoffs]
{rows(ORIENT_NOTES)}

     _standoffs (upright only): the standoffs are printed as part of the plate.
     Without it, the plate has through holes for your own standoffs and screws.
{cradle}
Print the 3MF and STL files as they lie, without supports. Pictures of the
orientations, print settings, screw sizes and how to mount the bracket:
{REPO}#readme

{CREDIT}
"""


def coupons_readme(version):
    fits = "\n".join(f"  fit_test_<mount>_{i + 1}.stl  clearance {fit:.2f} mm, {i + 1} notch{'es' if i else ''}"
                     + ("  (what the brackets use)" if fit == sb.FIT else "") for i, fit in enumerate(sb.COUPON_FITS))
    return f"""SBC Frame Brackets {version} - fit test coupons
{REPO}

Short pieces of the grip that holds a bracket on an extrusion, in three
clearances. Print them and try them on your own extrusion before you change the
fit of the brackets (README, "Customising"). <mount> is 2020 for 20x20 extrusion
and 4040 for 40x40.

{fits}

{CREDIT}
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--models", default=os.path.join(HERE, "models"), help="where build_all.py --coupons wrote every model")
    ap.add_argument("--out", default=os.path.join(HERE, "dist"), help="where to write the release files (must not exist or be empty)")
    ap.add_argument("--version", default="(unreleased build)", help="the version to name in the README.txt of each zip")
    a = ap.parse_args()
    archives = layout()
    have = set(os.listdir(a.models))
    want = [f for files in archives.values() for f in files.values()] + ["viewer.html"]
    missing, extra = sorted(set(want) - have), sorted(have - set(want))
    twice = sorted({f for f in want if want.count(f) > 1})
    if missing or extra or twice:
        sys.exit(f"{a.models} does not hold exactly the files of a release: {len(missing)} missing {missing[:3]}, "
                 f"{len(extra)} that belong to no archive {extra[:3]}, {len(twice)} that layout() puts in two places {twice[:3]}")
    os.makedirs(a.out, exist_ok=True)
    if os.listdir(a.out):
        sys.exit(f"{a.out} is not empty")
    with open(os.path.join(HERE, "LICENSE-CC-BY-4.0.txt"), encoding="utf-8") as f:
        license_text = f.read()
    boards = {B.name: B for B in sb.BOARDS}
    for name, files in archives.items():
        readme = bracket_readme(boards[name], a.version) if name in boards else coupons_readme(a.version)
        with zipfile.ZipFile(os.path.join(a.out, name + ".zip"), "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(f"{name}/README.txt", readme)
            z.writestr(f"{name}/LICENSE.txt", license_text)
            for inside in sorted(files):
                z.write(os.path.join(a.models, files[inside]), f"{name}/{inside}")
        print(f"{name}.zip  {len(files)} files")
    with open(os.path.join(a.models, "viewer.html"), "rb") as src, open(os.path.join(a.out, "viewer.html"), "wb") as dst:
        dst.write(src.read())
    print(f"Wrote {len(archives)} zips and viewer.html to {a.out}")


if __name__ == "__main__":
    main()
