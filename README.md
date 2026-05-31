# PulseOx — local pulse-oximetry monitoring stack (tested with LPOW A340B-LK)

PulseOx records SpO₂ and pulse rate from a BLE pulse oximeter and turns it into
something you can watch live and analyse afterwards. It has three parts:

- **`pulseox/`** — a Python BLE package + CLI: scan, connect, decode, and record
  to CSV, with **duration-authoritative** timing and **automatic reconnection**
  so a timed recording runs the full duration and survives link drops.
- **`pulseox_server/`** — a local FastAPI service that wraps the package: REST
  control (`scan` / `start` / `stop` / `sessions` / `upload`) plus a WebSocket
  live stream.
- **`frontend/`** — an "aeromedical instrument console" (Next.js + TypeScript):
  a **Live** mode to control the device and watch realtime gauges, and an
  **Analysis** mode to import recordings and explore them with publication-grade
  charts.

Research / education only — not for diagnosis, treatment, or clinical decisions.

## Disclaimer (medical / safety)

This project is a research/education tool. It is not medical advice and is not intended for diagnosis, treatment, or clinical decision-making. If you publish this repo, be careful with wording that implies medical intended use; regulatory status can depend heavily on intended use/claims.

## Evidence-based limitations of pulse oximetry

Pulse oximeters estimate functional arterial oxygen saturation (SpO2) using optical absorption. SpO2 is an estimate of arterial oxygen saturation (SaO2) and does not directly measure oxygen content or fractional saturation. Accuracy depends on device calibration, signal quality, and physiologic conditions.

Known limitations and bias sources (see references):

- Skin pigmentation and low perfusion can increase positive bias and missed hypoxemia in low-SaO2 ranges.
- Motion artifact, low perfusion, and ambient light interference can degrade signal quality and increase error.
- Dyshemoglobinemias (carboxyhemoglobin, methemoglobin) and hemoglobin variants can distort SpO2 because standard pulse oximeters estimate functional saturation rather than fractional saturation.
- FDA notes that OTC/wellness pulse oximeters may be less accurate and lists risk factors (skin pigmentation, poor circulation, skin temperature, nail polish, tobacco use); readings should not be the sole basis for diagnosis or treatment decisions.

References:

- Leon-Valladares D, et al. "Determining factors of pulse oximetry accuracy: a literature review." (2024). https://doi.org/10.1016/j.rceng.2024.04.005
- Gudelunas MK, et al. "Low perfusion and missed diagnosis of hypoxemia by pulse oximetry in darkly pigmented skin: a prospective study." (2022). https://doi.org/10.1213/ANE.0000000000006755
- Al-Beltagi M, et al. "Pulse oximetry in pediatric care: Balancing advantages and limitations." (2024). https://doi.org/10.5409/wjcp.v13.i3.96950
- FDA safety communication (Feb 19, 2021): https://www.fda.gov/news-events/fda-brief/fda-brief-fda-warns-about-limitations-and-accuracy-pulse-oximeters

## Architecture

```
                 ┌─────────────────────────────────────────────┐
   BLE oximeter  │  pulseox/ (Python)                           │
  ───notify────► │   ble.py · decode.py · record.py · streaming │
  (A340B-LK)     │   deadline-bounded loop + reconnect supervisor│
                 └───────────────┬───────────────┬─────────────┘
                        CLI ─────┘               │ imported by
                 (python -m pulseox.cli)         ▼
                                   ┌──────────────────────────────┐
                                   │ pulseox_server/ (FastAPI)     │
                                   │  REST: scan/start/stop/...    │
                                   │  WebSocket: /ws/stream        │
                                   └───────┬───────────────┬──────┘
                                  REST/WS  │               │ writes
                                           ▼               ▼
                            ┌────────────────────┐   sessions/*.csv
                            │ frontend/ (Next.js) │
                            │  Live · Analysis    │
                            └────────────────────┘
```

The browser cannot speak BLE, so the **backend must run on the machine with the
Bluetooth adapter**. The CLI and the backend share the same `pulseox` core, so a
recording made either way produces the identical CSV schema.

## Quick start

### Option A — full UI (control + live + analysis)

```bash
# 1) install
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt   # or: conda env create -f environment.yml
cd frontend && npm install && cd ..

# 2) run (two terminals)
python -m pulseox_server          # backend → http://127.0.0.1:8000
cd frontend && npm run dev        # console → http://localhost:3000
```

