from __future__ import annotations

from datetime import datetime
import random
from typing import Any

import pandas as pd

from src.engineering import (
    ELEVATION_HEAD_FT,
    PSI_TO_LBF_PER_FT2,
    WATER_SPECIFIC_WEIGHT_LB_FT3,
    compute_head_ft_from_delta_and_flow,
    samples_to_dataframe,
    safe_float,
    velocity_head_ft,
)
from src.pump_modes import get_mode, get_mode_label

PSI_TO_FT_FACTOR = PSI_TO_LBF_PER_FT2 / WATER_SPECIFIC_WEIGHT_LB_FT3

QUIZ_COLUMNS = [
    ("timer", "Timer (s)", 0),
    ("flow_l_hr", "Flow (L/hr)", 0),
    ("p1_suction", "P1 suction (psi)", 2),
    ("p1_discharge", "P1 discharge (psi)", 2),
    ("p2_suction", "P2 suction (psi)", 2),
    ("p2_discharge", "P2 discharge (psi)", 2),
    ("head_ft", "Head (ft)", 2),
]

COLUMN_LABELS = {column: label for column, label, _ in QUIZ_COLUMNS}
COLUMN_DECIMALS = {column: decimals for column, _, decimals in QUIZ_COLUMNS}

DEFAULT_QUESTION_TYPES = ["head"]


def compute_delta_psi(row: pd.Series | dict[str, Any], mode: str) -> float:
    mode_info = get_mode(mode)
    strategy = mode_info.get("head_strategy", "series")

    p1_suction = safe_float(row.get("p1_suction"))
    p1_discharge = safe_float(row.get("p1_discharge"))
    p2_suction = safe_float(row.get("p2_suction"))
    p2_discharge = safe_float(row.get("p2_discharge"))

    pump_1_delta = p1_discharge - p1_suction
    pump_2_delta = p2_discharge - p2_suction

    if strategy == "series":
        delta_psi = pump_1_delta + pump_2_delta
    elif strategy == "parallel":
        delta_psi = (pump_1_delta + pump_2_delta) / 2
    else:
        delta_psi = pump_1_delta + pump_2_delta

    return max(0.0, delta_psi)


def head_offset_ft(flow_l_hr: float) -> float:
    return velocity_head_ft(flow_l_hr) + ELEVATION_HEAD_FT


def compute_head_ft_from_delta(delta_psi: float, flow_l_hr: float) -> float:
    return compute_head_ft_from_delta_and_flow(delta_psi, flow_l_hr)


def compute_delta_psi_from_head(head_ft: float, flow_l_hr: float) -> float:
    return max(0.0, (head_ft - head_offset_ft(flow_l_hr)) / PSI_TO_FT_FACTOR)


def enrich_quiz_frame(df: pd.DataFrame, mode: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[column for column, _, _ in QUIZ_COLUMNS])

    quiz_df = df.copy()

    for column, _, _ in QUIZ_COLUMNS:
        if column not in quiz_df.columns:
            quiz_df[column] = 0.0

    quiz_df["delta_psi"] = quiz_df.apply(lambda row: compute_delta_psi(row, mode), axis=1)

    numeric_cols = [column for column, _, _ in QUIZ_COLUMNS] + ["delta_psi"]
    for column in numeric_cols:
        quiz_df[column] = pd.to_numeric(quiz_df[column], errors="coerce").fillna(0.0)

    # Keep rows with at least a meaningful flow or pressure/head reading.
    quiz_df = quiz_df[
        (quiz_df["flow_l_hr"].abs() > 0)
        | (quiz_df["head_ft"].abs() > 0)
        | (quiz_df["delta_psi"].abs() > 0)
    ].reset_index(drop=True)

    return quiz_df


def build_sample_quiz_dataframe(mode: str) -> pd.DataFrame:
    base_rows = []
    now = datetime.now().isoformat()

    for index in range(1, 9):
        timer = index * 10
        p1_suction = 8.0 + (index % 3) * 0.35

        if mode == "parallel":
            p1_discharge = p1_suction + 15.5 + index * 0.12
            p2_suction = p1_suction + 0.15
            p2_discharge = p2_suction + 15.0 + index * 0.15
            flow_l_hr = 1510 + index * 26
        else:
            p1_discharge = p1_suction + 13.5 + index * 0.18
            p2_suction = p1_discharge - 0.45
            p2_discharge = p2_suction + 12.8 + index * 0.14
            flow_l_hr = 1060 + index * 14

        base_rows.append(
            {
                "timestamp": now,
                "timer": timer,
                "flow_l_hr": flow_l_hr,
                "p1_suction": p1_suction,
                "p1_discharge": p1_discharge,
                "p2_suction": p2_suction,
                "p2_discharge": p2_discharge,
                "pump_mode": mode,
                "is_recording": False,
                "session_id": "sample-quiz-data",
            }
        )

    return samples_to_dataframe(base_rows, mode)


def _format_cell(value: Any, decimals: int) -> str:
    try:
        if decimals == 0:
            return f"{float(value):,.0f}"
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return "—"


