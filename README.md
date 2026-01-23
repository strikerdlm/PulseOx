# PulseOx — BLE reader for pulse oximeters (tested with LPOW A340B)

Minimal Python CLI that scans BLE devices, prints GATT services/characteristics, subscribes to notify/indicate characteristics, and prints raw + best-effort decoded SpO2/pulse frames.

## Disclaimer (medical / safety)
This project is a research/education tool. It is not medical advice and is not intended for diagnosis, treatment, or clinical decision-making. If you publish this repo, be careful with wording that implies medical intended use; regulatory status can depend heavily on intended use/claims.

## What it does (summary)
- Scan nearby BLE devices (`--scan`)
- Optionally prompt you to select a device to connect
- Print GATT services/characteristics (`--print-gatt`)
- Subscribe to:
  - a specific notify characteristic (`--notify-uuid ...`), or
  - all notify/indicate characteristics (`--auto-notify`) for discovery
- Print:
  - timestamp + sender + raw payload hex
  - decoded frames with a basic plausibility tag

All streaming loops are bounded by `--duration` and `--max-notifications`.

## Requirements
- Windows with BLE support enabled
- conda (recommended)
- Python 3.11 (see `environment.yml`)

## Setup (conda)
```bash
conda env create -f environment.yml
conda activate pulseox
```

## Manual / usage

### 1) Scan and pick a device interactively
```bash
python -m pulseox.cli --scan
```
If you do not pass `--address`, the CLI will prompt for a device index.

### 2) Connect directly if you already know the address
```bash
python -m pulseox.cli --address "AA:BB:CC:DD:EE:FF"
```

### 3) Print GATT (services/characteristics)
```bash
python -m pulseox.cli --address "AA:BB:CC:DD:EE:FF" --print-gatt
```
Note: `--print-gatt` exits unless you also set `--auto-notify` or `--notify-uuid`.

### 4) Subscribe and decode notifications

Option A (recommended for discovery): subscribe to all notify/indicate characteristics and print the GATT listing
```bash
python -m pulseox.cli --address "AA:BB:CC:DD:EE:FF" --auto-notify --print-gatt --duration 30
```

Option B: subscribe to a specific characteristic UUID

The default UART-like TX UUID in this repo is:
`49535343-1e4d-4bd9-ba61-23c647249616`

```bash
python -m pulseox.cli --address "AA:BB:CC:DD:EE:FF" --notify-uuid 49535343-1e4d-4bd9-ba61-23c647249616 --duration 30
```

### 5) Tuning runtime bounds/timeouts
- `--duration`: how long to listen (seconds)
- `--max-notifications`: stop after N notifications
- `--timeout`: per-operation BLE timeout (seconds)
- `--poll-interval`: internal bounded loop sleep (seconds)

### 6) CSV data collection
Use `--csv` to write **timestamped** decoded samples to a CSV file for analysis.

Recommended (stable, low-overhead) collection command:
```bash
python -m pulseox.cli --address "AA:BB:CC:DD:EE:FF" --csv session.csv --duration 300 --quiet
```

Notes:
- If `session.csv` already exists, you must choose one:
  - `--csv-append` to append (header is written only if the file is empty)
  - `--csv-overwrite` to overwrite
- Sampling control: `--sample-hz` limits how often rows are written (default **1.0 Hz** when `--csv` is set).
  - `--sample-hz 0` disables rate limiting (not recommended unless you really need every notification).
- By default the CSV includes **only plausible frames**. Use `--include-implausible` for debugging.

CSV columns:
- `timestamp_utc`: UTC ISO 8601 timestamp (millisecond resolution)
- `elapsed_s`: seconds since the recorder started (monotonic)
- `sender`: BLE sender/handle/UUID (best-effort)
- `spo2_percent`, `pulse_bpm`, `perfusion_index`
- `plausible`: `1` if basic plausibility checks passed, else `0`
- `raw_frame_hex`: dash-separated hex of the selected 5-byte frame
- `raw_notification_hex`: dash-separated hex of the full notification payload
- `remainder_hex`: dash-separated hex of leftover bytes when payload length is not a multiple of 5

### Examples (copy/paste)

Example 1 — scan, select a device, and record 5 minutes to a new CSV:
```bash
python -m pulseox.cli --scan --csv session.csv --csv-overwrite --duration 300 --quiet
```

Example 2 — record 10 minutes from a known address (default 1 Hz sampling):
```bash
python -m pulseox.cli --address "AA:BB:CC:DD:EE:FF" --csv session.csv --csv-overwrite --duration 600 --quiet
```

