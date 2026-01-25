# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false
# pyright: reportArgumentType=false, reportCallIssue=false, reportUnusedFunction=false
# pyright: reportMissingTypeStubs=false
# NOTE: Reflex + Plotly have incomplete/partial type stubs in strict mode.
# We keep the core data/validation logic fully typed, and relax only the
# UI-layer unknown-member noise in this module.

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import TypedDict

import plotly.graph_objects as go
import reflex as rx

from pulseox.dashboard_data import (
    PulseOxSample,
    latest_two,
    load_recent_samples_from_path,
    samples_to_series,
)

DEFAULT_CSV_PATH = "validated_60s.csv"
MIN_WINDOW_ROWS = 20
MAX_WINDOW_ROWS = 500
MAX_TABLE_ROWS = 50
MIN_REFRESH_S = 0.0
MAX_REFRESH_S = 5.0
MAX_WIDTH = "1280px"


class SampleRow(TypedDict):
    timestamp_utc: str
    spo2_percent: int
    pulse_bpm: int
    perfusion_index: int
    plausible: str
    sender: str


def _require_nonempty_str(value: object, name: str) -> str:
    """Return a non-empty string or raise a validation error."""
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{name} must be non-empty")
    return cleaned


def _require_int_in_range(value: object, name: str, min_value: int, max_value: int) -> int:
    """Return an int within the inclusive range or raise a validation error."""
    parsed: int
    if isinstance(value, bool):
        raise TypeError(f"{name} must be an int")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, float):
        if value.is_integer():
            parsed = int(value)
        else:
            raise ValueError(f"{name} must be an int")
    elif isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError as exc:
            raise ValueError(f"{name} must be an int") from exc
    else:
        raise TypeError(f"{name} must be an int")

    if parsed < min_value or parsed > max_value:
        raise ValueError(f"{name} must be between {min_value} and {max_value}")
    return parsed


def _require_float_in_range(value: object, name: str, min_value: float, max_value: float) -> float:
    """Return a float within the inclusive range or raise a validation error."""
    if isinstance(value, bool):
        raise TypeError(f"{name} must be a float")
    if isinstance(value, int | float):
        parsed = float(value)
    elif isinstance(value, str):
        try:
            parsed = float(value)
        except ValueError as exc:
            raise ValueError(f"{name} must be a float") from exc
    else:
        raise TypeError(f"{name} must be a float")

    if parsed < min_value or parsed > max_value:
        raise ValueError(f"{name} must be between {min_value} and {max_value}")
    return parsed


def _format_timestamp(value: datetime) -> str:
    """Format timestamps in ISO-8601 seconds for display."""
    return value.isoformat(timespec="seconds")


def _series_from_samples(
    samples: Sequence[PulseOxSample],
) -> tuple[list[str], list[int], list[int]]:
    """Convert samples to (timestamp, spo2, hr) series for charting."""
    ts, spo2, hr = samples_to_series(samples)
    ts_text = [_format_timestamp(item) for item in ts]
    return ts_text, spo2, hr


def _table_rows_from_samples(samples: Sequence[PulseOxSample]) -> list[SampleRow]:
    """Convert samples to table rows for display."""
    rows: list[SampleRow] = []
    for sample in samples:
        rows.append(
            {
                "timestamp_utc": _format_timestamp(sample.timestamp_utc),
                "spo2_percent": sample.spo2_percent,
                "pulse_bpm": sample.pulse_bpm,
                "perfusion_index": sample.perfusion_index,
                "plausible": "Yes" if sample.plausible else "No",
                "sender": sample.sender,
            }
        )
    return rows


def _safe_int(value: int | None, default: int) -> int:
    """Return value or default when value is None."""
    if value is None:
        return default
    return value


def _gauge_spo2(value: int, *, previous: int | None) -> go.Figure:
    """Build the SpO2 gauge figure."""
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=float(value),
            number={"suffix": "%", "font": {"size": 72}},
            delta={"reference": float(previous) if previous is not None else float(value)},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#10b981"},
                "steps": [
                    {"range": [0, 88], "color": "#ef4444"},
                    {"range": [88, 92], "color": "#f59e0b"},
                    {"range": [92, 100], "color": "#22c55e"},
                ],
                "threshold": {
                    "line": {"color": "#e2e8f0", "width": 4},
                    "thickness": 0.75,
                    "value": 92,
                },
            },
            title={"text": "SpO2", "font": {"size": 26}},
        )
    )
    fig.update_layout(
        height=360,
        margin={"l": 20, "r": 20, "t": 50, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "#e2e8f0"},
    )
    return fig


