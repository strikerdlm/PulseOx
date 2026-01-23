from __future__ import annotations

import argparse
import csv
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

A340B_LK_MEASUREMENT_PREFIX = 0xF1


@dataclass(frozen=True, slots=True)
class CleanConfig:
    """Configuration for re-decoding and cleaning pulse-ox CSV data."""

    spo2_min: int
    spo2_max: int
    pulse_min: int
    pulse_max: int
    max_spo2_dev: int
    max_pulse_dev: int
    max_dspo2: int
    max_dpulse: int
    ffill_max_age_s: float


def _require_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int")
    return value


def _require_nonnegative_float(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, float | int):
        raise TypeError(f"{name} must be a float")
    fval = float(value)
    if not math.isfinite(fval) or fval < 0:
        raise ValueError(f"{name} must be finite and >= 0")
    return fval


def parse_dash_hex(value: object) -> bytes:
    """Parse dash-separated hex into bytes.

    Example:
        "f1-5c-46-00-5b-03-f0" -> b"\xf1\\x5c\\x46\\x00\\x5b\\x03\\xf0"
    """
    if not isinstance(value, str):
        raise TypeError("value must be a str")
    if not value:
        return b""

    parts = [p for p in value.split("-") if p]
    out = bytearray()
    for p in parts:
        try:
            out.append(int(p, 16))
        except ValueError as exc:
            raise ValueError(f"Invalid hex byte: {p!r}") from exc
    return bytes(out)


def packet_type_hex(payload: bytes) -> str:
    if not payload:
        return ""
    return f"{payload[0]:02x}"


def try_decode_a340b_lk_measurement(payload: bytes) -> tuple[int, int] | None:
    """Decode A340B-LK measurement from a notification payload.

    Observed format:
        f1 <spo2_percent> <pulse_bpm> ...

    Returns:
        (spo2_percent, pulse_bpm) if payload matches, else None.
    """
    if len(payload) < 3:
        return None
    if payload[0] != A340B_LK_MEASUREMENT_PREFIX:
        return None
    return int(payload[1]), int(payload[2])


def _parse_float_field(row: dict[str, str], field: str) -> float | None:
    raw = row.get(field, "")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _baseline_median(values: list[int], *, name: str) -> float:
    if not values:
        raise ValueError(f"No values available to compute {name} baseline")
    # statistics.median is deterministic and robust to a few outliers.
    return float(statistics.median(values))


def _validate_config(config: CleanConfig) -> None:
    _require_int(config.spo2_min, "spo2_min")
    _require_int(config.spo2_max, "spo2_max")
    _require_int(config.pulse_min, "pulse_min")
    _require_int(config.pulse_max, "pulse_max")
    _require_int(config.max_spo2_dev, "max_spo2_dev")
    _require_int(config.max_pulse_dev, "max_pulse_dev")
    _require_int(config.max_dspo2, "max_dspo2")
    _require_int(config.max_dpulse, "max_dpulse")
    _require_nonnegative_float(config.ffill_max_age_s, "ffill_max_age_s")


def _decode_prepass(
    rows: list[dict[str, str]],
) -> tuple[list[tuple[int | None, int | None, str]], dict[str, int], float, float]:
    decoded_spo2: list[int] = []
    decoded_pulse: list[int] = []
    per_row_decoded: list[tuple[int | None, int | None, str]] = []

    pkt_counts: dict[str, int] = {}

    for row in rows:
        payload = parse_dash_hex(row.get("raw_notification_hex", ""))
        pkt_hex = packet_type_hex(payload)
        if pkt_hex:
            pkt_counts[pkt_hex] = pkt_counts.get(pkt_hex, 0) + 1

        decoded = try_decode_a340b_lk_measurement(payload)
        if decoded is None:
            per_row_decoded.append((None, None, pkt_hex))
            continue

        spo2, pulse = decoded
        decoded_spo2.append(spo2)
        decoded_pulse.append(pulse)
        per_row_decoded.append((spo2, pulse, pkt_hex))

    baseline_spo2 = _baseline_median(decoded_spo2, name="SpO2")
    baseline_pulse = _baseline_median(decoded_pulse, name="pulse")

    return per_row_decoded, pkt_counts, baseline_spo2, baseline_pulse