Open http://localhost:3000, set the device address in **Live**, and Start.

### Option B — headless CLI recording

```bash
python -m pulseox.cli --address "FF:FF:FF:FF:00:21" --csv session.csv \
  --csv-overwrite --duration 600 --quiet
```

Then drop `session.csv` into the console's **Analysis** mode (or `--csv` path it
into `sessions/`).

## Requirements

- BLE-capable host (Linux/BlueZ, Windows/WinRT, or macOS) with Bluetooth enabled
- Python 3.11 (`pip install -r requirements.txt`, or conda via `environment.yml`)
- Node 18+ and npm (for the `frontend/` console)

## Backend service (FastAPI + WebSocket)

The `pulseox_server/` package is a local control plane that lets the TypeScript
UI scan, connect to, and record from the device, and stream live samples over a
WebSocket. It must run on the machine with the Bluetooth adapter (the browser
cannot speak BLE directly).

```bash
python -m pulseox_server          # serves http://127.0.0.1:8000
```

Endpoints (all under `/api`): `GET /health`, `GET /status`, `POST /scan`,
`POST /recording/start`, `POST /recording/stop`, `GET /sessions`,
`GET /sessions/{name}`, `POST /upload`, and `WS /ws/stream` for live
`{"type":"sample"|"status", ...}` frames. Recordings are written to `sessions/`
(override with `PULSEOX_SESSIONS_DIR`). Sample/`sessions` payloads match the
`PulseOxSample` shape the frontend expects.

Example: start a 5-minute recording from Diego's device, then stop it:

```bash
curl -X POST http://127.0.0.1:8000/api/recording/start \
  -H 'content-type: application/json' \
  -d '{"address":"FF:FF:FF:FF:00:21","duration_s":300}'
curl -X POST http://127.0.0.1:8000/api/recording/stop
```

## Console (TypeScript/Next.js)

An "aeromedical instrument console" frontend lives in `frontend/`. It talks to the
local FastAPI backend (above) and has two modes:

- **Live** — control the device from the browser (scan, address, duration,
  sample rate, auto-reconnect, start/stop) and watch realtime SpO₂ and
  heart-rate **instrument gauges** plus a live trace, streamed over WebSocket.
- **Analysis** — import a recorded session (drag/drop a CSV, or pick one
  recorded on the host) and explore it: session statistics, SpO₂
  oxygenation-burden (time-in-zone), dual-axis trend, value distributions,
  SpO₂ × HR correlation, a heart-rate Poincaré return map, and a sample log.

### Quick Start

```bash
# terminal 1 — backend (must run on the machine with the BLE adapter)
python -m pulseox_server

# terminal 2 — frontend
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. The frontend reaches the backend at
`http://127.0.0.1:8000` by default; override with `NEXT_PUBLIC_API_BASE`.

### Build for Production

```bash
cd frontend
npm run build
npm start
```

### Technology Stack

- **Next.js 14** (App Router) + **TypeScript** + **Tailwind CSS**
- **ECharts** for charts; custom SVG instrument gauges
- **IBM Plex Sans / Mono** typography
- Live data over **WebSocket** from the FastAPI backend

### Oximetry report

When a session is loaded from the backend (host session, or a drag/drop file
while the backend is running), Analysis shows a server-computed **oximetry
report**: nadir / mean SpO₂, **T90 / T88** (time below 90% / 88%, integrated over
real timestamps with reconnect gaps excluded), recording coverage, HR summary,
and **ODI** (oxygen desaturation index). ODI is **rate-gated** — if the effective
sampling rate is too coarse to resolve desaturations (e.g. the 0.2 Hz validated
sample) it is reported as `n/a` with the reason, rather than a misleading number.
All metric definitions live in one place, `pulseox/analysis.py`.

### Exporting figures

- **In-app:** every Analysis chart has `⤓ SVG / PNG` controls that export the
  rendered figure client-side (vector SVG, or rasterized PNG).
- **Journal-quality (offline):** render publication figures from a session with
  the `echarts` skill — themed for Nature / NEJM / Lancet / Cell / JAMA, vector
  SVG (or 300 DPI PNG). A ready example option lives at
  `docs/figures/pulseox_trend_option.json`:

  ```bash
  SKILL=/root/.claude/skills/echarts
  node "$SKILL/render.js" --option docs/figures/pulseox_trend_option.json \
    --theme nejm --width 800 --height 500 \
    --out pulseox-trend-nejm.svg
  ```

  The backend is **not** coupled to this Node renderer — it stays a clean local
  Python service.

