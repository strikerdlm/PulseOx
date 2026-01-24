from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import plotly.graph_objects as go

from pulseox.dashboard_data import (
    PulseOxSample,
    latest_two,
    load_recent_samples_from_path,
    samples_to_series,
)


def _try_autorefresh(interval_ms: int) -> bool:
    """Trigger Streamlit auto-refresh if available.

    Returns:
        True if auto-refresh was enabled; False otherwise.
    """
    if interval_ms <= 0:
        return False

    try:
        from streamlit_autorefresh import st_autorefresh
    except ModuleNotFoundError:
        return False

    _ = st_autorefresh(interval=interval_ms, key="pulseox_autorefresh")  # intentionally ignored
    return True


def _gauge_spo2(value: int, *, previous: int | None) -> go.Figure:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=float(value),
            number={"suffix": "%", "font": {"size": 72}},
            delta={"reference": float(previous) if previous is not None else float(value)},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#00d084"},
                "steps": [
                    {"range": [0, 88], "color": "#ff4d4f"},
                    {"range": [88, 92], "color": "#faad14"},
                    {"range": [92, 100], "color": "#1fdd8a"},
                ],
                "threshold": {
                    "line": {"color": "#ffffff", "width": 4},
                    "thickness": 0.75,
                    "value": 92,
                },
            },
            title={"text": "SpO₂", "font": {"size": 28}},
        )
    )
    fig.update_layout(
        height=420,
        margin={"l": 30, "r": 30, "t": 60, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "#eaf2ff"},
    )
    return fig


def _gauge_hr(value: int, *, previous: int | None) -> go.Figure:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=float(value),
            number={"suffix": " bpm", "font": {"size": 52}},
            delta={"reference": float(previous) if previous is not None else float(value)},
            gauge={
                "axis": {"range": [0, 220]},
                "bar": {"color": "#3b82f6"},
                "steps": [
                    {"range": [0, 40], "color": "#faad14"},
                    {"range": [40, 130], "color": "#2dd4bf"},
                    {"range": [130, 220], "color": "#ff4d4f"},
                ],
            },
            title={"text": "Heart rate", "font": {"size": 22}},
        )
    )
    fig.update_layout(
        height=260,
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "#eaf2ff"},
    )
    return fig


def _trend_chart(samples: list[PulseOxSample]) -> go.Figure:
    ts, spo2, hr = samples_to_series(samples)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=ts,
            y=spo2,
            mode="lines+markers",
            name="SpO₂ (%)",
            line={"width": 3, "color": "#00d084"},
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
        margin={"l": 30, "r": 30, "t": 40, "b": 30},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#eaf2ff"},
        xaxis={"title": "Time (UTC)"},
        yaxis={"title": "SpO₂ (%)", "range": [0, 100]},
        yaxis2={"title": "HR (bpm)", "overlaying": "y", "side": "right", "range": [0, 220]},
        legend={"orientation": "h", "y": 1.12},
    )
    return fig


@dataclass(frozen=True, slots=True)
class UiSettings:
    csv_path: str
    window_rows: int
    only_plausible: bool
    refresh_s: float


def _inject_css(st: Any) -> None:
    css = """
<style>
  .stApp {
    background: radial-gradient(1200px 600px at 15% 5%, rgba(59,130,246,0.22), rgba(0,0,0,0) 60%),
                radial-gradient(900px 600px at 85% 10%, rgba(0,208,132,0.20), rgba(0,0,0,0) 55%),
                linear-gradient(180deg, #0b1020 0%, #070a14 100%);
    color: #eaf2ff;
  }
  [data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
    border-right: 1px solid rgba(255,255,255,0.08);
  }
  .pulseox-card {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 14px;
    padding: 14px 16px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.25);
  }
  .pulseox-muted {
    opacity: 0.85;
    font-size: 0.92rem;
  }
</style>
"""
    st.markdown(css, unsafe_allow_html=True)


