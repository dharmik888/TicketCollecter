"""
============================================================
FAIR DROP - TABULAR ANTI-BOT MODEL
============================================================

Project:
    Fair Drop: Selling 500 Seats to 50,000 People
    Without Letting Bots Win

Purpose:
    Train an XGBoost model to detect bots from behavioral/
    session-level tabular features.

Traffic classes:
    - human
    - aggressive_bot
    - rapid_retry_bot
    - multi_session_bot
    - distributed_bot
    - stealth_bot
    - adaptive_bot

This file handles ONLY the tabular model.

GRU / sequence model comes later.
============================================================
"""


# ============================================================
# 1. IMPORTS
# ============================================================

import os
import json
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
    confusion_matrix,
)
from sklearn.calibration import CalibratedClassifierCV

warnings.filterwarnings("ignore")


# ============================================================
# 2. CONFIGURATION
# ============================================================

SEED = 42

# Your generated dataset.
# The code checks both possible names used in our previous files.
DATA_PATHS = [
    "ML/data/traffic_behavior_dataset.csv",
    "ML/data/bot_behavior_dataset.csv",
]

# Folder where trained models and explanations will be saved.
MODEL_DIR = Path("ML/models")

MODEL_DIR.mkdir(
    parents=True,
    exist_ok=True
)

# Output files.
BASE_MODEL_PATH = MODEL_DIR / "xgboost_bot_detector.joblib"

CALIBRATED_MODEL_PATH = (
    MODEL_DIR /
    "xgboost_bot_detector_calibrated.joblib"
)

METADATA_PATH = (
    MODEL_DIR /
    "model_metadata.json"
)

FEATURE_IMPORTANCE_PATH = (
    MODEL_DIR /
    "feature_importance.csv"
)

SHAP_PATH = (
    MODEL_DIR /
    "shap_values.csv"
)


# ============================================================
# 3. TARGET
# ============================================================

TARGET = "is_bot"


# ============================================================
# 4. FEATURES
# ============================================================

"""
These are behavioral features.

We intentionally DO NOT include:

    is_bot
    traffic_type
    session_id
    user_id
    bot_cluster_id
    drop_id

Those are either:
    - the answer itself
    - identifiers
    - simulator-specific labels

Using them would create leakage.
"""


BEHAVIOR_FEATURES = [

    # --------------------------------------------------------
    # Request behavior
    # --------------------------------------------------------

    "requests",

    "successful_requests",

    "failed_requests",

    "retry_count",

    "refresh_count",

    "reconnect_count",

    "queue_join_count",

    "queue_poll_count",

    "requests_per_second",


    # --------------------------------------------------------
    # Session behavior
    # --------------------------------------------------------

    "session_duration_sec",


    # --------------------------------------------------------
    # Timing behavior
    # --------------------------------------------------------

    "avg_inter_event_ms",

    "std_inter_event_ms",

    "timing_cv",

    "timing_entropy",

    "request_interval_cv",

    "mean_retry_latency_ms",

    "retry_latency_std_ms",


    # --------------------------------------------------------
    # Behavioral pattern
    # --------------------------------------------------------

    "event_entropy",

    "burstiness_score",


    # --------------------------------------------------------
    # Human interaction
    # --------------------------------------------------------

    "mouse_events",

    "keyboard_events",

    "scroll_events",

    "human_action_ratio",


    # --------------------------------------------------------
    # Request / action relationship
    # --------------------------------------------------------

    "request_action_ratio",


    # --------------------------------------------------------
    # Cross-session behavior
    # --------------------------------------------------------

    "user_session_count",

    "peak_active_sessions",

    "mean_active_sessions",


    # --------------------------------------------------------
    # Rates
    # --------------------------------------------------------

    "success_rate",

    "failure_rate",

    "retry_rate",

    "reconnect_rate",
]


# These were created by the cross-session feature stage
# in some versions of your simulator.

OPTIONAL_BEHAVIOR_FEATURES = [

    "sessions_per_user",

    "cluster_size",

    "multi_session_behavior",

    "cluster_request_rate_std",
]


# Explicitly forbidden columns.

LEAKAGE_COLUMNS = {

    "is_bot",

    "traffic_type",

    "session_id",

    "user_id",

    "bot_cluster_id",

    "drop_id",
}