def _display_row(row: pd.Series, hidden_column: str) -> dict[str, str]:
    display = {}
    for column, label, decimals in QUIZ_COLUMNS:
        if column == hidden_column:
            display[label] = "____"
        else:
            display[label] = _format_cell(row.get(column), decimals)
    return display


def _formula_phrase(mode: str) -> str:
    mode_info = get_mode(mode)
    return mode_info.get(
        "formula",
        "Head (ft) = ((ΔP × 144) / 62.4) + velocity head + 3.70735",
    )


def _head_question(row: pd.Series, mode: str, question_no: int) -> dict[str, Any]:
    delta_psi = compute_delta_psi(row, mode)
    flow_l_hr = safe_float(row.get("flow_l_hr"))
    velocity_term = velocity_head_ft(flow_l_hr)
    answer = safe_float(row.get("head_ft"))

    return {
        "id": f"q{question_no}_head",
        "type": "head",
        "prompt": "Compute the missing head value in feet.",
        "hidden_column": "head_ft",
        "answer": answer,
        "unit": "ft",
        "tolerance": 0.15,
        "solution": (
            f"Mode: {get_mode_label(mode)}\n"
            f"Formula: {_formula_phrase(mode)}\n"
            f"Pressure term = {delta_psi:.2f} psi\n"
            f"Flow term = {flow_l_hr:.2f} L/hr × 0.00000980965\n"
            f"Velocity head = {velocity_term:.4f} ft\n"
            f"Head = (({delta_psi:.2f} × 144) / 62.4) + {velocity_term:.4f} + 3.70735\n"
            f"Head = {answer:.2f} ft"
        ),
    }


def _delta_question(row: pd.Series, mode: str, question_no: int) -> dict[str, Any]:
    answer = compute_delta_psi(row, mode)
    strategy = get_mode(mode).get("head_strategy", "series")

    pump_1_delta = row["p1_discharge"] - row["p1_suction"]
    pump_2_delta = row["p2_discharge"] - row["p2_suction"]

    if strategy == "series":
        equation = (
            "ΔP = (P1 discharge − P1 suction) + (P2 discharge − P2 suction)\n"
            f"Pump 1 ΔP = {row['p1_discharge']:.2f} − {row['p1_suction']:.2f} = {pump_1_delta:.2f} psi\n"
            f"Pump 2 ΔP = {row['p2_discharge']:.2f} − {row['p2_suction']:.2f} = {pump_2_delta:.2f} psi"
        )
    elif strategy == "parallel":
        equation = (
            "ΔP = average(P1 discharge − P1 suction, P2 discharge − P2 suction)\n"
            f"Pump 1 ΔP = {row['p1_discharge']:.2f} − {row['p1_suction']:.2f} = {pump_1_delta:.2f} psi\n"
            f"Pump 2 ΔP = {row['p2_discharge']:.2f} − {row['p2_suction']:.2f} = {pump_2_delta:.2f} psi"
        )
    else:
        equation = f"ΔP = {answer:.2f} psi"

    return {
        "id": f"q{question_no}_delta",
        "type": "delta",
        "prompt": "Compute the missing pressure term used for the head calculation.",
        "hidden_column": "delta_psi",
        "answer": answer,
        "unit": "psi",
        "tolerance": 0.15,
        "solution": (
            f"Mode: {get_mode_label(mode)}\n"
            f"{equation}\n"
            f"Pressure term = {answer:.2f} psi"
        ),
    }


def _reverse_discharge_question(row: pd.Series, mode: str, question_no: int) -> dict[str, Any]:
    strategy = get_mode(mode).get("head_strategy", "series")
    head_ft = safe_float(row.get("head_ft"))
    flow_l_hr = safe_float(row.get("flow_l_hr"))
    offset_ft = head_offset_ft(flow_l_hr)
    delta_from_head = compute_delta_psi_from_head(head_ft, flow_l_hr)

    hidden_column = "p2_discharge"
    answer = safe_float(row.get(hidden_column))
    pump_1_delta = row["p1_discharge"] - row["p1_suction"]

    if strategy == "parallel":
        pump_2_delta = (2 * delta_from_head) - pump_1_delta
        solution_prefix = "For parallel mode, ΔP is the average of Pump 1 ΔP and Pump 2 ΔP."
    else:
        pump_2_delta = delta_from_head - pump_1_delta
        solution_prefix = "For series mode, ΔP is Pump 1 ΔP plus Pump 2 ΔP."

    solution = (
        f"{solution_prefix}\n"
        f"Pressure term from head = ({head_ft:.2f} − {offset_ft:.2f}) / {PSI_TO_FT_FACTOR:.4f} = {delta_from_head:.2f} psi\n"
        f"Pump 1 ΔP = {row['p1_discharge']:.2f} − {row['p1_suction']:.2f} = {pump_1_delta:.2f} psi\n"
        f"Pump 2 ΔP = {pump_2_delta:.2f} psi\n"
        f"P2 discharge = P2 suction + Pump 2 ΔP = {row['p2_suction']:.2f} + {pump_2_delta:.2f}\n"
        f"P2 discharge = {answer:.2f} psi"
    )

    return {
        "id": f"q{question_no}_reverse_discharge",
        "type": "reverse_discharge",
        "prompt": "Solve for the missing discharge pressure using the given head value.",
        "hidden_column": hidden_column,
        "answer": answer,
        "unit": "psi",
        "tolerance": 0.20,
        "solution": f"Mode: {get_mode_label(mode)}\n{solution}",
    }


