# ============================================================
# FAIR DROP - GRU TEMPORAL BOT DETECTOR
# ============================================================
#
# Purpose:
# Detect bots from chronological behavioral event sequences.
#
# Input:
#     ML/data/traffic_events.csv
#
# Representation:
#     One sequence = one user session
#     14 event-type features
#     11 numerical behavioral features
#     Total = 25 features per timestep
#
# Sequence:
#     Maximum 100 chronological events
#
# Model:
#     Masking
#     GRU(64)
#     Dropout
#     GRU(32)
#     Dropout
#     Dense(16)
#     Dropout
#     Sigmoid
#
# ============================================================


import os
import json
import random

import numpy as np
import pandas as pd

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

from sklearn.model_selection import GroupShuffleSplit
from sklearn.utils.class_weight import compute_class_weight

from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report
)


# ============================================================
# CONFIGURATION
# ============================================================

RANDOM_STATE = 42

SEQ_LEN = 100

BATCH_SIZE = 128

EPOCHS = 40

LEARNING_RATE = 1e-3

MODEL_DIR = "models"

DATA_PATH = "data/traffic_events.csv"

MODEL_PATH = os.path.join(
    MODEL_DIR,
    "gru_bot_detector.keras"
)

METADATA_PATH = os.path.join(
    MODEL_DIR,
    "gru_metadata.json"
)

TRAFFIC_RESULTS_PATH = os.path.join(
    MODEL_DIR,
    "gru_traffic_type_results.csv"
)

os.makedirs(
    MODEL_DIR,
    exist_ok=True
)


# ============================================================
# REPRODUCIBILITY
# ============================================================

np.random.seed(RANDOM_STATE)

random.seed(RANDOM_STATE)

tf.random.set_seed(RANDOM_STATE)


# ============================================================
# EVENT TYPES
# ============================================================

EVENT_TYPES = [
    "session_start",
    "page_load",
    "wait",
    "request",
    "request_success",
    "request_failure",
    "retry",
    "refresh",
    "reconnect",
    "queue_join",
    "queue_poll",
    "pow_start",
    "pow_complete",
    "session_end"
]


EVENT_TO_INDEX = {
    event: i
    for i, event in enumerate(EVENT_TYPES)
}


# ============================================================
# NUMERICAL FEATURES PER EVENT
# ============================================================

NUMERIC_FEATURES = [
    "inter_event_time_ms",
    "retry_count",
    "request_number",
    "active_sessions",
    "queue_position",
    "session_age_sec",
    "time_since_last_request_ms",
    "time_since_last_failure_ms",
    "mouse_events",
    "keyboard_events",
    "scroll_events"
]


# ============================================================
# TOTAL FEATURES
# ============================================================

# One-hot event type:
#     14 features
#
# Numerical:
#     11 features
#
# Total:
#     25 features/event
#
# ============================================================

INPUT_DIM = (
    len(EVENT_TYPES)
    + len(NUMERIC_FEATURES)
)


# ============================================================
# LOAD DATA
# ============================================================

