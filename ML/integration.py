"""
FAIR DROP
Production ML Integration API
=============================

Node.js / Express
        |
        | POST /predict-risk
        v
FastAPI
        |
        +--> XGBoost
        |
        +--> GRU
        |
        +--> Isolation Forest
        |
        +--> Rule Signals
        |
        v
risk_fusion_engine.py
        |
        v
Risk + Policy
        |
        v
Node.js Queue / Allocation

Run:

    uvicorn integration:app --host 0.0.0.0 --port 8000

Expected location:

    TicketCollecter/
    └── ML/
        ├── integration.py
        ├── model.py
        ├── gru_model.py
        ├── isolationforest.py
        ├── risk_fusion_engine.py
        └── models/
"""

from __future__ import annotations

import inspect
import json
import logging
import os
import pickle
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"

MODEL_VERSION = os.getenv(
    "MODEL_VERSION",
    "fairdrop-v1"
)

SERVICE_NAME = "fair-drop-ml"

# Optional internal service authentication.
ML_SERVICE_KEY = os.getenv(
    "ML_SERVICE_KEY",
    ""
)

# Maximum number of historical risk observations kept per session.
MAX_HISTORY = int(
    os.getenv(
        "MAX_RISK_HISTORY",
        "10"
    )
)

# GRU expected sequence size.
GRU_SEQUENCE_LENGTH = 100

# Isolation Forest threshold from your trained model.
ISOLATION_THRESHOLD = float(
    os.getenv(
        "ISOLATION_THRESHOLD",
        "0.149955"
    )
)

# XGBoost artifacts created by model.py.
XGB_MODEL_PATH = (
    MODEL_DIR /
    "xgboost_bot_detector_calibrated.joblib"
)

XGB_METADATA_PATH = (
    MODEL_DIR /
    "model_metadata.json"
)

# GRU artifacts.
GRU_MODEL_PATH = (
    MODEL_DIR /
    "gru_bot_detector.keras"
)

GRU_METADATA_PATH = (
    MODEL_DIR /
    "gru_metadata.json"
)

# Isolation Forest artifact.
ISOLATION_MODEL_PATH = (
    MODEL_DIR /
    "isolation_forest.pkl"
)

ISOLATION_METADATA_PATH = (
    MODEL_DIR /
    "isolation_forest_metadata.json"
)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    )
)

logger = logging.getLogger(
    "fair-drop-ml"
)


# ============================================================
# PYDANTIC REQUEST MODELS
# ============================================================

class Event(BaseModel):
    """
    One chronological browser/backend event.

    The GRU's existing preprocessing handles the actual
    conversion into its 25-dimensional representation.
    """

    model_config = ConfigDict(
        extra="allow"
    )

    timestamp: Optional[float] = None
    event_type: str

    # Optional GRU / behavioral fields.
    inter_event_time_ms: Optional[float] = None
    retry_count: Optional[float] = None
    request_number: Optional[float] = None
    active_sessions: Optional[float] = None
    queue_position: Optional[float] = None
    session_age_sec: Optional[float] = None
    time_since_last_request_ms: Optional[float] = None
    time_since_last_failure_ms: Optional[float] = None
    mouse_events: Optional[float] = None
    keyboard_events: Optional[float] = None
    scroll_events: Optional[float] = None


class RiskRequest(BaseModel):
    """
    Request sent by the Node.js backend.
    """

    model_config = ConfigDict(
        extra="allow"
    )

    session_id: str = Field(
        min_length=1,
        max_length=200
    )

    user_id: str = Field(
        min_length=1,
        max_length=200
    )

    drop_id: str = Field(
        min_length=1,
        max_length=200
    )

    # Aggregated/session-level behavioral features
    behavior_features: Dict[str, Any] = Field(
        default_factory=dict
    )

    # Chronological event sequence for GRU
    events: List[Event] = Field(
        default_factory=list,
        max_length=1000
    )

    # Explicit rule signals
    rule_signals: Dict[str, Any] = Field(
        default_factory=dict
    )

    # Optional previous history supplied by Node.
    risk_history: List[float] = Field(
        default_factory=list,
        max_length=20
    )


# ============================================================
# GLOBAL MODEL STATE
# ============================================================