def _assess_measurement(
    *,
    spo2: int,
    pulse: int,
    baseline_spo2: float,
    baseline_pulse: float,
    last_kept_spo2: int | None,
    last_kept_pulse: int | None,
    config: CleanConfig,
) -> tuple[bool, str]:
    if not (config.spo2_min <= spo2 <= config.spo2_max):
        return False, "spo2_out_of_range"
    if not (config.pulse_min <= pulse <= config.pulse_max):
        return False, "pulse_out_of_range"
    if abs(spo2 - baseline_spo2) > config.max_spo2_dev:
        return False, "spo2_far_from_baseline"
    if abs(pulse - baseline_pulse) > config.max_pulse_dev:
        return False, "pulse_far_from_baseline"
    if last_kept_spo2 is not None and abs(spo2 - last_kept_spo2) > config.max_dspo2:
        return False, "spo2_step_too_large"
    if last_kept_pulse is not None and abs(pulse - last_kept_pulse) > config.max_dpulse:
        return False, "pulse_step_too_large"

    return True, ""


def _forward_fill(
    *,
    elapsed: float | None,
    last_kept_elapsed: float | None,
    last_kept_spo2: int | None,
    last_kept_pulse: int | None,
    config: CleanConfig,
) -> tuple[int | None, int | None]:
    if elapsed is None or last_kept_elapsed is None:
        return None, None
    if last_kept_spo2 is None or last_kept_pulse is None:
        return None, None

    if (elapsed - last_kept_elapsed) > config.ffill_max_age_s:
        return None, None

    return last_kept_spo2, last_kept_pulse


def _augment_row(
    *,
    row: dict[str, str],
    pkt_hex: str,
    spo2: int | None,
    pulse: int | None,
    keep: bool,
    drop_reason: str,
    spo2_clean: int | None,
    pulse_clean: int | None,
) -> dict[str, str]:
    is_meas = spo2 is not None and pulse is not None

    out = dict(row)
    out.update(
        {
            "packet_type_hex": pkt_hex,
            "spo2_redecoded": "" if spo2 is None else str(spo2),
            "pulse_redecoded": "" if pulse is None else str(pulse),
            "is_measurement": "1" if is_meas else "0",
            "keep": "1" if keep else "0",
            "drop_reason": drop_reason,
            "spo2_clean": "" if spo2_clean is None else str(spo2_clean),
            "pulse_clean": "" if pulse_clean is None else str(pulse_clean),
        }
    )
    return out