def load_event_data(path):

    print("\nLoading event sequence dataset...")

    if not os.path.exists(path):

        raise FileNotFoundError(
            f"\nDataset not found: {path}\n"
            "Run the traffic simulator first."
        )

    df = pd.read_csv(path)

    print(
        "\nDataset shape:",
        df.shape
    )

    required_columns = [
        "timestamp",
        "session_id",
        "user_id",
        "bot_cluster_id",
        "event_type",
        "inter_event_time_ms",
        "request_status",
        "retry_count",
        "request_number",
        "active_sessions",
        "queue_position",
        "session_age_sec",
        "time_since_last_request_ms",
        "time_since_last_failure_ms",
        "mouse_events",
        "keyboard_events",
        "scroll_events",
        "traffic_type",
        "is_bot"
    ]

    missing_columns = [
        col
        for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:

        raise ValueError(
            "Required columns missing from dataset:\n"
            f"{missing_columns}"
        )

    # --------------------------------------------------------
    # Basic validation
    # --------------------------------------------------------

    if df.empty:

        raise ValueError(
            "The event dataset is empty."
        )

    if df["session_id"].isna().any():

        raise ValueError(
            "session_id contains missing values."
        )

    if df["event_type"].isna().any():

        raise ValueError(
            "event_type contains missing values."
        )

    if df["is_bot"].isna().any():

        raise ValueError(
            "is_bot contains missing values."
        )

    # --------------------------------------------------------
    # Dataset information
    # --------------------------------------------------------

    print("\nEvent types:")
    print(
        df["event_type"]
        .value_counts()
    )

    print("\nTraffic types:")
    print(
        df["traffic_type"]
        .value_counts()
    )

    print("\nClass distribution:")
    print(
        df["is_bot"]
        .value_counts()
    )

    print(
        "\nNumber of sessions:",
        df["session_id"].nunique()
    )

    print(
        "Number of users:",
        df["user_id"].nunique()
    )

    print("\nEvents per session:")
    print(
        df.groupby("session_id")
        .size()
        .describe()
    )

    return df


# ============================================================
# EVENT ENCODING
# ============================================================

def encode_event(row):

    """
    Convert one event into a numerical vector.

    14 one-hot event features
    +
    11 numerical behavioral features

    Total = 25 features/event.
    """

    vector = []

    # --------------------------------------------------------
    # EVENT TYPE ONE-HOT
    # --------------------------------------------------------

    event_one_hot = np.zeros(
        len(EVENT_TYPES),
        dtype=np.float32
    )

    event_type = row["event_type"]

    if event_type in EVENT_TO_INDEX:

        event_one_hot[
            EVENT_TO_INDEX[event_type]
        ] = 1.0

    vector.extend(
        event_one_hot
    )

    # --------------------------------------------------------
    # NUMERICAL FEATURES
    # --------------------------------------------------------

    for feature in NUMERIC_FEATURES:

        value = row[feature]

        if pd.isna(value):

            value = 0.0

        try:

            value = float(value)

        except (ValueError, TypeError):

            value = 0.0

        # Simulator uses -1 for some unavailable
        # temporal values / queue positions.

        if feature in [
            "time_since_last_request_ms",
            "time_since_last_failure_ms",
            "queue_position"
        ]:

            if value < 0:

                value = 0.0

        vector.append(value)

    return np.array(
        vector,
        dtype=np.float32
    )


# ============================================================
# NORMALIZE EVENT FEATURES
# ============================================================

def normalize_event_features(df):

    """
    Deterministic preprocessing.

    Time features:
        clip >= 0
        log1p

    Count features:
        clip >= 0
        log1p

    No scaler is fitted on the full dataset, avoiding
    train/validation/test preprocessing leakage.
    """

    df = df.copy()

    # --------------------------------------------------------
    # TIME FEATURES
    # --------------------------------------------------------

    time_columns = [
        "inter_event_time_ms",
        "time_since_last_request_ms",
        "time_since_last_failure_ms",
        "session_age_sec"
    ]

    for col in time_columns:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        ).fillna(0.0)

        df[col] = df[col].clip(
            lower=0.0
        )

        df[col] = np.log1p(
            df[col]
        )

    # --------------------------------------------------------
    # COUNT FEATURES
    # --------------------------------------------------------

    count_columns = [
        "retry_count",
        "request_number",
        "active_sessions",
        "queue_position",
        "mouse_events",
        "keyboard_events",
        "scroll_events"
    ]

    for col in count_columns:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        ).fillna(0.0)

        df[col] = df[col].clip(
            lower=0.0
        )

        df[col] = np.log1p(
            df[col]
        )

    return df


# ============================================================
# BUILD SESSION SEQUENCES
# ============================================================

