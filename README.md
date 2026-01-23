# PulseOx — BLE reader for pulse oximeters (tested with LPOW A340B-LK)

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
python -m pulseox.cli --address "FF:FF:FF:FF:00:21"
```

### 3) Print GATT (services/characteristics)
```bash
python -m pulseox.cli --address "FF:FF:FF:FF:00:21" --print-gatt
```
Note: `--print-gatt` exits unless you also set `--auto-notify` or `--notify-uuid`.

### 4) Subscribe and decode notifications

Option A (recommended for discovery): subscribe to all notify/indicate characteristics and print the GATT listing
```bash
python -m pulseox.cli --address "FF:FF:FF:FF:00:21" --auto-notify --print-gatt --duration 30
```

Option B: subscribe to a specific characteristic UUID

Default for the tested LPOW A340B-LK:
- Service: `0000fff0-0000-1000-8000-00805f9b34fb`
- Notify characteristic: `0000fff6-0000-1000-8000-00805f9b34fb`

```bash
python -m pulseox.cli --address "FF:FF:FF:FF:00:21" --notify-uuid 0000fff6-0000-1000-8000-00805f9b34fb --duration 30
```

Other devices:
Some consumer oximeters expose UART-like characteristics. One observed TX UUID is:
`49535343-1e4d-4bd9-ba61-23c647249616`

```bash
python -m pulseox.cli --address "FF:FF:FF:FF:00:21" --notify-uuid 49535343-1e4d-4bd9-ba61-23c647249616 --duration 30
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
python -m pulseox.cli --address "FF:FF:FF:FF:00:21" --csv session.csv --duration 300 --quiet
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
- `raw_frame_hex`: dash-separated hex of the selected measurement frame (device-dependent; A340B-LK uses `f1 ...`)
- `raw_notification_hex`: dash-separated hex of the full notification payload
- `remainder_hex`: dash-separated hex of leftover bytes when payload length is not a multiple of the frame length (generic 5-byte mode)

### Examples (copy/paste)

Example 1 — scan, select a device, and record 5 minutes to a new CSV:
```bash
python -m pulseox.cli --scan --csv session.csv --csv-overwrite --duration 300 --quiet
```

Example 2 — record 10 minutes from a known address (default 1 Hz sampling):
```bash
python -m pulseox.cli --address "FF:FF:FF:FF:00:21" --csv session.csv --csv-overwrite --duration 600 --quiet
```

Example 3 — long run with lower write rate (0.5 Hz) to reduce overhead:
```bash
python -m pulseox.cli --address "FF:FF:FF:FF:00:21" --csv long_run.csv --csv-overwrite --sample-hz 0.5 --duration 3600 --quiet
```

Example 4 — append multiple sessions into the same CSV file:
```bash
python -m pulseox.cli --address "FF:FF:FF:FF:00:21" --csv study.csv --csv-append --duration 300 --quiet
```

Example 5 — debug capture (no rate limit + include implausible frames):
```bash
python -m pulseox.cli --address "FF:FF:FF:FF:00:21" --csv debug.csv --csv-overwrite --sample-hz 0 --include-implausible --duration 60
```

Example 6 — discovery mode: subscribe to all notify/indicate characteristics, print GATT, and still record:
```bash
python -m pulseox.cli --address "FF:FF:FF:FF:00:21" --auto-notify --print-gatt --csv discover.csv --csv-overwrite --duration 30 --quiet
```

Example 7 — record validated samples (~every 5 seconds) for 60 seconds (0.2 Hz), flushing each row (PowerShell):
```powershell
python -m pulseox.cli --address "FF:FF:FF:FF:00:21" `
  --csv validated_60s.csv --csv-overwrite `
  --duration 60 --sample-hz 0.2 --csv-flush-every 1 `
  --quiet --timeout 15
```

Example 8 — programmatic recording (Python): save as `record_validated_60s.py`, then run `python record_validated_60s.py`:
```python
from __future__ import annotations

import asyncio
from typing import Final

from pulseox.ble import stream_notifications
from pulseox.record import PulseOxCsvRecorder, open_csv_path

A340B_LK_NOTIFY_UUID: Final[str] = "0000fff6-0000-1000-8000-00805f9b34fb"


def _require_positive(value: float, name: str) -> float:
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