class ModelState:
    """
    All models are loaded once.

    No model loading occurs inside /predict-risk.
    """

    xgb_model: Any = None
    xgb_metadata: Dict[str, Any] = {}

    gru_model: Any = None
    gru_metadata: Dict[str, Any] = {}

    isolation_model: Any = None
    isolation_metadata: Dict[str, Any] = {}

    fusion_engine: Any = None
    fusion_module: Any = None

    loaded: bool = False


STATE = ModelState()


# ============================================================
# TEMPORAL RISK HISTORY
# ============================================================

risk_history_store: Dict[
    str,
    deque
] = defaultdict(
    lambda: deque(
        maxlen=MAX_HISTORY
    )
)

history_lock = threading.Lock()


def get_risk_history(
    session_id: str
) -> List[float]:

    with history_lock:
        return list(
            risk_history_store[
                session_id
            ]
        )


def append_risk_history(
    session_id: str,
    risk: float
) -> None:

    with history_lock:
        risk_history_store[
            session_id
        ].append(
            float(risk)
        )


# ============================================================
# UTILITY
# ============================================================

def clamp(
    value: Any,
    minimum: float = 0.0,
    maximum: float = 1.0
) -> float:

    try:
        value = float(value)
    except (
        TypeError,
        ValueError
    ):
        return minimum

    if not np.isfinite(value):
        return minimum

    return float(
        np.clip(
            value,
            minimum,
            maximum
        )
    )


def json_safe(
    value: Any
) -> Any:
    """
    Convert numpy / TensorFlow / Python objects into
    JSON serializable values.
    """

    if isinstance(
        value,
        dict
    ):
        return {
            str(k): json_safe(v)
            for k, v in value.items()
        }

    if isinstance(
        value,
        (list, tuple)
    ):
        return [
            json_safe(v)
            for v in value
        ]

    if isinstance(
        value,
        np.ndarray
    ):
        return value.tolist()

    if isinstance(
        value,
        np.generic
    ):
        return value.item()

    if isinstance(
        value,
        (float, int, str, bool)
    ):
        return value

    if value is None:
        return None

    return str(value)


# ============================================================
# LOAD JSON
# ============================================================

def load_json(
    path: Path
) -> Dict[str, Any]:

    if not path.exists():
        logger.warning(
            "Metadata file not found: %s",
            path
        )
        return {}

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


# ============================================================
# LOAD XGBOOST
# ============================================================

def load_xgboost() -> None:

    logger.info(
        "Loading XGBoost..."
    )

    if not XGB_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"XGBoost model not found: "
            f"{XGB_MODEL_PATH}"
        )

    STATE.xgb_model = joblib.load(
        XGB_MODEL_PATH
    )

    STATE.xgb_metadata = load_json(
        XGB_METADATA_PATH
    )

    logger.info(
        "XGBoost loaded"
    )


def predict_xgboost(
    behavior_features: Dict[str, Any]
) -> float:

    if STATE.xgb_model is None:
        raise RuntimeError(
            "XGBoost model is not loaded"
        )

    feature_columns = (
        STATE.xgb_metadata.get(
            "features"
        )
    )

    if not feature_columns:

        raise RuntimeError(
            "XGBoost metadata does not "
            "contain 'features'."
        )

    row = pd.DataFrame(
        [behavior_features]
    )

    # Match training feature order.
    for column in feature_columns:

        if column not in row.columns:
            row[column] = np.nan

    X = row[
        feature_columns
    ].copy()

    for column in X.columns:

        X[column] = pd.to_numeric(
            X[column],
            errors="coerce"
        )

    X = X.replace(
        [np.inf, -np.inf],
        np.nan
    )

    # Same inference behavior as model.py.
    X = X.fillna(0.0)

    probability = (
        STATE.xgb_model
        .predict_proba(X)[0, 1]
    )

    return clamp(
        probability
    )


# ============================================================
# LOAD GRU
# ============================================================

def load_gru() -> None:

    logger.info(
        "Loading GRU..."
    )

    if not GRU_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"GRU model not found: "
            f"{GRU_MODEL_PATH}"
        )

    """
    Import the existing GRU implementation.

    This is intentional.

    We do NOT recreate the GRU preprocessing here because
    gru_model.py already contains the exact preprocessing
    used during training.
    """

    import gru_model

    model, metadata = (
        gru_model.load_saved_model()
    )

    STATE.gru_model = model
    STATE.gru_metadata = metadata

    logger.info(
        "GRU loaded"
    )