def build_sequences(df):

    """
    Convert event-level dataframe into:

        X:
            (num_sessions, SEQ_LEN, INPUT_DIM)

        y:
            (num_sessions,)

        groups:
            leakage-safe group IDs

        traffic_types:
            traffic labels

        session_ids:
            session identifiers

    Grouping:

        Normal user:
            user_id

        Multi-session user:
            user_id

        Distributed bot:
            bot_cluster_id

    This prevents related distributed bot sessions
    from appearing in both train and test.
    """

    print(
        "\nBuilding session sequences..."
    )

    X = []
    y = []
    groups = []
    traffic_types = []
    session_ids = []

    # --------------------------------------------------------
    # Sort chronologically
    # --------------------------------------------------------

    df = df.sort_values(
        [
            "session_id",
            "timestamp"
        ]
    )

    # --------------------------------------------------------
    # Group by session
    # --------------------------------------------------------

    grouped = df.groupby(
        "session_id",
        sort=False
    )

    for session_id, session in grouped:

        session = session.sort_values(
            "timestamp"
        )

        # ----------------------------------------------------
        # Check label consistency
        # ----------------------------------------------------

        if session["is_bot"].nunique() != 1:

            raise ValueError(
                f"Session {session_id} contains "
                "inconsistent is_bot labels."
            )

        if session["traffic_type"].nunique() != 1:

            raise ValueError(
                f"Session {session_id} contains "
                "inconsistent traffic_type labels."
            )

        # ----------------------------------------------------
        # Encode events
        # ----------------------------------------------------

        sequence = np.array(
            [
                encode_event(row)
                for _, row in session.iterrows()
            ],
            dtype=np.float32
        )

        # ----------------------------------------------------
        # Keep latest SEQ_LEN events
        # ----------------------------------------------------

        if len(sequence) > SEQ_LEN:

            sequence = sequence[
                -SEQ_LEN:
            ]

        # ----------------------------------------------------
        # Padding
        # ----------------------------------------------------

        padded = np.zeros(
            (
                SEQ_LEN,
                INPUT_DIM
            ),
            dtype=np.float32
        )

        # Real events go at the beginning.
        # Remaining zeros are ignored by Masking.

        padded[
            :len(sequence)
        ] = sequence

        X.append(
            padded
        )

        # ----------------------------------------------------
        # Label
        # ----------------------------------------------------

        label = int(
            session["is_bot"].iloc[0]
        )

        y.append(
            label
        )

        # ----------------------------------------------------
        # Leakage-safe grouping
        # ----------------------------------------------------

        bot_cluster = session[
            "bot_cluster_id"
        ].iloc[0]

        if pd.notna(bot_cluster):

            # All sessions belonging to a distributed
            # bot cluster stay in the same split.

            group_id = (
                f"cluster_{bot_cluster}"
            )

        else:

            # Normal users / non-clustered bots:
            # keep all sessions of the same user together.

            user_id = session[
                "user_id"
            ].iloc[0]

            group_id = (
                f"user_{user_id}"
            )

        groups.append(
            group_id
        )

        # ----------------------------------------------------
        # Traffic type
        # ----------------------------------------------------

        traffic_types.append(
            session[
                "traffic_type"
            ].iloc[0]
        )

        # ----------------------------------------------------
        # Session ID
        # ----------------------------------------------------

        session_ids.append(
            session_id
        )

    # --------------------------------------------------------
    # Convert to numpy
    # --------------------------------------------------------

    X = np.array(
        X,
        dtype=np.float32
    )

    y = np.array(
        y,
        dtype=np.int32
    )

    groups = np.array(
        groups
    )

    traffic_types = np.array(
        traffic_types
    )

    session_ids = np.array(
        session_ids
    )

    # --------------------------------------------------------
    # Information
    # --------------------------------------------------------

    print(
        "\nSequence tensor shape:",
        X.shape
    )

    print(
        "Expected input dimension:",
        INPUT_DIM
    )

    print(
        "Labels shape:",
        y.shape
    )

    print(
        "Number of sessions:",
        len(X)
    )

    print(
        "Number of unique groups:",
        len(np.unique(groups))
    )

    return (
        X,
        y,
        groups,
        traffic_types,
        session_ids
    )


