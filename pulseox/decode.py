from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DecodedFrame:
    """Decoded oximeter frame with basic plausibility checks."""

    spo2_percent: int
    pulse_bpm: int
    perfusion_index: int
    plausible: bool
    raw: bytes


# A340B-LK measurement notifications are observed as:
#   f1 <spo2> <pulse> ...
# where the remaining bytes appear to be device-specific metadata.
A340B_LK_MEASUREMENT_PREFIX = 0xF1


def _require_bytes(data: object, name: str) -> bytes:
    if not isinstance(data, bytes | bytearray):
        raise TypeError(f"{name} must be bytes or bytearray")
    return bytes(data)


def decode_5byte_frame(frame: bytes | bytearray) -> DecodedFrame:
    """
    Decode a common 5-byte oximeter frame.

    Heuristic format seen in multiple BLE oximeters:
      perfusion_index = frame[0] & 0x0F
      pulse_bpm = frame[3] | ((frame[2] & 0x40) << 1)
      spo2_percent = frame[4]

    Raises:
        TypeError: if frame is not bytes-like
        ValueError: if frame length is not 5
    """
    data = _require_bytes(frame, "frame")
    if len(data) != 5:
        raise ValueError("frame must be exactly 5 bytes")

    b0, _b1, b2, b3, b4 = data
    perfusion_index = b0 & 0x0F
    pulse_bpm = b3 | ((b2 & 0x40) << 1)
    spo2_percent = b4

    plausible = 0 <= spo2_percent <= 100 and 20 <= pulse_bpm <= 250 and 0 <= perfusion_index <= 15

    return DecodedFrame(
        spo2_percent=spo2_percent,
        pulse_bpm=pulse_bpm,
        perfusion_index=perfusion_index,
        plausible=plausible,
        raw=data,
    )


def split_payload(payload: bytes | bytearray, frame_len: int = 5) -> tuple[list[bytes], bytes]:
    """
    Split a payload into fixed-length frames and a remainder.

    Raises:
        TypeError: if payload is not bytes-like
        ValueError: if frame_len is not positive
    """
    data = _require_bytes(payload, "payload")
    if frame_len <= 0:
        raise ValueError("frame_len must be positive")

    full_len = (len(data) // frame_len) * frame_len
    frames: list[bytes] = []
    for off in range(0, full_len, frame_len):
        frames.append(data[off : off + frame_len])
    remainder = data[full_len:]
    return frames, remainder


def decode_payload(payload: bytes | bytearray) -> tuple[list[DecodedFrame], bytes]:
    """
    Decode a payload that may contain multiple 5-byte frames.

    Returns:
        (decoded_frames, remainder_bytes)
    """
    frames, remainder = split_payload(payload, frame_len=5)
    decoded: list[DecodedFrame] = []
    for frame in frames:
        decoded.append(decode_5byte_frame(frame))
    return decoded, remainder


def decode_a340b_lk_notification(payload: bytes | bytearray) -> DecodedFrame | None:
    """Decode an A340B-LK measurement notification.

    Observed format:
        f1 <spo2_percent> <pulse_bpm> ...

    Returns:
        DecodedFrame if payload matches the A340B-LK measurement pattern, else None.

    Notes:
        perfusion_index is not known for this packet type and is reported as 0.
    """
    data = _require_bytes(payload, "payload")
    if len(data) < 3:
        return None
    if data[0] != A340B_LK_MEASUREMENT_PREFIX:
        return None

    spo2_percent = int(data[1])
    pulse_bpm = int(data[2])
    perfusion_index = 0
    plausible = 0 <= spo2_percent <= 100 and 20 <= pulse_bpm <= 250

    return DecodedFrame(
        spo2_percent=spo2_percent,
        pulse_bpm=pulse_bpm,
        perfusion_index=perfusion_index,
        plausible=plausible,
        raw=data,
    )


def decode_notification(payload: bytes | bytearray) -> tuple[list[DecodedFrame], bytes]:
    """Best-effort decode for a single notification payload.

    This function tries known device-specific formats first (e.g., A340B-LK),
    then falls back to generic 5-byte frame decoding.
    """
    frame = decode_a340b_lk_notification(payload)
    if frame is not None:
        return [frame], b""

    return decode_payload(payload)


def hexlify(data: bytes | bytearray) -> str:
    """Return dash-separated hex string for logging."""
    raw = _require_bytes(data, "data")
    return raw.hex("-")