# ============================================================
# 5. FIND DATASET
# ============================================================

def find_dataset():

    for path in DATA_PATHS:

        if Path(path).exists():

            return Path(path)

    raise FileNotFoundError(

        "\nCould not find the dataset.\n\n"

        "Expected one of:\n"

        + "\n".join(
            f"    {path}"
            for path in DATA_PATHS
        )

    )


# ============================================================
# 6. LOAD DATA
# ============================================================

def load_dataset():

    path = find_dataset()

    print()
    print("=" * 70)
    print("LOADING DATASET")
    print("=" * 70)

    print(
        f"\nDataset path:\n{path}"
    )

    df = pd.read_csv(path)

    print(
        f"\nDataset shape: {df.shape}"
    )

    if TARGET not in df.columns:

        raise ValueError(
            f"\nTarget column '{TARGET}' "
            f"was not found."
        )

    print("\nTarget distribution:")

    print(
        df[TARGET]
        .value_counts()
    )

    print("\nTarget percentage:")

    print(
        df[TARGET]
        .value_counts(
            normalize=True
        )
        .mul(100)
        .round(2)
    )

    return df


# ============================================================
# 7. SELECT FEATURES
# ============================================================

def get_feature_columns(df):

    available_features = []

    for feature in (
        BEHAVIOR_FEATURES
        +
        OPTIONAL_BEHAVIOR_FEATURES
    ):

        if feature in df.columns:

            available_features.append(
                feature
            )


    # --------------------------------------------------------
    # Safety check
    # --------------------------------------------------------

    for feature in available_features:

        if feature in LEAKAGE_COLUMNS:

            raise ValueError(
                f"LEAKAGE DETECTED: {feature}"
            )


    if len(available_features) < 10:

        raise ValueError(

            "\nToo few behavioral features found."

            f"\nFound: {available_features}"

        )


    print()
    print("=" * 70)
    print("FEATURES USED")
    print("=" * 70)

    for number, feature in enumerate(
        available_features,
        start=1
    ):

        print(
            f"{number:2d}. {feature}"
        )

    print(
        f"\nTotal features: "
        f"{len(available_features)}"
    )

    return available_features


# ============================================================
# 8. PREPROCESS FEATURES
# ============================================================

def prepare_features(
    df,
    feature_columns
):

    X = df[
        feature_columns
    ].copy()


    # --------------------------------------------------------
    # Convert everything to numeric.
    # --------------------------------------------------------

    for column in X.columns:

        X[column] = pd.to_numeric(
            X[column],
            errors="coerce"
        )


    # --------------------------------------------------------
    # Replace infinite values.
    # --------------------------------------------------------

    X = X.replace(
        [np.inf, -np.inf],
        np.nan
    )


    # --------------------------------------------------------
    # Median imputation.
    # --------------------------------------------------------

    for column in X.columns:

        median_value = X[column].median()

        if pd.isna(median_value):

            median_value = 0.0

        X[column] = (
            X[column]
            .fillna(median_value)
        )


    return X


# ============================================================
# 9. CREATE GROUPS
# ============================================================

def create_groups(df):

    """
    Groups prevent the same user/session family from appearing
    in both training and test.

    This is especially important because your simulator contains
    multi-session and distributed behavior.
    """

    # --------------------------------------------------------
    # If user_id exists, use it.
    # --------------------------------------------------------

    if "user_id" in df.columns:

        groups = (
            df["user_id"]
            .astype(str)
        )

    else:

        groups = pd.Series(
            [
                f"row_{i}"
                for i in range(len(df))
            ],
            index=df.index
        )


    # --------------------------------------------------------
    # Keep distributed bot clusters together.
    # --------------------------------------------------------

    if "bot_cluster_id" in df.columns:

        cluster_values = (
            df["bot_cluster_id"]
            .astype("string")
        )


        groups = np.where(

            cluster_values.notna(),

            "cluster_" +
            cluster_values
            .fillna("")
            .astype(str),

            "user_" +
            groups.astype(str)

        )


        groups = pd.Series(
            groups,
            index=df.index
        )


    return groups


# ============================================================
# 10. TRAIN / VALIDATION / TEST SPLIT
# ============================================================