# ============================================================
# GROUP-AWARE SPLIT
# ============================================================

def group_split(
    X,
    y,
    groups,
    traffic_types,
    session_ids
):

    """
    Split into:

        70% train
        15% validation
        15% test

    No group can appear in multiple splits.
    """

    print(
        "\nPerforming group-aware split..."
    )

    # --------------------------------------------------------
    # First split
    # --------------------------------------------------------

    splitter_1 = GroupShuffleSplit(
        n_splits=1,
        test_size=0.30,
        random_state=RANDOM_STATE
    )

    train_idx, temp_idx = next(
        splitter_1.split(
            X,
            y,
            groups=groups
        )
    )

    # --------------------------------------------------------
    # Second split
    # --------------------------------------------------------

    splitter_2 = GroupShuffleSplit(
        n_splits=1,
        test_size=0.50,
        random_state=RANDOM_STATE
    )

    val_relative, test_relative = next(
        splitter_2.split(
            X[temp_idx],
            y[temp_idx],
            groups=groups[temp_idx]
        )
    )

    val_idx = temp_idx[
        val_relative
    ]

    test_idx = temp_idx[
        test_relative
    ]

    # --------------------------------------------------------
    # Split arrays
    # --------------------------------------------------------

    X_train = X[train_idx]
    X_val = X[val_idx]
    X_test = X[test_idx]

    y_train = y[train_idx]
    y_val = y[val_idx]
    y_test = y[test_idx]

    traffic_train = traffic_types[
        train_idx
    ]

    traffic_val = traffic_types[
        val_idx
    ]

    traffic_test = traffic_types[
        test_idx
    ]

    session_train = session_ids[
        train_idx
    ]

    session_val = session_ids[
        val_idx
    ]

    session_test = session_ids[
        test_idx
    ]

    # --------------------------------------------------------
    # Print split information
    # --------------------------------------------------------

    print("\nSplit sizes:")

    print(
        "Train:",
        len(X_train)
    )

    print(
        "Validation:",
        len(X_val)
    )

    print(
        "Test:",
        len(X_test)
    )

    print("\nTrain class distribution:")
    print(
        pd.Series(y_train)
        .value_counts()
    )

    print("\nValidation class distribution:")
    print(
        pd.Series(y_val)
        .value_counts()
    )

    print("\nTest class distribution:")
    print(
        pd.Series(y_test)
        .value_counts()
    )

    return (
        X_train,
        X_val,
        X_test,
        y_train,
        y_val,
        y_test,
        traffic_train,
        traffic_val,
        traffic_test,
        session_train,
        session_val,
        session_test
    )


# ============================================================
# BUILD GRU MODEL
# ============================================================

def build_gru_model():

    print(
        "\nBuilding GRU model..."
    )

    model = keras.Sequential(
        [

            # ------------------------------------------------
            # Input
            # ------------------------------------------------

            layers.Input(
                shape=(
                    SEQ_LEN,
                    INPUT_DIM
                )
            ),

            # ------------------------------------------------
            # Ignore zero padding
            # ------------------------------------------------

            layers.Masking(
                mask_value=0.0
            ),

            # ------------------------------------------------
            # First GRU
            # ------------------------------------------------

            layers.GRU(
                64,
                return_sequences=True
            ),

            layers.Dropout(
                0.25
            ),

            # ------------------------------------------------
            # Second GRU
            # ------------------------------------------------

            layers.GRU(
                32,
                return_sequences=False
            ),

            layers.Dropout(
                0.25
            ),

            # ------------------------------------------------
            # Dense representation
            # ------------------------------------------------

            layers.Dense(
                16,
                activation="relu"
            ),

            layers.Dropout(
                0.20
            ),

            # ------------------------------------------------
            # Binary output
            # ------------------------------------------------

            layers.Dense(
                1,
                activation="sigmoid"
            )
        ]
    )

    # --------------------------------------------------------
    # Compile
    # --------------------------------------------------------

    model.compile(

        optimizer=keras.optimizers.Adam(
            learning_rate=LEARNING_RATE
        ),

        loss="binary_crossentropy",

        metrics=[

            keras.metrics.AUC(
                name="roc_auc"
            ),

            keras.metrics.AUC(
                name="pr_auc",
                curve="PR"
            ),

            keras.metrics.Precision(
                name="precision"
            ),

            keras.metrics.Recall(
                name="recall"
            )
        ]
    )

    model.summary()

    return model


