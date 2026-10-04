import numpy as np
import pandas as pd
import os

# ============================================================
# FAIR DROP
# Synthetic Bot Detection Dataset Generator
# ============================================================

SEED = 42
rng = np.random.default_rng(SEED)

# Number of samples for EACH traffic type
SAMPLES_PER_TYPE = 10000


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clipped_normal(mean, std, n, low, high):
    return np.clip(
        rng.normal(mean, std, n),
        low,
        high
    )


def clipped_gamma(shape, scale, n, low=0, high=None):

    values = rng.gamma(shape, scale, n)

    values = np.maximum(values, low)

    if high is not None:
        values = np.minimum(values, high)

    return values


def poisson(lam):
    """
    Supports both:
    - scalar lambda
    - array lambda
    """
    return rng.poisson(lam)


def lognormal(mean, sigma, n, low=0, high=None):

    values = rng.lognormal(mean, sigma, n)

    values = np.maximum(values, low)

    if high is not None:
        values = np.minimum(values, high)

    return values


# ============================================================
# 1. GENUINE HUMAN
# ============================================================

def generate_humans(n):

    # Different humans have different activity levels
    activity = rng.lognormal(
        mean=0,
        sigma=0.35,
        size=n
    )

    requests_per_second = (
        rng.gamma(1.7, 0.35, n)
        * activity
    )

    requests_per_second = np.clip(
        requests_per_second,
        0.03,
        8
    )

    actions_per_second = (
        rng.gamma(1.8, 0.45, n)
        * activity
    )

    actions_per_second = np.clip(
        actions_per_second,
        0.05,
        8
    )

    avg_inter_action_ms = (
        1000 /
        np.maximum(actions_per_second, 0.05)
    )

    avg_inter_action_ms += rng.normal(
        0,
        120,
        n
    )

    avg_inter_action_ms = np.clip(
        avg_inter_action_ms,
        120,
        5000
    )

    std_inter_action_ms = (
        avg_inter_action_ms *
        rng.uniform(0.25, 0.8, n)
    )

    session_duration = lognormal(
        3.5,
        0.55,
        n,
        10,
        600
    )

    return pd.DataFrame({

        "user_type": "human",

        "requests_per_second":
            requests_per_second,

        "requests_last_10s":
            poisson(
                requests_per_second * 10
            ),

        "requests_last_30s":
            poisson(
                requests_per_second * 30
            ),

        "duplicate_requests":
            poisson(
                np.clip(
                    requests_per_second * 0.8,
                    0.2,
                    3
                )
            ),

        "failed_requests":
            poisson(
                np.clip(
                    requests_per_second * 0.5,
                    0.2,
                    3
                )
            ),

        "reconnect_count":
            poisson(
                0.25 + activity * 0.15
            ),

        "mouse_events":
            poisson(
                150 * activity
            ),

        "keyboard_events":
            poisson(
                30 * activity
            ),

        "scroll_events":
            poisson(
                12 * activity
            ),

        "actions_per_second":
            actions_per_second,

        "avg_inter_action_ms":
            avg_inter_action_ms,

        "std_inter_action_ms":
            np.clip(
                std_inter_action_ms,
                20,
                2500
            ),

        "session_duration_sec":
            session_duration,

        "pow_solve_time_ms":
            clipped_normal(
                2100,
                750,
                n,
                500,
                6000
            ),

        "queue_join_attempts":
            poisson(
                np.clip(
                    0.7 + activity * 0.4,
                    0.2,
                    3
                )
            ),

        "refresh_count":
            poisson(
                np.clip(
                    0.4 + activity * 0.5,
                    0.1,
                    4
                )
            )
    })


# ============================================================
# 2. AGGRESSIVE BOT
# ============================================================

def generate_aggressive_bots(n):

    requests = clipped_gamma(
        5,
        1.8,
        n,
        2,
        30
    )

    actions = clipped_gamma(
        4,
        1.5,
        n,
        2,
        25
    )

    return pd.DataFrame({

        "user_type": "aggressive_bot",

        "requests_per_second":
            requests,

        "requests_last_10s":
            poisson(
                requests * 10
            ),

        "requests_last_30s":
            poisson(
                requests * 30
            ),

        "duplicate_requests":
            poisson(
                np.clip(
                    requests * 1.2,
                    3,
                    35
                )
            ),

        "failed_requests":
            poisson(
                np.clip(
                    requests * 0.7,
                    2,
                    25
                )
            ),

        "reconnect_count":
            poisson(4),

        "mouse_events":
            poisson(10),

        "keyboard_events":
            poisson(4),

        "scroll_events":
            poisson(2),

        "actions_per_second":
            actions,

        "avg_inter_action_ms":
            clipped_normal(
                100,
                35,
                n,
                15,
                400
            ),

        "std_inter_action_ms":
            clipped_normal(
                35,
                20,
                n,
                2,
                150
            ),

        "session_duration_sec":
            lognormal(
                2.7,
                0.6,
                n,
                2,
                300
            ),

        "pow_solve_time_ms":
            clipped_normal(
                850,
                300,
                n,
                200,
                3500
            ),

        "queue_join_attempts":
            poisson(4),

        "refresh_count":
            poisson(7)
    })