def _reverse_suction_question(row: pd.Series, mode: str, question_no: int) -> dict[str, Any]:
    strategy = get_mode(mode).get("head_strategy", "series")
    head_ft = safe_float(row.get("head_ft"))
    flow_l_hr = safe_float(row.get("flow_l_hr"))
    offset_ft = head_offset_ft(flow_l_hr)
    delta_from_head = compute_delta_psi_from_head(head_ft, flow_l_hr)

    if strategy == "parallel":
        hidden_column = "p2_suction"
        answer = safe_float(row.get(hidden_column))
        pump_1_delta = row["p1_discharge"] - row["p1_suction"]
        pump_2_delta = (2 * delta_from_head) - pump_1_delta
        solution = (
            "For parallel mode, ΔP is the average of Pump 1 ΔP and Pump 2 ΔP.\n"
            f"Pressure term from head = ({head_ft:.2f} − {offset_ft:.2f}) / {PSI_TO_FT_FACTOR:.4f} = {delta_from_head:.2f} psi\n"
            f"Pump 1 ΔP = {row['p1_discharge']:.2f} − {row['p1_suction']:.2f} = {pump_1_delta:.2f} psi\n"
            f"Pump 2 ΔP = (2 × {delta_from_head:.2f}) − {pump_1_delta:.2f} = {pump_2_delta:.2f} psi\n"
            f"P2 suction = P2 discharge − Pump 2 ΔP = {row['p2_discharge']:.2f} − {pump_2_delta:.2f}\n"
            f"P2 suction = {answer:.2f} psi"
        )
    else:
        hidden_column = "p1_suction"
        answer = safe_float(row.get(hidden_column))
        pump_2_delta = row["p2_discharge"] - row["p2_suction"]
        pump_1_delta = delta_from_head - pump_2_delta
        solution = (
            "For series mode, ΔP is Pump 1 ΔP plus Pump 2 ΔP.\n"
            f"Pressure term from head = ({head_ft:.2f} − {offset_ft:.2f}) / {PSI_TO_FT_FACTOR:.4f} = {delta_from_head:.2f} psi\n"
            f"Pump 2 ΔP = {row['p2_discharge']:.2f} − {row['p2_suction']:.2f} = {pump_2_delta:.2f} psi\n"
            f"Pump 1 ΔP = {delta_from_head:.2f} − {pump_2_delta:.2f} = {pump_1_delta:.2f} psi\n"
            f"P1 suction = P1 discharge − Pump 1 ΔP = {row['p1_discharge']:.2f} − {pump_1_delta:.2f}\n"
            f"P1 suction = {answer:.2f} psi"
        )

    return {
        "id": f"q{question_no}_reverse_suction",
        "type": "reverse_suction",
        "prompt": "Solve for the missing suction pressure using the given head value.",
        "hidden_column": hidden_column,
        "answer": answer,
        "unit": "psi",
        "tolerance": 0.20,
        "solution": f"Mode: {get_mode_label(mode)}\n{solution}",
    }


def _make_question(row: pd.Series, mode: str, question_type: str, question_no: int) -> dict[str, Any]:
    if question_type == "delta":
        question = _delta_question(row, mode, question_no)
    elif question_type == "reverse_discharge":
        question = _reverse_discharge_question(row, mode, question_no)
    elif question_type == "reverse_suction":
        question = _reverse_suction_question(row, mode, question_no)
    else:
        question = _head_question(row, mode, question_no)

    question["table"] = [_display_row(row, question["hidden_column"])]
    question["hidden_label"] = COLUMN_LABELS.get(question["hidden_column"], question["hidden_column"])
    question["answer_display"] = _format_cell(
        question["answer"], COLUMN_DECIMALS.get(question["hidden_column"], 2)
    )
    return question


def generate_hidden_value_questions(
    df: pd.DataFrame,
    mode: str,
    question_count: int = 5,
) -> list[dict[str, Any]]:
    quiz_df = enrich_quiz_frame(df, mode)
    if quiz_df.empty:
        return []

    question_count = max(1, min(int(question_count), 10))
    question_types = DEFAULT_QUESTION_TYPES

    # Use recent rows, then sample from them so the quiz feels connected to the current run
    # but does not always hide values from the exact same timestamps.
    recent_df = quiz_df.tail(max(question_count * 4, 12)).reset_index(drop=True)
    rows = recent_df.to_dict("records")
    random.shuffle(rows)

    questions: list[dict[str, Any]] = []
    for idx in range(question_count):
        row_data = rows[idx % len(rows)]
        row = pd.Series(row_data)
        question_type = question_types[idx % len(question_types)]
        questions.append(_make_question(row, mode, question_type, idx + 1))

    return questions