async def record_validated(
    *,
    address: str,
    out_csv: str,
    duration_s: float = 60.0,
    interval_s: float = 5.0,
    timeout_s: float = 15.0,
) -> None:
    if not address:
        raise ValueError("address must be non-empty")
    if not out_csv:
        raise ValueError("out_csv must be non-empty")

    _require_positive(duration_s, "duration_s")
    _require_positive(interval_s, "interval_s")
    _require_positive(timeout_s, "timeout_s")

    sample_hz = 1.0 / interval_s

    opened = open_csv_path(out_csv, append=False, overwrite=True)
    recorder = PulseOxCsvRecorder(
        opened.file,
        write_header=opened.write_header,
        sample_hz=sample_hz,  # 0.2 Hz => ~every 5 seconds
        include_implausible=False,  # only plausible/validated
        flush_every=1,  # flush each row
    )

    def on_payload(sender: object, data: bytes) -> None:
        recorder.on_notification(sender=sender, data=data)

    try:
        await stream_notifications(
            address=address,
            notify_uuids=[A340B_LK_NOTIFY_UUID],
            auto_notify=False,
            run_seconds=duration_s,
            max_notifications=100_000,  # bounded
            poll_interval=0.2,
            timeout_s=timeout_s,
            on_payload=on_payload,
        )
    finally:
        recorder.close()
        opened.file.close()


def main() -> None:
    asyncio.run(
        record_validated(
            address="FF:FF:FF:FF:00:21",
            out_csv="validated_60s.csv",
            duration_s=60.0,
            interval_s=5.0,
            timeout_s=15.0,
        )
    )


if __name__ == "__main__":
    main()
```

### 7) Re-decode / clean an existing CSV (A340B-LK)
Older CSVs recorded with a generic 5-byte frame decoder can contain obviously wrong values (e.g. HR stuck at 128, SpO2 at 0/100), because A340B-LK sends its measurements in `0xF1` packets.

Use the included re-decoder/cleaner to produce a new CSV with corrected values and cleaning flags:
```bash
python -m pulseox.clean_csv session.csv --out session_clean.csv
```

This writes `session_clean.csv` with extra columns:
- `packet_type_hex`: first byte of the notification payload (`f1`, `f0`, `f2`, ...)
- `spo2_redecoded`, `pulse_redecoded`: re-decoded values for `f1` packets
- `keep`: `1` if the sample passed filters, else `0`
- `spo2_clean`, `pulse_clean`: forward-filled cleaned series (bounded)
- `drop_reason`: why a sample was rejected

Tuning (examples):
- tighter spike rejection: `--max-dpulse 10 --max-dspo2 3`
- tighter baseline window: `--max-pulse-dev 15 --max-spo2-dev 4`

## Output format
For each BLE notification the CLI prints something like:
- `[timestamp] from=<handle|uuid> len=<n> data=<hex-bytes>`
- One or more decoded frames:
  - `SpO2=<percent>%  Pulse=<bpm>bpm  PI=<0-15>  [OK|?]`
- `remainder=<hex>` if the payload is not a clean multiple of the frame length

`[OK]` means the decoded values passed basic plausibility checks (SpO2 0–100, pulse 20–250, PI 0–15). `[?]` means it did not.

## Decoder notes

### A340B-LK
The tested LPOW A340B-LK emits measurement notifications as `0xF1` packets:
- `f1 <spo2_percent> <pulse_bpm> ...`

Other packet types (commonly `0xF0` and `0xF2`) may be waveform-like data and/or device metadata and should **not** be interpreted as SpO2/HR.

### Generic mode (other devices)
For other devices, `pulseox.decode` can fall back to a generic 5-byte heuristic (common across some consumer oximeters). Many devices embed headers/footers or use a different framing scheme; in that case you may see `remainder=` and/or implausible frames.

If you want to support another model:
1. Run `--auto-notify --print-gatt`
2. Capture raw notification payloads (the `data=` lines)
3. Update `pulseox.decode` (frame length, header parsing, checksum, etc.)

## Troubleshooting
- Many oximeters only emit notifications while actively measuring (finger inserted).
- If you see no data:
  - try `--auto-notify` (some models notify on a different UUID)
  - increase `--timeout` (Windows/WinRT can be slow at service discovery)
- `--auto-notify` skips `00002a05-0000-1000-8000-00805f9b34fb` (GATT Service Changed, `indicate`),
  because on Windows it often fails with `PermissionError(13, 'Access is denied', ...)` and it is not oximeter data.
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
