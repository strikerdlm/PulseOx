import pytest

from pulseox.decode import (
    decode_5byte_frame,
    decode_a340b_lk_notification,
    decode_notification,
    decode_payload,
    split_payload,
)


def test_decode_5byte_frame_basic() -> None:
    frame = bytes([0x0A, 0x00, 0x00, 60, 98])
    decoded = decode_5byte_frame(frame)
    assert decoded.spo2_percent == 98
    assert decoded.pulse_bpm == 60
    assert decoded.perfusion_index == 10
    assert decoded.plausible is True


def test_decode_5byte_frame_invalid_length() -> None:
    with pytest.raises(ValueError):
        decode_5byte_frame(b"\x01\x02\x03\x04")


def test_split_and_decode_payload_with_remainder() -> None:
    frame1 = bytes([0x01, 0x00, 0x00, 70, 97])
    frame2 = bytes([0x0F, 0x00, 0x00, 80, 99])
    payload = frame1 + frame2 + b"\xaa\xbb"
    frames, remainder = split_payload(payload, frame_len=5)
    assert len(frames) == 2
    assert remainder == b"\xaa\xbb"

    decoded, remainder2 = decode_payload(payload)
    assert len(decoded) == 2
    assert remainder2 == b"\xaa\xbb"


def test_decode_a340b_lk_notification_f1() -> None:
    payload = bytes([0xF1, 0x5C, 0x46, 0x00, 0x5B, 0x03, 0xF0])
    frame = decode_a340b_lk_notification(payload)
    assert frame is not None
    assert frame.spo2_percent == 92
    assert frame.pulse_bpm == 70
    assert frame.perfusion_index == 0
    assert frame.plausible is True
    assert frame.raw == payload


def test_decode_notification_prefers_a340b_lk() -> None:
    payload = bytes([0xF1, 0x5C, 0x58, 0x00, 0x50, 0x03, 0xF8])
    frames, remainder = decode_notification(payload)
    assert remainder == b""
    assert len(frames) == 1
    assert frames[0].spo2_percent == 92
    assert frames[0].pulse_bpm == 88