def split_dataset(df):

    """
    Split:

        70% training
        15% validation
        15% testing

    GroupShuffleSplit prevents user/session leakage.
    """

    groups = create_groups(df)


    # ========================================================
    # First split:
    #
    # TRAIN = 70%
    # TEMP  = 30%
    # ========================================================

    splitter_1 = GroupShuffleSplit(

        n_splits=1,

        train_size=0.70,

        random_state=SEED

    )


    train_indices, temp_indices = next(

        splitter_1.split(

            df,

            df[TARGET],

            groups=groups

        )

    )


    train_df = (
        df.iloc[train_indices]
        .copy()
    )

    temp_df = (
        df.iloc[temp_indices]
        .copy()
    )


    # ========================================================
    # Second split:
    #
    # VALIDATION = 15%
    # TEST       = 15%
    # ========================================================

    temp_groups = (
        groups.iloc[temp_indices]
    )


    splitter_2 = GroupShuffleSplit(

        n_splits=1,

        train_size=0.50,

        random_state=SEED + 1

    )


    validation_indices, test_indices = next(

        splitter_2.split(

            temp_df,

            temp_df[TARGET],

            groups=temp_groups

        )

    )


    validation_df = (
        temp_df
        .iloc[validation_indices]
        .copy()
    )

    test_df = (
        temp_df
        .iloc[test_indices]
        .copy()
    )


    # ========================================================
    # REPORT
    # ========================================================

    print()
    print("=" * 70)
    print("TRAIN / VALIDATION / TEST SPLIT")
    print("=" * 70)


    for name, data in [

        ("TRAIN", train_df),

        ("VALIDATION", validation_df),

        ("TEST", test_df),

    ]:

        print(

            f"{name:12s} | "
            f"Rows: {len(data):6d} | "
            f"Bot rate: "
            f"{data[TARGET].mean():.4f}"

        )


    return (
        train_df,
        validation_df,
        test_df
    )


# ============================================================
# 11. BUILD XGBOOST MODEL
# ============================================================

def build_xgboost_model(
    scale_pos_weight
):

    try:

        from xgboost import XGBClassifier

    except ImportError:

        raise ImportError(

            "\nXGBoost is not installed."

            "\nInstall it with:"

            "\n\npip install xgboost"

        )


    model = XGBClassifier(

        # ----------------------------------------------------
        # Objective
        # ----------------------------------------------------

        objective="binary:logistic",


        # ----------------------------------------------------
        # Number of boosting rounds
        # ----------------------------------------------------

        n_estimators=800,


        # ----------------------------------------------------
        # Tree complexity
        # ----------------------------------------------------

        max_depth=6,


        # ----------------------------------------------------
        # Learning rate
        # ----------------------------------------------------

        learning_rate=0.04,


        # ----------------------------------------------------
        # Row sampling
        # ----------------------------------------------------

        subsample=0.85,


        # ----------------------------------------------------
        # Feature sampling
        # ----------------------------------------------------

        colsample_bytree=0.85,


        # ----------------------------------------------------
        # Minimum child weight
        # ----------------------------------------------------

        min_child_weight=3,


        # ----------------------------------------------------
        # Minimum loss reduction
        # ----------------------------------------------------

        gamma=0.10,


        # ----------------------------------------------------
        # L1 regularization
        # ----------------------------------------------------

        reg_alpha=0.10,


        # ----------------------------------------------------
        # L2 regularization
        # ----------------------------------------------------

        reg_lambda=2.0,


        # ----------------------------------------------------
        # Class imbalance
        # ----------------------------------------------------

        scale_pos_weight=scale_pos_weight,


        # ----------------------------------------------------
        # Reproducibility
        # ----------------------------------------------------

        random_state=SEED,


        # ----------------------------------------------------
        # CPU parallelization
        # ----------------------------------------------------

        n_jobs=-1,


        # ----------------------------------------------------
        # Evaluation metric
        # ----------------------------------------------------

        eval_metric="aucpr",


        # ----------------------------------------------------
        # Faster histogram algorithm
        # ----------------------------------------------------

        tree_method="hist",

    )


    return model


# ============================================================
# 12. TRAIN XGBOOST
# ============================================================

