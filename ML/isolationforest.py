# ============================================================
# FAIR DROP - ISOLATION FOREST ANOMALY DETECTOR
# ============================================================
#
# Purpose:
# Detect behavioral patterns that are significantly different
# from legitimate human traffic.
#
# This model is NOT trained to classify known bot types.
# It learns the distribution of HUMAN behavior and flags
# sessions that look anomalous.
#
# Input:
#   ML/data/traffic_behavior_dataset.csv
#
# Output:
#   ML/models/isolation_forest.pkl
#   ML/models/isolation_forest_metadata.json
#   ML/models/isolation_forest_results.csv
#
# ============================================================

import os
import json
import pickle
import warnings

import numpy as np
import pandas as pd

from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)

warnings.filterwarnings("ignore")


# ============================================================
# CONFIGURATION
# ============================================================

DATA_PATH = "ML/data/traffic_behavior_dataset.csv"

MODEL_DIR = "ML/models"

MODEL_PATH = os.path.join(
    MODEL_DIR,
    "isolation_forest.pkl"
)

METADATA_PATH = os.path.join(
    MODEL_DIR,
    "isolation_forest_metadata.json"
)

RESULTS_PATH = os.path.join(
    MODEL_DIR,
    "isolation_forest_results.csv"
)

RANDOM_STATE = 42

# We choose the threshold using legitimate validation traffic.
# This means approximately 1% of legitimate users are allowed
# to be flagged by the anomaly detector.
TARGET_HUMAN_FPR = 0.01


# ============================================================
# CREATE MODEL DIRECTORY
# ============================================================

os.makedirs(MODEL_DIR, exist_ok=True)


# ============================================================
# LOAD DATA
# ============================================================

print("=" * 70)
print("FAIR DROP - ISOLATION FOREST ANOMALY DETECTOR")
print("=" * 70)

print("\nLoading dataset...")

df = pd.read_csv(DATA_PATH)

print(f"Dataset shape: {df.shape}")


# ============================================================
# BASIC VALIDATION
# ============================================================

required_columns = ["is_bot"]

for column in required_columns:

    if column not in df.columns:

        raise ValueError(
            f"Required column '{column}' was not found "
            f"in the dataset."
        )


print("\nClass distribution:")

print(
    df["is_bot"]
    .value_counts()
    .rename(index={0: "human", 1: "bot"})
)


# ============================================================
# IDENTIFY LEAKAGE / ID COLUMNS
# ============================================================

DROP_COLUMNS = [
    "session_id",
    "user_id",
    "traffic_type",
    "is_bot",
    "bot_cluster_id",
]


# Only keep columns that actually exist
DROP_COLUMNS = [
    column
    for column in DROP_COLUMNS
    if column in df.columns
]


# ============================================================
# SELECT NUMERIC FEATURES
# ============================================================

feature_df = df.drop(
    columns=DROP_COLUMNS,
    errors="ignore"
)

# Keep only numeric columns
feature_df = feature_df.select_dtypes(
    include=[np.number]
)

feature_columns = feature_df.columns.tolist()


if len(feature_columns) == 0:

    raise ValueError(
        "No numeric behavioral features were found."
    )


print("\nFeatures used by Isolation Forest:")

for i, feature in enumerate(feature_columns, start=1):

    print(f"{i:2d}. {feature}")


print(
    f"\nTotal numeric features: "
    f"{len(feature_columns)}"
)


# ============================================================
# CLEAN NUMERICAL DATA
# ============================================================

X = feature_df.copy()

y = df["is_bot"].astype(int).values


# Replace infinite values
X = X.replace(
    [np.inf, -np.inf],
    np.nan
)


# Fill missing values using training-independent
# robust median values.
#
# Because Isolation Forest is not sensitive to feature
# scaling in the same way as distance-based models,
# scaling is not required here.

X = X.fillna(
    X.median(numeric_only=True)
)


# Safety check
if X.isna().sum().sum() > 0:

    X = X.fillna(0)


X = X.astype(np.float32)


# ============================================================
# GROUP-AWARE SPLIT
# ============================================================
#
# We try to reproduce the same philosophy as the GRU:
# related sessions should ideally not be split across
# train/validation/test.
#
# bot_cluster_id is used when available.
# Otherwise user_id is used.
#
# If neither exists, stratified random splitting is used.
# ============================================================

