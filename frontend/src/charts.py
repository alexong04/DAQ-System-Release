from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def empty_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        showarrow=False,
        xref="paper",
        yref="paper",
        font={"size": 16},
    )
    fig.update_layout(
        height=340,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis={"visible": False},
        yaxis={"visible": False},
    )
    return fig


def pressure_time_chart(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return empty_figure("Pressure readings will appear once samples are received.")

    fig = go.Figure()

    traces = [
        ("p1_suction", "P1 suction"),
        ("p1_discharge", "P1 discharge"),
        ("p2_suction", "P2 suction"),
        ("p2_discharge", "P2 discharge"),
    ]

    for col, label in traces:
        fig.add_trace(
            go.Scatter(
                x=df["timer"],
                y=df[col],
                mode="lines",
                name=label,
                line={"width": 2},
            )
        )

    fig.update_layout(
        height=360,
        margin=dict(l=10, r=10, t=20, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        xaxis_title="Timer",
        yaxis_title="Pressure (psi)",
        hovermode="x unified",
    )

    return fig


def flow_head_time_chart(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return empty_figure("Flow and head readings will appear once samples are received.")

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Scatter(
            x=df["timer"],
            y=df["flow_l_hr"],
            mode="lines",
            name="Flow",
            line={"width": 2},
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=df["timer"],
            y=df["head_ft"],
            mode="lines",
            name="Computed head",
            line={"width": 2},
        ),
        secondary_y=True,
    )

    fig.update_layout(
        height=360,
        margin=dict(l=10, r=10, t=20, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hovermode="x unified",
    )

    fig.update_xaxes(title_text="Timer")
    fig.update_yaxes(title_text="Flow (L/hr)", secondary_y=False)
    fig.update_yaxes(title_text="Head (ft)", secondary_y=True)

    return fig


def pulse_count_chart(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return empty_figure("Pulse count will appear once samples are received.")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["timer"],
            y=df["pulse_count"],
            mode="lines",
            name="Pulse count",
            line={"width": 2},
        )
    )

    fig.update_layout(
        height=280,
        margin=dict(l=10, r=10, t=20, b=10),
        xaxis_title="Timer",
        yaxis_title="Pulse count",
        hovermode="x unified",
    )

    return fig


def head_flow_curve(df: pd.DataFrame, title: str = "Head vs. Flow") -> go.Figure:
    if df.empty:
        return empty_figure("Start monitoring or load a session to plot the pump curve.")

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df["flow_l_hr"],
            y=df["head_ft"],
            mode="markers+lines",
            name=title,
            marker={"size": 8},
            line={"width": 1.5},
            text=df["timer"],
            hovertemplate=(
                "Flow: %{x:,.0f} L/hr<br>"
                "Head: %{y:,.2f} ft<br>"
                "Timer: %{text}<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        height=430,
        margin=dict(l=10, r=10, t=20, b=10),
        xaxis_title="Flow (L/hr)",
        yaxis_title="Computed Head (ft)",
        hovermode="closest",
    )

    return fig


def comparison_curve(session_frames: dict[str, pd.DataFrame], labels: dict[str, str]) -> go.Figure:
    non_empty = {sid: df for sid, df in session_frames.items() if not df.empty}

    if not non_empty:
        return empty_figure("Select sessions and click Compare selected.")

    fig = go.Figure()

    for session_id, df in non_empty.items():
        fig.add_trace(
            go.Scatter(
                x=df["flow_l_hr"],
                y=df["head_ft"],
                mode="markers+lines",
                name=labels.get(session_id, session_id),
                marker={"size": 7},
                line={"width": 1.5},
                hovertemplate=(
                    "Flow: %{x:,.0f} L/hr<br>"
                    "Head: %{y:,.2f} ft<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        height=430,
        margin=dict(l=10, r=10, t=20, b=10),
        xaxis_title="Flow (L/hr)",
        yaxis_title="Computed Head (ft)",
        hovermode="closest",
    )

    return fig