def _render(st: Any) -> None:
    st.set_page_config(page_title="PulseOx Dashboard", layout="wide")
    _inject_css(st)

    st.markdown(
        """
<div class="pulseox-card">
  <div style="font-size: 1.6rem; font-weight: 700;">PulseOx Dashboard</div>
  <div class="pulseox-muted">
    Live view for CSV recordings from <code>python -m pulseox.cli --csv ... --quiet</code>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown("### Data source")
        default_path = str(Path("validated_60s.csv"))
        csv_path = st.text_input("CSV path", value=default_path, help="Path to a PulseOx CSV file.")
        only_plausible = st.toggle(
            "Only plausible samples",
            value=True,
            help="Matches the CLI default behavior (filters implausible frames).",
        )
        window_rows = st.slider("Window (rows)", min_value=20, max_value=500, value=120, step=10)
        refresh_s = float(
            st.slider("Auto-refresh (seconds)", min_value=0.0, max_value=5.0, value=1.0, step=0.5)
        )

        st.markdown("---")
        st.markdown("### Recorder (example)")
        st.code(
            'python -m pulseox.cli --address "FF:FF:FF:FF:00:21" '
            "--csv session.csv --csv-overwrite --duration 600 --quiet",
            language="bash",
        )

    settings = UiSettings(
        csv_path=csv_path,
        window_rows=window_rows,
        only_plausible=only_plausible,
        refresh_s=refresh_s,
    )

    refresh_ok = False
    if settings.refresh_s > 0:
        try:
            refresh_ok = _try_autorefresh(int(settings.refresh_s * 1000))
        except ModuleNotFoundError:
            refresh_ok = False

    if settings.refresh_s > 0 and not refresh_ok:
        st.warning(
            "Auto-refresh is disabled because `streamlit-autorefresh` is not available. "
            "You can still use the browser refresh button."
        )

    try:
        samples = load_recent_samples_from_path(
            settings.csv_path,
            max_rows=settings.window_rows,
            only_plausible=settings.only_plausible,
        )
    except FileNotFoundError:
        st.error(f"CSV not found: `{settings.csv_path}`")
        st.stop()
    except Exception as e:  # noqa: BLE001 - UI boundary; report and stop.
        st.error(f"Failed to load CSV: {e}")
        st.stop()

    latest, prev = latest_two(samples)
    if latest is None:
        st.info("No samples available yet. Start recording with `--csv ... --quiet`.")
        st.stop()

    prev_spo2 = prev.spo2_percent if prev is not None else None
    prev_hr = prev.pulse_bpm if prev is not None else None

    top_left, top_right = st.columns([2, 1], gap="large")
    with top_left:
        st.plotly_chart(
            _gauge_spo2(latest.spo2_percent, previous=prev_spo2), use_container_width=True
        )

    with top_right:
        st.plotly_chart(_gauge_hr(latest.pulse_bpm, previous=prev_hr), use_container_width=True)
        st.markdown(
            f"""
<div class="pulseox-card">
  <div class="pulseox-muted">Latest sample</div>
  <div style="font-size: 1.05rem;"><b>Time</b>: {latest.timestamp_utc.isoformat(timespec="seconds")}</div>
  <div style="font-size: 1.05rem;"><b>Sender</b>: <code>{latest.sender}</code></div>
  <div style="font-size: 1.05rem;"><b>Plausible</b>: {"Yes" if latest.plausible else "No"}</div>
</div>
""",
            unsafe_allow_html=True,
        )

    st.plotly_chart(_trend_chart(samples), use_container_width=True)
    st.dataframe(
        [
            {
                "timestamp_utc": s.timestamp_utc.isoformat(),
                "spo2_percent": s.spo2_percent,
                "pulse_bpm": s.pulse_bpm,
                "perfusion_index": s.perfusion_index,
                "plausible": 1 if s.plausible else 0,
                "sender": s.sender,
            }
            for s in samples[-50:]
        ],
        use_container_width=True,
        height=220,
    )


def main() -> None:
    import streamlit as st  # type: ignore[import-not-found]

    _render(st)


if __name__ == "__main__":
    main()