def train_xgboost(
    X_train,
    y_train,
    X_validation,
    y_validation
):

    # --------------------------------------------------------
    # Calculate class imbalance.
    # --------------------------------------------------------

    negative_count = (
        y_train == 0
    ).sum()

    positive_count = (
        y_train == 1
    ).sum()


    if positive_count == 0:

        raise ValueError(
            "Training set contains no bots."
        )


    scale_pos_weight = (
        negative_count
        /
        positive_count
    )


    print()
    print("=" * 70)
    print("TRAINING XGBOOST")
    print("=" * 70)

    print(
        f"\nHuman samples: "
        f"{negative_count}"
    )

    print(
        f"Bot samples: "
        f"{positive_count}"
    )

    print(
        f"scale_pos_weight: "
        f"{scale_pos_weight:.4f}"
    )


    model = build_xgboost_model(
        scale_pos_weight
    )


    # --------------------------------------------------------
    # Train
    # --------------------------------------------------------

    model.fit(

        X_train,

        y_train,

        eval_set=[
            (
                X_validation,
                y_validation
            )
        ],

        verbose=False

    )


    print(
        "\nXGBoost training complete."
    )


    return model


# ============================================================
# 13. GET PROBABILITIES
# ============================================================

def get_probabilities(
    model,
    X
):

    probabilities = (
        model
        .predict_proba(X)
        [:, 1]
    )

    return probabilities


# ============================================================
# 14. EVALUATE MODEL
# ============================================================

def evaluate_model(
    model,
    X,
    y,
    name,
    threshold=0.50
):

    probabilities = (
        get_probabilities(
            model,
            X
        )
    )


    predictions = (
        probabilities >= threshold
    ).astype(int)


    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

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


    roc_auc = roc_auc_score(

        y,

        probabilities

    )


    pr_auc = average_precision_score(

        y,

        probabilities

    )


    cm = confusion_matrix(

        y,

        predictions

    )


    # --------------------------------------------------------
    # Print
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(
        f"{name.upper()} RESULTS"
    )
    print("=" * 70)

    print(
        f"\nThreshold : "
        f"{threshold:.4f}"
    )

    print(
        f"Precision : "
        f"{precision:.4f}"
    )

    print(
        f"Recall    : "
        f"{recall:.4f}"
    )

    print(
        f"F1        : "
        f"{f1:.4f}"
    )

    print(
        f"ROC-AUC   : "
        f"{roc_auc:.4f}"
    )

    print(
        f"PR-AUC    : "
        f"{pr_auc:.4f}"
    )


    print(
        "\nConfusion Matrix:"
    )

    print(
        "\n                 "
        "Pred Human   Pred Bot"
    )

    print(

        f"Actual Human     "
        f"{cm[0][0]:10d}   "
        f"{cm[0][1]:9d}"

    )

    print(

        f"Actual Bot       "
        f"{cm[1][0]:10d}   "
        f"{cm[1][1]:9d}"

    )


    return {

        "precision":
            float(precision),

        "recall":
            float(recall),

        "f1":
            float(f1),

        "roc_auc":
            float(roc_auc),

        "pr_auc":
            float(pr_auc),

        "threshold":
            float(threshold),

        "confusion_matrix":
            cm.tolist(),

    }


# ============================================================
# 15. FIND DECISION THRESHOLD
# ============================================================

def find_best_threshold(
    model,
    X_validation,
    y_validation
):

    """
    Search thresholds from 0.10 to 0.90.

    The validation set chooses the operating threshold.

    The final test set is NOT used for threshold selection.
    """

    probabilities = (
        get_probabilities(
            model,
            X_validation
        )
    )


    thresholds = np.arange(

        0.10,

        0.91,

        0.01

    )


    best_threshold = 0.50

    best_f1 = -1


    for threshold in thresholds:

        predictions = (

            probabilities >= threshold

        ).astype(int)


        current_f1 = f1_score(

            y_validation,

            predictions,

            zero_division=0

        )


        if current_f1 > best_f1:

            best_f1 = current_f1

            best_threshold = (
                float(threshold)
            )


    print()
    print("=" * 70)
    print("THRESHOLD SELECTION")
    print("=" * 70)

    print(
        f"\nBest validation threshold: "
        f"{best_threshold:.2f}"
    )

    print(
        f"Validation F1: "
        f"{best_f1:.4f}"
    )


    return best_threshold