# ============================================================
# 3. RAPID RETRY BOT
# ============================================================

def generate_rapid_retry_bots(n):

    requests = clipped_gamma(
        2.5,
        1.2,
        n,
        1,
        12
    )

    return pd.DataFrame({

        "user_type": "rapid_retry_bot",

        "requests_per_second":
            requests,

        "requests_last_10s":
            poisson(
                requests * 10
            ),

        "requests_last_30s":
            poisson(
                requests * 30
            ),

        "duplicate_requests":
            poisson(
                np.clip(
                    requests * 2.0,
                    5,
                    40
                )
            ),

        "failed_requests":
            poisson(
                np.clip(
                    requests * 1.2,
                    3,
                    20
                )
            ),

        "reconnect_count":
            poisson(2.5),

        "mouse_events":
            poisson(15),

        "keyboard_events":
            poisson(5),

        "scroll_events":
            poisson(2),

        "actions_per_second":
            clipped_gamma(
                3,
                1,
                n,
                1,
                15
            ),

        "avg_inter_action_ms":
            clipped_normal(
                180,
                80,
                n,
                20,
                800
            ),

        "std_inter_action_ms":
            clipped_normal(
                70,
                40,
                n,
                5,
                400
            ),

        "session_duration_sec":
            lognormal(
                2.8,
                0.6,
                n,
                5,
                300
            ),

        "pow_solve_time_ms":
            clipped_normal(
                1100,
                450,
                n,
                250,
                4000
            ),

        "queue_join_attempts":
            poisson(5),

        "refresh_count":
            poisson(6)
    })


# ============================================================
# 4. MULTI-SESSION BOT
# ============================================================

def generate_multi_session_bots(n):

    requests = clipped_gamma(
        2.2,
        0.9,
        n,
        0.5,
        8
    )

    return pd.DataFrame({

        "user_type": "multi_session_bot",

        "requests_per_second":
            requests,

        "requests_last_10s":
            poisson(
                requests * 10
            ),

        "requests_last_30s":
            poisson(
                requests * 30
            ),

        "duplicate_requests":
            poisson(
                np.clip(
                    requests * 1.3,
                    2,
                    20
                )
            ),

        "failed_requests":
            poisson(
                np.clip(
                    requests * 0.8,
                    1,
                    15
                )
            ),

        "reconnect_count":
            poisson(6),

        "mouse_events":
            poisson(12),

        "keyboard_events":
            poisson(4),

        "scroll_events":
            poisson(2),

        "actions_per_second":
            clipped_gamma(
                2.5,
                0.8,
                n,
                0.5,
                10
            ),

        "avg_inter_action_ms":
            clipped_normal(
                350,
                150,
                n,
                30,
                1500
            ),

        "std_inter_action_ms":
            clipped_normal(
                100,
                60,
                n,
                5,
                600
            ),

        "session_duration_sec":
            lognormal(
                3.0,
                0.7,
                n,
                5,
                400
            ),

        "pow_solve_time_ms":
            clipped_normal(
                1200,
                500,
                n,
                250,
                4500
            ),

        "queue_join_attempts":
            poisson(4),

        "refresh_count":
            poisson(5)
    })


# ============================================================
# 5. DISTRIBUTED BOT
# ============================================================

def generate_distributed_bots(n):

    # Each individual session looks relatively normal.
    # Cross-session behavior will expose the attack.

    requests = clipped_gamma(
        1.8,
        0.45,
        n,
        0.1,
        5
    )

    return pd.DataFrame({

        "user_type": "distributed_bot",

        "requests_per_second":
            requests,

        "requests_last_10s":
            poisson(
                requests * 10
            ),

        "requests_last_30s":
            poisson(
                requests * 30
            ),

        "duplicate_requests":
            poisson(
                np.clip(
                    requests * 0.9,
                    1,
                    8
                )
            ),

        "failed_requests":
            poisson(
                np.clip(
                    requests * 0.6,
                    0.5,
                    6
                )
            ),

        "reconnect_count":
            poisson(2),

        "mouse_events":
            poisson(100),

        "keyboard_events":
            poisson(25),

        "scroll_events":
            poisson(10),

        "actions_per_second":
            clipped_gamma(
                1.8,
                0.45,
                n,
                0.1,
                6
            ),

        "avg_inter_action_ms":
            clipped_normal(
                700,
                250,
                n,
                100,
                3000
            ),

        "std_inter_action_ms":
            clipped_normal(
                250,
                120,
                n,
                20,
                1500
            ),

        "session_duration_sec":
            lognormal(
                3.3,
                0.6,
                n,
                10,
                500
            ),

        "pow_solve_time_ms":
            clipped_normal(
                1700,
                600,
                n,
                400,
                5500
            ),

        "queue_join_attempts":
            poisson(2),

        "refresh_count":
            poisson(2)
    })