Example 3 — long run with lower write rate (0.5 Hz) to reduce overhead:
```bash
python -m pulseox.cli --address "AA:BB:CC:DD:EE:FF" --csv long_run.csv --csv-overwrite --sample-hz 0.5 --duration 3600 --quiet
```

Example 4 — append multiple sessions into the same CSV file:
```bash
python -m pulseox.cli --address "AA:BB:CC:DD:EE:FF" --csv study.csv --csv-append --duration 300 --quiet
```

Example 5 — debug capture (no rate limit + include implausible frames):
```bash
python -m pulseox.cli --address "AA:BB:CC:DD:EE:FF" --csv debug.csv --csv-overwrite --sample-hz 0 --include-implausible --duration 60
```

Example 6 — discovery mode: subscribe to all notify/indicate characteristics, print GATT, and still record:
```bash
python -m pulseox.cli --address "AA:BB:CC:DD:EE:FF" --auto-notify --print-gatt --csv discover.csv --csv-overwrite --duration 30 --quiet
```

## Output format
For each BLE notification the CLI prints something like:
- `[timestamp] from=<handle|uuid> len=<n> data=<hex-bytes>`
- One or more decoded frames:
  - `SpO2=<percent>%  Pulse=<bpm>bpm  PI=<0-15>  [OK|?]`
- `remainder=<hex>` if the payload is not a clean multiple of the frame length

`[OK]` means the decoded values passed basic plausibility checks (SpO2 0–100, pulse 20–250, PI 0–15). `[?]` means it did not.

## Decoder notes
`pulseox.decode` currently assumes the payload is a sequence of fixed 5-byte frames and applies heuristics observed in multiple consumer oximeters. Many devices embed headers/footers or use a different framing scheme; in that case you may see `remainder=` and/or implausible frames.

If you want to support another model:
1. Run `--auto-notify --print-gatt`
2. Capture raw notification payloads (the `data=` lines)
3. Update `pulseox.decode` (frame length, header parsing, checksum, etc.)

## Troubleshooting
- Many oximeters only emit notifications while actively measuring (finger inserted).
- If you see no data:
  - try `--auto-notify` (some models notify on a different UUID)
  - increase `--timeout` (Windows/WinRT can be slow at service discovery)
- Notifications are bounded by `--duration` and `--max-notifications` to keep execution finite.

## Open-source publishing & legal notes (read before making public)
This section is general information, not legal advice.

### 1) Add an explicit license before calling it “open source”
If you publish code without a license, default copyright laws apply and others generally cannot reuse/modify/distribute your code legally.
Pick a standard license (MIT/Apache-2.0/GPL-3.0, etc.) and add it as a `LICENSE` file at repo root.

References:
- GitHub: https://docs.github.com/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository
- Choose a License: https://choosealicense.com/licenses/
- OSI (Open Source definition / approved licenses): https://opensource.org/about/authority

### 2) Avoid distributing anything you don’t own
Keep the repo limited to your original code and documentation. Do not include:
- firmware dumps
- decompiled proprietary apps
- proprietary protocol docs copied from manuals/apps

### 3) Reverse engineering / interoperability (US DMCA context)
In the US, DMCA §1201 has anti-circumvention provisions, but it also contains statutory exceptions (e.g., reverse engineering for interoperability in 17 U.S.C. §1201(f)). Whether it applies depends on the facts—especially if any “technological protection measure” is being bypassed.

This project reads BLE notifications using standard OS BLE APIs and does not include circumvention tools, but be careful about features that bypass authentication/encryption or distribute keys.

Reference:
- 17 U.S.C. §1201 (Cornell LII): https://www.law.cornell.edu/uscode/text/17/1201

### 4) Trademarks and product names
Using a device model name to describe compatibility is usually fine, but avoid implying endorsement by the manufacturer. Consider phrasing like “tested with …”.

### 5) Medical/regulatory positioning (US)
In the US, whether software is a “medical device” depends heavily on intended use/claims. If you publish:
- keep language focused on interoperability, research, and education
- avoid medical claims (e.g., “diagnose”, “treat”, “clinical-grade”)
- include a clear “not for medical use” disclaimer

References:
- FDA (intended medical purpose): https://www.fda.gov/medical-devices/digital-health-center-excellence/step-1-software-function-intended-medical-purpose
- FDA (examples of software functions not medical devices): https://www.fda.gov/medical-devices/device-software-functions-including-mobile-medical-applications/examples-software-functions-are-not-medical-devices

### 6) Privacy
BLE addresses and health readings can be personal data. Avoid committing logs with real device identifiers or health data; consider a redaction approach for bug reports.

## License
Apache-2.0 (see `LICENSE`).

## Development
- Lint: `python -m ruff check .`
- Format: `python -m ruff format .`
- Typecheck: `python -m pyright`
- Tests: `pytest`