def predict_gru(
    events: List[Dict[str, Any]]
) -> float:

    if STATE.gru_model is None:
        raise RuntimeError(
            "GRU model is not loaded"
        )

    import gru_model

    if not events:
        return 0.0

    # Preserve chronological order.
    events = list(events)

    try:

        result = (
            gru_model.predict_single_session(
                STATE.gru_model,
                events,
                threshold=float(
                    STATE.gru_metadata.get(
                        "threshold",
                        0.56
                    )
                )
            )
        )

        probability = result.get(
            "bot_probability",
            0.0
        )

        return clamp(
            probability
        )

    except Exception as exc:

        logger.exception(
            "GRU inference failed"
        )

        raise RuntimeError(
            f"GRU inference failed: {exc}"
        ) from exc


# ============================================================
# LOAD ISOLATION FOREST
# ============================================================

def load_isolation_forest() -> None:

    logger.info(
        "Loading Isolation Forest..."
    )

    if not ISOLATION_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Isolation Forest not found: "
            f"{ISOLATION_MODEL_PATH}"
        )

    STATE.isolation_model = (
        joblib.load(
            ISOLATION_MODEL_PATH
        )
    )

    STATE.isolation_metadata = (
        load_json(
            ISOLATION_METADATA_PATH
        )
    )

    logger.info(
        "Isolation Forest loaded"
    )


def get_isolation_features(
    behavior_features: Dict[str, Any]
) -> pd.DataFrame:

    """
    Use the exact feature list saved by the Isolation Forest
    training pipeline whenever available.
    """

    metadata = (
        STATE.isolation_metadata
    )

    feature_columns = (
        metadata.get("features")
        or metadata.get("feature_columns")
    )

    if not feature_columns:

        # Fallback to all numeric behavioral values.
        numeric = {}

        for key, value in (
            behavior_features.items()
        ):

            try:
                numeric[key] = float(value)
            except (
                TypeError,
                ValueError
            ):
                continue

        if not numeric:
            raise RuntimeError(
                "No numeric behavioral "
                "features supplied."
            )

        return pd.DataFrame(
            [numeric]
        )

    row = {}

    for column in feature_columns:

        value = behavior_features.get(
            column,
            0.0
        )

        try:
            row[column] = float(
                value
            )
        except (
            TypeError,
            ValueError
        ):
            row[column] = 0.0

    return pd.DataFrame(
        [row],
        columns=feature_columns
    )


def raw_isolation_score(
    X: pd.DataFrame
) -> float:

    """
    Convert Isolation Forest's anomaly output into the
    normalized 0–1 signal expected by risk fusion.

    The trained system uses 0.149955 as its selected
    anomaly threshold.

    If the training metadata contains the exact score
    calibration values, those are preferred.
    """

    model = (
        STATE.isolation_model
    )

    metadata = (
        STATE.isolation_metadata
    )

    # Prefer a saved prediction/scoring method if the
    # trained model exposes one.
    if hasattr(
        model,
        "decision_function"
    ):

        decision = float(
            model.decision_function(
                X
            )[0]
        )

        # IsolationForest decision_function:
        # larger = more normal
        # smaller = more anomalous.
        #
        # Convert to an anomaly-like signal.
        #
        # This is deliberately bounded because the fusion
        # engine expects [0,1].

        anomaly = (
            0.5 - decision
        )

        anomaly = (
            anomaly / 0.5
        )

        anomaly = clamp(
            anomaly
        )

    else:

        prediction = int(
            model.predict(X)[0]
        )

        anomaly = (
            1.0
            if prediction == -1
            else 0.0
        )

    # If the metadata provides a calibration range,
    # use it.
    score_min = metadata.get(
        "score_min"
    )

    score_max = metadata.get(
        "score_max"
    )

    if (
        score_min is not None
        and score_max is not None
        and score_max > score_min
        and hasattr(
            model,
            "decision_function"
        )
    ):

        decision = float(
            model.decision_function(
                X
            )[0]
        )

        # Reverse the normality direction.
        anomaly = (
            float(score_max)
            - decision
        ) / (
            float(score_max)
            - float(score_min)
        )

        anomaly = clamp(
            anomaly
        )

    return clamp(
        anomaly
    )


