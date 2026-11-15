# Security Policy

## Reporting a vulnerability

Please report security problems privately through
[GitHub's private vulnerability reporting](https://github.com/koedame/sbc-frame-brackets/security/advisories/new).
Do not open a public issue for them.
We will reply within 7 days to confirm that we received your report, and keep you updated until it is fixed.

## Supported versions

Security fixes go into the `main` branch and the next release. Older releases are not updated.

## What counts as a vulnerability

The scripts run on your own computer. They read the files you give them and write the models to the output directory. `viewer.html` is a single
file that works offline: it loads nothing from the network and sends nothing anywhere. We treat these as
vulnerabilities:

- `viewer.html` loading or running anything that is not embedded in the file, or sending data anywhere.
- The GitHub Actions workflow exposing its token, or a pull request being able to change a release.
- A release with files that were not built by the workflow from the tagged commit.
- A pinned dependency in `requirements.txt` with a known vulnerability that affects how these scripts use it.

Problems with the shape of a bracket (a board that does not fit, a grip that is too weak) are not security
problems. Please open a normal issue for those.