## Manual / usage

### 1) Scan and pick a device interactively

```bash
python -m pulseox.cli --scan --sort-rssi
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

- `--duration`: how long to record (seconds). **Authoritative bound** — the run
  lasts the full duration regardless of notification rate.
- `--max-notifications`: opt-in safety ceiling on *raw* notifications; **`0`
  (default) disables it**. (Previously defaulted to `1000`, which could end a
  timed run early because high-rate waveform packets are counted before they are
  filtered out.)
- `--reconnect` / `--no-reconnect`: on a dropped BLE link, re-scan, reconnect,
  resubscribe, and resume appending to the same CSV until the duration elapses
  (default: on).
- `--max-reconnect-attempts`: bounded consecutive reconnect attempts (default 5).
- `--timeout`: per-operation BLE timeout (seconds)
- `--poll-interval`: internal bounded loop sleep (seconds)

At the end of a run the CLI prints a summary line:
`Session ended (deadline): rows=<n> reconnects=<n> gap=<seconds>s`.

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

Other packet types (commonly `0xF0` and `0xF2`) appear to be waveform/metadata. The recorder filters these out for CSV rows so you don’t get garbage samples.

### Generic mode (other devices)

For other devices, `pulseox.decode` can fall back to a generic 5-byte heuristic (common across some consumer oximeters). Many devices embed headers/footers or use a different framing scheme; in that case you may see `remainder=` and/or implausible frames.

If you want to support another model:

1. Run `--auto-notify --print-gatt`
2. Capture raw notification payloads (the `data=` lines)
3. Update `pulseox.decode` (frame length, header parsing, checksum, etc.)

## Troubleshooting

### Linux permissions (scan works, connect/read fails)

If `--scan` sees your device but connect/read fails on Linux, try:

```bash
# 1) Add your user to bluetooth group (log out/in after)
sudo usermod -aG bluetooth $USER

# 2) Ensure Bluetooth is unblocked and service is running
rfkill unblock bluetooth
sudo systemctl status bluetooth
```

Some devices require pairing/trusting before GATT reads:

```bash
bluetoothctl
power on
agent on
default-agent
pair FF:FF:FF:FF:00:21
trust FF:FF:FF:FF:00:21
connect FF:FF:FF:FF:00:21
quit
```

Then retry:

```bash
python -m pulseox.cli --address "FF:FF:FF:FF:00:21" --print-gatt
```

- Many oximeters only emit notifications while actively measuring (finger inserted).
- If you see no data:
  - try `--auto-notify` (some models notify on a different UUID)
  - increase `--timeout` (Windows/WinRT can be slow at service discovery)
- `--auto-notify` skips `00002a05-0000-1000-8000-00805f9b34fb` (GATT Service Changed, `indicate`),
  because on Windows it often fails with `PermissionError(13, 'Access is denied', ...)` and it is not oximeter data.
- Notifications are bounded by `--duration` and `--max-notifications` to keep execution finite.

## Open-source publishing & legal notes

## This section is general information, not legal advice.

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

Python (`pulseox/`, `pulseox_server/`):

- Lint: `python -m ruff check pulseox pulseox_server tests`
- Typecheck: `python -m pyright` (strict; run inside the project venv/conda env)
- Tests: `pytest` — covers decoding, CSV recording, the deadline/reconnect
  streaming core, the recorder, the backend session manager, and the FastAPI
  routes (incl. a WebSocket stream test) using injected fakes — no hardware
  required.

Frontend (`frontend/`):

- Lint: `npm run lint` · Types: `npm run type-check` · Build: `npm run build`

### Repository layout

| Path | What |
|---|---|
| `pulseox/` | BLE package + CLI (`ble`, `decode`, `record`, `streaming`, `cli`, `dashboard_data`, `clean_csv`) |
| `pulseox_server/` | FastAPI backend (`app`, `session`, `hub`, `config`, `__main__`) |
| `frontend/` | Next.js + TypeScript console (Live + Analysis) |
| `tests/` | pytest suite |
| `docs/superpowers/` | design specs + implementation plans |