def predict_isolation_forest(
    behavior_features: Dict[str, Any]
) -> float:

    if STATE.isolation_model is None:
        raise RuntimeError(
            "Isolation Forest is not loaded"
        )

    X = get_isolation_features(
        behavior_features
    )

    return raw_isolation_score(
        X
    )


# ============================================================
# RULE ENGINE
# ============================================================

def calculate_rule_score(
    rule_signals: Dict[str, Any]
) -> float:

    """
    Convert Node-provided rule signals into the normalized
    rule_violation_score expected by the fusion engine.

    Node can send:

        {
            "rapid_retry": 0.0,
            "excessive_refresh": 0.2,
            "parallel_sessions": 0.0
        }

    If a direct `rule_violation_score` is supplied,
    it is used directly.
    """

    if not rule_signals:
        return 0.0

    if (
        "rule_violation_score"
        in rule_signals
    ):

        return clamp(
            rule_signals[
                "rule_violation_score"
            ]
        )

    values = []

    for value in (
        rule_signals.values()
    ):

        try:

            values.append(
                clamp(value)
            )

        except Exception:
            continue

    if not values:
        return 0.0

    # The rule signals represent independent evidence.
    #
    # We use the strongest active rule rather than summing
    # them beyond 1.0.

    return clamp(
        max(values)
    )


# ============================================================
# LOAD RISK FUSION ENGINE
# ============================================================

def load_risk_fusion_engine() -> None:

    logger.info(
        "Loading risk fusion engine..."
    )

    import risk_fusion_engine

    STATE.fusion_module = (
        risk_fusion_engine
    )

    # Try the most likely class names without forcing
    # a rewrite of the already-tested engine.
    candidates = [
        "RiskFusionEngine",
        "RiskEngine",
        "AdaptiveRiskEngine",
        "RiskFusion",
    ]

    for class_name in candidates:

        cls = getattr(
            risk_fusion_engine,
            class_name,
            None
        )

        if cls is None:
            continue

        try:

            STATE.fusion_engine = cls()

            logger.info(
                "Using fusion class: %s",
                class_name
            )

            return

        except TypeError:

            # Some existing engines may not require
            # constructor arguments but can still fail
            # for other reasons.
            continue

    logger.info(
        "Using module-level risk fusion functions"
    )


# ============================================================
# CALL EXISTING FUSION ENGINE
# ============================================================

def call_compatible_function(
    fn: Any,
    payload: Dict[str, Any]
) -> Any:

    """
    Call an existing fusion function while adapting to its
    actual parameter names.

    This lets integration.py reuse the completed
    risk_fusion_engine.py without duplicating its logic.
    """

    signature = inspect.signature(
        fn
    )

    parameters = signature.parameters

    kwargs = {}

    aliases = {
        "session_id": [
            "session_id",
            "sid"
        ],

        "xgb_probability": [
            "xgb_probability",
            "xgboost_probability",
            "xgb_prob",
            "xgb"
        ],

        "gru_probability": [
            "gru_probability",
            "gru_prob",
            "gru"
        ],

        "anomaly_score": [
            "anomaly_score",
            "isolation_score",
            "anomaly"
        ],

        "rule_violation_score": [
            "rule_violation_score",
            "rule_score",
            "rules"
        ],

        "risk_history": [
            "risk_history",
            "history",
            "previous_risks"
        ]
    }

    for canonical, names in aliases.items():

        if canonical not in payload:
            continue

        for name in names:

            if name in parameters:

                kwargs[name] = (
                    payload[canonical]
                )

                break

    # Some engines accept a single dictionary.
    if not kwargs:

        try:
            return fn(payload)
        except TypeError:
            pass

    return fn(
        **kwargs
    )