def _gauge_hr(value: int, *, previous: int | None) -> go.Figure:
    """Build the heart-rate gauge figure."""
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=float(value),
            number={"suffix": " bpm", "font": {"size": 48}},
            delta={"reference": float(previous) if previous is not None else float(value)},
            gauge={
                "axis": {"range": [0, 220]},
                "bar": {"color": "#3b82f6"},
                "steps": [
                    {"range": [0, 40], "color": "#f59e0b"},
                    {"range": [40, 130], "color": "#14b8a6"},
                    {"range": [130, 220], "color": "#ef4444"},
                ],
            },
            title={"text": "Heart rate", "font": {"size": 22}},
        )
    )
    fig.update_layout(
        height=260,
        margin={"l": 20, "r": 20, "t": 45, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "#e2e8f0"},
    )
    return fig


def _trend_chart(ts: list[str], spo2: list[int], hr: list[int]) -> go.Figure:
    """Build the SpO2 / HR trend chart."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=ts,
            y=spo2,
            mode="lines+markers",
            name="SpO2 (%)",
            line={"width": 3, "color": "#10b981"},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=ts,
            y=hr,
            mode="lines+markers",
            name="HR (bpm)",
            line={"width": 3, "color": "#3b82f6"},
            yaxis="y2",
        )
    )
    fig.update_layout(
        height=320,
        margin={"l": 20, "r": 20, "t": 35, "b": 30},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#e2e8f0"},
        xaxis={"title": "Time (UTC)"},
        yaxis={"title": "SpO2 (%)", "range": [0, 100]},
        yaxis2={"title": "HR (bpm)", "overlaying": "y", "side": "right", "range": [0, 220]},
        legend={"orientation": "h", "y": 1.1},
    )
    return fig


class DashboardState(rx.State):
    """State for the Reflex PulseOx dashboard."""

    csv_path: str = DEFAULT_CSV_PATH
    window_rows: int = 120
    only_plausible: bool = True
    refresh_s: float = 1.0
    error_message: str = ""
    status_message: str = ""
    last_updated_utc: str = ""
    latest_time: str = ""
    latest_sender: str = ""
    latest_plausible: str = ""
    latest_spo2: int | None = None
    prev_spo2: int | None = None
    latest_hr: int | None = None
    prev_hr: int | None = None
    trend_ts: list[str] = []
    trend_spo2: list[int] = []
    trend_hr: list[int] = []
    table_rows: list[SampleRow] = []

    def _clear_samples(self) -> None:
        """Reset derived sample data to empty values."""
        self.latest_time = ""
        self.latest_sender = ""
        self.latest_plausible = ""
        self.latest_spo2 = None
        self.prev_spo2 = None
        self.latest_hr = None
        self.prev_hr = None
        self.trend_ts = []
        self.trend_spo2 = []
        self.trend_hr = []
        self.table_rows = []

    def _set_error(self, message: str) -> None:
        """Store an error message and clear status info."""
        self.error_message = message
        self.status_message = ""

    def set_csv_path(self, value: str) -> None:
        """Update the CSV path with validation and error reporting."""
        try:
            self.csv_path = _require_nonempty_str(value, "csv_path")
        except (TypeError, ValueError) as exc:
            self._set_error(str(exc))
            return
        self.error_message = ""

    def set_window_rows(self, value: int | float | str) -> None:
        """Update window size (rows) with validation and error reporting."""
        try:
            parsed = _require_int_in_range(value, "window_rows", MIN_WINDOW_ROWS, MAX_WINDOW_ROWS)
        except (TypeError, ValueError) as exc:
            self._set_error(str(exc))
            return
        self.window_rows = parsed
        self.error_message = ""

    def set_refresh_s(self, value: int | float | str) -> None:
        """Update auto-refresh seconds with validation and error reporting."""
        try:
            parsed = _require_float_in_range(value, "refresh_s", MIN_REFRESH_S, MAX_REFRESH_S)
        except (TypeError, ValueError) as exc:
            self._set_error(str(exc))
            return
        self.refresh_s = parsed
        self.error_message = ""

    def set_only_plausible(self, value: object) -> None:
        """Update plausible-only filtering with validation."""
        if not isinstance(value, bool):
            self._set_error("only_plausible must be a bool")
            return
        self.only_plausible = value
        self.error_message = ""

    def refresh(self) -> None:
        """Load CSV samples and update charts, tables, and metrics."""
        try:
            csv_path = _require_nonempty_str(self.csv_path, "csv_path")
            window_rows = _require_int_in_range(
                self.window_rows, "window_rows", MIN_WINDOW_ROWS, MAX_WINDOW_ROWS
            )
            _ = _require_float_in_range(
                self.refresh_s, "refresh_s", MIN_REFRESH_S, MAX_REFRESH_S
            )
        except (TypeError, ValueError) as exc:
            self._set_error(str(exc))
            self._clear_samples()
            return

        try:
            samples = load_recent_samples_from_path(
                csv_path,
                max_rows=window_rows,
                only_plausible=self.only_plausible,
            )
        except (FileNotFoundError, IsADirectoryError, ValueError, OSError) as exc:
            self._set_error(f"Failed to load CSV: {exc}")
            self._clear_samples()
            return

        latest, prev = latest_two(samples)
        if latest is None:
            self._clear_samples()
            self.error_message = ""
            self.status_message = (
                "No samples available yet. Start recording with --csv ... --quiet."
            )
            return

        self.latest_spo2 = latest.spo2_percent
        self.prev_spo2 = prev.spo2_percent if prev is not None else None
        self.latest_hr = latest.pulse_bpm
        self.prev_hr = prev.pulse_bpm if prev is not None else None
        self.latest_time = _format_timestamp(latest.timestamp_utc)
        self.latest_sender = latest.sender
        self.latest_plausible = "Yes" if latest.plausible else "No"
        self.trend_ts, self.trend_spo2, self.trend_hr = _series_from_samples(samples)
        self.table_rows = _table_rows_from_samples(samples[-MAX_TABLE_ROWS:])
        self.last_updated_utc = datetime.now(UTC).isoformat(timespec="seconds")
        self.error_message = ""
        self.status_message = ""

    @rx.var(cache=False)
    def has_samples(self) -> bool:
        """Return True when at least one sample is loaded."""
        return bool(self.trend_ts)

    @rx.var(cache=False)
    def refresh_enabled(self) -> bool:
        """Return True when auto-refresh is enabled."""
        return self.refresh_s > 0

    @rx.var(cache=False)
    def refresh_interval_ms(self) -> int:
        """Return refresh interval in milliseconds."""
        if self.refresh_s <= 0:
            return 0
        return int(round(self.refresh_s * 1000))

    @rx.var(cache=False)
    def spo2_fig(self) -> go.Figure:
        """Return the current SpO2 gauge figure."""
        return _gauge_spo2(_safe_int(self.latest_spo2, 0), previous=self.prev_spo2)

    @rx.var(cache=False)
    def hr_fig(self) -> go.Figure:
        """Return the current heart-rate gauge figure."""
        return _gauge_hr(_safe_int(self.latest_hr, 0), previous=self.prev_hr)

    @rx.var(cache=False)
    def trend_fig(self) -> go.Figure:
        """Return the current trend chart figure."""
        return _trend_chart(self.trend_ts, self.trend_spo2, self.trend_hr)


APP_BACKGROUND = (
    "radial-gradient(1200px 600px at 15% 5%, rgba(59,130,246,0.18), rgba(0,0,0,0) 60%),"
    "radial-gradient(900px 600px at 85% 10%, rgba(16,185,129,0.16), rgba(0,0,0,0) 55%),"
    "linear-gradient(180deg, #0b1020 0%, #070a14 100%)"
)
CARD_BG = "rgba(15, 23, 42, 0.7)"
CARD_BORDER = "1px solid rgba(148, 163, 184, 0.2)"
TEXT_MUTED = "rgba(226, 232, 240, 0.72)"
TEXT_SOFT = "rgba(226, 232, 240, 0.85)"
ACCENT_BLUE = "rgba(59, 130, 246, 1.0)"
ACCENT_GREEN = "rgba(16, 185, 129, 1.0)"
SURFACE_GLASS = "rgba(15, 23, 42, 0.55)"


def _card(*children: rx.Component, min_width: str | None = None) -> rx.Component:
    """Create a styled card container."""
    style: dict[str, object] = {
        "background": CARD_BG,
        "border": CARD_BORDER,
        "border_radius": "16px",
        "box_shadow": "0 14px 40px rgba(0,0,0,0.35)",
        "padding": "16px",
    }
    if min_width is not None:
        style["min_width"] = min_width
    return rx.box(*children, style=style)


def _pill(*children: rx.Component, color: str, background: str) -> rx.Component:
    """Create a small pill/badge."""
    return rx.box(
        rx.hstack(*children, spacing="2", align="center"),
        style={
            "display": "inline-flex",
            "align_items": "center",
            "gap": "8px",
            "padding": "6px 10px",
            "border_radius": "9999px",
            "border": "1px solid rgba(148, 163, 184, 0.25)",
            "background": background,
            "color": color,
        },
    )


def _label(text: str) -> rx.Component:
    """Render a small form label."""
    return rx.text(text, color=TEXT_MUTED, size="2", style={"font_weight": "600"})


def _help(text: str) -> rx.Component:
    """Render muted helper text."""
    return rx.text(text, color=TEXT_MUTED, size="1")


def _live_dot(enabled: bool) -> rx.Component:
    """Render an enabled/disabled indicator dot."""
    if enabled:
        return rx.box(
            style={
                "width": "10px",
                "height": "10px",
                "border_radius": "9999px",
                "background": ACCENT_GREEN,
                "box_shadow": "0 0 0 4px rgba(16,185,129,0.12)",
            }
        )
    return rx.box(
        style={
            "width": "10px",
            "height": "10px",
            "border_radius": "9999px",
            "background": "rgba(148, 163, 184, 0.7)",
        }
    )


def _topbar() -> rx.Component:
    """Render a modern, sticky top bar."""
    live_pill = rx.cond(
        DashboardState.refresh_enabled,
        _pill(
            _live_dot(True),
            rx.text("Live", size="2", style={"font_weight": "700"}),
            color=TEXT_SOFT,
            background="rgba(16,185,129,0.10)",
        ),
        _pill(
            _live_dot(False),
            rx.text("Paused", size="2", style={"font_weight": "700"}),
            color=TEXT_SOFT,
            background="rgba(148, 163, 184, 0.10)",
        ),
    )

    refresh_text = rx.cond(
        DashboardState.refresh_enabled,
        rx.text(
            f"Refresh: {DashboardState.refresh_s}s",
            size="2",
            color=TEXT_MUTED,
            style={"font_weight": "600"},
        ),
        rx.text(
            "Refresh: off",
            size="2",
            color=TEXT_MUTED,
            style={"font_weight": "600"},
        ),
    )

    updated_text = rx.cond(
        DashboardState.last_updated_utc != "",
        rx.text(
            f"Updated: {DashboardState.last_updated_utc}",
            size="2",
            color=TEXT_MUTED,
            style={"font_weight": "600"},
        ),
        rx.text("", size="2"),
    )

    return rx.box(
        rx.container(
            rx.hstack(
                rx.vstack(
                    rx.hstack(
                        rx.text(
                            "PulseOx",
                            size="5",
                            style={
                                "letter_spacing": "-0.02em",
                                "font_weight": "800",
                            },
                        ),
                        _pill(
                            rx.text("Dashboard", size="1", style={"font_weight": "700"}),
                            color=TEXT_SOFT,
                            background="rgba(59,130,246,0.10)",
                        ),
                        spacing="3",
                        align="center",
                    ),
                    rx.text(
                        "Live CSV view for recordings from "
                        "`python -m pulseox.cli --csv ... --quiet`",
                        color=TEXT_MUTED,
                        size="2",
                        style={"max_width": "760px"},
                    ),
                    spacing="1",
                    align="start",
                ),
                rx.hstack(
                    rx.vstack(live_pill, refresh_text, updated_text, spacing="1", align="end"),
                    rx.button(
                        "Refresh",
                        on_click=DashboardState.refresh,
                        color_scheme="sky",
                        variant="solid",
                    ),
                    spacing="4",
                    align="center",
                ),
                justify="between",
                align="center",
                width="100%",
                spacing="4",
            ),
            max_width=MAX_WIDTH,
            padding="16px 24px",
        ),
        style={
            "position": "sticky",
            "top": "0",
            "z_index": "20",
            "background": SURFACE_GLASS,
            "backdrop_filter": "blur(14px)",
            "border_bottom": "1px solid rgba(148, 163, 184, 0.15)",
        },
    )


def _status_banner() -> rx.Component:
    """Render error and status banners."""
    error_box = rx.box(
        rx.text(DashboardState.error_message, color="#fecaca"),
        style={
            "background": "rgba(127, 29, 29, 0.6)",
            "border": "1px solid rgba(248, 113, 113, 0.5)",
            "border_radius": "12px",
            "padding": "12px 14px",
        },
    )
    status_box = rx.box(
        rx.text(DashboardState.status_message, color="#bfdbfe"),
        style={
            "background": "rgba(30, 64, 175, 0.35)",
            "border": "1px solid rgba(96, 165, 250, 0.4)",
            "border_radius": "12px",
            "padding": "12px 14px",
        },
    )
    return rx.vstack(
        rx.cond(DashboardState.error_message != "", error_box, rx.fragment()),
        rx.cond(DashboardState.status_message != "", status_box, rx.fragment()),
        spacing="2",
        width="100%",
    )


def _sidebar() -> rx.Component:
    """Render sidebar controls."""
    return _card(
        rx.heading("Controls", size="5", style={"letter_spacing": "-0.01em"}),
        _label("CSV path"),
        rx.input(
            value=DashboardState.csv_path,
            on_change=DashboardState.set_csv_path,
            placeholder="path/to/session.csv",
            size="3",
            width="100%",
        ),
        _help("Tip: record data with `--csv session.csv --quiet`, then point the dashboard at it."),
        rx.checkbox(
            text="Only plausible samples",
            checked=DashboardState.only_plausible,
            on_change=DashboardState.set_only_plausible,
        ),
        _label("Window (rows)"),
        rx.input(
            type="number",
            min=MIN_WINDOW_ROWS,
            max=MAX_WINDOW_ROWS,
            step=10,
            value=DashboardState.window_rows,
            on_change=DashboardState.set_window_rows,
            width="100%",
        ),
        _label("Auto-refresh (seconds)"),
        rx.input(
            type="number",
            min=MIN_REFRESH_S,
            max=MAX_REFRESH_S,
            step=0.5,
            value=DashboardState.refresh_s,
            on_change=DashboardState.set_refresh_s,
            width="100%",
        ),
        rx.hstack(
            rx.button(
                "Refresh now",
                on_click=DashboardState.refresh,
                color_scheme="sky",
                width="100%",
            ),
            spacing="2",
            width="100%",
        ),
        rx.separator(),
        _label("Recorder command (example)"),
        rx.box(
            rx.text(
                'python -m pulseox.cli --address "FF:FF:FF:FF:00:21" '
                "--csv session.csv --csv-overwrite --duration 600 --quiet",
                style={"font_family": "ui-monospace", "font_size": "0.85rem"},
            ),
            style={
                "background": "rgba(15, 23, 42, 0.9)",
                "border": "1px solid rgba(148, 163, 184, 0.25)",
                "border_radius": "12px",
                "padding": "10px 12px",
            },
        ),
        spacing="3",
        min_width="300px",
    )


def _latest_card() -> rx.Component:
    """Render the latest sample summary."""
    return _card(
        rx.text("Latest sample", size="2", color=TEXT_MUTED, style={"font_weight": "700"}),
        rx.separator(),
        rx.vstack(
            rx.hstack(
                _label("Time"),
                rx.text(DashboardState.latest_time, size="3"),
                justify="between",
            ),
            rx.hstack(
                _label("Sender"),
                rx.text(DashboardState.latest_sender, size="3"),
                justify="between",
            ),
            rx.hstack(
                _label("Plausible"),
                rx.text(DashboardState.latest_plausible, size="3"),
                justify="between",
            ),
            spacing="2",
        ),
        min_width="240px",
    )


def _table_row(row: SampleRow) -> rx.Component:
    """Render a single table row."""
    return rx.table.row(
        rx.table.cell(row["timestamp_utc"]),
        rx.table.cell(row["spo2_percent"]),
        rx.table.cell(row["pulse_bpm"]),
        rx.table.cell(row["perfusion_index"]),
        rx.table.cell(row["plausible"]),
        rx.table.cell(row["sender"]),
    )


def _table() -> rx.Component:
    """Render the recent samples table."""
    return _card(
        rx.heading("Recent samples", size="4"),
        rx.box(
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Time (UTC)"),
                        rx.table.column_header_cell("SpO2"),
                        rx.table.column_header_cell("HR"),
                        rx.table.column_header_cell("PI"),
                        rx.table.column_header_cell("Plausible"),
                        rx.table.column_header_cell("Sender"),
                    )
                ),
                rx.table.body(rx.foreach(DashboardState.table_rows, _table_row)),
                width="100%",
                variant="surface",
            ),
            style={
                "overflow_x": "auto",
                "border_radius": "12px",
                "border": "1px solid rgba(148, 163, 184, 0.18)",
            },
        ),
        min_width="100%",
    )


def _charts() -> rx.Component:
    """Render charts and latest metrics."""
    return rx.vstack(
        rx.flex(
            rx.box(
                _card(rx.plotly(data=DashboardState.spo2_fig), min_width="360px"),
                style={"flex": "2 1 440px"},
            ),
            rx.box(
                rx.vstack(
                    _card(rx.plotly(data=DashboardState.hr_fig), min_width="320px"),
                    _latest_card(),
                    spacing="4",
                    width="100%",
                ),
                style={"flex": "1 1 360px"},
            ),
            spacing="4",
            wrap="wrap",
            align="stretch",
            width="100%",
        ),
        _card(
            rx.vstack(
                rx.hstack(
                    rx.heading("Trends", size="4"),
                    rx.text("SpO2 and HR over the most recent window", size="2", color=TEXT_MUTED),
                    justify="between",
                    width="100%",
                    align="center",
                ),
                rx.plotly(data=DashboardState.trend_fig),
                spacing="3",
            ),
            min_width="100%",
        ),
        _table(),
        spacing="4",
        width="100%",
    )


def _auto_refresh_tick() -> rx.Component:
    """Hidden timer to trigger periodic refresh."""
    return rx.cond(
        DashboardState.refresh_enabled,
        rx.moment(
            interval=DashboardState.refresh_interval_ms,
            on_change=DashboardState.refresh,
            style={"display": "none"},
        ),
        rx.fragment(),
    )


@rx.page(title="PulseOx Dashboard", on_load=DashboardState.refresh)
def index() -> rx.Component:
    """Render the main dashboard page."""
    return rx.box(
        _auto_refresh_tick(),
        _topbar(),
        rx.container(
            rx.vstack(
                _status_banner(),
                rx.flex(
                    rx.box(_sidebar(), style={"flex": "0 0 340px", "width": "340px"}),
                    rx.box(
                        rx.cond(
                            DashboardState.has_samples,
                            _charts(),
                            _card(
                                rx.heading("Waiting for samples", size="5"),
                                rx.text(
                                    "Start recording with `--csv ... --quiet`, then press Refresh.",
                                    color=TEXT_MUTED,
                                ),
                                rx.box(
                                    rx.text(
                                        "If you just started recording, it may take a few seconds "
                                        "for rows to appear.",
                                        color=TEXT_MUTED,
                                        size="2",
                                    ),
                                    style={
                                        "margin_top": "10px",
                                        "padding": "10px 12px",
                                        "border_radius": "12px",
                                        "border": "1px solid rgba(148, 163, 184, 0.18)",
                                        "background": "rgba(2, 6, 23, 0.25)",
                                    },
                                ),
                                min_width="100%",
                            ),
                        ),
                        style={"flex": "1 1 auto", "min_width": "0"},
                    ),
                    spacing="5",
                    align="start",
                    wrap="wrap",
                    width="100%",
                ),
                spacing="4",
                width="100%",
            ),
            max_width=MAX_WIDTH,
            padding="24px",
        ),
        style={
            "background": APP_BACKGROUND,
            "min_height": "100vh",
            "color": "#e2e8f0",
        },
    )


app = rx.App(
    theme=rx.theme(
        appearance="dark",
        accent_color="sky",
        gray_color="slate",
        radius="large",
        scaling="100%",
        panel_background="solid",
    )
)