# ============================================================
# 16. PROBABILITY CALIBRATION
# ============================================================
def calibrate_model(model, X_val, y_val):
    """
    Calibrate an already-trained XGBoost model using validation data.

    Newer versions of scikit-learn removed cv="prefit".
    FrozenEstimator is the replacement.
    """

    try:
        # New scikit-learn API
        from sklearn.frozen import FrozenEstimator

        frozen_model = FrozenEstimator(model)

        calibrated_model = CalibratedClassifierCV(
            estimator=frozen_model,
            method="sigmoid"
        )

    except ImportError:
        # Compatibility fallback for older scikit-learn versions
        calibrated_model = CalibratedClassifierCV(
            estimator=model,
            method="sigmoid",
            cv=5
        )

    calibrated_model.fit(X_val, y_val)

    return calibrated_model


# ============================================================
# 17. FEATURE IMPORTANCE
# ============================================================

def calculate_feature_importance(
    model,
    feature_columns
):

    importance = pd.DataFrame({

        "feature":
            feature_columns,

        "importance":
            model.feature_importances_

    })


    importance = (
        importance
        .sort_values(
            "importance",
            ascending=False
        )
        .reset_index(drop=True)
    )


    importance.to_csv(

        FEATURE_IMPORTANCE_PATH,

        index=False

    )


    print()
    print("=" * 70)
    print("TOP FEATURE IMPORTANCE")
    print("=" * 70)

    print(
        importance
        .head(20)
        .to_string(
            index=False
        )
    )


    return importance


# ============================================================
# 18. SHAP
# ============================================================

def calculate_shap(
    model,
    X_test,
    max_samples=2000
):

    """
    SHAP explains WHY the XGBoost model produced its prediction.

    We explain the base XGBoost model rather than the calibration
    wrapper because TreeExplainer works directly with the tree model.
    """

    try:

        import shap

    except ImportError:

        raise ImportError(

            "\nSHAP is not installed."

            "\nInstall it with:"

            "\n\npip install shap"

        )


    # --------------------------------------------------------
    # Limit SHAP calculation for speed.
    # --------------------------------------------------------

    number_of_samples = min(

        max_samples,

        len(X_test)

    )


    X_sample = (
        X_test
        .iloc[:number_of_samples]
        .copy()
    )


    print()
    print("=" * 70)
    print("CALCULATING SHAP")
    print("=" * 70)

    print(
        f"\nSHAP samples: "
        f"{len(X_sample)}"
    )


    # --------------------------------------------------------
    # TreeExplainer
    # --------------------------------------------------------

    explainer = (
        shap.TreeExplainer(
            model
        )
    )


    shap_values = (
        explainer
        .shap_values(
            X_sample
        )
    )


    # --------------------------------------------------------
    # Save individual SHAP values.
    # --------------------------------------------------------

    shap_dataframe = pd.DataFrame(

        shap_values,

        columns=X_sample.columns,

        index=X_sample.index

    )


    shap_dataframe.to_csv(

        SHAP_PATH,

        index=False

    )


    # --------------------------------------------------------
    # Global SHAP importance.
    # --------------------------------------------------------

    global_shap = (

        shap_dataframe
        .abs()
        .mean()
        .sort_values(
            ascending=False
        )

    )


    global_shap = (
        global_shap
        .rename(
            "mean_absolute_shap"
        )
        .reset_index()
    )


    global_shap.columns = [

        "feature",

        "mean_absolute_shap"

    ]


    print()
    print(
        "TOP SHAP FEATURES:"
    )

    print(

        global_shap
        .head(20)
        .to_string(
            index=False
        )

    )


    print(
        f"\nSHAP values saved to:"
        f"\n{SHAP_PATH}"
    )


    return (

        explainer,

        shap_dataframe,

        global_shap

    )


# ============================================================
# 19. SAVE MODEL
# ============================================================

