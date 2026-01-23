import pytest

from pulseox.decode import decode_5byte_frame, decode_payload, split_payload


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