# ============================================================
# 6. STEALTH / HUMAN-LIKE BOT
# ============================================================

def generate_stealth_bots(n):

    # Very important:
    # Stealth bots intentionally overlap with humans.

    activity = rng.lognormal(
        0,
        0.3,
        n
    )

    requests = np.clip(
        rng.gamma(1.8, 0.5, n) * activity,
        0.2,
        5
    )

    actions = np.clip(
        rng.gamma(1.7, 0.5, n),
        0.1,
        7
    )

    avg_action = np.clip(
        1000 / actions
        + rng.normal(0, 100, n),
        120,
        4000
    )

    return pd.DataFrame({

        "user_type": "stealth_bot",

        "requests_per_second":
            requests,

        "requests_last_10s":
            poisson(
                requests * 10
            ),

        "requests_last_30s":
            poisson(
                requests * 30
            ),

        "duplicate_requests":
            poisson(
                np.clip(
                    requests * 1.3,
                    1,
                    10
                )
            ),

        "failed_requests":
            poisson(
                np.clip(
                    requests * 0.7,
                    0.5,
                    8
                )
            ),

        "reconnect_count":
            poisson(1.5),

        "mouse_events":
            poisson(
                80 * activity
            ),

        "keyboard_events":
            poisson(
                18 * activity
            ),

        "scroll_events":
            poisson(
                8 * activity
            ),

        "actions_per_second":
            actions,

        "avg_inter_action_ms":
            avg_action,

        # More consistent timing than humans

        "std_inter_action_ms":
            clipped_normal(
                180,
                70,
                n,
                20,
                800
            ),

        "session_duration_sec":
            lognormal(
                3.4,
                0.55,
                n,
                10,
                500
            ),

        "pow_solve_time_ms":
            clipped_normal(
                1400,
                450,
                n,
                300,
                4000
            ),

        "queue_join_attempts":
            poisson(2.5),

        "refresh_count":
            poisson(3)
    })


# ============================================================
# 7. ADAPTIVE BOT
# ============================================================

def generate_adaptive_bots(n):

    # Two strategies:
    #
    # aggressive_first:
    # starts aggressive and then slows down
    #
    # stealth_first:
    # starts human-like and becomes more aggressive

    strategy = rng.choice(
        [
            "aggressive_first",
            "stealth_first"
        ],
        n
    )

    base_rate = np.where(
        strategy == "aggressive_first",

        rng.uniform(
            5,
            15,
            n
        ),

        rng.uniform(
            0.5,
            3,
            n
        )
    )

    adaptation_factor = rng.uniform(
        0.25,
        0.65,
        n
    )

    final_rate = np.clip(
        base_rate * adaptation_factor,
        0.2,
        12
    )

    return pd.DataFrame({

        "user_type": "adaptive_bot",

        "requests_per_second":
            final_rate,

        "requests_last_10s":
            poisson(
                final_rate * 10
            ),

        "requests_last_30s":
            poisson(
                final_rate * 30
            ),

        "duplicate_requests":
            poisson(
                np.clip(
                    final_rate * 1.2,
                    1,
                    15
                )
            ),

        "failed_requests":
            poisson(
                np.clip(
                    final_rate * 0.7,
                    1,
                    12
                )
            ),

        "reconnect_count":
            poisson(2.5),

        "mouse_events":
            poisson(
                rng.uniform(
                    30,
                    130,
                    n
                )
            ),

        "keyboard_events":
            poisson(
                rng.uniform(
                    8,
                    35,
                    n
                )
            ),

        "scroll_events":
            poisson(
                rng.uniform(
                    3,
                    15,
                    n
                )
            ),

        "actions_per_second":
            np.clip(
                rng.gamma(2, 0.7, n),
                0.2,
                10
            ),

        "avg_inter_action_ms":
            clipped_normal(
                500,
                220,
                n,
                80,
                3000
            ),

        "std_inter_action_ms":
            clipped_normal(
                220,
                100,
                n,
                20,
                1200
            ),

        "session_duration_sec":
            lognormal(
                3.3,
                0.7,
                n,
                10,
                500
            ),

        "pow_solve_time_ms":
            clipped_normal(
                1500,
                600,
                n,
                300,
                5000
            ),

        "queue_join_attempts":
            poisson(3),

        "refresh_count":
            poisson(4)
    })


