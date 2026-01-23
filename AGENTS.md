# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Repository purpose
PulseOx is a minimal Python CLI for scanning BLE devices, printing GATT services/characteristics, subscribing to notify/indicate characteristics, and printing raw + best-effort decoded SpO2/pulse frames (research/education; not medical use).

## Setup
This repo is conda-first.

```bash
conda env create -f environment.yml
conda activate pulseox
```

## Common commands
### Run the CLI
Run the module directly (there is no packaged console entrypoint):

```bash
python -m pulseox.cli --help
python -m pulseox.cli --scan
```

### Lint / format
```bash
python -m ruff check .
python -m ruff format .
```

### Typecheck
Pyright is configured in `pyproject.toml` (strict mode).

```bash
python -m pyright
```

### Tests
Pytest config lives in `pyproject.toml`.

```bash
pytest
```

Run one file:
```bash
pytest tests/test_decode.py
```

Run one test:
```bash
pytest tests/test_decode.py::test_decode_5byte_frame_basic
```

## High-level architecture
### Data flow
1. `pulseox/cli.py` parses CLI args, resolves a target device address (scan + optional interactive selection), and decides whether to print GATT and/or listen for notifications.
2. `pulseox/ble.py` handles the Bleak boundary:
   - scanning (`scan_devices`)
   - connecting + service discovery (`fetch_services`)
   - subscribing (`stream_notifications`) either to explicit UUIDs or, in `--auto-notify` mode, to all notify/indicate characteristics discovered from the active connection
   - running a bounded stream loop (`--duration`, `--max-notifications`, `--timeout`, `--poll-interval`)
3. Each notification callback in `pulseox/cli.py`:
   - logs timestamp/sender/raw hex
   - decodes via `pulseox/decode.py` (fixed 5-byte frame heuristic)
   - optionally records rows via `pulseox/record.py`

### Key modules (what to look at first)
- `pulseox/cli.py`: orchestration and UX (args, scan/select, wiring decode + recorder).
- `pulseox/ble.py`: all BLE I/O and time-bounded/retry behavior.
- `pulseox/decode.py`: frame splitting + decoding heuristic; emits `DecodedFrame` with a `plausible` flag.
- `pulseox/record.py`: CSV writing with safety controls (append/overwrite), rate limiting (`--sample-hz`), and “prefer plausible frames” selection.

### Tests
- `tests/test_decode.py` covers frame decoding and payload splitting.
- `tests/test_record.py` covers CSV rate limiting and plausible-frame selection logic.