if "bot_cluster_id" in df.columns:

    groups = df["bot_cluster_id"].astype(str)

    # Replace missing cluster IDs with user IDs if possible
    if "user_id" in df.columns:

        missing_mask = (
            df["bot_cluster_id"]
            .isna()
        )

        groups = groups.where(
            ~missing_mask,
            df["user_id"].astype(str)
        )

elif "user_id" in df.columns:

    groups = df["user_id"].astype(str)

else:

    groups = None


# ============================================================
# SPLIT DATA
# ============================================================

indices = np.arange(len(df))


if groups is not None:

    # --------------------------------------------------------
    # Group-aware splitting
    # --------------------------------------------------------

    unique_groups = groups.unique()

    rng = np.random.default_rng(
        RANDOM_STATE
    )

    rng.shuffle(unique_groups)

    n_groups = len(unique_groups)

    train_end = int(
        0.64 * n_groups
    )

    val_end = int(
        0.82 * n_groups
    )

    train_groups = set(
        unique_groups[:train_end]
    )

    val_groups = set(
        unique_groups[
            train_end:val_end
        ]
    )

    test_groups = set(
        unique_groups[val_end:]
    )

    train_idx = np.array([
        i
        for i, g in enumerate(groups)
        if g in train_groups
    ])

    val_idx = np.array([
        i
        for i, g in enumerate(groups)
        if g in val_groups
    ])

    test_idx = np.array([
        i
        for i, g in enumerate(groups)
        if g in test_groups
    ])

else:

    # --------------------------------------------------------
    # Fallback stratified split
    # --------------------------------------------------------

    train_idx, temp_idx = train_test_split(
        indices,
        test_size=0.36,
        stratify=y,
        random_state=RANDOM_STATE
    )

    val_idx, test_idx = train_test_split(
        temp_idx,
        test_size=0.50,
        stratify=y[temp_idx],
        random_state=RANDOM_STATE
    )


# ============================================================
# PRINT SPLIT INFORMATION
# ============================================================

print("\nDataset split:")

print(
    f"Train:      {len(train_idx)}"
)

print(
    f"Validation: {len(val_idx)}"
)

print(
    f"Test:       {len(test_idx)}"
)


def print_distribution(name, indices):

    values = y[indices]

    humans = np.sum(values == 0)
    bots = np.sum(values == 1)

    print(
        f"{name:<12} "
        f"human={humans:<6} "
        f"bot={bots:<6}"
    )


print("\nClass distribution:")

print_distribution(
    "Train",
    train_idx
)

print_distribution(
    "Validation",
    val_idx
)

print_distribution(
    "Test",
    test_idx
)


# ============================================================
# TRAIN ONLY ON HUMAN TRAFFIC
# ============================================================

train_human_idx = train_idx[
    y[train_idx] == 0
]

X_train_human = X.iloc[
    train_human_idx
].copy()


print(
    "\nHuman sessions used for "
    "Isolation Forest training:",
    len(X_train_human)
)


if len(X_train_human) < 20:

    raise ValueError(
        "Too few human training samples. "
        "Generate more human traffic."
    )


# ============================================================
# TRAIN ISOLATION FOREST
# ============================================================

print("\nTraining Isolation Forest...")

model = IsolationForest(

    # Number of trees
    n_estimators=300,

    # Let the model determine the contamination internally.
    # Threshold will be selected separately using validation
    # human traffic.
    contamination="auto",

    # Bootstrap disabled by default
    bootstrap=False,

    # Reproducibility
    random_state=RANDOM_STATE,

    # Use all CPU cores
    n_jobs=-1,

    # Maximum samples per tree
    max_samples="auto"
)


model.fit(X_train_human)


print("Isolation Forest training completed.")


# ============================================================
# ANOMALY SCORES
# ============================================================
#
# sklearn:
#
# decision_function:
#     higher = more normal
#     lower  = more anomalous
#
# We reverse it so:
#
#     higher anomaly_score = more suspicious
#
# This makes interpretation easier.
# ============================================================