def clean_a340b_lk_csv_rows(
    rows: list[dict[str, str]],
    *,
    config: CleanConfig,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Re-decode and clean CSV rows produced by pulseox.

    The input is expected to include pulseox's standard columns, including:
        - elapsed_s
        - raw_notification_hex

    Output:
        A new list of rows with extra columns appended:
            packet_type_hex
            spo2_redecoded
            pulse_redecoded
            is_measurement
            keep
            drop_reason
            spo2_clean
            pulse_clean
    """
    _validate_config(config)

    per_row_decoded, pkt_counts, baseline_spo2, baseline_pulse = _decode_prepass(rows)

    out_rows: list[dict[str, str]] = []

    last_kept_spo2: int | None = None
    last_kept_pulse: int | None = None
    last_kept_elapsed: float | None = None

    kept = 0
    dropped = 0
    measurements = 0

    for row, (spo2, pulse, pkt_hex) in zip(rows, per_row_decoded, strict=True):
        elapsed = _parse_float_field(row, "elapsed_s")

        keep = False
        drop_reason = ""

        if spo2 is not None and pulse is not None:
            measurements += 1
            keep, drop_reason = _assess_measurement(
                spo2=spo2,
                pulse=pulse,
                baseline_spo2=baseline_spo2,
                baseline_pulse=baseline_pulse,
                last_kept_spo2=last_kept_spo2,
                last_kept_pulse=last_kept_pulse,
                config=config,
            )

            if keep:
                kept += 1
                last_kept_spo2 = spo2
                last_kept_pulse = pulse
                last_kept_elapsed = elapsed
            else:
                dropped += 1

        if keep and spo2 is not None and pulse is not None:
            spo2_clean, pulse_clean = spo2, pulse
        else:
            spo2_clean, pulse_clean = _forward_fill(
                elapsed=elapsed,
                last_kept_elapsed=last_kept_elapsed,
                last_kept_spo2=last_kept_spo2,
                last_kept_pulse=last_kept_pulse,
                config=config,
            )

        out_rows.append(
            _augment_row(
                row=row,
                pkt_hex=pkt_hex,
                spo2=spo2,
                pulse=pulse,
                keep=keep,
                drop_reason=drop_reason,
                spo2_clean=spo2_clean,
                pulse_clean=pulse_clean,
            )
        )

    stats: dict[str, Any] = {
        "rows": len(rows),
        "measurements": measurements,
        "kept": kept,
        "dropped": dropped,
        "baseline_spo2": baseline_spo2,
        "baseline_pulse": baseline_pulse,
        "packet_counts": dict(sorted(pkt_counts.items())),
    }
    return out_rows, stats


def _read_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        if reader.fieldnames is None:
            raise ValueError("CSV file has no header")
        fieldnames = list(reader.fieldnames)
        rows: list[dict[str, str]] = []
        for row in reader:
            # DictReader values are str|None; normalize None to "".
            normalized: dict[str, str] = {k: (v if v is not None else "") for k, v in row.items()}
            rows.append(normalized)
        return rows, fieldnames


def _write_csv_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Re-decode and clean PulseOx CSV files for the LPOW A340B-LK "
            "(extracts measurements from F1 packets)."
        )
    )
    parser.add_argument("input_csv", help="Input CSV produced by pulseox")
    parser.add_argument("--out", required=True, help="Output CSV path")

    parser.add_argument("--spo2-min", type=int, default=80)
    parser.add_argument("--spo2-max", type=int, default=100)
    parser.add_argument("--pulse-min", type=int, default=35)
    parser.add_argument("--pulse-max", type=int, default=140)

    parser.add_argument("--max-spo2-dev", type=int, default=6)
    parser.add_argument("--max-pulse-dev", type=int, default=20)

    parser.add_argument("--max-dspo2", type=int, default=4)
    parser.add_argument("--max-dpulse", type=int, default=15)

    parser.add_argument(
        "--ffill-max-age-s",
        type=float,
        default=5.0,
        help="Forward-fill last kept measurement for up to this many seconds",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    in_path = Path(args.input_csv)
    out_path = Path(args.out)
    if in_path.resolve() == out_path.resolve():
        raise ValueError("--out must be different from input_csv")

    rows, input_fieldnames = _read_csv_rows(in_path)

    config = CleanConfig(
        spo2_min=int(args.spo2_min),
        spo2_max=int(args.spo2_max),
        pulse_min=int(args.pulse_min),
        pulse_max=int(args.pulse_max),
        max_spo2_dev=int(args.max_spo2_dev),
        max_pulse_dev=int(args.max_pulse_dev),
        max_dspo2=int(args.max_dspo2),
        max_dpulse=int(args.max_dpulse),
        ffill_max_age_s=float(args.ffill_max_age_s),
    )

    cleaned_rows, stats = clean_a340b_lk_csv_rows(rows, config=config)

    extra_fields = [
        "packet_type_hex",
        "spo2_redecoded",
        "pulse_redecoded",
        "is_measurement",
        "keep",
        "drop_reason",
        "spo2_clean",
        "pulse_clean",
    ]

    fieldnames = input_fieldnames + [f for f in extra_fields if f not in input_fieldnames]
    _write_csv_rows(out_path, cleaned_rows, fieldnames)

    print("\n== Clean summary ==")
    print(
        f"rows={stats['rows']} measurements={stats['measurements']} "
        f"kept={stats['kept']} dropped={stats['dropped']}"
    )
    print(
        f"baseline_spo2={stats['baseline_spo2']:.3f} "
        f"baseline_pulse={stats['baseline_pulse']:.3f}"
    )
    print(f"packet_counts={stats['packet_counts']}")
    print(f"wrote={out_path}")


if __name__ == "__main__":
    main()
