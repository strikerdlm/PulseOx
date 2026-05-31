from pulseox_server.hub import SampleHub


def test_publish_returns_increasing_seq() -> None:
    hub = SampleHub()
    assert hub.publish({"type": "sample", "spo2_percent": 98}) == 1
    assert hub.publish({"type": "sample", "spo2_percent": 97}) == 2
    assert hub.latest_seq == 2


def test_since_returns_frames_after_cursor() -> None:
    hub = SampleHub()
    hub.publish({"type": "sample", "i": 1})
    hub.publish({"type": "sample", "i": 2})
    hub.publish({"type": "sample", "i": 3})
    latest, frames = hub.since(1)
    assert latest == 3
    assert [f["i"] for f in frames] == [2, 3]


def test_backlog_returns_last_n() -> None:
    hub = SampleHub()
    for i in range(5):
        hub.publish({"type": "sample", "i": i})
    latest, frames = hub.backlog(2)
    assert latest == 5
    assert [f["i"] for f in frames] == [3, 4]


def test_bounded_by_maxlen() -> None:
    hub = SampleHub(maxlen=3)
    for i in range(10):
        hub.publish({"type": "sample", "i": i})
    latest, frames = hub.since(0)
    assert latest == 10
    assert len(frames) == 3
    assert [f["i"] for f in frames] == [7, 8, 9]


def test_clear_keeps_seq_monotonic() -> None:
    hub = SampleHub()
    hub.publish({"x": 1})
    hub.clear()
    assert hub.latest_seq == 1
    assert hub.publish({"x": 2}) == 2
    _latest, frames = hub.since(1)
    assert [f["x"] for f in frames] == [2]