def get_anomaly_scores(X_data):

    normality = model.decision_function(
        X_data
    )

    return -normality


train_scores = get_anomaly_scores(
    X.iloc[train_idx]
)

val_scores = get_anomaly_scores(
    X.iloc[val_idx]
)

test_scores = get_anomaly_scores(
    X.iloc[test_idx]
)


# ============================================================
# THRESHOLD SELECTION
# ============================================================
#
# Only legitimate HUMAN validation sessions are used.
#
# Example:
#
# TARGET_HUMAN_FPR = 0.01
#
# means approximately 1% of validation humans may be
# classified as anomalous.
# ============================================================

val_human_mask = (
    y[val_idx] == 0
)

val_human_scores = val_scores[
    val_human_mask
]


if len(val_human_scores) == 0:

    raise ValueError(
        "Validation set contains no human samples."
    )


threshold = np.quantile(
    val_human_scores,
    1.0 - TARGET_HUMAN_FPR
)


print("\n" + "=" * 70)
print("THRESHOLD CALIBRATION")
print("=" * 70)

print(
    f"Target human FPR: "
    f"{TARGET_HUMAN_FPR * 100:.2f}%"
)

print(
    f"Selected anomaly threshold: "
    f"{threshold:.6f}"
)


# ============================================================
# PREDICTION FUNCTION
# ============================================================

def predict_anomaly(scores):

    return (
        scores >= threshold
    ).astype(int)


val_pred = predict_anomaly(
    val_scores
)

test_pred = predict_anomaly(
    test_scores
)


# ============================================================
# EVALUATION FUNCTION
# ============================================================

def evaluate(
    name,
    scores,
    predictions,
    labels
):

    print("\n" + "=" * 70)
    print(name)
    print("=" * 70)

    roc_auc = roc_auc_score(
        labels,
        scores
    )

    pr_auc = average_precision_score(
        labels,
        scores
    )

    precision = precision_score(
        labels,
        predictions,
        zero_division=0
    )

    recall = recall_score(
        labels,
        predictions,
        zero_division=0
    )

    f1 = f1_score(
        labels,
        predictions,
        zero_division=0
    )

    cm = confusion_matrix(
        labels,
        predictions
    )

    print(
        f"ROC-AUC : {roc_auc:.4f}"
    )

    print(
        f"PR-AUC  : {pr_auc:.4f}"
    )

    print(
        f"Precision: {precision:.4f}"
    )

    print(
        f"Recall   : {recall:.4f}"
    )

    print(
        f"F1       : {f1:.4f}"
    )

    print("\nConfusion Matrix:")

    print(cm)

    if len(cm) == 2:

        tn, fp, fn, tp = cm.ravel()

        fpr = fp / (
            fp + tn
        ) if (fp + tn) > 0 else 0

        print(
            f"\nHuman False Positive Rate: "
            f"{fpr:.4%}"
        )

        print(
            f"Bot Detection Rate: "
            f"{tp / (tp + fn):.4%}"
        )

    return {
        "roc_auc": float(roc_auc),
        "pr_auc": float(pr_auc),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "confusion_matrix": cm.tolist()
    }


# ============================================================
# VALIDATION EVALUATION
# ============================================================

val_metrics = evaluate(
    "VALIDATION RESULTS",
    val_scores,
    val_pred,
    y[val_idx]
)


# ============================================================
# TEST EVALUATION
# ============================================================

test_metrics = evaluate(
    "TEST RESULTS",
    test_scores,
    test_pred,
    y[test_idx]
)


# ============================================================
# PER-TRAFFIC-TYPE EVALUATION
# ============================================================

print("\n" + "=" * 70)
print("PER-TRAFFIC-TYPE ANOMALY DETECTION")
print("=" * 70)


test_result_df = df.iloc[
    test_idx
].copy()

test_result_df[
    "anomaly_score"
] = test_scores

test_result_df[
    "anomaly_prediction"
] = test_pred


traffic_results = []