def save_model(
    model,
    calibrated_model,
    feature_columns,
    threshold
):

    # --------------------------------------------------------
    # Save raw XGBoost
    # --------------------------------------------------------

    joblib.dump(

        model,

        BASE_MODEL_PATH

    )


    # --------------------------------------------------------
    # Save calibrated model
    # --------------------------------------------------------

    joblib.dump(

        calibrated_model,

        CALIBRATED_MODEL_PATH

    )


    # --------------------------------------------------------
    # Save metadata
    # --------------------------------------------------------

    metadata = {

        "seed":
            SEED,

        "target":
            TARGET,

        "features":
            feature_columns,

        "threshold":
            float(threshold),

        "calibration":
            "sigmoid",

        "model_type":
            "XGBoost",

        "base_model_path":
            str(BASE_MODEL_PATH),

        "calibrated_model_path":
            str(CALIBRATED_MODEL_PATH),

    }


    with open(

        METADATA_PATH,

        "w",

        encoding="utf-8"

    ) as file:

        json.dump(

            metadata,

            file,

            indent=4

        )


    print()
    print("=" * 70)
    print("MODEL SAVED")
    print("=" * 70)

    print(
        f"\nBase model:"
        f"\n{BASE_MODEL_PATH}"
    )

    print(
        f"\nCalibrated model:"
        f"\n{CALIBRATED_MODEL_PATH}"
    )

    print(
        f"\nMetadata:"
        f"\n{METADATA_PATH}"
    )


# ============================================================
# 20. LOAD MODEL
# ============================================================

def load_trained_model():

    calibrated_model = joblib.load(

        CALIBRATED_MODEL_PATH

    )


    with open(

        METADATA_PATH,

        "r",

        encoding="utf-8"

    ) as file:

        metadata = json.load(
            file
        )


    return (

        calibrated_model,

        metadata

    )


# ============================================================
# 21. PREPARE INFERENCE DATA
# ============================================================

def prepare_inference_data(
    data,
    feature_columns
):

    # --------------------------------------------------------
    # Dictionary input
    # --------------------------------------------------------

    if isinstance(
        data,
        dict
    ):

        X = pd.DataFrame(
            [data]
        )

    # --------------------------------------------------------
    # DataFrame input
    # --------------------------------------------------------

    elif isinstance(
        data,
        pd.DataFrame
    ):

        X = data.copy()

    else:

        raise TypeError(

            "Inference input must be "
            "a dictionary or pandas DataFrame."

        )


    # --------------------------------------------------------
    # Add missing columns.
    # --------------------------------------------------------

    for feature in feature_columns:

        if feature not in X.columns:

            X[feature] = np.nan


    # --------------------------------------------------------
    # Keep only trained features.
    # --------------------------------------------------------

    X = X[
        feature_columns
    ].copy()


    # --------------------------------------------------------
    # Numeric conversion.
    # --------------------------------------------------------

    for feature in X.columns:

        X[feature] = pd.to_numeric(

            X[feature],

            errors="coerce"

        )


    # --------------------------------------------------------
    # Replace infinity.
    # --------------------------------------------------------

    X = X.replace(

        [np.inf, -np.inf],

        np.nan

    )


    # --------------------------------------------------------
    # Fill missing inference values.
    #
    # For the hackathon simulator this is safe.
    # In production, store training medians in metadata.
    # --------------------------------------------------------

    X = X.fillna(0.0)


    return X


# ============================================================
# 22. BOT PROBABILITY INFERENCE
# ============================================================

def predict_bot_probability(
    behavioral_data
):

    """
    Return a bot probability between 0 and 1.

    Example:

        probability = predict_bot_probability({
            "requests": 40,
            "failed_requests": 20,
            "retry_count": 15,
            ...
        })
    """

    calibrated_model, metadata = (
        load_trained_model()
    )


    feature_columns = (
        metadata["features"]
    )


    X = prepare_inference_data(

        behavioral_data,

        feature_columns

    )


    probability = (

        calibrated_model
        .predict_proba(X)[0][1]

    )


    probability = float(

        np.clip(

            probability,

            0.0,

            1.0

        )

    )


    return probability


# ============================================================
# 23. COMPLETE BOT PREDICTION
# ============================================================