# ============================================================
# CLASS WEIGHTS
# ============================================================

def calculate_class_weights(y_train):

    classes = np.unique(
        y_train
    )

    weights = compute_class_weight(
        class_weight="balanced",
        classes=classes,
        y=y_train
    )

    class_weights = dict(
        zip(
            classes,
            weights
        )
    )

    print(
        "\nClass weights:"
    )

    print(
        class_weights
    )

    return class_weights


# ============================================================
# TRAIN MODEL
# ============================================================

def train_model(
    model,
    X_train,
    y_train,
    X_val,
    y_val
):

    print(
        "\nTraining GRU..."
    )

    class_weights = calculate_class_weights(
        y_train
    )

    # --------------------------------------------------------
    # Early stopping
    # --------------------------------------------------------

    early_stopping = keras.callbacks.EarlyStopping(

        monitor="val_pr_auc",

        mode="max",

        patience=7,

        restore_best_weights=True,

        verbose=1
    )

    # --------------------------------------------------------
    # Reduce learning rate
    # --------------------------------------------------------

    reduce_lr = keras.callbacks.ReduceLROnPlateau(

        monitor="val_pr_auc",

        mode="max",

        factor=0.5,

        patience=3,

        min_lr=1e-6,

        verbose=1
    )

    # --------------------------------------------------------
    # Train
    # --------------------------------------------------------

    history = model.fit(

        X_train,

        y_train,

        validation_data=(
            X_val,
            y_val
        ),

        epochs=EPOCHS,

        batch_size=BATCH_SIZE,

        class_weight=class_weights,

        callbacks=[
            early_stopping,
            reduce_lr
        ],

        verbose=1
    )

    return (
        model,
        history
    )


# ============================================================
# PREDICTIONS
# ============================================================

def predict_probabilities(
    model,
    X
):

    probabilities = model.predict(
        X,
        batch_size=BATCH_SIZE,
        verbose=0
    ).reshape(-1)

    return probabilities


# ============================================================
# THRESHOLD SEARCH
# ============================================================

def find_best_threshold(
    y_true,
    probabilities
):

    print(
        "\nSearching for optimal threshold..."
    )

    thresholds = np.arange(
        0.05,
        0.96,
        0.01
    )

    best_threshold = 0.5

    best_f1 = -1

    for threshold in thresholds:

        predictions = (
            probabilities >= threshold
        ).astype(int)

        f1 = f1_score(
            y_true,
            predictions,
            zero_division=0
        )

        if f1 > best_f1:

            best_f1 = f1

            best_threshold = threshold

    print(
        f"Best threshold: "
        f"{best_threshold:.2f}"
    )

    print(
        f"Validation F1: "
        f"{best_f1:.4f}"
    )

    return best_threshold


# ============================================================
# EVALUATION
# ============================================================

