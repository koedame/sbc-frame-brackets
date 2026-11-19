# Contributing

Issues and pull requests are welcome, for example a board that is missing or a dimension that is wrong.

## What is accepted

- A new board or a corrected dimension. Take dimensions from the manufacturer's published drawings or 3D models, and write the source in the `notes` of the board's definition in `boards/` and in section 7 of [`DESIGN_NOTES.md`](DESIGN_NOTES.md). See "Customising" in the [README](README.md#customising) for how to add a board.
- Fixes to the scripts, the viewer and the documentation.
- Do not add the manufacturer's CAD files, or shapes converted from them, to the repository: most of them are not licensed for redistribution.
- Do not add code or data copied from another project unless its license allows it. Say where it comes from in the pull request.

## Before you open a pull request

- Run `python build_all.py --board <board> --check` for the brackets you changed. The pull request runs the same check for every model.
- Keep one change per pull request.

## License of your contribution

Your contribution is licensed under the same terms as the files it changes: [MIT](LICENSE) for the scripts and documentation, [CC BY 4.0](LICENSE-CC-BY-4.0.txt) for the models and images. By opening a pull request you agree to that. There is no contributor license agreement.

## Security problems

Report them privately as described in [`SECURITY.md`](SECURITY.md), not in an issue.
