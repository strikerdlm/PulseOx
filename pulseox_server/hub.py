from __future__ import annotations

from collections import deque

Frame = dict[str, object]


class SampleHub:
    """Bounded, monotonically-sequenced log of frames for WebSocket fan-out.

    Single-threaded (event-loop) use: ``publish()`` is called from the synchronous
    BLE notification callback; ``since()``/``backlog()`` are read by per-connection
    WebSocket loops. All access happens on the asyncio loop thread, so no locking
    is required. The deque also serves as the late-joiner replay buffer.
    """

    def __init__(self, maxlen: int = 2000) -> None:
        if maxlen <= 0:
            raise ValueError("maxlen must be positive")
        self._frames: deque[tuple[int, Frame]] = deque(maxlen=maxlen)
        self._seq = 0

    @property
    def latest_seq(self) -> int:
        return self._seq

    def publish(self, frame: Frame) -> int:
        """Append a frame and return its monotonically increasing sequence id."""
        self._seq += 1
        self._frames.append((self._seq, frame))
        return self._seq

    def since(self, cursor: int) -> tuple[int, list[Frame]]:
        """Return ``(latest_seq, frames)`` for frames with seq > ``cursor``."""
        out = [frame for (seq, frame) in self._frames if seq > cursor]
        return self._seq, out

    def backlog(self, limit: int) -> tuple[int, list[Frame]]:
        """Return ``(latest_seq, frames)`` for the most recent ``limit`` frames."""
        if limit <= 0:
            raise ValueError("limit must be positive")
        items = list(self._frames)[-limit:]
        return self._seq, [frame for (_seq, frame) in items]

    def clear(self) -> None:
        """Drop buffered frames. ``seq`` is NOT reset, keeping cursors monotonic."""
        self._frames.clear()