def predict_bot(
    behavioral_data
):

    """
    Returns:

        bot_probability
        is_bot
        threshold
    """

    calibrated_model, metadata = (
        load_trained_model()
    )


    feature_columns = (
        metadata["features"]
    )


    threshold = float(

        metadata["threshold"]

    )


    X = prepare_inference_data(

        behavioral_data,

        feature_columns

    )


    probability = (

        calibrated_model
        .predict_proba(X)[0][1]

    )


    probability = float(

        np.clip(

            probability,

            0.0,

            1.0

        )

    )


    is_bot = int(

        probability >= threshold

    )


    return {

        "bot_probability":
            probability,

        "is_bot":
            is_bot,

        "threshold":
            threshold,

    }


# ============================================================
# 24. TEST CALIBRATED MODEL
# ============================================================

def evaluate_calibrated_model(
    calibrated_model,
    X_test,
    y_test,
    threshold
):

    probabilities = (

        calibrated_model
        .predict_proba(X_test)
        [:, 1]

    )


    predictions = (

        probabilities >= threshold

    ).astype(int)


    precision = precision_score(

        y_test,

        predictions,

        zero_division=0

    )


    recall = recall_score(

        y_test,

        predictions,

        zero_division=0

    )


    f1 = f1_score(

        y_test,

        predictions,

        zero_division=0

    )


    roc_auc = roc_auc_score(

        y_test,

        probabilities

    )


    pr_auc = average_precision_score(

        y_test,

        probabilities

    )


    cm = confusion_matrix(

        y_test,

        predictions

    )


    print()
    print("=" * 70)
    print("FINAL CALIBRATED TEST RESULTS")
    print("=" * 70)

    print(
        f"\nDecision threshold: "
        f"{threshold:.4f}"
    )

    print(
        f"\nPrecision : "
        f"{precision:.4f}"
    )

    print(
        f"Recall    : "
        f"{recall:.4f}"
    )

    print(
        f"F1        : "
        f"{f1:.4f}"
    )

    print(
        f"ROC-AUC   : "
        f"{roc_auc:.4f}"
    )

    print(
        f"PR-AUC    : "
        f"{pr_auc:.4f}"
    )


    print(
        "\nConfusion Matrix:"
    )


    print(
        "\n                 "
        "Pred Human   Pred Bot"
    )


    print(

        f"Actual Human     "
        f"{cm[0][0]:10d}   "
        f"{cm[0][1]:9d}"

    )


    print(

        f"Actual Bot       "
        f"{cm[1][0]:10d}   "
        f"{cm[1][1]:9d}"

    )


    return {

        "precision":
            float(precision),

        "recall":
            float(recall),

        "f1":
            float(f1),

        "roc_auc":
            float(roc_auc),

        "pr_auc":
            float(pr_auc),

        "threshold":
            float(threshold),

        "confusion_matrix":
            cm.tolist(),

    }


# ============================================================
# 25. CLASS-WISE ANALYSIS
# ============================================================

def evaluate_traffic_types(
    model,
    df,
    feature_columns,
    threshold
):

    """
    This is particularly useful for our hackathon.

    Overall bot detection can look excellent while the model
    struggles with stealth/adaptive bots.

    This function measures detection separately for:

        aggressive_bot
        rapid_retry_bot
        multi_session_bot
        distributed_bot
        stealth_bot
        adaptive_bot
    """

    if "traffic_type" not in df.columns:

        print(
            "\ntraffic_type not available. "
            "Skipping class-wise evaluation."
        )

        return


    X = prepare_features(

        df,

        feature_columns

    )


    probabilities = (

        model
        .predict_proba(X)[:, 1]

    )


    print()
    print("=" * 70)
    print("TRAFFIC-TYPE ANALYSIS")
    print("=" * 70)


    traffic_types = (
        df["traffic_type"]
        .unique()
    )


    for traffic_type in traffic_types:

        subset = (
            df["traffic_type"]
            == traffic_type
        )


        actual = (
            df.loc[
                subset,
                TARGET
            ]
            .astype(int)
        )


        if len(actual) == 0:

            continue


        subset_probabilities = (
            probabilities[subset.values]
        )


        predictions = (

            subset_probabilities
            >= threshold

        ).astype(int)


        # ----------------------------------------------------
        # Human class
        # ----------------------------------------------------

        if actual.nunique() == 1:

            if actual.iloc[0] == 0:

                false_positive_rate = (

                    predictions.sum()
                    /
                    len(predictions)

                )


                print(
                    f"\n{traffic_type}"
                )

                print(
                    f"Samples: "
                    f"{len(actual)}"
                )

                print(
                    f"False-positive rate: "
                    f"{false_positive_rate:.4f}"
                )


            else:

                detection_rate = (

                    predictions.sum()
                    /
                    len(predictions)

                )


                print(
                    f"\n{traffic_type}"
                )

                print(
                    f"Samples: "
                    f"{len(actual)}"
                )

                print(
                    f"Detection rate: "
                    f"{detection_rate:.4f}"
                )