def run_fusion(
    session_id: str,
    xgb_probability: float,
    gru_probability: float,
    anomaly_score: float,
    rule_violation_score: float,
    risk_history: List[float]
) -> Dict[str, Any]:

    payload = {
        "session_id": session_id,

        "xgb_probability":
            xgb_probability,

        "gru_probability":
            gru_probability,

        "anomaly_score":
            anomaly_score,

        "rule_violation_score":
            rule_violation_score,

        "risk_history":
            risk_history
    }

    # --------------------------------------------------------
    # Existing engine class
    # --------------------------------------------------------

    if STATE.fusion_engine is not None:

        engine = (
            STATE.fusion_engine
        )

        methods = [
            "evaluate",
            "process",
            "predict",
            "calculate_risk",
            "fuse",
            "run"
        ]

        for method_name in methods:

            method = getattr(
                engine,
                method_name,
                None
            )

            if method is None:
                continue

            try:

                result = (
                    call_compatible_function(
                        method,
                        payload
                    )
                )

                if isinstance(
                    result,
                    dict
                ):

                    return json_safe(
                        result
                    )

            except TypeError:
                continue

    # --------------------------------------------------------
    # Existing module-level functions
    # --------------------------------------------------------

    module = (
        STATE.fusion_module
    )

    if module is not None:

        functions = [
            "evaluate_risk",
            "fuse_risk",
            "calculate_risk",
            "process_risk",
            "risk_fusion",
            "predict_risk"
        ]

        for function_name in functions:

            fn = getattr(
                module,
                function_name,
                None
            )

            if fn is None:
                continue

            try:

                result = (
                    call_compatible_function(
                        fn,
                        payload
                    )
                )

                if isinstance(
                    result,
                    dict
                ):

                    return json_safe(
                        result
                    )

            except TypeError:
                continue

    raise RuntimeError(
        "Could not find a compatible "
        "risk fusion function in "
        "risk_fusion_engine.py. "
        "Expected a RiskFusionEngine "
        "class or one of: "
        "evaluate_risk, fuse_risk, "
        "calculate_risk, process_risk, "
        "risk_fusion, predict_risk."
    )


# ============================================================
# NORMALIZE FUSION RESPONSE
# ============================================================

def normalize_fusion_response(
    result: Dict[str, Any],
    session_id: str
) -> Dict[str, Any]:

    """
    Preserve the existing fusion engine output while making
    the API response stable for Node.js.
    """

    risk = (
        result.get(
            "risk_score"
        )
        if "risk_score" in result
        else result.get(
            "bot_risk_score",
            result.get(
                "risk",
                0.0
            )
        )
    )

    # Some engines may return 0-1.
    try:
        risk = float(risk)
    except (
        TypeError,
        ValueError
    ):
        risk = 0.0

    if 0.0 <= risk <= 1.0:
        risk *= 100.0

    risk = float(
        np.clip(
            risk,
            0.0,
            100.0
        )
    )

    risk_level = (
        result.get(
            "risk_level"
        )
    )

    if risk_level is None:

        if risk < 30:
            risk_level = "LOW"

        elif risk < 60:
            risk_level = "MEDIUM"

        elif risk < 80:
            risk_level = "HIGH"

        else:
            risk_level = "VERY_HIGH"

    policy = (
        result.get(
            "policy"
        )
    )

    if policy is None:
        policy = {}

    return {
        **json_safe(result),

        "session_id":
            session_id,

        "risk_score":
            round(risk, 4),

        "risk_level":
            risk_level,

        "model_version":
            MODEL_VERSION,

        "policy":
            policy
    }


# ============================================================
# STARTUP
# ============================================================

@asynccontextmanager
async def lifespan(
    app: FastAPI
):

    start = time.perf_counter()

    logger.info(
        "=" * 70
    )

    logger.info(
        "FAIR DROP ML SERVICE"
    )

    logger.info(
        "Loading models..."
    )

    # --------------------------------------------------------
    # Load all artifacts ONCE.
    # --------------------------------------------------------

    load_xgboost()
    load_gru()
    load_isolation_forest()
    load_risk_fusion_engine()

    STATE.loaded = True

    elapsed = (
        time.perf_counter()
        - start
    )

    logger.info(
        "All ML components loaded in %.2f seconds",
        elapsed
    )

    logger.info(
        "Model version: %s",
        MODEL_VERSION
    )

    logger.info(
        "=" * 70
    )

    yield

    logger.info(
        "Shutting down Fair Drop ML service"
    )


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="Fair Drop ML Service",
    description=(
        "Private ML risk service for TicketCollecter"
    ),
    version=MODEL_VERSION,
    lifespan=lifespan
)


# ============================================================
# AUTHENTICATION
# ============================================================

def verify_internal_request(
    supplied_key: Optional[str]
) -> None:

    # If no key is configured, allow local development.
    if not ML_SERVICE_KEY:
        return

    if supplied_key != ML_SERVICE_KEY:

        raise HTTPException(
            status_code=401,
            detail="Unauthorized ML service request"
        )


# ============================================================
# HEALTH
# ============================================================