if "traffic_type" in test_result_df.columns:

    traffic_types = (
        test_result_df[
            "traffic_type"
        ]
        .dropna()
        .unique()
    )

    for traffic_type in sorted(
        traffic_types
    ):

        subset = test_result_df[
            test_result_df[
                "traffic_type"
            ] == traffic_type
        ]

        labels = subset[
            "is_bot"
        ].values

        scores = subset[
            "anomaly_score"
        ].values

        predictions = subset[
            "anomaly_prediction"
        ].values

        n_samples = len(subset)

        n_bots = int(
            np.sum(labels == 1)
        )

        n_humans = int(
            np.sum(labels == 0)
        )

        if len(np.unique(labels)) == 2:

            roc_auc = roc_auc_score(
                labels,
                scores
            )

        else:

            roc_auc = np.nan

        precision = precision_score(
            labels,
            predictions,
            zero_division=0
        )

        recall = recall_score(
            labels,
            predictions,
            zero_division=0
        )

        f1 = f1_score(
            labels,
            predictions,
            zero_division=0
        )

        traffic_results.append({

            "traffic_type": traffic_type,

            "samples": n_samples,

            "bots": n_bots,

            "humans": n_humans,

            "roc_auc": roc_auc,

            "precision": precision,

            "recall": recall,

            "f1": f1

        })

        print(
            f"\n{traffic_type}"
        )

        print(
            f"  Samples:  {n_samples}"
        )

        print(
            f"  Bots:     {n_bots}"
        )

        print(
            f"  Humans:   {n_humans}"
        )

        if not np.isnan(roc_auc):

            print(
                f"  ROC-AUC:  {roc_auc:.4f}"
            )

        print(
            f"  Precision:{precision:.4f}"
        )

        print(
            f"  Recall:   {recall:.4f}"
        )

        print(
            f"  F1:       {f1:.4f}"
        )


# ============================================================
# SAVE PER-SESSION RESULTS
# ============================================================

test_result_df.to_csv(
    RESULTS_PATH,
    index=False
)


print(
    f"\nSaved session-level results to:"
)

print(
    RESULTS_PATH
)


# ============================================================
# SAVE MODEL
# ============================================================

with open(
    MODEL_PATH,
    "wb"
) as f:

    pickle.dump(
        model,
        f
    )


print(
    f"Saved Isolation Forest model to:"
)

print(
    MODEL_PATH
)


# ============================================================
# SAVE METADATA
# ============================================================

metadata = {

    "model": "IsolationForest",

    "purpose": (
        "Novel behavioral anomaly detection "
        "against legitimate human traffic"
    ),

    "data_path": DATA_PATH,

    "feature_columns": feature_columns,

    "num_features": len(
        feature_columns
    ),

    "random_state": RANDOM_STATE,

    "n_estimators": 300,

    "contamination": "auto",

    "training_strategy": (
        "Model trained exclusively on "
        "legitimate human training sessions"
    ),

    "target_human_fpr": (
        TARGET_HUMAN_FPR
    ),

    "threshold": float(
        threshold
    ),

    "validation_metrics": val_metrics,

    "test_metrics": test_metrics,

    "score_definition": (
        "Higher anomaly_score means "
        "more anomalous"
    ),

    "threshold_definition": (
        "Validation human percentile "
        "corresponding to target human FPR"
    )
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
    f"Saved metadata to:"
)

print(
    METADATA_PATH
)


# ============================================================
# FINAL SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("ISOLATION FOREST COMPLETE")
print("=" * 70)

print(
    f"\nFeatures: {len(feature_columns)}"
)

print(
    f"Human training sessions: "
    f"{len(X_train_human)}"
)

print(
    f"Threshold: {threshold:.6f}"
)

print(
    f"\nTest ROC-AUC: "
    f"{test_metrics['roc_auc']:.4f}"
)

print(
    f"Test PR-AUC: "
    f"{test_metrics['pr_auc']:.4f}"
)

print(
    f"Test Precision: "
    f"{test_metrics['precision']:.4f}"
)

print(
    f"Test Recall: "
    f"{test_metrics['recall']:.4f}"
)

print(
    f"Test F1: "
    f"{test_metrics['f1']:.4f}"
)

print("\nOutput files:")

print(
    f"  {MODEL_PATH}"
)

print(
    f"  {METADATA_PATH}"
)

print(
    f"  {RESULTS_PATH}"
)

print("\nDone.")