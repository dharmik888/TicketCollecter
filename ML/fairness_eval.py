"""
======================================================================
FAIR DROP - FAIRNESS EVALUATION ENGINE
======================================================================

Purpose:
    Compare:

        BASELINE
        --------
        Naive First-Come-First-Served allocation

        FAIR DROP
        ---------
        ML detection + adaptive policy + fair lottery

    across:

        1. Normal traffic
        2. Flood attack
        3. Rapid retry attack
        4. Multi-session attack
        5. Distributed attack
        6. Stealth bot
        7. Adaptive bot

Core metrics:

    - Bot allocation rate
    - Human allocation rate
    - Bot success rate
    - Human success rate
    - False positive rate
    - False negative rate
    - Average waiting time
    - Median waiting time
    - P95 waiting time
    - Duplicate allocations
    - Overselling
    - Inventory consistency
    - Requests/sec
    - Detection latency
    - Attack advantage
    - Jain fairness index
    - Lottery fairness deviation
    - Eligible users
    - Lottery entries

Important architecture principle:

    ML DOES NOT SELECT TICKETS.

    ML -> Risk -> Adaptive Policy -> Eligibility

    Eligibility -> Equal Lottery Entry

    Lottery -> Winner Selection

======================================================================
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


# ======================================================================
# CONFIGURATION
# ======================================================================

DEFAULT_CAPACITY = 500

SCENARIOS = [
    "normal",
    "flood",
    "rapid_retry",
    "multi_session",
    "distributed",
    "stealth",
    "adaptive",
]


# ======================================================================
# DATA STRUCTURE
# ======================================================================

@dataclass
class EvaluationResult:

    scenario: str
    system: str

    # Population
    total_users: int
    human_users: int
    bot_users: int
    eligible_users: int
    lottery_entries: int

    # Traffic
    total_requests: int
    requests_per_second: float

    # Allocation
    capacity: int
    allocated_tickets: int
    human_tickets: int
    bot_tickets: int

    # Success rates
    human_success_rate: float
    bot_success_rate: float

    # Allocation composition
    human_allocation_rate: float
    bot_allocation_rate: float

    # Detection
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int

    false_positive_rate: float
    false_negative_rate: float
    detection_rate: float

    # Timing
    average_waiting_time: float
    median_waiting_time: float
    p95_waiting_time: float

    # Detection latency
    average_detection_latency: float
    p95_detection_latency: float

    # Reliability
    duplicate_allocations: int
    oversold: int
    inventory_consistent: bool

    # Fairness
    attack_advantage: float
    jain_fairness: float
    expected_allocation_probability: float
    observed_allocation_probability: float
    lottery_fairness_deviation: float


# ======================================================================
# SAFE MATH HELPERS
# ======================================================================

def safe_divide(numerator: float, denominator: float) -> float:
    """
    Safe division.

    Returns 0 when denominator is zero.
    """

    if denominator == 0:
        return 0.0

    return float(numerator) / float(denominator)


def clean_float(value) -> float:
    """
    Convert values to finite float.
    """

    try:
        value = float(value)

        if not math.isfinite(value):
            return 0.0

        return value

    except (TypeError, ValueError):
        return 0.0


# ======================================================================
# BOOLEAN NORMALIZATION
# ======================================================================

def normalize_bool_series(series: pd.Series) -> pd.Series:
    """
    Convert common boolean representations into real booleans.
    """

    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)

    mapping = {
        True: True,
        False: False,

        1: True,
        0: False,

        "1": True,
        "0": False,

        "true": True,
        "false": False,

        "True": True,
        "False": False,

        "yes": True,
        "no": False,

        "YES": True,
        "NO": False,

        "y": True,
        "n": False,
    }

    return series.map(
        lambda x: mapping.get(x, False)
    ).astype(bool)


# ======================================================================
# COLUMN DISCOVERY
# ======================================================================

def find_column(
    df: pd.DataFrame,
    candidates: list[str]
) -> Optional[str]:
    """
    Find the first matching column from candidates.
    """

    lower_map = {
        str(column).lower(): column
        for column in df.columns
    }

    for candidate in candidates:

        if candidate in df.columns:
            return candidate

        candidate_lower = candidate.lower()

        if candidate_lower in lower_map:
            return lower_map[candidate_lower]

    return None


# ======================================================================
# USER TYPE NORMALIZATION
# ======================================================================

def normalize_user_type(value) -> str:
    """
    Normalize simulator user-type values.

    Returns:
        human
        bot
        unknown
    """

    value = str(value).strip().lower()

    human_values = {
        "human",
        "genuine",
        "legitimate",
        "real",
        "user",
    }

    bot_values = {
        "bot",
        "aggressive_bot",
        "rapid_retry_bot",
        "multi_session_bot",
        "distributed_bot",
        "stealth_bot",
        "adaptive_bot",
    }

    if value in human_values:
        return "human"

    if value in bot_values:
        return "bot"

    if "bot" in value:
        return "bot"

    return "unknown"


# ======================================================================
# JAIN FAIRNESS INDEX
# ======================================================================

def jains_fairness(values) -> float:
    """
    Jain's fairness index.

        J = (sum(x_i)^2) /
            (n * sum(x_i^2))

    Range:
        0 -> maximum inequality
        1 -> perfect equality
    """

    values = np.asarray(
        list(values),
        dtype=float
    )

    if len(values) == 0:
        return 1.0

    values = np.nan_to_num(
        values,
        nan=0.0,
        posinf=0.0,
        neginf=0.0
    )

    numerator = np.sum(values) ** 2

    denominator = (
        len(values) *
        np.sum(values ** 2)
    )

    if denominator == 0:
        return 1.0

    return float(
        numerator / denominator
    )


# ======================================================================
# PREPARE DATASET
# ======================================================================

def prepare_dataset(
    df: pd.DataFrame
) -> pd.DataFrame:
    """
    Normalize the evaluation dataset.

    Supported input columns include:

        user_id
        user_type
        allocated
        eligible
        expected_bot
        detected_bot
        waiting_time
        detection_latency
        timestamp
    """

    df = df.copy()

    # --------------------------------------------------------------
    # USER ID
    # --------------------------------------------------------------

    user_id_col = find_column(
        df,
        [
            "user_id",
            "userid",
            "user",
            "id",
        ]
    )

    if user_id_col is None:

        df["user_id"] = np.arange(
            len(df)
        )

    elif user_id_col != "user_id":

        df["user_id"] = df[
            user_id_col
        ]

    # --------------------------------------------------------------
    # USER TYPE
    # --------------------------------------------------------------

    user_type_col = find_column(
        df,
        [
            "user_type",
            "type",
            "traffic_type",
            "actor_type",
        ]
    )

    if user_type_col is None:

        raise ValueError(
            "Dataset must contain a user_type column."
        )

    df["user_type"] = (
        df[user_type_col]
        .apply(normalize_user_type)
    )

    # Remove unknown types from population
    # only when possible.
    df.loc[
        ~df["user_type"].isin(
            ["human", "bot"]
        ),
        "user_type"
    ] = "unknown"

    # --------------------------------------------------------------
    # ALLOCATED
    # --------------------------------------------------------------

    allocated_col = find_column(
        df,
        [
            "allocated",
            "ticket_allocated",
            "has_ticket",
            "winner",
            "is_winner",
        ]
    )

    if allocated_col is None:

        df["allocated"] = False

    else:

        df["allocated"] = normalize_bool_series(
            df[allocated_col]
        )

    # --------------------------------------------------------------
    # ELIGIBLE
    # --------------------------------------------------------------

    eligible_col = find_column(
        df,
        [
            "eligible",
            "is_eligible",
            "allocation_eligible",
        ]
    )

    if eligible_col is None:

        # If eligibility isn't present, assume
        # every record is eligible.
        df["eligible"] = True

    else:

        df["eligible"] = normalize_bool_series(
            df[eligible_col]
        )

    # --------------------------------------------------------------
    # EXPECTED BOT
    # --------------------------------------------------------------

    expected_bot_col = find_column(
        df,
        [
            "expected_bot",
            "is_bot",
            "actual_bot",
            "ground_truth_bot",
        ]
    )

    if expected_bot_col is None:

        df["expected_bot"] = (
            df["user_type"] == "bot"
        ).astype(int)

    else:

        df["expected_bot"] = (
            normalize_bool_series(
                df[expected_bot_col]
            )
            .astype(int)
        )

    # --------------------------------------------------------------
    # DETECTED BOT
    # --------------------------------------------------------------

    detected_bot_col = find_column(
        df,
        [
            "detected_bot",
            "predicted_bot",
            "model_bot",
            "bot_detected",
        ]
    )

    if detected_bot_col is None:

        # No detection result.
        # Keep NaN rather than pretending
        # the model detected nobody.
        df["detected_bot"] = np.nan

    else:

        df["detected_bot"] = (
            normalize_bool_series(
                df[detected_bot_col]
            )
            .astype(int)
        )

    # --------------------------------------------------------------
    # WAITING TIME
    # --------------------------------------------------------------

    waiting_col = find_column(
        df,
        [
            "waiting_time",
            "wait_time",
            "waiting_seconds",
            "wait_seconds",
        ]
    )

    if waiting_col is None:

        df["waiting_time"] = 0.0

    else:

        df["waiting_time"] = pd.to_numeric(
            df[waiting_col],
            errors="coerce"
        ).fillna(0.0)

    # --------------------------------------------------------------
    # DETECTION LATENCY
    # --------------------------------------------------------------

    latency_col = find_column(
        df,
        [
            "detection_latency",
            "detection_latency_ms",
            "detection_time",
        ]
    )

    if latency_col is None:

        df["detection_latency"] = 0.0

    else:

        df["detection_latency"] = pd.to_numeric(
            df[latency_col],
            errors="coerce"
        ).fillna(0.0)

    # --------------------------------------------------------------
    # TIMESTAMP
    # --------------------------------------------------------------

    timestamp_col = find_column(
        df,
        [
            "timestamp",
            "time",
            "request_time",
            "event_time",
        ]
    )

    if timestamp_col is not None:

        df["timestamp"] = pd.to_datetime(
            df[timestamp_col],
            errors="coerce"
        )

    return df


# ======================================================================
# DURATION
# ======================================================================

def calculate_duration(
    df: pd.DataFrame
) -> float:
    """
    Calculate traffic duration in seconds.
    """

    if "timestamp" not in df.columns:
        return 1.0

    timestamps = df["timestamp"].dropna()

    if len(timestamps) < 2:
        return 1.0

    duration = (
        timestamps.max() -
        timestamps.min()
    ).total_seconds()

    return max(
        clean_float(duration),
        1.0
    )


# ======================================================================
# CONFUSION MATRIX
# ======================================================================

def calculate_confusion_matrix(
    df: pd.DataFrame
):
    """
    Calculate:

        TP
        FP
        TN
        FN

    using expected_bot and detected_bot.
    """

    detected = df[
        df["detected_bot"].notna()
    ].copy()

    if len(detected) == 0:

        return 0, 0, 0, 0

    expected = detected[
        "expected_bot"
    ].astype(int)

    predicted = detected[
        "detected_bot"
    ].astype(int)

    tp = int(
        ((expected == 1) &
         (predicted == 1)).sum()
    )

    fp = int(
        ((expected == 0) &
         (predicted == 1)).sum()
    )

    tn = int(
        ((expected == 0) &
         (predicted == 0)).sum()
    )

    fn = int(
        ((expected == 1) &
         (predicted == 0)).sum()
    )

    return tp, fp, tn, fn


# ======================================================================
# WAITING TIME METRICS
# ======================================================================

def calculate_waiting_metrics(
    df: pd.DataFrame
):
    """
    Calculate waiting-time statistics
    for allocated users.
    """

    waits = df.loc[
        df["allocated"],
        "waiting_time"
    ]

    waits = pd.to_numeric(
        waits,
        errors="coerce"
    ).dropna()

    if len(waits) == 0:

        return 0.0, 0.0, 0.0

    return (
        float(waits.mean()),
        float(waits.median()),
        float(waits.quantile(0.95)),
    )


# ======================================================================
# DETECTION LATENCY METRICS
# ======================================================================

def calculate_latency_metrics(
    df: pd.DataFrame
):
    """
    Detection latency statistics.
    """

    latencies = pd.to_numeric(
        df["detection_latency"],
        errors="coerce"
    ).dropna()

    if len(latencies) == 0:

        return 0.0, 0.0

    return (
        float(latencies.mean()),
        float(latencies.quantile(0.95)),
    )


# ======================================================================
# FAIRNESS METRICS
# ======================================================================

def calculate_fairness_metrics(
    df: pd.DataFrame,
    capacity: int
):
    """
    Calculate allocation fairness.

    Jain fairness is calculated from allocation counts
    per eligible logical user.

    For a single lottery:
        each user has 0 or 1 allocation.

    For repeated experiments:
        aggregate allocation counts should be passed
        to this function or the results should be
        evaluated over multiple seeds.
    """

    eligible = df[
        df["eligible"]
    ].copy()

    if len(eligible) == 0:

        return (
            0,
            0,
            0.0,
            0.0,
            0.0
        )

    # --------------------------------------------------------------
    # Logical user allocation count
    # --------------------------------------------------------------

    allocation_by_user = (
        eligible
        .groupby("user_id")["allocated"]
        .max()
    )

    eligible_users = len(
        allocation_by_user
    )

    lottery_entries = eligible_users

    allocated_eligible = int(
        allocation_by_user.sum()
    )

    # --------------------------------------------------------------
    # Expected probability
    # --------------------------------------------------------------

    expected_probability = safe_divide(
        min(capacity, eligible_users),
        eligible_users
    )

    # --------------------------------------------------------------
    # Observed probability
    # --------------------------------------------------------------

    observed_probability = safe_divide(
        allocated_eligible,
        eligible_users
    )

    # --------------------------------------------------------------
    # Deviation
    # --------------------------------------------------------------

    fairness_deviation = abs(
        observed_probability -
        expected_probability
    )

    # --------------------------------------------------------------
    # Jain fairness
    # --------------------------------------------------------------

    fairness = jains_fairness(
        allocation_by_user.values
    )

    return (
        eligible_users,
        lottery_entries,
        fairness,
        expected_probability,
        observed_probability,
        fairness_deviation,
    )


# ======================================================================
# MAIN EVALUATION
# ======================================================================

def evaluate_experiment(
    df: pd.DataFrame,
    scenario: str,
    system: str,
    capacity: int = DEFAULT_CAPACITY,
):
    """
    Evaluate one scenario/system combination.
    """

    df = prepare_dataset(df)

    # ==============================================================
    # USER POPULATION
    # ==============================================================

    known_users = df[
        df["user_type"].isin(
            ["human", "bot"]
        )
    ]

    total_users = (
        known_users["user_id"]
        .nunique()
    )

    human_users = (
        known_users[
            known_users["user_type"] == "human"
        ]["user_id"]
        .nunique()
    )

    bot_users = (
        known_users[
            known_users["user_type"] == "bot"
        ]["user_id"]
        .nunique()
    )

    # ==============================================================
    # TRAFFIC
    # ==============================================================

    total_requests = len(df)

    duration = calculate_duration(df)

    requests_per_second = safe_divide(
        total_requests,
        duration
    )

    # ==============================================================
    # ALLOCATION
    # ==============================================================

    allocated = df[
        df["allocated"]
    ]

    allocated_tickets = len(
        allocated
    )

    human_tickets = len(
        allocated[
            allocated["user_type"] == "human"
        ]
    )

    bot_tickets = len(
        allocated[
            allocated["user_type"] == "bot"
        ]
    )

    # ==============================================================
    # SUCCESS RATES
    # ==============================================================

    human_success_rate = safe_divide(
        human_tickets,
        human_users
    )

    bot_success_rate = safe_divide(
        bot_tickets,
        bot_users
    )

    # ==============================================================
    # ALLOCATION COMPOSITION
    # ==============================================================

    human_allocation_rate = safe_divide(
        human_tickets,
        allocated_tickets
    )

    bot_allocation_rate = safe_divide(
        bot_tickets,
        allocated_tickets
    )

    # ==============================================================
    # CONFUSION MATRIX
    # ==============================================================

    tp, fp, tn, fn = calculate_confusion_matrix(
        df
    )

    false_positive_rate = safe_divide(
        fp,
        fp + tn
    )

    false_negative_rate = safe_divide(
        fn,
        fn + tp
    )

    detection_rate = safe_divide(
        tp,
        tp + fn
    )

    # ==============================================================
    # WAITING
    # ==============================================================

    (
        average_waiting_time,
        median_waiting_time,
        p95_waiting_time,
    ) = calculate_waiting_metrics(df)

    # ==============================================================
    # DETECTION LATENCY
    # ==============================================================

    (
        average_detection_latency,
        p95_detection_latency,
    ) = calculate_latency_metrics(df)

    # ==============================================================
    # DUPLICATES
    # ==============================================================

    allocated_counts = (
        allocated
        .groupby("user_id")
        .size()
    )

    duplicate_allocations = int(
        (allocated_counts > 1).sum()
    )

    # ==============================================================
    # OVERSELLING
    # ==============================================================

    oversold = max(
        0,
        allocated_tickets - capacity
    )

    # ==============================================================
    # INVENTORY
    # ==============================================================

    inventory_consistent = (
        allocated_tickets <= capacity
    )

    # ==============================================================
    # ATTACK ADVANTAGE
    # ==============================================================

    attack_advantage = safe_divide(
        bot_success_rate,
        human_success_rate
    )

    # ==============================================================
    # FAIRNESS
    # ==============================================================

    (
        eligible_users,
        lottery_entries,
        jain_fairness_value,
        expected_probability,
        observed_probability,
        fairness_deviation,
    ) = calculate_fairness_metrics(
        df,
        capacity
    )

    # ==============================================================
    # RESULT
    # ==============================================================

    return EvaluationResult(

        scenario=scenario,
        system=system,

        total_users=total_users,
        human_users=human_users,
        bot_users=bot_users,

        eligible_users=eligible_users,
        lottery_entries=lottery_entries,

        total_requests=total_requests,
        requests_per_second=requests_per_second,

        capacity=capacity,
        allocated_tickets=allocated_tickets,

        human_tickets=human_tickets,
        bot_tickets=bot_tickets,

        human_success_rate=human_success_rate,
        bot_success_rate=bot_success_rate,

        human_allocation_rate=human_allocation_rate,
        bot_allocation_rate=bot_allocation_rate,

        true_positive=tp,
        false_positive=fp,
        true_negative=tn,
        false_negative=fn,

        false_positive_rate=false_positive_rate,
        false_negative_rate=false_negative_rate,
        detection_rate=detection_rate,

        average_waiting_time=average_waiting_time,
        median_waiting_time=median_waiting_time,
        p95_waiting_time=p95_waiting_time,

        average_detection_latency=average_detection_latency,
        p95_detection_latency=p95_detection_latency,

        duplicate_allocations=duplicate_allocations,
        oversold=oversold,
        inventory_consistent=inventory_consistent,

        attack_advantage=attack_advantage,

        jain_fairness=jain_fairness_value,

        expected_allocation_probability=expected_probability,
        observed_allocation_probability=observed_probability,

        lottery_fairness_deviation=fairness_deviation,
    )


# ======================================================================
# COMPARE BASELINE VS FAIR DROP
# ======================================================================

def compare_experiments(
    baseline_df: pd.DataFrame,
    fairdrop_df: pd.DataFrame,
    scenario: str,
    capacity: int = DEFAULT_CAPACITY,
):
    """
    Evaluate baseline and Fair Drop using the same scenario.
    """

    baseline = evaluate_experiment(
        baseline_df,
        scenario=scenario,
        system="BASELINE_FCFS",
        capacity=capacity,
    )

    fairdrop = evaluate_experiment(
        fairdrop_df,
        scenario=scenario,
        system="FAIR_DROP",
        capacity=capacity,
    )

    return baseline, fairdrop


# ======================================================================
# PERCENTAGE CHANGE
# ======================================================================

def percentage_change(
    baseline: float,
    fairdrop: float
) -> float:
    """
    Percentage change from baseline to Fair Drop.
    """

    if baseline == 0:

        return 0.0

    return (
        (fairdrop - baseline) /
        abs(baseline)
    ) * 100.0


def percentage_reduction(
    baseline: float,
    fairdrop: float
) -> float:
    """
    Positive percentage means Fair Drop reduced the metric.
    """

    if baseline == 0:

        return 0.0

    return (
        (baseline - fairdrop) /
        abs(baseline)
    ) * 100.0


# ======================================================================
# RESULT TABLE
# ======================================================================

def results_to_dataframe(
    results: list[EvaluationResult]
) -> pd.DataFrame:

    return pd.DataFrame(
        [asdict(result) for result in results]
    )


# ======================================================================
# JUDGE SUMMARY
# ======================================================================

def print_single_result(
    result: EvaluationResult
):

    print()
    print("=" * 78)
    print(
        f"{result.system} | "
        f"{result.scenario.upper()}"
    )
    print("=" * 78)

    print(
        f"Users                    : "
        f"{result.total_users}"
    )

    print(
        f"Humans                   : "
        f"{result.human_users}"
    )

    print(
        f"Bots                     : "
        f"{result.bot_users}"
    )

    print(
        f"Eligible users            : "
        f"{result.eligible_users}"
    )

    print(
        f"Lottery entries           : "
        f"{result.lottery_entries}"
    )

    print(
        f"Requests                  : "
        f"{result.total_requests}"
    )

    print(
        f"Requests/sec              : "
        f"{result.requests_per_second:.2f}"
    )

    print(
        f"Tickets allocated         : "
        f"{result.allocated_tickets}/{result.capacity}"
    )

    print(
        f"Human success rate        : "
        f"{result.human_success_rate * 100:.2f}%"
    )

    print(
        f"Bot success rate          : "
        f"{result.bot_success_rate * 100:.2f}%"
    )

    print(
        f"Human allocation rate     : "
        f"{result.human_allocation_rate * 100:.2f}%"
    )

    print(
        f"Bot allocation rate       : "
        f"{result.bot_allocation_rate * 100:.2f}%"
    )

    print(
        f"False positive rate       : "
        f"{result.false_positive_rate * 100:.2f}%"
    )

    print(
        f"False negative rate       : "
        f"{result.false_negative_rate * 100:.2f}%"
    )

    print(
        f"Detection rate            : "
        f"{result.detection_rate * 100:.2f}%"
    )

    print(
        f"Average waiting time      : "
        f"{result.average_waiting_time:.4f}s"
    )

    print(
        f"P95 waiting time          : "
        f"{result.p95_waiting_time:.4f}s"
    )

    print(
        f"Detection latency         : "
        f"{result.average_detection_latency:.4f}"
    )

    print(
        f"P95 detection latency     : "
        f"{result.p95_detection_latency:.4f}"
    )

    print(
        f"Duplicate allocations     : "
        f"{result.duplicate_allocations}"
    )

    print(
        f"Overselling               : "
        f"{result.oversold}"
    )

    print(
        f"Inventory consistent      : "
        f"{result.inventory_consistent}"
    )

    print(
        f"Attack advantage          : "
        f"{result.attack_advantage:.4f}"
    )

    print(
        f"Jain fairness             : "
        f"{result.jain_fairness:.6f}"
    )

    print(
        f"Expected lottery prob.    : "
        f"{result.expected_allocation_probability * 100:.4f}%"
    )

    print(
        f"Observed allocation prob. : "
        f"{result.observed_allocation_probability * 100:.4f}%"
    )

    print(
        f"Lottery fairness deviation: "
        f"{result.lottery_fairness_deviation * 100:.4f}%"
    )


# ======================================================================
# BASELINE VS FAIR DROP TABLE
# ======================================================================

def print_comparison(
    baseline: EvaluationResult,
    fairdrop: EvaluationResult,
):

    print()
    print("=" * 100)
    print(
        f"SCENARIO: {baseline.scenario.upper()}"
    )
    print("=" * 100)

    print(
        f"{'METRIC':38}"
        f"{'BASELINE FCFS':22}"
        f"{'FAIR DROP':22}"
    )

    print("-" * 100)

    rows = [

        (
            "Bot allocation rate",
            f"{baseline.bot_allocation_rate * 100:.2f}%",
            f"{fairdrop.bot_allocation_rate * 100:.2f}%"
        ),

        (
            "Human allocation rate",
            f"{baseline.human_allocation_rate * 100:.2f}%",
            f"{fairdrop.human_allocation_rate * 100:.2f}%"
        ),

        (
            "Bot success rate",
            f"{baseline.bot_success_rate * 100:.2f}%",
            f"{fairdrop.bot_success_rate * 100:.2f}%"
        ),

        (
            "Human success rate",
            f"{baseline.human_success_rate * 100:.2f}%",
            f"{fairdrop.human_success_rate * 100:.2f}%"
        ),

        (
            "False positive rate",
            f"{baseline.false_positive_rate * 100:.2f}%",
            f"{fairdrop.false_positive_rate * 100:.2f}%"
        ),

        (
            "False negative rate",
            f"{baseline.false_negative_rate * 100:.2f}%",
            f"{fairdrop.false_negative_rate * 100:.2f}%"
        ),

        (
            "Average waiting time",
            f"{baseline.average_waiting_time:.3f}s",
            f"{fairdrop.average_waiting_time:.3f}s"
        ),

        (
            "P95 waiting time",
            f"{baseline.p95_waiting_time:.3f}s",
            f"{fairdrop.p95_waiting_time:.3f}s"
        ),

        (
            "Requests/sec",
            f"{baseline.requests_per_second:.2f}",
            f"{fairdrop.requests_per_second:.2f}"
        ),

        (
            "Detection latency",
            f"{baseline.average_detection_latency:.3f}",
            f"{fairdrop.average_detection_latency:.3f}"
        ),

        (
            "Duplicate allocations",
            str(baseline.duplicate_allocations),
            str(fairdrop.duplicate_allocations)
        ),

        (
            "Overselling",
            str(baseline.oversold),
            str(fairdrop.oversold)
        ),

        (
            "Inventory consistent",
            str(baseline.inventory_consistent),
            str(fairdrop.inventory_consistent)
        ),

        (
            "Attack advantage",
            f"{baseline.attack_advantage:.4f}",
            f"{fairdrop.attack_advantage:.4f}"
        ),

        (
            "Jain fairness",
            f"{baseline.jain_fairness:.6f}",
            f"{fairdrop.jain_fairness:.6f}"
        ),

        (
            "Lottery entries",
            str(baseline.lottery_entries),
            str(fairdrop.lottery_entries)
        ),

        (
            "Expected lottery probability",
            f"{baseline.expected_allocation_probability * 100:.4f}%",
            f"{fairdrop.expected_allocation_probability * 100:.4f}%"
        ),

        (
            "Observed allocation probability",
            f"{baseline.observed_allocation_probability * 100:.4f}%",
            f"{fairdrop.observed_allocation_probability * 100:.4f}%"
        ),
    ]

    for metric, baseline_value, fairdrop_value in rows:

        print(
            f"{metric:38}"
            f"{baseline_value:<22}"
            f"{fairdrop_value:<22}"
        )


# ======================================================================
# OVERALL RESULTS
# ======================================================================

def print_overall_summary(
    results_df: pd.DataFrame
):

    print()
    print()
    print("=" * 100)
    print("FAIR DROP - OVERALL EVALUATION")
    print("=" * 100)

    print()

    for scenario in SCENARIOS:

        scenario_df = results_df[
            results_df["scenario"] == scenario
        ]

        if scenario_df.empty:
            continue

        print()
        print(
            f"--- {scenario.upper()} ---"
        )

        for system in [
            "BASELINE_FCFS",
            "FAIR_DROP"
        ]:

            row = scenario_df[
                scenario_df["system"] == system
            ]

            if row.empty:
                continue

            row = row.iloc[0]

            print(
                f"{system:18} | "
                f"Bot success: "
                f"{row['bot_success_rate'] * 100:6.2f}% | "
                f"Human success: "
                f"{row['human_success_rate'] * 100:6.2f}% | "
                f"Bot allocation: "
                f"{row['bot_allocation_rate'] * 100:6.2f}% | "
                f"FPR: "
                f"{row['false_positive_rate'] * 100:6.2f}% | "
                f"FNR: "
                f"{row['false_negative_rate'] * 100:6.2f}% | "
                f"Oversold: "
                f"{int(row['oversold'])}"
            )


# ======================================================================
# LOAD CSV
# ======================================================================

def load_csv(
    path: str
) -> pd.DataFrame:

    if not os.path.exists(path):

        raise FileNotFoundError(
            f"Dataset not found: {path}"
        )

    print(
        f"Loading dataset: {path}"
    )

    df = pd.read_csv(path)

    print(
        f"Dataset shape: {df.shape}"
    )

    return df


# ======================================================================
# SAVE JSON
# ======================================================================

def save_json(
    results: list[EvaluationResult],
    path: str
):

    data = [
        asdict(result)
        for result in results
    ]

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=4
        )

    print(
        f"JSON results saved: {path}"
    )


# ======================================================================
# SINGLE DATASET MODE
# ======================================================================

def evaluate_single_dataset(
    path: str,
    system: str,
    scenario: str,
    capacity: int
):

    df = load_csv(path)

    result = evaluate_experiment(
        df=df,
        scenario=scenario,
        system=system,
        capacity=capacity
    )

    print_single_result(
        result
    )

    return result


# ======================================================================
# BASELINE + FAIR DROP MODE
# ======================================================================

def evaluate_pair(
    baseline_path: str,
    fairdrop_path: str,
    scenario: str,
    capacity: int
):

    baseline_df = load_csv(
        baseline_path
    )

    fairdrop_df = load_csv(
        fairdrop_path
    )

    baseline, fairdrop = compare_experiments(
        baseline_df=baseline_df,
        fairdrop_df=fairdrop_df,
        scenario=scenario,
        capacity=capacity
    )

    print_comparison(
        baseline,
        fairdrop
    )

    return baseline, fairdrop


# ======================================================================
# ALL SCENARIOS FROM DIRECTORY
# ======================================================================

def evaluate_directory(
    baseline_dir: str,
    fairdrop_dir: str,
    capacity: int,
    output_dir: str
):

    baseline_dir = Path(
        baseline_dir
    )

    fairdrop_dir = Path(
        fairdrop_dir
    )

    output_dir = Path(
        output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    results = []

    print()
    print("=" * 100)
    print("FAIR DROP - FULL 7-SCENARIO EVALUATION")
    print("=" * 100)

    for scenario in SCENARIOS:

        baseline_path = (
            baseline_dir /
            f"{scenario}.csv"
        )

        fairdrop_path = (
            fairdrop_dir /
            f"{scenario}.csv"
        )

        if not baseline_path.exists():

            print(
                f"\n[SKIP] Missing baseline: "
                f"{baseline_path}"
            )

            continue

        if not fairdrop_path.exists():

            print(
                f"\n[SKIP] Missing Fair Drop: "
                f"{fairdrop_path}"
            )

            continue

        print()
        print(
            f"[RUNNING] {scenario}"
        )

        baseline, fairdrop = evaluate_pair(
            baseline_path=str(
                baseline_path
            ),
            fairdrop_path=str(
                fairdrop_path
            ),
            scenario=scenario,
            capacity=capacity
        )

        results.extend(
            [baseline, fairdrop]
        )

    if not results:

        raise RuntimeError(
            "No valid scenario datasets found."
        )

    results_df = results_to_dataframe(
        results
    )

    csv_path = (
        output_dir /
        "fairness_results.csv"
    )

    json_path = (
        output_dir /
        "fairness_results.json"
    )

    results_df.to_csv(
        csv_path,
        index=False
    )

    save_json(
        results,
        str(json_path)
    )

    print_overall_summary(
        results_df
    )

    print()
    print("=" * 100)
    print("OUTPUT FILES")
    print("=" * 100)

    print(
        f"CSV : {csv_path}"
    )

    print(
        f"JSON: {json_path}"
    )

    return results_df


# ======================================================================
# COMMAND LINE
# ======================================================================

def build_parser():

    parser = argparse.ArgumentParser(
        description=(
            "Fair Drop fairness and evaluation engine"
        )
    )

    parser.add_argument(
        "--baseline",
        type=str,
        default=None,
        help="Baseline CSV"
    )

    parser.add_argument(
        "--fairdrop",
        type=str,
        default=None,
        help="Fair Drop CSV"
    )

    parser.add_argument(
        "--scenario",
        type=str,
        default="normal",
        choices=SCENARIOS,
        help="Traffic scenario"
    )

    parser.add_argument(
        "--baseline-dir",
        type=str,
        default=None,
        help="Directory containing baseline scenario CSVs"
    )

    parser.add_argument(
        "--fairdrop-dir",
        type=str,
        default=None,
        help="Directory containing Fair Drop scenario CSVs"
    )

    parser.add_argument(
        "--capacity",
        type=int,
        default=DEFAULT_CAPACITY,
        help="Number of available seats"
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="evaluation_results",
        help="Output directory"
    )

    return parser


# ======================================================================
# MAIN
# ======================================================================

def main():

    parser = build_parser()

    args = parser.parse_args()

    print()
    print("=" * 78)
    print("FAIR DROP - FAIRNESS EVALUATION ENGINE")
    print("=" * 78)

    print(
        f"Ticket capacity: {args.capacity}"
    )

    # ==============================================================
    # FULL DIRECTORY MODE
    # ==============================================================

    if (
        args.baseline_dir is not None
        and
        args.fairdrop_dir is not None
    ):

        evaluate_directory(
            baseline_dir=args.baseline_dir,
            fairdrop_dir=args.fairdrop_dir,
            capacity=args.capacity,
            output_dir=args.output_dir
        )

        return

    # ==============================================================
    # PAIR MODE
    # ==============================================================

    if (
        args.baseline is not None
        and
        args.fairdrop is not None
    ):

        baseline, fairdrop = evaluate_pair(
            baseline_path=args.baseline,
            fairdrop_path=args.fairdrop,
            scenario=args.scenario,
            capacity=args.capacity
        )

        results = [
            baseline,
            fairdrop
        ]

        output_dir = Path(
            args.output_dir
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        results_df = results_to_dataframe(
            results
        )

        csv_path = (
            output_dir /
            f"{args.scenario}_comparison.csv"
        )

        json_path = (
            output_dir /
            f"{args.scenario}_comparison.json"
        )

        results_df.to_csv(
            csv_path,
            index=False
        )

        save_json(
            results,
            str(json_path)
        )

        print()
        print(
            f"CSV saved : {csv_path}"
        )

        print(
            f"JSON saved: {json_path}"
        )

        return

    # ==============================================================
    # SINGLE DATASET MODE
    # ==============================================================

    if args.baseline is not None:

        result = evaluate_single_dataset(
            path=args.baseline,
            system="BASELINE_FCFS",
            scenario=args.scenario,
            capacity=args.capacity
        )

        output_dir = Path(
            args.output_dir
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        save_json(
            [result],
            str(
                output_dir /
                "single_evaluation.json"
            )
        )

        return

    if args.fairdrop is not None:

        result = evaluate_single_dataset(
            path=args.fairdrop,
            system="FAIR_DROP",
            scenario=args.scenario,
            capacity=args.capacity
        )

        output_dir = Path(
            args.output_dir
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        save_json(
            [result],
            str(
                output_dir /
                "single_evaluation.json"
            )
        )

        return

    # ==============================================================
    # NO ARGUMENTS
    # ==============================================================

    print()
    print("Usage examples:")
    print()
    print(
        "Single dataset:"
    )
    print(
        "python ML/fairness_eval.py "
        "--fairdrop fairdrop.csv "
        "--scenario flood"
    )

    print()
    print(
        "Baseline vs Fair Drop:"
    )
    print(
        "python ML/fairness_eval.py "
        "--baseline baseline.csv "
        "--fairdrop fairdrop.csv "
        "--scenario flood"
    )

    print()
    print(
        "All seven scenarios:"
    )
    print(
        "python ML/fairness_eval.py "
        "--baseline-dir evaluation/baseline "
        "--fairdrop-dir evaluation/fairdrop"
    )


# ======================================================================
# ENTRY POINT
# ======================================================================

if __name__ == "__main__":

    main()