def evaluate_model(
    model,
    X,
    y,
    threshold,
    dataset_name="Test"
):

    print(
        f"\n{'=' * 60}"
    )

    print(
        f"{dataset_name.upper()} EVALUATION"
    )

    print(
        f"{'=' * 60}"
    )

    probabilities = predict_probabilities(
        model,
        X
    )

    predictions = (
        probabilities >= threshold
    ).astype(int)

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    roc_auc = roc_auc_score(
        y,
        probabilities
    )

    pr_auc = average_precision_score(
        y,
        probabilities
    )

    precision = precision_score(
        y,
        predictions,
        zero_division=0
    )

    recall = recall_score(
        y,
        predictions,
        zero_division=0
    )

    f1 = f1_score(
        y,
        predictions,
        zero_division=0
    )

    # --------------------------------------------------------
    # Confusion matrix
    # --------------------------------------------------------

    cm = confusion_matrix(
        y,
        predictions
    )

    print(
        f"\nThreshold : {threshold:.4f}"
    )

    print(
        f"Precision : {precision:.4f}"
    )

    print(
        f"Recall    : {recall:.4f}"
    )

    print(
        f"F1        : {f1:.4f}"
    )

    print(
        f"ROC-AUC   : {roc_auc:.4f}"
    )

    print(
        f"PR-AUC    : {pr_auc:.4f}"
    )

    print(
        "\nConfusion Matrix:"
    )

    print(
        cm
    )

    print(
        "\nClassification Report:"
    )

    print(
        classification_report(
            y,
            predictions,
            target_names=[
                "Human",
                "Bot"
            ],
            zero_division=0
        )
    )

    return {
        "threshold": float(threshold),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "roc_auc": float(roc_auc),
        "pr_auc": float(pr_auc)
    }


# ============================================================
# PER TRAFFIC TYPE EVALUATION
# ============================================================

def evaluate_by_traffic_type(
    model,
    X,
    y,
    traffic_types,
    threshold
):

    print(
        "\n"
        + "=" * 60
    )

    print(
        "PER TRAFFIC TYPE EVALUATION"
    )

    print(
        "=" * 60
    )

    probabilities = predict_probabilities(
        model,
        X
    )

    predictions = (
        probabilities >= threshold
    ).astype(int)

    results = []

    unique_types = np.unique(
        traffic_types
    )

    for traffic_type in unique_types:

        mask = (
            traffic_types
            == traffic_type
        )

        type_y = y[mask]

        type_prob = probabilities[
            mask
        ]

        type_pred = predictions[
            mask
        ]

        precision = precision_score(
            type_y,
            type_pred,
            zero_division=0
        )

        recall = recall_score(
            type_y,
            type_pred,
            zero_division=0
        )

        f1 = f1_score(
            type_y,
            type_pred,
            zero_division=0
        )

        # ROC-AUC only exists when both
        # classes are present.

        if len(
            np.unique(type_y)
        ) == 2:

            roc_auc = roc_auc_score(
                type_y,
                type_prob
            )

        else:

            roc_auc = np.nan

        results.append(
            {
                "traffic_type": traffic_type,
                "samples": int(
                    mask.sum()
                ),
                "actual_bots": int(
                    type_y.sum()
                ),
                "predicted_bots": int(
                    type_pred.sum()
                ),
                "precision": float(
                    precision
                ),
                "recall": float(
                    recall
                ),
                "f1": float(
                    f1
                ),
                "roc_auc": (
                    float(roc_auc)
                    if not np.isnan(roc_auc)
                    else np.nan
                )
            }
        )

    results_df = pd.DataFrame(
        results
    )

    print(
        results_df.to_string(
            index=False
        )
    )

    return results_df


# ============================================================
# SAVE MODEL
# ============================================================

def save_model(
    model,
    threshold,
    metrics
):

    print(
        "\nSaving GRU model..."
    )

    model.save(
        MODEL_PATH
    )

    metadata = {

        "sequence_length": SEQ_LEN,

        "input_dimension": INPUT_DIM,

        "event_types": EVENT_TYPES,

        "numeric_features": NUMERIC_FEATURES,

        "threshold": float(
            threshold
        ),

        "metrics": metrics,

        "preprocessing": {

            "time_transform": "log1p",

            "count_transform": "log1p",

            "negative_values": (
                "clipped_to_zero"
            ),

            "padding": "zero",

            "mask_value": 0.0
        },

        "architecture": {

            "gru_1": 64,

            "gru_2": 32,

            "dense": 16,

            "dropout_1": 0.25,

            "dropout_2": 0.25,

            "dropout_3": 0.20
        },

        "training": {

            "batch_size": BATCH_SIZE,

            "epochs": EPOCHS,

            "learning_rate": LEARNING_RATE,

            "loss": "binary_crossentropy"
        },

        "random_state": RANDOM_STATE
    }

    with open(
        METADATA_PATH,
        "w"
    ) as f:

        json.dump(
            metadata,
            f,
            indent=4
        )

    print(
        "Model saved to:",
        MODEL_PATH
    )

    print(
        "Metadata saved to:",
        METADATA_PATH
    )