# ============================================================
# 26. MAIN PIPELINE
# ============================================================

def main():

    print()
    print("=" * 70)
    print("FAIR DROP - TABULAR ANTI-BOT ML PIPELINE")
    print("=" * 70)


    # ========================================================
    # STEP 1
    # Load dataset
    # ========================================================

    df = load_dataset()


    # ========================================================
    # STEP 2
    # Select behavioral features
    # ========================================================

    feature_columns = (
        get_feature_columns(df)
    )


    # ========================================================
    # STEP 3
    # Split BEFORE model fitting
    # ========================================================

    (
        train_df,
        validation_df,
        test_df

    ) = split_dataset(df)


    # ========================================================
    # STEP 4
    # Prepare X
    # ========================================================

    X_train = prepare_features(

        train_df,

        feature_columns

    )


    X_validation = prepare_features(

        validation_df,

        feature_columns

    )


    X_test = prepare_features(

        test_df,

        feature_columns

    )


    # ========================================================
    # STEP 5
    # Prepare y
    # ========================================================

    y_train = (

        train_df[TARGET]
        .astype(int)

    )


    y_validation = (

        validation_df[TARGET]
        .astype(int)

    )


    y_test = (

        test_df[TARGET]
        .astype(int)

    )


    # ========================================================
    # STEP 6
    # Train XGBoost
    # ========================================================

    model = train_xgboost(

        X_train,

        y_train,

        X_validation,

        y_validation

    )


    # ========================================================
    # STEP 7
    # Raw validation evaluation
    # ========================================================

    evaluate_model(

        model,

        X_validation,

        y_validation,

        "Raw XGBoost Validation",

        threshold=0.50

    )


    # ========================================================
    # STEP 8
    # Find threshold using validation
    # ========================================================

    threshold = find_best_threshold(

        model,

        X_validation,

        y_validation

    )


    # ========================================================
    # STEP 9
    # Probability calibration
    # ========================================================

    calibrated_model = calibrate_model(

        model,

        X_validation,

        y_validation

    )


    # ========================================================
    # STEP 10
    # Final test evaluation
    # ========================================================

    test_results = (
        evaluate_calibrated_model(

            calibrated_model,

            X_test,

            y_test,

            threshold

        )
    )


    # ========================================================
    # STEP 11
    # Feature importance
    # ========================================================

    calculate_feature_importance(

        model,

        feature_columns

    )


    # ========================================================
    # STEP 12
    # SHAP
    # ========================================================

    calculate_shap(

        model,

        X_test

    )


    # ========================================================
    # STEP 13
    # Save model
    # ========================================================

    save_model(

        model,

        calibrated_model,

        feature_columns,

        threshold

    )


    # ========================================================
    # STEP 14
    # Class-wise traffic analysis
    # ========================================================

    evaluate_traffic_types(

        calibrated_model,

        test_df,

        feature_columns,

        threshold

    )


    # ========================================================
    # STEP 15
    # Example inference
    # ========================================================

    example_data = (
        X_test
        .iloc[[0]]
        .copy()
    )


    example_result = predict_bot(

        example_data

    )


    print()
    print("=" * 70)
    print("EXAMPLE INFERENCE")
    print("=" * 70)

    print(
        "\nExample result:"
    )

    print(
        example_result
    )


    # ========================================================
    # FINAL
    # ========================================================

    print()
    print("=" * 70)
    print("TABULAR MODEL PIPELINE COMPLETE")
    print("=" * 70)

    print(
        "\nThe trained model is ready "
        "for integration with the next stage."
    )

    print(
        "\nNext stage later:"
        "\nGRU / sequence-based behavioral detection"
    )


# ============================================================
# 27. RUN
# ============================================================

if __name__ == "__main__":

    main()