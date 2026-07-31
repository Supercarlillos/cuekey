# Contributing to CueKey

Thanks for your interest in improving CueKey! Issues and pull requests are welcome.

## Development setup

```bash
git clone https://github.com/Supercarlillos/cuekey && cd cuekey
make dev        # creates .venv and installs in editable mode with dev extras
make test       # runs the pytest suite
```

Requirements: macOS, Python 3.11+ (`brew install python@3.13`), and `brew install ffmpeg` for MP3/M4A decoding. Run the desktop app from source with `.venv/bin/cuekey-gui` (use `CUEKEY_DEMO=1` for sample data, `CUEKEY_SMOKE=1` for a launch-and-exit check). Build the DMG with `make dmg`.

## Pull requests

1. Open an issue first for anything non-trivial, so we can discuss the approach.
2. Fork, create a feature branch, and keep PRs focused on one change.
3. Add or update tests — the suite must pass (`make test`). Analysis changes should include a synthesized-audio test (see `tests/conftest.py`; never commit copyrighted audio).
4. Match the existing style: type-hinted Python, English code/comments, no new dependencies without discussion.
5. UI changes: include a screenshot in the PR.

## Reporting bugs

Use the bug report template. For analysis quality issues (wrong key/BPM), include the track's genre and what the expected value was — ideally with a way to reproduce using synthesized or freely-licensed audio.

## Licensing of contributions

CueKey is licensed under [PolyForm Noncommercial 1.0.0](LICENSE). By submitting a contribution you agree that it is your own work and that you license it to the project under the same terms (inbound = outbound). Please sign off your commits (`git commit -s`) to certify the [Developer Certificate of Origin](https://developercertificate.org/).
