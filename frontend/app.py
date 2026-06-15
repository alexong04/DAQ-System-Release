from __future__ import annotations

from datetime import datetime
import time

import pandas as pd
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

from src.api_client import ApiClient, BackendError
from src.charts import (
    comparison_curve,
    flow_head_time_chart,
    head_flow_curve,
    pressure_time_chart,
)
from src.config import APP_SUBTITLE, APP_TITLE, DEFAULT_BACKEND_URL, RECENT_SAMPLE_LIMIT
from src.engineering import (
    format_integer,
    format_number,
    normalize_sample,
    samples_to_dataframe,
    summarize_dataframe,
)
from src.mock_data import ensure_mock_history
from src.pump_modes import get_mode, get_mode_label, get_mode_options
from src.quiz import build_sample_quiz_dataframe, generate_hidden_value_questions
from src.styles import inject_global_styles, status_pill


st.set_page_config(
    page_title=APP_TITLE,
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_global_styles(st)

LIVE_REFRESH_INTERVAL_SECONDS = 1



def init_state() -> None:
    defaults = {
        "backend_url": DEFAULT_BACKEND_URL,
        "selected_mode": "series",
        "recording": False,
        "active_session": None,
        "comparison_frames": {},
        "comparison_labels": {},
        "loaded_session_id": None,
        "loaded_session_info": None,
        "loaded_session_frame": None,
        "last_error": "",
        "live_reset_timer": None,
        "live_reset_timestamp": None,
        "current_live_timer": 0.0,
        "current_live_timestamp": None,
        "show_reset_toast": False,
        "live_reset_empty_until": 0.0,
        "live_frame_cache_key": None,
        "live_frame_cache_df": None,
        "live_frame_cache_using_mock": False,
        "hidden_quiz_questions": [],
        "hidden_quiz_generation": 0,
        "hidden_quiz_submitted": False,
        "hidden_quiz_config": {},
        "manual_pressure_samples": [],
        "manual_pressure_flow_avg": None,
        "manual_pressure_flow_sample_count": 0,
        "manual_pressure_flow_updated_at": None,
        "manual_pressure_session_name": "",
        "manual_pressure_last_saved_session": None,
        "serial_control_error": "",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if st.session_state.get("selected_mode") not in get_mode_options():
        st.session_state.selected_mode = "series"


def make_default_session_name(mode: str) -> str:
    label = get_mode_label(mode)
    now = datetime.now().strftime("%b %d, %I:%M %p")
    return f"{label} run - {now}"


def format_datetime_label(value: object) -> str:
    if value in (None, ""):
        return "—"

    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return str(value)

    return timestamp.strftime("%b %d, %Y %I:%M %p")


def get_client() -> ApiClient:
    return ApiClient(st.session_state.backend_url)


def check_backend(client: ApiClient) -> tuple[bool, str]:
    try:
        health = client.health()
        message = health.get("message") or health.get("status") or "Backend connected"
        return True, str(message)
    except BackendError as exc:
        return False, str(exc)


def render_serial_controls(client: ApiClient, backend_available: bool) -> None:
    with st.sidebar.expander("HC-05 / serial connection", expanded=False):
        if not backend_available:
            st.caption("Start the backend first to list COM ports and connect to the HC-05.")
            return

        try:
            status = client.get_serial_status()
        except BackendError as exc:
            st.markdown(status_pill("Serial status unavailable", "bad"), unsafe_allow_html=True)
            st.caption(str(exc))
            return

        connected = bool(status.get("connected"))
        current_port = str(status.get("port") or "")
        current_mode = str(status.get("mode") or "idle")
        samples_received = int(status.get("samples_received") or 0)

        if connected:
            st.markdown(
                status_pill(f"Connected to {current_port or 'serial'}", "good"),
                unsafe_allow_html=True,
            )
            # st.caption(f"Mode: {current_mode} · Samples received: {samples_received:,}")
        else:
            st.markdown(status_pill("Serial disconnected", "warn"), unsafe_allow_html=True)

        if status.get("last_error"):
            st.caption(f"Last serial note: {status.get('last_error')}")
        # if status.get("last_line"):
        #     st.caption(f"Last line: {str(status.get('last_line'))[:100]}")
        if st.session_state.get("serial_control_error"):
            st.caption(st.session_state.serial_control_error)

        default_baud = int(status.get("baud_rate") or st.session_state.get("serial_baud_rate", 9600) or 9600)
        baud_rate = st.number_input(
            "Baud rate",
            min_value=300,
            max_value=230400,
            value=default_baud,
            step=300,
            key="serial_baud_rate",
            help="HC-05 modules are commonly configured at 9600 baud.",
        )

        try:
            ports = client.get_serial_ports()
        except BackendError as exc:
            ports = []
            st.caption(f"Could not refresh port list: {exc}")

        port_options = [str(item.get("device")) for item in ports if item.get("device")]
        if current_port and current_port not in port_options:
            port_options.insert(0, current_port)
        if "SIMULATOR" not in port_options:
            port_options.append("SIMULATOR")
        port_options.append("Manual COM port")

        selected_port = st.selectbox(
            "COM / serial port",
            options=port_options,
            key="serial_selected_port",
            disabled=connected,
            help="Choose the COM port paired to the HC-05, or use Auto-detect to try likely Bluetooth ports.",
        )

        if selected_port == "Manual COM port":
            selected_port = st.text_input(
                "Manual port name",
                value=current_port or "COM4",
                key="serial_manual_port",
                disabled=connected,
            ).strip()

        for item in ports:
            if item.get("device") == selected_port:
                st.caption(str(item.get("description") or "Detected serial port"))
                break

        auto_col, connect_col = st.columns(2)
        with auto_col:
            auto_clicked = st.button(
                "Auto-detect",
                width="stretch",
                disabled=connected,
                help="Tries likely HC-05/Bluetooth ports and keeps the first port that produces serial data.",
            )
        with connect_col:
            connect_clicked = st.button(
                "Connect",
                width="stretch",
                disabled=connected or not selected_port,
            )

        disconnect_clicked = st.button(
            "Disconnect",
            width="stretch",
            disabled=not connected,
        )

        if auto_clicked:
            try:
                client.auto_connect_serial(int(baud_rate))
                st.session_state.serial_control_error = ""
                st.session_state.last_error = ""
                st.rerun()
            except BackendError as exc:
                st.session_state.serial_control_error = f"Auto-detect failed: {exc}"
                st.session_state.last_error = "Serial connection issue. Check the HC-05 / serial connection panel in the sidebar."

        if connect_clicked:
            try:
                client.connect_serial(str(selected_port), int(baud_rate))
                st.session_state.serial_control_error = ""
                st.session_state.last_error = ""
                st.rerun()
            except BackendError as exc:
                st.session_state.serial_control_error = f"Serial connect failed: {exc}"
                st.session_state.last_error = "Serial connection issue. Check the HC-05 / serial connection panel in the sidebar."

        if disconnect_clicked:
            try:
                client.disconnect_serial()
                st.session_state.serial_control_error = ""
                st.session_state.last_error = ""
                st.rerun()
            except BackendError as exc:
                st.session_state.serial_control_error = f"Serial disconnect failed: {exc}"
                st.session_state.last_error = "Serial connection issue. Check the HC-05 / serial connection panel in the sidebar."


def load_live_samples(
    client: ApiClient,
    backend_available: bool,
    use_mock_if_offline: bool,
    mode: str,
    recording: bool,
) -> tuple[pd.DataFrame, bool]:
    if backend_available:
        try:
            samples = client.get_recent_samples(limit=RECENT_SAMPLE_LIMIT)
            return samples_to_dataframe(samples, mode), False
        except BackendError as exc:
            st.session_state.last_error = str(exc)

    if use_mock_if_offline:
        samples = ensure_mock_history(
            st.session_state,
            mode=mode,
            is_recording=recording,
            limit=RECENT_SAMPLE_LIMIT,
        )
        return samples_to_dataframe(samples, mode), True

    return samples_to_dataframe([], mode), False



def remember_current_live_position(df: pd.DataFrame) -> None:
    if df.empty:
        return

    latest = df.iloc[-1]
    st.session_state.current_live_timer = float(latest.get("timer", 0.0) or 0.0)
    st.session_state.current_live_timestamp = latest.get("timestamp")


def apply_live_reset_filter(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    reset_timer = st.session_state.get("live_reset_timer")
    reset_timestamp = st.session_state.get("live_reset_timestamp")

    filtered = df

    if reset_timer is not None and "timer" in filtered.columns:
        filtered = filtered[filtered["timer"] > float(reset_timer)]

    if filtered.empty and reset_timestamp is not None and "timestamp" in df.columns:
        reset_ts = pd.to_datetime(reset_timestamp, errors="coerce")
        if pd.notna(reset_ts):
            filtered = df[df["timestamp"] > reset_ts]

    return filtered.reset_index(drop=True)


def reset_live_readings(use_mock_if_offline: bool = False, backend_available: bool = False) -> None:
    using_mock_source = use_mock_if_offline and not backend_available

    # Keep the visible live components empty briefly so reset feels instant,
    # then allow the next incoming samples to appear after the reset marker.
    st.session_state.live_reset_empty_until = time.time() + LIVE_REFRESH_INTERVAL_SECONDS
    st.session_state.live_frame_cache_key = None
    st.session_state.live_frame_cache_df = None

    if using_mock_source:
        # Mock data should restart cleanly.
        st.session_state.live_reset_timer = None
        st.session_state.live_reset_timestamp = None
        st.session_state.mock_samples = []
        st.session_state.mock_index = 0
    else:
        # Backend data may still contain old readings, so mark the current position.
        # After the one empty render, only readings after this point are shown.
        st.session_state.live_reset_timer = st.session_state.get("current_live_timer", 0.0)
        st.session_state.live_reset_timestamp = st.session_state.get("current_live_timestamp")

        # Clear cached recent samples if the optimized version is being used.
        try:
            cached_recent_samples.clear()
        except NameError:
            pass

    st.session_state.show_reset_toast = True
    st.session_state.last_error = ""


def render_header() -> None:
    st.markdown(
        f"""
        <div class="dashboard-hero">
            <div class="eyebrow">Arduino pump data acquisition system</div>
            <h1>{APP_TITLE}</h1>
            <p>{APP_SUBTITLE}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(client: ApiClient, backend_available: bool, backend_message: str) -> dict:
    st.sidebar.title("DAQ Controls")

    st.sidebar.text_input(
        "Backend URL",
        key="backend_url",
        help="Default is http://localhost:8000. Change this if your backend runs elsewhere.",
    )

    if backend_available:
        st.sidebar.markdown(status_pill("Backend connected", "good"), unsafe_allow_html=True)
        st.sidebar.caption(backend_message)
    else:
        st.sidebar.markdown(status_pill("Backend offline", "bad"), unsafe_allow_html=True)
        st.sidebar.caption(backend_message)

    use_mock_if_offline = st.sidebar.toggle(
        "Use mock data when backend is offline",
        value=True,
        help="Useful for UI testing before the Arduino/backend is ready.",
    )

    render_serial_controls(client, backend_available)

    auto_refresh = st.sidebar.toggle(
        "Start / pause live reading",
        value=True,
        help="Toggle to start or pause live reading.",
    )

    if st.sidebar.button(
        "Reset live readings",
        width='stretch',
        help="Clears the currently displayed live readings and restarts the visible charts from the next incoming sample. This does not delete saved sessions.",
    ):
        reset_live_readings(
            use_mock_if_offline=use_mock_if_offline,
            backend_available=backend_available,
        )
        st.rerun()

    st.sidebar.divider()

    mode = st.sidebar.selectbox(
        "Pump mode",
        options=get_mode_options(),
        format_func=get_mode_label,
        key="selected_mode",
        disabled=st.session_state.recording,
    )

    default_name = make_default_session_name(mode)
    session_name = st.sidebar.text_input("Session name", value=default_name)

    col_start, col_stop = st.sidebar.columns(2)

    with col_start:
        start_clicked = st.button(
            "Start",
            type="primary",
            width='stretch',
            disabled=st.session_state.recording,
        )

    with col_stop:
        stop_clicked = st.button(
            "Stop",
            width='stretch',
            disabled=not st.session_state.recording,
        )

    if start_clicked:
        if backend_available:
            try:
                created = client.start_session(session_name, mode)
                st.session_state.active_session = created
                st.session_state.recording = True
                st.session_state.last_error = ""
                st.rerun()
            except BackendError as exc:
                st.session_state.last_error = str(exc)
        elif use_mock_if_offline:
            st.session_state.active_session = {
                "id": "mock-session",
                "name": session_name,
                "pump_mode": mode,
                "started_at": datetime.now().isoformat(),
            }
            st.session_state.recording = True
            st.session_state.last_error = (
                "Backend is offline. Recording is simulated and will not be saved."
            )
            st.rerun()
        else:
            st.session_state.last_error = "Backend is offline. Cannot start a saved session."

    if stop_clicked:
        if backend_available:
            try:
                client.stop_session()
                st.session_state.recording = False
                st.session_state.active_session = None
                st.session_state.last_error = ""
                st.rerun()
            except BackendError as exc:
                st.session_state.last_error = str(exc)
        else:
            st.session_state.recording = False
            st.session_state.active_session = None
            st.session_state.last_error = "Stopped simulated recording."
            st.rerun()

    st.sidebar.divider()

    active = st.session_state.active_session
    st.sidebar.subheader("Active session")
    if active:
        st.sidebar.write(f"**{active.get('name', 'Untitled session')}**")
        st.sidebar.caption(f"Mode: {active.get('pump_mode', mode)}")
        st.sidebar.caption(f"ID: {active.get('id', '—')}")
    else:
        st.sidebar.caption("No active recording session.")

    return {
        "mode": mode,
        "session_name": session_name,
        "use_mock_if_offline": use_mock_if_offline,
        "auto_refresh": auto_refresh,
    }


def render_mode_context(mode: str, using_mock: bool, backend_available: bool) -> None:
    mode_info = get_mode(mode)

    c1, c2, c3 = st.columns([1.2, 1.2, 1])

    with c1:
        st.markdown(
            f"""
            <div class="info-card">
                <div class="eyebrow">Pump configuration</div>
                <h3>{mode_info["label"]}</h3>
                <p>{mode_info["description"]}</p>
                <div class="formula-pill">{mode_info["formula"]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            """
            <div class="info-card">
                <div class="eyebrow">DAQ fields</div>
                <h3>Expected incoming columns</h3>
                <p>
                    <b>timer</b>, <b>flow_l_hr</b><br>
                    <b>p1_suction</b>, <b>p1_discharge</b><br>
                    <b>p2_suction</b>, <b>p2_discharge</b>
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c3:
        status_label = "Recording" if st.session_state.recording else "Monitoring"
        source_label = "Mock data" if using_mock else "Backend data"
        status_type = "warn" if using_mock else "good" if backend_available else "bad"

        st.markdown(
            (
                f'<div class="info-card">'
                f'<div class="eyebrow">Current status</div>'
                f'<h3>{status_label}</h3>'
                f'{status_pill(source_label, status_type)}'
                f'<p style="margin-top: 0.85rem;">Mode badge: <b>{mode_info["badge"]}</b></p>'
                f'</div>'
            ),
            unsafe_allow_html=True,
        )


def render_metrics(df: pd.DataFrame) -> None:
    latest = df.iloc[-1].to_dict() if not df.empty else {}

    m1, m2, m3 = st.columns(3)
    m1.metric("Timer", format_number(latest.get("timer"), 0))
    m2.metric("Flow rate", f"{format_integer(latest.get('flow_l_hr'))} L/hr")
    m3.metric("Computed head", f"{format_number(latest.get('head_ft'))} ft")

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("P1 suction", f"{format_number(latest.get('p1_suction'))} psi")
    p2.metric("P1 discharge", f"{format_number(latest.get('p1_discharge'))} psi")
    p3.metric("P2 suction", f"{format_number(latest.get('p2_suction'))} psi")
    p4.metric("P2 discharge", f"{format_number(latest.get('p2_discharge'))} psi")


def get_current_live_frame(
    client: ApiClient,
    backend_available: bool,
    use_mock_if_offline: bool,
    mode: str,
    recording: bool,
) -> tuple[pd.DataFrame, bool]:
    using_mock = use_mock_if_offline and not backend_available

    if time.time() < float(st.session_state.get("live_reset_empty_until", 0.0) or 0.0):
        return samples_to_dataframe([], mode), using_mock

    cache_key = (
        int(time.time() // LIVE_REFRESH_INTERVAL_SECONDS),
        st.session_state.backend_url,
        backend_available,
        use_mock_if_offline,
        mode,
        recording,
        st.session_state.get("live_reset_timer"),
        str(st.session_state.get("live_reset_timestamp")),
    )

    if st.session_state.get("live_frame_cache_key") == cache_key:
        cached_df = st.session_state.get("live_frame_cache_df")
        if isinstance(cached_df, pd.DataFrame):
            return cached_df.copy(), bool(st.session_state.get("live_frame_cache_using_mock", False))

    df, using_mock = load_live_samples(
        client=client,
        backend_available=backend_available,
        use_mock_if_offline=use_mock_if_offline,
        mode=mode,
        recording=recording,
    )

    remember_current_live_position(df)
    df = apply_live_reset_filter(df)

    st.session_state.live_frame_cache_key = cache_key
    st.session_state.live_frame_cache_df = df.copy()
    st.session_state.live_frame_cache_using_mock = using_mock

    return df, using_mock


def render_live_dashboard(
    df: pd.DataFrame,
    mode: str,
    key_prefix: str = "live",
    show_raw_readings: bool = True,
    raw_readings_label: str = "Show latest raw readings",
    raw_readings_limit: int | None = 25,
    show_metrics: bool = True,
) -> None:
    if show_metrics:
        render_metrics(df)
        st.divider()

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Pressure over timer")
        st.plotly_chart(pressure_time_chart(df), width='stretch', key=f"{key_prefix}_pressure_time_chart")

    with col_b:
        st.subheader("Flow and head over timer")
        st.plotly_chart(flow_head_time_chart(df), width='stretch', key=f"{key_prefix}_flow_head_time_chart")


    st.subheader("Head vs. Flow curve")
    # st.caption(
    #     "This is the pump performance plot. Unlike the timer graph, the x-axis is flow and the y-axis is computed head."
    # )
    st.plotly_chart(
        head_flow_curve(df, title=get_mode_label(mode)),
        width='stretch',
        key=f"{key_prefix}_head_flow_curve",
    )

    if show_raw_readings:
        with st.expander(raw_readings_label):
            if df.empty:
                st.info("No readings available yet.")
            else:
                display_cols = [
                    "timer",
                    "flow_l_hr",
                    "head_ft",
                    "p1_suction",
                    "p1_discharge",
                    "p2_suction",
                    "p2_discharge",
                    "pump_mode",
                    "timestamp",
                    "is_recording",
                    "session_id",
                ]
                table_df = df[display_cols]
                if raw_readings_limit is None:
                    table_df = table_df.sort_values("timer", ascending=True)
                else:
                    table_df = table_df.tail(raw_readings_limit).sort_values("timer", ascending=False)

                st.dataframe(
                    table_df,
                    width='stretch',
                    hide_index=True,
                )


def render_live_dashboard_partial(
    client: ApiClient,
    backend_available: bool,
    use_mock_if_offline: bool,
    mode: str,
    recording: bool,
    auto_refresh: bool,
) -> None:
    if auto_refresh and hasattr(st, "fragment"):
        render_live_dashboard_fragment(
            st.session_state.backend_url,
            backend_available,
            use_mock_if_offline,
            mode,
            recording,
        )
    else:
        df, _ = get_current_live_frame(
            client=client,
            backend_available=backend_available,
            use_mock_if_offline=use_mock_if_offline,
            mode=mode,
            recording=recording,
        )
        render_live_dashboard(df, mode)


if hasattr(st, "fragment"):
    @st.fragment(run_every=f"{LIVE_REFRESH_INTERVAL_SECONDS}s")
    def render_live_dashboard_fragment(
        backend_url: str,
        backend_available: bool,
        use_mock_if_offline: bool,
        mode: str,
        recording: bool,
    ) -> None:
        fragment_client = ApiClient(backend_url)
        df, _ = get_current_live_frame(
            client=fragment_client,
            backend_available=backend_available,
            use_mock_if_offline=use_mock_if_offline,
            mode=mode,
            recording=recording,
        )
        render_live_dashboard(df, mode)
else:
    def render_live_dashboard_fragment(*args, **kwargs) -> None:
        return None


def render_session_tab(client: ApiClient, backend_available: bool, mode: str) -> None:
    st.subheader("Saved sessions")

    if not backend_available:
        st.warning("Backend is offline. Saved sessions and CSV export are unavailable.")
        return

    try:
        sessions = client.get_sessions()
    except BackendError as exc:
        st.error(str(exc))
        return

    if not sessions:
        st.info("No saved sessions yet. Start and stop a recording to create one.")
        return

    session_df = pd.DataFrame(sessions)
    visible_cols = [
        col
        for col in [
            "id",
            "name",
            "pump_mode",
            "started_at",
            "ended_at",
            "sample_count",
        ]
        if col in session_df.columns
    ]

    st.dataframe(session_df[visible_cols], width='stretch', hide_index=True)

    session_labels = {
        str(item.get("id")): f"{item.get('name', 'Untitled')} [{item.get('pump_mode', 'mode?')}]"
        for item in sessions
    }

    selected_ids = st.multiselect(
        "Select sessions to compare",
        options=list(session_labels.keys()),
        format_func=lambda sid: session_labels.get(sid, sid),
        max_selections=4,
    )

    col_load, col_clear = st.columns([1, 1])

    with col_load:
        compare_clicked = st.button(
            "Compare selected",
            type="primary",
            disabled=not selected_ids,
            width='stretch',
        )

    with col_clear:
        if st.button("Clear comparison", width='stretch'):
            st.session_state.comparison_frames = {}
            st.session_state.comparison_labels = {}

    if compare_clicked:
        frames = {}
        labels = {}

        for session_id in selected_ids:
            try:
                samples = client.get_session_samples(session_id)
                frames[session_id] = samples_to_dataframe(samples, mode)
                labels[session_id] = session_labels.get(session_id, session_id)
            except BackendError as exc:
                st.error(f"Failed to load {session_labels.get(session_id, session_id)}: {exc}")

        st.session_state.comparison_frames = frames
        st.session_state.comparison_labels = labels

    if st.session_state.comparison_frames:
        st.subheader("Session comparison curve")
        st.plotly_chart(
            comparison_curve(
                st.session_state.comparison_frames,
                st.session_state.comparison_labels,
            ),
            width='stretch',
        )

        summary_rows = []
        for session_id, frame in st.session_state.comparison_frames.items():
            summary = summarize_dataframe(frame)
            summary_rows.append(
                {
                    "Session": st.session_state.comparison_labels.get(session_id, session_id),
                    "Samples": summary["sample_count"],
                    "Latest timer": round(summary["latest_timer"], 0),
                    "Avg Flow (L/hr)": round(summary["avg_flow_l_hr"], 2),
                    "Max Flow (L/hr)": round(summary["max_flow_l_hr"], 2),
                    "Avg Head (ft)": round(summary["avg_head_ft"], 2),
                    "Max Head (ft)": round(summary["max_head_ft"], 2),
                }
            )

        st.dataframe(pd.DataFrame(summary_rows), width='stretch', hide_index=True)


def render_load_session_tab(client: ApiClient, backend_available: bool, fallback_mode: str) -> None:
    st.subheader("Load Session")

    if not backend_available:
        st.warning("Backend is offline. Load session and CSV export are unavailable.")
        return

    try:
        sessions = client.get_sessions()
    except BackendError as exc:
        st.error(str(exc))
        return

    if not sessions:
        st.info("No saved sessions yet. Start and stop a recording to create one.")
        return

    session_labels = {
        str(item.get("id")): f"{item.get('name', 'Untitled')} [{item.get('pump_mode', 'mode?')}]"
        for item in sessions
    }
    session_lookup = {str(item.get("id")): item for item in sessions}

    selected_session_id = st.selectbox(
        "Choose an existing session",
        options=list(session_labels.keys()),
        format_func=lambda sid: session_labels.get(sid, sid),
        key="load_session_selectbox",
    )

    selected_info = session_lookup.get(str(selected_session_id), {})
    selected_mode = str(selected_info.get("pump_mode") or fallback_mode)

    load_col, download_col = st.columns([1, 1])
    with load_col:
        load_clicked = st.button(
            "Load selected session",
            type="primary",
            width='stretch',
            disabled=not selected_session_id,
        )

    with download_col:
        if selected_session_id:
            st.link_button(
                "Download selected CSV",
                client.export_url(str(selected_session_id)),
                width='stretch',
            )

    if load_clicked and selected_session_id:
        try:
            samples = client.get_session_samples(str(selected_session_id))
            loaded_df = samples_to_dataframe(samples, selected_mode)
            st.session_state.loaded_session_id = str(selected_session_id)
            st.session_state.loaded_session_info = selected_info
            st.session_state.loaded_session_frame = loaded_df
            st.session_state.last_error = ""
            st.rerun()
        except BackendError as exc:
            st.error(f"Failed to load session: {exc}")
            return

    loaded_df = st.session_state.get("loaded_session_frame")
    loaded_info = st.session_state.get("loaded_session_info") or {}
    loaded_session_id = st.session_state.get("loaded_session_id")

    if not isinstance(loaded_df, pd.DataFrame) or loaded_df.empty or not loaded_session_id:
        st.info("Select a saved session, then click Load selected session to view its summary, graphs, and readings table.")
        return

    loaded_mode = str(loaded_info.get("pump_mode") or fallback_mode)
    st.markdown(f"**{loaded_info.get('name', 'Untitled session')}**")
    st.caption(
        f"Mode: {get_mode_label(loaded_mode)} · "
        f"Started: {format_datetime_label(loaded_info.get('started_at'))} · "
        f"Ended: {format_datetime_label(loaded_info.get('ended_at'))}"
    )

    render_summary_panel(loaded_df, title="Loaded session summary")

    st.divider()
    render_live_dashboard(
        loaded_df,
        loaded_mode,
        key_prefix=f"loaded_session_{loaded_session_id}",
        raw_readings_label="Show session readings table",
        raw_readings_limit=None,
        show_metrics=False,
    )


def render_summary_panel(df: pd.DataFrame, title: str = "Current run summary") -> None:
    st.subheader(title)
    summary = summarize_dataframe(df)

    c1, c2, c3 = st.columns(3)
    c1.metric("Samples", f"{summary['sample_count']:,}")
    c2.metric("Latest timer", f"{summary['latest_timer']:,.0f}")
    c3.metric("Average flow", f"{summary['avg_flow_l_hr']:,.0f} L/hr")

    c5, c6, c7 = st.columns(3)
    c5.metric("Average head", f"{summary['avg_head_ft']:,.2f} ft")
    c6.metric("Max head", f"{summary['max_head_ft']:,.2f} ft")
    c7.metric("Max flow", f"{summary['max_flow_l_hr']:,.0f} L/hr")


def render_summary_panel_partial(
    client: ApiClient,
    backend_available: bool,
    use_mock_if_offline: bool,
    mode: str,
    recording: bool,
    auto_refresh: bool,
) -> None:
    if auto_refresh and hasattr(st, "fragment"):
        render_summary_panel_fragment(
            st.session_state.backend_url,
            backend_available,
            use_mock_if_offline,
            mode,
            recording,
        )
    else:
        df, _ = get_current_live_frame(
            client=client,
            backend_available=backend_available,
            use_mock_if_offline=use_mock_if_offline,
            mode=mode,
            recording=recording,
        )
        render_summary_panel(df)


def parse_quiz_answer(raw_value: str) -> float | None:
    try:
        cleaned = str(raw_value).strip().replace(",", "")
        if not cleaned:
            return None
        return float(cleaned)
    except (TypeError, ValueError):
        return None


def reset_hidden_quiz_answers() -> None:
    generation = int(st.session_state.get("hidden_quiz_generation", 0) or 0)
    for key in list(st.session_state.keys()):
        if key.startswith(f"hidden_quiz_answer_{generation}_"):
            del st.session_state[key]


def _session_identifier(session: dict) -> str:
    for key in ("id", "session_id", "uuid"):
        value = session.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _session_mode(session: dict, fallback_mode: str) -> str:
    raw_mode = str(session.get("pump_mode") or session.get("mode") or fallback_mode).strip().lower()
    return raw_mode if raw_mode in get_mode_options() else fallback_mode


def _session_quiz_label(session: dict, fallback_mode: str) -> str:
    name = session.get("name") or session.get("title") or "Untitled session"
    mode_label = get_mode_label(_session_mode(session, fallback_mode))
    sample_count = session.get("sample_count")
    started_at = session.get("started_at") or session.get("created_at") or ""

    details = [mode_label]
    if sample_count not in (None, ""):
        details.append(f"{sample_count} samples")
    if started_at:
        details.append(str(started_at))

    return f"{name} — {' · '.join(details)}"



def _manual_session_default_name(mode: str) -> str:
    label = get_mode_label(mode)
    now = datetime.now().strftime("%b %d, %I:%M %p")
    return f"Manual {label} run - {now}"


def _manual_samples_payload(samples: list[dict]) -> list[dict]:
    payload = []
    for index, sample in enumerate(samples, start=1):
        payload.append(
            {
                "timestamp": str(sample.get("timestamp") or datetime.now().isoformat(timespec="seconds")),
                "timer": float(sample.get("timer") or index),
                "flow_l_hr": float(sample.get("flow_l_hr") or 0.0),
                "p1_suction": float(sample.get("p1_suction") or 0.0),
                "p1_discharge": float(sample.get("p1_discharge") or 0.0),
                "p2_suction": float(sample.get("p2_suction") or 0.0),
                "p2_discharge": float(sample.get("p2_discharge") or 0.0),
            }
        )
    return payload


def save_manual_pressure_session(
    client: ApiClient,
    name: str,
    mode: str,
    samples: list[dict],
) -> dict:
    return client._request(
        "POST",
        "/api/sessions/manual",
        json={
            "name": name.strip(),
            "pump_mode": mode,
            "notes": "Saved from the Live flow + manual pressure tab.",
            "samples": _manual_samples_payload(samples),
        },
        timeout=(1.0, 12.0),
    )


def _manual_pressure_flow_stats(df: pd.DataFrame) -> tuple[float | None, int]:
    if df.empty or "flow_l_hr" not in df.columns:
        return None, 0

    flow_series = pd.to_numeric(df["flow_l_hr"], errors="coerce").dropna()
    if flow_series.empty:
        return None, 0

    return float(flow_series.mean()), int(flow_series.count())


def update_manual_pressure_flow_state(df: pd.DataFrame) -> None:
    flow_avg, sample_count = _manual_pressure_flow_stats(df)
    st.session_state.manual_pressure_flow_avg = flow_avg
    st.session_state.manual_pressure_flow_sample_count = sample_count
    st.session_state.manual_pressure_flow_updated_at = datetime.now().isoformat(timespec="seconds")


def render_manual_pressure_live_source(df: pd.DataFrame) -> None:
    update_manual_pressure_flow_state(df)

    flow_avg = st.session_state.get("manual_pressure_flow_avg")
    sample_count = int(st.session_state.get("manual_pressure_flow_sample_count") or 0)

    status_cols = st.columns(2)
    if flow_avg is None:
        status_cols[0].metric("Average live flow", "— L/hr")
    else:
        status_cols[0].metric("Average live flow", f"{format_integer(flow_avg)} L/hr")
    status_cols[1].metric("Live flow samples averaged", f"{sample_count:,}")

    if flow_avg is None:
        st.warning(
            "No live flow reading is available yet. Start the backend/serial connection or enable mock data before appending samples."
        )
    else:
        updated_at = st.session_state.get("manual_pressure_flow_updated_at") or "now"
        st.caption(
            "Flow is computed as the average of the currently visible live flow readings. "
            f"Last refreshed: {updated_at}."
        )


def render_manual_pressure_live_source_partial(
    client: ApiClient,
    backend_available: bool,
    use_mock_if_offline: bool,
    mode: str,
    recording: bool,
    auto_refresh: bool,
) -> None:
    if auto_refresh and hasattr(st, "fragment"):
        render_manual_pressure_live_source_fragment(
            st.session_state.backend_url,
            backend_available,
            use_mock_if_offline,
            mode,
            recording,
        )
    else:
        df, _ = get_current_live_frame(
            client=client,
            backend_available=backend_available,
            use_mock_if_offline=use_mock_if_offline,
            mode=mode,
            recording=recording,
        )
        render_manual_pressure_live_source(df)


def render_manual_pressure_tab(
    client: ApiClient,
    backend_available: bool,
    use_mock_if_offline: bool,
    mode: str,
    recording: bool,
    auto_refresh: bool,
) -> None:
    st.subheader("Live flow + manual pressure readings")
    st.caption(
        "Use the average flow meter value from the visible live readings, then manually enter the four pressure readings. "
        "Each appended sample is shown with the same metrics and charts as the live dashboard."
    )

    render_manual_pressure_live_source_partial(
        client=client,
        backend_available=backend_available,
        use_mock_if_offline=use_mock_if_offline,
        mode=mode,
        recording=recording,
        auto_refresh=auto_refresh,
    )

    st.markdown("#### Enter pressure readings")
    p1, p2, p3, p4 = st.columns(4)
    with p1:
        p1_suction = st.number_input("P1 suction (psi)", min_value=0.0, value=0.0, step=0.01, format="%.2f", key="manual_p1_suction")
    with p2:
        p1_discharge = st.number_input("P1 discharge (psi)", min_value=0.0, value=0.0, step=0.01, format="%.2f", key="manual_p1_discharge")
    with p3:
        p2_suction = st.number_input("P2 suction (psi)", min_value=0.0, value=0.0, step=0.01, format="%.2f", key="manual_p2_suction")
    with p4:
        p2_discharge = st.number_input("P2 discharge (psi)", min_value=0.0, value=0.0, step=0.01, format="%.2f", key="manual_p2_discharge")

    flow_avg = st.session_state.get("manual_pressure_flow_avg")
    flow_available = flow_avg is not None

    append_col, clear_col = st.columns([1, 1])
    with append_col:
        append_clicked = st.button(
            "Append sample",
            type="primary",
            width="stretch",
            disabled=not flow_available,
            help="Adds one row using the current average live flow value and the pressure values you entered.",
        )
    with clear_col:
        clear_clicked = st.button(
            "Clear manual table",
            width="stretch",
            disabled=not st.session_state.manual_pressure_samples,
        )

    if clear_clicked:
        st.session_state.manual_pressure_samples = []
        st.session_state.manual_pressure_last_saved_session = None
        st.rerun()

    if append_clicked and flow_available:
        sample_number = len(st.session_state.manual_pressure_samples) + 1
        sample = normalize_sample(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "timer": sample_number,
                "flow_l_hr": float(flow_avg),
                "p1_suction": p1_suction,
                "p1_discharge": p1_discharge,
                "p2_suction": p2_suction,
                "p2_discharge": p2_discharge,
                "pump_mode": mode,
                "is_recording": False,
                "session_id": "manual-pressure-input",
            },
            mode,
        )
        st.session_state.manual_pressure_samples.append(sample)
        st.session_state.manual_pressure_last_saved_session = None
        st.rerun()

    manual_df = samples_to_dataframe(st.session_state.manual_pressure_samples, mode)

    st.divider()
    st.markdown("#### Save manual samples")
    if not st.session_state.get("manual_pressure_session_name"):
        st.session_state.manual_pressure_session_name = _manual_session_default_name(mode)

    save_name = st.text_input(
        "Manual saved session name",
        key="manual_pressure_session_name",
        help="This name will appear in Saved sessions, session comparison, and export CSV.",
    )

    save_disabled = manual_df.empty or not backend_available or not str(save_name).strip()
    save_clicked = st.button(
        "Save appended samples to Saved sessions",
        type="primary",
        width="stretch",
        disabled=save_disabled,
        help="Creates a normal backend saved session from the appended manual sample table.",
    )

    if manual_df.empty:
        st.caption("Append at least one sample before saving as a session.")
    elif not backend_available:
        st.warning("Backend is offline. Start the backend before saving manual samples as a session.")

    if save_clicked and not save_disabled:
        try:
            created = save_manual_pressure_session(
                client=client,
                name=save_name,
                mode=mode,
                samples=st.session_state.manual_pressure_samples,
            )
            st.session_state.manual_pressure_last_saved_session = created
            st.success(
                f"Saved manual samples as session #{created.get('id')} — {created.get('name', save_name)}. "
                "It is now available under Saved sessions."
            )
        except BackendError as exc:
            st.error(f"Failed to save manual samples: {exc}")

    last_saved = st.session_state.get("manual_pressure_last_saved_session")
    if last_saved:
        st.caption(
            f"Last saved: session #{last_saved.get('id')} · "
            f"{last_saved.get('sample_count', len(st.session_state.manual_pressure_samples))} samples"
        )

    st.divider()
    if manual_df.empty:
        st.info("No manual pressure samples appended yet.")
    else:
        render_live_dashboard(
            manual_df,
            mode,
            key_prefix="manual_pressure",
            show_raw_readings=False,
        )

    with st.expander("Show appended samples"):
        # if manual_df.empty:
        #     st.info("No manual pressure samples appended yet.")
        # else:
            display_cols = [
                "timer",
                "flow_l_hr",
                "head_ft",
                "p1_suction",
                "p1_discharge",
                "p2_suction",
                "p2_discharge",
                "pump_mode",
                "timestamp",
            ]
            st.dataframe(
                manual_df[display_cols].tail(50).sort_values("timer", ascending=False),
                width="stretch",
                hide_index=True,
            )

def render_hidden_value_quiz_tab(
    current_df: pd.DataFrame,
    mode: str,
    client: ApiClient,
    backend_available: bool,
    auto_refresh: bool,
) -> None:
    st.subheader("Hidden table values quiz")
    st.caption(
        "Compute the missing head value using pressure readings, pump mode, and the head formula."
    )
    # st.info(
    #     "For Current live readings, pause live reading in the sidebar first so the quiz freezes a stable set of values."
    # )

    config_a, config_b = st.columns([1.4, 1])

    with config_a:
        source = st.selectbox(
            "Quiz source",
            options=["Current live readings", "Saved session"],
            key="hidden_quiz_source",
            help=(
                "Use live readings for lab activity, a saved session for post-lab practice, "
                "or sample data for practice without hardware/backend data."
            ),
        )

    with config_b:
        question_count = st.selectbox(
            "Questions",
            options=[3, 5, 8, 10],
            index=1,
            key="hidden_quiz_count",
        )

    quiz_df = pd.DataFrame()
    quiz_mode = mode
    quiz_source_label = source
    selected_session_id = ""
    selected_session_label = ""

    if source == "Current live readings":
        quiz_df = current_df.copy()
        if quiz_df.empty:
            st.info(
                "No live readings are available yet. You can wait for data "
                "or switch the quiz source to saved sessions."
            )

    elif source == "Built-in sample data":
        quiz_df = build_sample_quiz_dataframe(mode)

    else:
        if not backend_available:
            st.warning("Backend is offline. Saved sessions cannot be loaded for the quiz.")
        else:
            try:
                sessions = client.get_sessions()
            except BackendError as exc:
                st.error(f"Failed to load saved sessions: {exc}")
                sessions = []

            valid_sessions = [session for session in sessions if _session_identifier(session)]

            if not valid_sessions:
                st.info("No saved sessions are available yet. Start and stop a recording first.")
            else:
                session_lookup = {_session_identifier(session): session for session in valid_sessions}
                session_labels = {
                    session_id: _session_quiz_label(session, mode)
                    for session_id, session in session_lookup.items()
                }

                selected_session_id = st.selectbox(
                    "Saved session",
                    options=list(session_labels.keys()),
                    format_func=lambda sid: session_labels.get(sid, sid),
                    key="hidden_quiz_session_id",
                    help="The quiz will use the samples and pump mode from this saved session.",
                )

                selected_session = session_lookup.get(selected_session_id, {})
                quiz_mode = _session_mode(selected_session, mode)
                selected_session_label = session_labels.get(selected_session_id, selected_session_id)
                quiz_source_label = f"Saved session: {selected_session_label}"
                st.caption(f"Using {get_mode_label(quiz_mode)} formula for this saved session.")

    live_source_requires_pause = source == "Current live readings" and auto_refresh
    if live_source_requires_pause:
        st.warning("Pause live reading in the sidebar before generating a quiz from current live readings.")

    can_generate = bool(
        not live_source_requires_pause
        and (
            (source == "Saved session" and selected_session_id and backend_available)
            or (source != "Saved session" and not quiz_df.empty)
        )
    )

    action_a, action_b = st.columns([1, 1])

    with action_a:
        generate_clicked = st.button(
            "Generate hidden values quiz",
            type="primary",
            width="stretch",
            disabled=not can_generate,
        )

    with action_b:
        clear_clicked = st.button(
            "Clear quiz",
            width="stretch",
            disabled=not st.session_state.hidden_quiz_questions,
        )

    if clear_clicked:
        reset_hidden_quiz_answers()
        st.session_state.hidden_quiz_questions = []
        st.session_state.hidden_quiz_submitted = False
        st.session_state.hidden_quiz_config = {}
        st.rerun()

    if generate_clicked:
        if source == "Saved session":
            try:
                samples = client.get_session_samples(selected_session_id)
                quiz_df = samples_to_dataframe(samples, quiz_mode)
            except BackendError as exc:
                st.error(f"Failed to load saved session samples: {exc}")
                quiz_df = pd.DataFrame()

        if quiz_df.empty:
            st.warning("This quiz source does not have enough readings to generate questions yet.")
        else:
            st.session_state.hidden_quiz_generation += 1
            reset_hidden_quiz_answers()
            questions = generate_hidden_value_questions(
                quiz_df,
                mode=quiz_mode,
                question_count=question_count,
            )

            if not questions:
                st.warning("This quiz source does not have enough meaningful pressure or flow readings yet.")
            else:
                st.session_state.hidden_quiz_questions = questions
                st.session_state.hidden_quiz_submitted = False
                st.session_state.hidden_quiz_config = {
                    "source": quiz_source_label,
                    "question_count": question_count,
                    "mode": get_mode_label(quiz_mode),
                    "generated_at": datetime.now().strftime("%b %d, %Y %I:%M %p"),
                }
                st.rerun()

    questions = st.session_state.get("hidden_quiz_questions", [])
    if not questions:
        with st.expander("How this quiz works", expanded=True):
            st.write(
                "Each question shows one table row "
                "with the head value hidden. Compute the missing head, then the app checks the "
                "answer with a small tolerance and shows the solution."
            )
        return

    # config = st.session_state.get("hidden_quiz_config", {})
    # st.markdown(
    #     f"**Quiz setup:** {config.get('mode', get_mode_label(mode))} · "
    #     f"{config.get('source', 'Current live readings')} · "
    #     f"Generated {config.get('generated_at', 'just now')}"
    # )

    generation = int(st.session_state.get("hidden_quiz_generation", 0) or 0)

    for index, question in enumerate(questions):
        st.markdown(f"### Question {index + 1}")
        st.write(question["prompt"])
        st.dataframe(pd.DataFrame(question["table"]), width="stretch", hide_index=True)

        answer_key = f"hidden_quiz_answer_{generation}_{index}"
        st.text_input(
            f"Your answer for {question['hidden_label']}",
            key=answer_key,
            placeholder=f"Enter value in {question['unit']}",
        )

        if st.session_state.hidden_quiz_submitted:
            user_answer = parse_quiz_answer(st.session_state.get(answer_key, ""))
            correct_answer = float(question["answer"])
            tolerance = float(question["tolerance"])

            if user_answer is None:
                st.error(
                    f"No valid answer provided. Correct answer: {question['answer_display']} {question['unit']}."
                )
            elif abs(user_answer - correct_answer) <= tolerance:
                st.success(
                    f"Correct. Your answer is within ±{tolerance:g} {question['unit']}."
                )
            else:
                st.error(
                    f"Incorrect. Correct answer: {question['answer_display']} {question['unit']}."
                )

            with st.expander("Show solution", expanded=False):
                st.code(question["solution"], language="text")

    submit_label = "Re-check answers" if st.session_state.hidden_quiz_submitted else "Submit answers"
    if st.button(submit_label, type="primary", width="stretch"):
        st.session_state.hidden_quiz_submitted = True
        st.rerun()

    if st.session_state.hidden_quiz_submitted:
        score = 0
        for index, question in enumerate(questions):
            answer_key = f"hidden_quiz_answer_{generation}_{index}"
            user_answer = parse_quiz_answer(st.session_state.get(answer_key, ""))
            if user_answer is not None and abs(user_answer - float(question["answer"])) <= float(question["tolerance"]):
                score += 1

        st.metric("Quiz score", f"{score}/{len(questions)}")


if hasattr(st, "fragment"):
    @st.fragment(run_every=f"{LIVE_REFRESH_INTERVAL_SECONDS}s")
    def render_manual_pressure_live_source_fragment(
        backend_url: str,
        backend_available: bool,
        use_mock_if_offline: bool,
        mode: str,
        recording: bool,
    ) -> None:
        fragment_client = ApiClient(backend_url)
        df, _ = get_current_live_frame(
            client=fragment_client,
            backend_available=backend_available,
            use_mock_if_offline=use_mock_if_offline,
            mode=mode,
            recording=recording,
        )
        render_manual_pressure_live_source(df)
else:
    def render_manual_pressure_live_source_fragment(*args, **kwargs) -> None:
        return None


if hasattr(st, "fragment"):
    @st.fragment(run_every=f"{LIVE_REFRESH_INTERVAL_SECONDS}s")
    def render_summary_panel_fragment(
        backend_url: str,
        backend_available: bool,
        use_mock_if_offline: bool,
        mode: str,
        recording: bool,
    ) -> None:
        fragment_client = ApiClient(backend_url)
        df, _ = get_current_live_frame(
            client=fragment_client,
            backend_available=backend_available,
            use_mock_if_offline=use_mock_if_offline,
            mode=mode,
            recording=recording,
        )
        render_summary_panel(df)
else:
    def render_summary_panel_fragment(*args, **kwargs) -> None:
        return None


def main() -> None:
    init_state()

    client = get_client()
    backend_available, backend_message = check_backend(client)

    controls = render_sidebar(client, backend_available, backend_message)

    supports_partial_refresh = hasattr(st, "fragment")

    if controls["auto_refresh"] and not supports_partial_refresh:
        if st_autorefresh is not None:
            st_autorefresh(
                interval=LIVE_REFRESH_INTERVAL_SECONDS * 1000,
                key="daq_live_refresh",
            )
        else:
            st.sidebar.warning(
                "Install Streamlit 1.37+ for smoother partial refresh, or install streamlit-autorefresh for the fallback refresh."
            )

    render_header()

    if st.session_state.last_error:
        st.markdown(
            f'<div class="danger-box">{st.session_state.last_error}</div>',
            unsafe_allow_html=True,
        )

    current_df, using_mock = get_current_live_frame(
        client=client,
        backend_available=backend_available,
        use_mock_if_offline=controls["use_mock_if_offline"],
        mode=controls["mode"],
        recording=st.session_state.recording,
    )

    if using_mock:
        st.markdown(
            """
            <div class="notice-box">
                Backend data is unavailable, so the dashboard is showing simulated readings
            </div>
            """,
            unsafe_allow_html=True,
        )

    if st.session_state.get("show_reset_toast"):
        st.toast("Live readings reset. Saved sessions were not deleted.", icon="✅")
        st.session_state.show_reset_toast = False

    render_mode_context(
        mode=controls["mode"],
        using_mock=using_mock,
        backend_available=backend_available,
    )

    st.divider()

    tab_live, tab_load, tab_sessions, tab_summary, tab_manual = st.tabs(
        [
            "Live Dashboard",
            "Load Session",
            "Sessions & Comparison",
            "Summary",
            "Manual Input",
            # "Quizlet",
        ]
    )

    with tab_live:
        render_live_dashboard_partial(
            client=client,
            backend_available=backend_available,
            use_mock_if_offline=controls["use_mock_if_offline"],
            mode=controls["mode"],
            recording=st.session_state.recording,
            auto_refresh=controls["auto_refresh"],
        )

    with tab_load:
        render_load_session_tab(client, backend_available, controls["mode"])

    with tab_sessions:
        render_session_tab(client, backend_available, controls["mode"])

    with tab_summary:
        render_summary_panel_partial(
            client=client,
            backend_available=backend_available,
            use_mock_if_offline=controls["use_mock_if_offline"],
            mode=controls["mode"],
            recording=st.session_state.recording,
            auto_refresh=controls["auto_refresh"],
        )

        with st.expander("Head computation note"):
            st.write(
                """
                For series mode, it uses (P1 discharge − P1 suction) + (P2 discharge − P2 suction).
                For parallel mode, it uses the average of Pump 1 pressure rise and Pump 2 pressure rise.
                Both modes use: Head (ft) = ((pressure term × 144) / 62.4) + velocity head + 3.70735.
                """
            )

        with st.expander("Expected DAQ fields"):
            st.code(
                "timer,flow_l_hr,p1_suction,p1_discharge,p2_suction,p2_discharge",
                language="text",
            )

    with tab_manual:
        render_manual_pressure_tab(
            client=client,
            backend_available=backend_available,
            use_mock_if_offline=controls["use_mock_if_offline"],
            mode=controls["mode"],
            recording=st.session_state.recording,
            auto_refresh=controls["auto_refresh"],
        )

    # with tab_quiz:
    #     render_hidden_value_quiz_tab(
    #         current_df,
    #         controls["mode"],
    #         client,
    #         backend_available,
    #         controls["auto_refresh"],
    #     )


if __name__ == "__main__":
    main()