# ============================================================
# LOAD MODEL
# ============================================================

def load_saved_model():

    model = keras.models.load_model(
        MODEL_PATH
    )

    with open(
        METADATA_PATH,
        "r"
    ) as f:

        metadata = json.load(f)

    return (
        model,
        metadata
    )


# ============================================================
# PREPARE INFERENCE DATA
# ============================================================

def prepare_inference_dataframe(df):

    """
    Make live/single-session event data compatible
    with the training feature schema.
    """

    df = df.copy()

    defaults = {

        "timestamp": 0,

        "session_id": "live_session",

        "user_id": "live_user",

        "bot_cluster_id": np.nan,

        "request_status": "none",

        "inter_event_time_ms": 0,

        "retry_count": 0,

        "request_number": 0,

        "active_sessions": 0,

        "queue_position": -1,

        "session_age_sec": 0,

        "time_since_last_request_ms": -1,

        "time_since_last_failure_ms": -1,

        "mouse_events": 0,

        "keyboard_events": 0,

        "scroll_events": 0
    }

    for column, default in defaults.items():

        if column not in df.columns:

            df[column] = default

    return df


# ============================================================
# SINGLE SESSION INFERENCE
# ============================================================

def predict_single_session(
    model,
    events,
    threshold=0.5
):

    """
    Predict a single session.

    `events` should be a list of dictionaries using
    the same schema as traffic_events.csv.
    """

    # --------------------------------------------------------
    # Convert to dataframe
    # --------------------------------------------------------

    session_df = pd.DataFrame(
        events
    )

    if session_df.empty:

        raise ValueError(
            "Cannot predict an empty session."
        )

    # --------------------------------------------------------
    # Prepare schema
    # --------------------------------------------------------

    session_df = prepare_inference_dataframe(
        session_df
    )

    # --------------------------------------------------------
    # Normalize numerical features
    # --------------------------------------------------------

    session_df = normalize_event_features(
        session_df
    )

    # --------------------------------------------------------
    # Sort chronologically
    # --------------------------------------------------------

    if "timestamp" in session_df.columns:

        session_df = session_df.sort_values(
            "timestamp"
        )

    # --------------------------------------------------------
    # Encode
    # --------------------------------------------------------

    sequence = np.array(
        [
            encode_event(row)
            for _, row in session_df.iterrows()
        ],
        dtype=np.float32
    )

    # --------------------------------------------------------
    # Keep latest events
    # --------------------------------------------------------

    if len(sequence) > SEQ_LEN:

        sequence = sequence[
            -SEQ_LEN:
        ]

    # --------------------------------------------------------
    # Pad
    # --------------------------------------------------------

    padded = np.zeros(
        (
            SEQ_LEN,
            INPUT_DIM
        ),
        dtype=np.float32
    )

    padded[
        :len(sequence)
    ] = sequence

    # --------------------------------------------------------
    # Batch dimension
    # --------------------------------------------------------

    X = np.expand_dims(
        padded,
        axis=0
    )

    # --------------------------------------------------------
    # Predict
    # --------------------------------------------------------

    probability = float(
        model.predict(
            X,
            verbose=0
        )[0][0]
    )

    prediction = int(
        probability >= threshold
    )

    return {

        "bot_probability": probability,

        "prediction": prediction,

        "decision": (
            "BOT"
            if prediction == 1
            else "HUMAN"
        )
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "\n"
        + "=" * 60
    )

    print(
        "FAIR DROP - GRU BOT DETECTOR"
    )

    print(
        "=" * 60
    )

    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    df = load_event_data(
        DATA_PATH
    )

    # --------------------------------------------------------
    # Normalize
    # --------------------------------------------------------

    df = normalize_event_features(
        df
    )

    # --------------------------------------------------------
    # Build sequences
    # --------------------------------------------------------

    (
        X,
        y,
        groups,
        traffic_types,
        session_ids
    ) = build_sequences(
        df
    )

    # --------------------------------------------------------
    # Validate tensor shape
    # --------------------------------------------------------

    expected_shape = (
        len(X),
        SEQ_LEN,
        INPUT_DIM
    )

    if X.shape != expected_shape:

        raise ValueError(
            f"Unexpected tensor shape: "
            f"{X.shape}. "
            f"Expected: {expected_shape}"
        )

    # --------------------------------------------------------
    # Split
    # --------------------------------------------------------

    (
        X_train,
        X_val,
        X_test,

        y_train,
        y_val,
        y_test,

        traffic_train,
        traffic_val,
        traffic_test,

        session_train,
        session_val,
        session_test

    ) = group_split(
        X,
        y,
        groups,
        traffic_types,
        session_ids
    )

    # --------------------------------------------------------
    # Model
    # --------------------------------------------------------

    model = build_gru_model()

    # --------------------------------------------------------
    # Train
    # --------------------------------------------------------

    model, history = train_model(
        model,

        X_train,
        y_train,

        X_val,
        y_val
    )

    # --------------------------------------------------------
    # Validation probabilities
    # --------------------------------------------------------

    val_probabilities = predict_probabilities(
        model,
        X_val
    )

    # --------------------------------------------------------
    # Threshold
    # --------------------------------------------------------

    threshold = find_best_threshold(
        y_val,
        val_probabilities
    )

    # --------------------------------------------------------
    # Validation evaluation
    # --------------------------------------------------------

    val_metrics = evaluate_model(
        model,
        X_val,
        y_val,
        threshold,
        dataset_name="Validation"
    )

    # --------------------------------------------------------
    # Final test evaluation
    # --------------------------------------------------------

    test_metrics = evaluate_model(
        model,
        X_test,
        y_test,
        threshold,
        dataset_name="Test"
    )

    # --------------------------------------------------------
    # Traffic type evaluation
    # --------------------------------------------------------

    traffic_results = evaluate_by_traffic_type(
        model,
        X_test,
        y_test,
        traffic_test,
        threshold
    )

    # --------------------------------------------------------
    # Save traffic results
    # --------------------------------------------------------

    traffic_results.to_csv(
        TRAFFIC_RESULTS_PATH,
        index=False
    )

    # --------------------------------------------------------
    # Save model
    # --------------------------------------------------------

    save_model(
        model,
        threshold,
        {
            "validation": val_metrics,
            "test": test_metrics
        }
    )

    # --------------------------------------------------------
    # Final information
    # --------------------------------------------------------

    print(
        "\n"
        + "=" * 60
    )

    print(
        "GRU TRAINING COMPLETE"
    )

    print(
        "=" * 60
    )

    print(
        "\nFinal Test Metrics:"
    )

    print(
        f"ROC-AUC : "
        f"{test_metrics['roc_auc']:.4f}"
    )

    print(
        f"PR-AUC  : "
        f"{test_metrics['pr_auc']:.4f}"
    )

    print(
        f"Precision: "
        f"{test_metrics['precision']:.4f}"
    )

    print(
        f"Recall   : "
        f"{test_metrics['recall']:.4f}"
    )

    print(
        f"F1       : "
        f"{test_metrics['f1']:.4f}"
    )

    print(
        "\nModel:",
        MODEL_PATH
    )

    print(
        "Metadata:",
        METADATA_PATH
    )

    print(
        "Traffic results:",
        TRAFFIC_RESULTS_PATH
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()