# ============================================================
# GENERATE DATA
# ============================================================

print("\nGenerating synthetic traffic...\n")

humans = generate_humans(
    SAMPLES_PER_TYPE
)

aggressive = generate_aggressive_bots(
    SAMPLES_PER_TYPE
)

rapid_retry = generate_rapid_retry_bots(
    SAMPLES_PER_TYPE
)

multi_session = generate_multi_session_bots(
    SAMPLES_PER_TYPE
)

distributed = generate_distributed_bots(
    SAMPLES_PER_TYPE
)

stealth = generate_stealth_bots(
    SAMPLES_PER_TYPE
)

adaptive = generate_adaptive_bots(
    SAMPLES_PER_TYPE
)


# ============================================================
# COMBINE
# ============================================================

df = pd.concat(
    [
        humans,
        aggressive,
        rapid_retry,
        multi_session,
        distributed,
        stealth,
        adaptive
    ],
    ignore_index=True
)


# ============================================================
# IDENTIFIERS
# ============================================================

df.insert(
    0,
    "session_id",
    [
        f"session_{i:07d}"
        for i in range(len(df))
    ]
)

df.insert(
    1,
    "user_id",
    [
        f"user_{i:07d}"
        for i in range(len(df))
    ]
)

df.insert(
    2,
    "drop_id",
    "drop_001"
)


# ============================================================
# DERIVED FEATURES
# ============================================================

# Success rate

df["success_rate"] = (
    1 -
    (
        df["failed_requests"]
        /
        np.maximum(
            df["requests_last_30s"],
            1
        )
    )
).clip(0, 1)


# Retry rate

df["retry_rate"] = (
    df["duplicate_requests"]
    /
    np.maximum(
        df["requests_last_30s"],
        1
    )
).clip(0, 1)


# Burstiness

df["burstiness_score"] = (
    df["requests_last_10s"]
    /
    np.maximum(
        df["requests_last_30s"],
        1
    )
)


# Human interaction density

df["human_action_ratio"] = (
    (
        df["mouse_events"]
        +
        df["keyboard_events"]
        +
        df["scroll_events"]
    )
    /
    np.maximum(
        df["requests_last_30s"],
        1
    )
)


# Request/action relationship

df["request_action_ratio"] = (
    df["requests_per_second"]
    /
    np.maximum(
        df["actions_per_second"],
        0.01
    )
)


# Timing coefficient of variation

df["timing_cv"] = (
    df["std_inter_action_ms"]
    /
    np.maximum(
        df["avg_inter_action_ms"],
        1
    )
)


# ============================================================
# TARGETS
# ============================================================

df["is_bot"] = (
    df["user_type"] != "human"
).astype(int)


# ============================================================
# SHUFFLE
# ============================================================

df = df.sample(
    frac=1,
    random_state=SEED
).reset_index(drop=True)


# ============================================================
# SAVE
# ============================================================

os.makedirs(
    "ML/data",
    exist_ok=True
)

output_path = (
    "ML/data/bot_behavior_dataset.csv"
)

df.to_csv(
    output_path,
    index=False
)


# ============================================================
# REPORT
# ============================================================

print("=" * 65)
print("FAIR DROP DATASET GENERATED SUCCESSFULLY")
print("=" * 65)

print("\nShape:")
print(df.shape)

print("\nTraffic distribution:")
print(
    df["user_type"].value_counts()
)

print("\nBinary distribution:")
print(
    df["is_bot"].value_counts()
)

print("\nBot percentage:")
print(
    round(
        df["is_bot"].mean() * 100,
        2
    ),
    "%"
)

print("\nNumber of features:")
print(
    len(df.columns)
)

print("\nFeature columns:")
print(
    df.columns.tolist()
)

print("\nAverage behavior by traffic type:\n")

print(
    df.groupby("user_type")[
        [
            "requests_per_second",
            "requests_last_10s",
            "requests_last_30s",
            "duplicate_requests",
            "failed_requests",
            "actions_per_second",
            "session_duration_sec",
            "pow_solve_time_ms",
            "retry_rate",
            "timing_cv"
        ]
    ]
    .mean()
    .round(3)
)

print("\nFirst 5 rows:")
print(df.head())

print("\nSaved to:")
print(output_path)

print("\n" + "=" * 65)