@app.get(
    "/health"
)
async def health():

    return {
        "status": (
            "healthy"
            if STATE.loaded
            else "starting"
        ),

        "service":
            SERVICE_NAME,

        "model_version":
            MODEL_VERSION,

        "models": {
            "xgboost":
                STATE.xgb_model is not None,

            "gru":
                STATE.gru_model is not None,

            "isolation_forest":
                STATE.isolation_model is not None,

            "risk_fusion":
                STATE.fusion_module is not None
        }
    }


# ============================================================
# PREDICT RISK
# ============================================================

@app.post(
    "/predict-risk"
)
async def predict_risk(
    request: RiskRequest,
    x_ml_service_key: Optional[str] = Header(
        default=None
    )
):

    verify_internal_request(
        x_ml_service_key
    )

    if not STATE.loaded:

        raise HTTPException(
            status_code=503,
            detail="ML service is not ready"
        )

    start = time.perf_counter()

    try:

        # ----------------------------------------------------
        # Convert request data.
        # ----------------------------------------------------

        behavior_features = dict(
            request.behavior_features
        )

        events = [
            event.model_dump(
                exclude_none=True
            )
            for event in request.events
        ]

        rule_signals = dict(
            request.rule_signals
        )

        # ----------------------------------------------------
        # Risk history
        # ----------------------------------------------------

        stored_history = (
            get_risk_history(
                request.session_id
            )
        )

        supplied_history = [
            clamp(
                value,
                0.0,
                100.0
            )
            for value
            in request.risk_history
        ]

        risk_history = (
            supplied_history
            if supplied_history
            else stored_history
        )

        # ----------------------------------------------------
        # XGBoost
        # ----------------------------------------------------

        xgb_probability = (
            predict_xgboost(
                behavior_features
            )
        )

        # ----------------------------------------------------
        # GRU
        # ----------------------------------------------------

        gru_probability = (
            predict_gru(
                events
            )
        )

        # ----------------------------------------------------
        # Isolation Forest
        # ----------------------------------------------------

        anomaly_score = (
            predict_isolation_forest(
                behavior_features
            )
        )

        # ----------------------------------------------------
        # Rules
        # ----------------------------------------------------

        rule_score = (
            calculate_rule_score(
                rule_signals
            )
        )

        # ----------------------------------------------------
        # Risk Fusion
        # ----------------------------------------------------

        fusion_result = run_fusion(
            session_id=request.session_id,

            xgb_probability=
                xgb_probability,

            gru_probability=
                gru_probability,

            anomaly_score=
                anomaly_score,

            rule_violation_score=
                rule_score,

            risk_history=
                risk_history
        )

        response = (
            normalize_fusion_response(
                fusion_result,
                request.session_id
            )
        )

        # ----------------------------------------------------
        # Guarantee component signals are present.
        # ----------------------------------------------------

        response[
            "signals"
        ] = {
            "xgboost_probability":
                round(
                    xgb_probability,
                    6
                ),

            "gru_probability":
                round(
                    gru_probability,
                    6
                ),

            "anomaly_score":
                round(
                    anomaly_score,
                    6
                ),

            "rule_violation_score":
                round(
                    rule_score,
                    6
                )
        }

        # ----------------------------------------------------
        # Save current risk for temporal persistence.
        # ----------------------------------------------------

        risk_score = float(
            response[
                "risk_score"
            ]
        )

        append_risk_history(
            request.session_id,
            risk_score
        )

        response[
            "risk_history"
        ] = get_risk_history(
            request.session_id
        )

        # ----------------------------------------------------
        # Metadata
        # ----------------------------------------------------

        response[
            "model_version"
        ] = MODEL_VERSION

        response[
            "service"
        ] = SERVICE_NAME

        response[
            "latency_ms"
        ] = round(
            (
                time.perf_counter()
                - start
            ) * 1000,
            3
        )

        return json_safe(
            response
        )

    except HTTPException:
        raise

    except Exception as exc:

        logger.exception(
            "Risk inference failed for session %s",
            request.session_id
        )

        raise HTTPException(
            status_code=500,
            detail={
                "error":
                    "ML_INFERENCE_FAILED",

                "message":
                    str(exc),

                "session_id":
                    request.session_id
            }
        )


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "integration:app",
        host="0.0.0.0",
        port=int(
            os.getenv(
                "PORT",
                "8000"
            )
        ),
        reload=False
    )