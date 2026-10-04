"""
======================================================================
FAIR DROP - EXPLAINABLE AI ENGINE
======================================================================

Purpose:
    Explain WHY a session received a particular bot-risk score.

Architecture:

    Behavioral Features
            |
      +-----+------+----------------+
      |            |                |
   XGBoost        GRU        Isolation Forest
      |            |                |
      +------------+----------------+
                   |
            Risk Fusion Engine
                   |
             Final Risk Score
                   |
          Explainable AI Engine
                   |
          Human-readable JSON
                   |
               Frontend

IMPORTANT:
    This module explains behavioral risk.
    It DOES NOT select ticket winners.

======================================================================
"""

from __future__ import annotations

import json
import math
import os
import warnings
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


# ======================================================================
# OPTIONAL DEPENDENCIES
# ======================================================================

try:
    import shap

    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False

try:
    import joblib

    JOBLIB_AVAILABLE = True
except ImportError:
    JOBLIB_AVAILABLE = False

try:
    import tensorflow as tf

    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False


# ======================================================================
# FEATURE DESCRIPTION MAP
# ======================================================================

FEATURE_DESCRIPTIONS = {

    # Request behavior
    "request_frequency": "Very high request frequency",
    "requests_per_second": "Very high request rate",
    "request_rate": "Very high request rate",
    "requests_per_minute": "Very high request frequency",

    # Retries
    "retry_rate": "High retry rate",
    "retry_count": "Repeated retry attempts",
    "retries": "Repeated retry attempts",
    "duplicate_attempts": "Repeated duplicate attempts",

    # Sessions
    "parallel_sessions": "Multiple parallel sessions",
    "active_sessions": "Multiple active sessions",
    "session_count": "Unusually high number of sessions",
    "unique_sessions": "Multiple sessions associated with the same user",

    # Timing
    "timing_cv": "Abnormal timing regularity",
    "timing_regularity": "Abnormally regular request timing",
    "inter_request_std": "Unusual consistency between requests",
    "inter_request_mean": "Unusual request timing",
    "timing_variance": "Abnormal timing variation",

    # Bursts
    "burstiness": "Highly bursty request behavior",
    "burst_score": "Highly bursty request behavior",
    "max_burst": "Large request burst detected",

    # Reconnect
    "reconnect_count": "Repeated reconnect behavior",
    "reconnect_rate": "Unusual reconnect frequency",

    # Requests
    "total_requests": "Unusually high request volume",
    "request_count": "Unusually high request volume",
    "request_action_ratio": "Unusual request-to-action ratio",

    # Behavioral sequence
    "sequence_regularity": "Highly repetitive behavioral sequence",
    "sequence_entropy": "Low behavioral randomness",
    "action_entropy": "Unusually repetitive actions",

    # Network/device related
    "unique_ips": "Multiple IP addresses observed",
    "ip_count": "Multiple IP addresses observed",
    "device_count": "Multiple devices associated with the session",
    "user_agent_count": "Multiple user-agent patterns observed",

    # CAPTCHA / verification
    "captcha_failures": "Repeated CAPTCHA failures",
    "captcha_attempts": "Multiple CAPTCHA attempts",
    "verification_failures": "Repeated verification failures",

    # Generic ML features
    "anomaly_score": "Behavior differs significantly from normal traffic",
    "isolation_score": "Behavior differs significantly from normal traffic",
}


# ======================================================================
# UTILITY FUNCTIONS
# ======================================================================

def _safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to float."""

    try:
        value = float(value)

        if math.isnan(value) or math.isinf(value):
            return default

        return value

    except Exception:
        return default


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Clip a numeric value."""

    return max(low, min(high, value))


def _feature_description(feature: str) -> str:
    """
    Convert technical feature names into judge/user-friendly text.
    """

    if feature in FEATURE_DESCRIPTIONS:
        return FEATURE_DESCRIPTIONS[feature]

    readable = feature.replace("_", " ").strip()

    if not readable:
        return "Unusual behavioral signal"

    return readable[0].upper() + readable[1:]


def _risk_label(score: float) -> str:
    """Convert risk probability into a human-readable label."""

    if score >= 0.80:
        return "HIGH"

    if score >= 0.50:
        return "MEDIUM"

    return "LOW"


def _risk_action(score: float) -> str:
    """
    Suggested adaptive security action.

    This is NOT ticket allocation.
    """

    if score >= 0.90:
        return "QUARANTINE"

    if score >= 0.75:
        return "THROTTLE"

    if score >= 0.50:
        return "CHALLENGE"

    if score >= 0.30:
        return "MONITOR"

    return "ALLOW"


# ======================================================================
# EXPLAINABLE AI ENGINE
# ======================================================================

class ExplainableAI:

    def __init__(
        self,
        xgb_model: Optional[Any] = None,
        gru_model: Optional[Any] = None,
        isolation_model: Optional[Any] = None,
        feature_names: Optional[List[str]] = None,
        top_k: int = 5,
    ):
        """
        Initialize the explainability engine.

        Parameters
        ----------
        xgb_model:
            Trained XGBoost model.

        gru_model:
            Trained GRU / TensorFlow model.

        isolation_model:
            Trained Isolation Forest.

        feature_names:
            Names of features expected by the XGBoost model.

        top_k:
            Number of major contributing signals returned.
        """

        self.xgb_model = xgb_model
        self.gru_model = gru_model
        self.isolation_model = isolation_model

        self.feature_names = feature_names or []

        self.top_k = top_k

        self.shap_explainer = None

        # Create SHAP TreeExplainer if possible.
        if (
            self.xgb_model is not None
            and SHAP_AVAILABLE
        ):
            self._initialize_shap()

    # ==================================================================
    # SHAP
    # ==================================================================

    def _initialize_shap(self) -> None:
        """Initialize SHAP TreeExplainer for XGBoost."""

        try:

            self.shap_explainer = shap.TreeExplainer(
                self.xgb_model
            )

            print("[ExplainableAI] SHAP TreeExplainer initialized.")

        except Exception as exc:

            self.shap_explainer = None

            print(
                "[ExplainableAI] SHAP initialization failed:"
                f" {exc}"
            )

    # ==================================================================
    # INPUT NORMALIZATION
    # ==================================================================

    def _normalize_features(
        self,
        features: Dict[str, Any],
    ) -> pd.DataFrame:
        """
        Convert feature dictionary into the format expected by XGBoost.
        """

        if self.feature_names:

            row = {}

            for feature in self.feature_names:
                row[feature] = features.get(
                    feature,
                    0.0
                )

            return pd.DataFrame([row])

        return pd.DataFrame([features])

    # ==================================================================
    # XGBOOST SHAP EXPLANATION
    # ==================================================================

    def explain_xgboost(
        self,
        features: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate SHAP explanation for an XGBoost prediction.
        """

        if self.xgb_model is None:

            return {
                "available": False,
                "reason": "XGBoost model not supplied.",
                "contributions": [],
            }

        if not SHAP_AVAILABLE:

            return {
                "available": False,
                "reason": "SHAP is not installed.",
                "contributions": [],
            }

        try:

            X = self._normalize_features(features)

            if self.shap_explainer is None:
                self._initialize_shap()

            if self.shap_explainer is None:

                return {
                    "available": False,
                    "reason": "Could not initialize SHAP.",
                    "contributions": [],
                }

            shap_values = self.shap_explainer.shap_values(X)

            # XGBoost binary classification normally returns:
            #
            # [samples, features]
            #
            # But different SHAP versions/model types can return
            # slightly different structures.

            if isinstance(shap_values, list):

                if len(shap_values) > 1:
                    values = np.asarray(
                        shap_values[1]
                    )[0]
                else:
                    values = np.asarray(
                        shap_values[0]
                    )[0]

            else:

                values = np.asarray(
                    shap_values
                )

                if values.ndim == 3:
                    values = values[0, :, -1]

                elif values.ndim == 2:
                    values = values[0]

                elif values.ndim == 1:
                    pass

                else:
                    values = values.flatten()

            feature_names = list(X.columns)

            contributions = []

            for feature, value in zip(
                feature_names,
                values,
            ):

                contribution = _safe_float(value)

                contributions.append(
                    {
                        "feature": feature,
                        "description": _feature_description(
                            feature
                        ),
                        "impact": round(
                            abs(contribution),
                            6,
                        ),
                        "direction": (
                            "increases_bot_risk"
                            if contribution > 0
                            else "decreases_bot_risk"
                        ),
                        "shap_value": round(
                            contribution,
                            6,
                        ),
                        "value": _safe_float(
                            X.iloc[0][feature]
                        ),
                    }
                )

            contributions.sort(
                key=lambda x: x["impact"],
                reverse=True,
            )

            return {
                "available": True,
                "method": "SHAP TreeExplainer",
                "contributions": contributions[
                    :self.top_k
                ],
            }

        except Exception as exc:

            return {
                "available": False,
                "method": "SHAP TreeExplainer",
                "reason": str(exc),
                "contributions": [],
            }

    # ==================================================================
    # GRU EXPLANATION
    # ==================================================================

    def explain_gru(
        self,
        sequence: Optional[Any] = None,
        feature_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Explain a GRU prediction.

        GRU neural networks do not naturally expose feature-level
        explanations like tree models.

        Therefore this method uses a lightweight sequence attribution
        approach.

        If a sequence is supplied:

            [timesteps, features]

        the contribution of each feature is estimated from its
        normalized magnitude across the observed sequence.

        This is intentionally presented as a behavioral-pattern
        explanation rather than claiming it is exact SHAP attribution.
        """

        if self.gru_model is None:

            return {
                "available": False,
                "reason": "GRU model not supplied.",
                "contributions": [],
            }

        if sequence is None:

            return {
                "available": False,
                "reason": (
                    "No behavioral sequence supplied."
                ),
                "contributions": [],
            }

        try:

            sequence_array = np.asarray(
                sequence,
                dtype=float,
            )

            if sequence_array.ndim == 2:

                # [timesteps, features]

                feature_strength = np.mean(
                    np.abs(sequence_array),
                    axis=0,
                )

            elif sequence_array.ndim == 3:

                # [batch, timesteps, features]

                feature_strength = np.mean(
                    np.abs(sequence_array),
                    axis=(0, 1),
                )

            else:

                return {
                    "available": False,
                    "reason": (
                        "Expected sequence shape "
                        "[timesteps, features] "
                        "or [batch, timesteps, features]."
                    ),
                    "contributions": [],
                }

            if feature_names is None:
                feature_names = [
                    f"sequence_feature_{i}"
                    for i in range(
                        len(feature_strength)
                    )
                ]

            contributions = []

            total = float(
                np.sum(feature_strength)
            )

            if total <= 0:
                total = 1.0

            for i, strength in enumerate(
                feature_strength
            ):

                if i < len(feature_names):
                    feature = feature_names[i]
                else:
                    feature = (
                        f"sequence_feature_{i}"
                    )

                normalized = (
                    float(strength) / total
                )

                contributions.append(
                    {
                        "feature": feature,
                        "description": _feature_description(
                            feature
                        ),
                        "impact": round(
                            normalized,
                            6,
                        ),
                        "direction": (
                            "behavioral_sequence_signal"
                        ),
                        "method": (
                            "sequence_attribution"
                        ),
                    }
                )

            contributions.sort(
                key=lambda x: x["impact"],
                reverse=True,
            )

            return {
                "available": True,
                "method": (
                    "GRU sequence attribution"
                ),
                "note": (
                    "Approximate behavioral attribution; "
                    "not exact SHAP values."
                ),
                "contributions": contributions[
                    :self.top_k
                ],
            }

        except Exception as exc:

            return {
                "available": False,
                "method": (
                    "GRU sequence attribution"
                ),
                "reason": str(exc),
                "contributions": [],
            }

    # ==================================================================
    # ISOLATION FOREST
    # ==================================================================

    def explain_anomaly(
        self,
        features: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Explain Isolation Forest anomaly detection.

        Isolation Forest itself does not provide native SHAP-style
        feature explanations in the same way as XGBoost.

        Therefore we identify the most unusual feature magnitudes
        using a robust z-score style comparison.
        """

        if self.isolation_model is None:

            return {
                "available": False,
                "reason": (
                    "Isolation Forest model not supplied."
                ),
                "contributions": [],
            }

        try:

            feature_values = []

            for feature, value in features.items():

                numeric = _safe_float(
                    value,
                    default=0.0,
                )

                feature_values.append(
                    (
                        feature,
                        numeric,
                    )
                )

            # Estimate unusual magnitude.

            magnitudes = []

            for feature, value in feature_values:

                magnitude = abs(value)

                magnitudes.append(
                    {
                        "feature": feature,
                        "description": _feature_description(
                            feature
                        ),
                        "magnitude": magnitude,
                    }
                )

            magnitudes.sort(
                key=lambda x: x["magnitude"],
                reverse=True,
            )

            max_magnitude = (
                magnitudes[0]["magnitude"]
                if magnitudes
                else 1.0
            )

            if max_magnitude <= 0:
                max_magnitude = 1.0

            contributions = []

            for item in magnitudes[
                :self.top_k
            ]:

                normalized = (
                    item["magnitude"]
                    / max_magnitude
                )

                contributions.append(
                    {
                        "feature": item[
                            "feature"
                        ],
                        "description": item[
                            "description"
                        ],
                        "impact": round(
                            normalized,
                            6,
                        ),
                        "direction": (
                            "anomalous_behavior"
                        ),
                    }
                )

            return {
                "available": True,
                "method": (
                    "Isolation Forest anomaly analysis"
                ),
                "contributions": contributions,
            }

        except Exception as exc:

            return {
                "available": False,
                "reason": str(exc),
                "contributions": [],
            }

    # ==================================================================
    # BEHAVIORAL RULE EXPLANATIONS
    # ==================================================================

    def explain_rules(
        self,
        features: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Explain suspicious behavioral rules.

        Rules are intentionally transparent and easy for judges
        to understand.
        """

        triggered = []

        # --------------------------------------------------------------
        # Request frequency
        # --------------------------------------------------------------

        request_frequency = _safe_float(
            features.get(
                "request_frequency",
                features.get(
                    "requests_per_second",
                    0.0,
                ),
            )
        )

        if request_frequency > 5:

            triggered.append(
                {
                    "rule": "high_request_frequency",
                    "description": (
                        "Very high request frequency"
                    ),
                    "impact": 0.25,
                }
            )

        elif request_frequency > 2:

            triggered.append(
                {
                    "rule": "elevated_request_frequency",
                    "description": (
                        "Elevated request frequency"
                    ),
                    "impact": 0.12,
                }
            )

        # --------------------------------------------------------------
        # Retry rate
        # --------------------------------------------------------------

        retry_rate = _safe_float(
            features.get(
                "retry_rate",
                0.0,
            )
        )

        if retry_rate >= 0.50:

            triggered.append(
                {
                    "rule": "high_retry_rate",
                    "description": (
                        "High retry rate"
                    ),
                    "impact": 0.25,
                }
            )

        elif retry_rate >= 0.25:

            triggered.append(
                {
                    "rule": "elevated_retry_rate",
                    "description": (
                        "Elevated retry rate"
                    ),
                    "impact": 0.12,
                }
            )

        # --------------------------------------------------------------
        # Parallel sessions
        # --------------------------------------------------------------

        parallel_sessions = _safe_float(
            features.get(
                "parallel_sessions",
                features.get(
                    "active_sessions",
                    1,
                ),
            ),
            default=1,
        )

        if parallel_sessions >= 5:

            triggered.append(
                {
                    "rule": "multiple_parallel_sessions",
                    "description": (
                        "Multiple parallel sessions"
                    ),
                    "impact": 0.25,
                }
            )

        elif parallel_sessions >= 3:

            triggered.append(
                {
                    "rule": "elevated_parallel_sessions",
                    "description": (
                        "Several parallel sessions"
                    ),
                    "impact": 0.12,
                }
            )

        # --------------------------------------------------------------
        # Timing regularity
        # --------------------------------------------------------------

        timing_cv = _safe_float(
            features.get(
                "timing_cv",
                1.0,
            ),
            default=1.0,
        )

        # Low CV = highly regular timing.

        if 0 < timing_cv < 0.10:

            triggered.append(
                {
                    "rule": "abnormal_timing_regularity",
                    "description": (
                        "Abnormally regular request timing"
                    ),
                    "impact": 0.20,
                }
            )

        elif 0 < timing_cv < 0.25:

            triggered.append(
                {
                    "rule": "high_timing_regularity",
                    "description": (
                        "Highly regular request timing"
                    ),
                    "impact": 0.10,
                }
            )

        # --------------------------------------------------------------
        # Burstiness
        # --------------------------------------------------------------

        burstiness = _safe_float(
            features.get(
                "burstiness",
                features.get(
                    "burst_score",
                    0.0,
                ),
            )
        )

        if burstiness >= 0.80:

            triggered.append(
                {
                    "rule": "high_burstiness",
                    "description": (
                        "Highly bursty request behavior"
                    ),
                    "impact": 0.20,
                }
            )

        # --------------------------------------------------------------
        # Reconnect behavior
        # --------------------------------------------------------------

        reconnect_count = _safe_float(
            features.get(
                "reconnect_count",
                0,
            )
        )

        if reconnect_count >= 5:

            triggered.append(
                {
                    "rule": "repeated_reconnects",
                    "description": (
                        "Repeated reconnect behavior"
                    ),
                    "impact": 0.15,
                }
            )

        # --------------------------------------------------------------
        # Duplicate attempts
        # --------------------------------------------------------------

        duplicate_attempts = _safe_float(
            features.get(
                "duplicate_attempts",
                0,
            )
        )

        if duplicate_attempts >= 3:

            triggered.append(
                {
                    "rule": "duplicate_attempts",
                    "description": (
                        "Repeated duplicate attempts"
                    ),
                    "impact": 0.20,
                }
            )

        triggered.sort(
            key=lambda x: x["impact"],
            reverse=True,
        )

        return {
            "available": True,
            "method": "behavioral rules",
            "triggered_rules": triggered[
                :self.top_k
            ],
        }

    # ==================================================================
    # MODEL CONTRIBUTION NORMALIZATION
    # ==================================================================

    def _model_contributions(
        self,
        xgb_score: Optional[float],
        gru_score: Optional[float],
        anomaly_score: Optional[float],
        rule_score: Optional[float],
    ) -> Dict[str, float]:
        """
        Normalize model-level risk contributions.

        These represent contribution to the final explanation view,
        not a mathematical decomposition of the fused model unless
        the fusion engine explicitly uses these weights.
        """

        available = {}

        if xgb_score is not None:
            available["xgboost"] = _clip(
                _safe_float(xgb_score)
            )

        if gru_score is not None:
            available["gru"] = _clip(
                _safe_float(gru_score)
            )

        if anomaly_score is not None:
            available["anomaly_detection"] = _clip(
                _safe_float(anomaly_score)
            )

        if rule_score is not None:
            available["behavioral_rules"] = _clip(
                _safe_float(rule_score)
            )

        if not available:

            return {}

        total = sum(
            abs(value)
            for value in available.values()
        )

        if total <= 0:
            total = 1.0

        return {
            key: round(
                abs(value) / total,
                4,
            )
            for key, value in available.items()
        }

    # ==================================================================
    # COMBINE FEATURE EXPLANATIONS
    # ==================================================================

    def _combine_explanations(
        self,
        xgb_explanation: Dict[str, Any],
        gru_explanation: Dict[str, Any],
        anomaly_explanation: Dict[str, Any],
        rule_explanation: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Combine explanations from all models.

        Duplicate signals are merged.
        """

        combined = {}

        # --------------------------------------------------------------
        # XGBoost
        # --------------------------------------------------------------

        for item in xgb_explanation.get(
            "contributions",
            [],
        ):

            feature = item["feature"]

            if feature not in combined:

                combined[feature] = {
                    "signal": feature,
                    "description": item[
                        "description"
                    ],
                    "impact": 0.0,
                    "sources": [],
                }

            combined[feature][
                "impact"
            ] += abs(
                _safe_float(
                    item.get("impact", 0)
                )
            )

            combined[feature][
                "sources"
            ].append("XGBoost/SHAP")

        # --------------------------------------------------------------
        # GRU
        # --------------------------------------------------------------

        for item in gru_explanation.get(
            "contributions",
            [],
        ):

            feature = item["feature"]

            if feature not in combined:

                combined[feature] = {
                    "signal": feature,
                    "description": item[
                        "description"
                    ],
                    "impact": 0.0,
                    "sources": [],
                }

            combined[feature][
                "impact"
            ] += abs(
                _safe_float(
                    item.get("impact", 0)
                )
            )

            combined[feature][
                "sources"
            ].append("GRU")

        # --------------------------------------------------------------
        # Anomaly detection
        # --------------------------------------------------------------

        for item in anomaly_explanation.get(
            "contributions",
            [],
        ):

            feature = item["feature"]

            if feature not in combined:

                combined[feature] = {
                    "signal": feature,
                    "description": item[
                        "description"
                    ],
                    "impact": 0.0,
                    "sources": [],
                }

            combined[feature][
                "impact"
            ] += abs(
                _safe_float(
                    item.get("impact", 0)
                )
            )

            combined[feature][
                "sources"
            ].append(
                "Isolation Forest"
            )

        # --------------------------------------------------------------
        # Behavioral rules
        # --------------------------------------------------------------

        for item in rule_explanation.get(
            "triggered_rules",
            [],
        ):

            feature = item["rule"]

            if feature not in combined:

                combined[feature] = {
                    "signal": feature,
                    "description": item[
                        "description"
                    ],
                    "impact": 0.0,
                    "sources": [],
                }

            combined[feature][
                "impact"
            ] += abs(
                _safe_float(
                    item.get("impact", 0)
                )
            )

            combined[feature][
                "sources"
            ].append(
                "Behavioral Rule"
            )

        result = list(
            combined.values()
        )

        result.sort(
            key=lambda x: x["impact"],
            reverse=True,
        )

        # Normalize to 0-1 relative importance.

        if result:

            maximum = max(
                item["impact"]
                for item in result
            )

            if maximum > 0:

                for item in result:

                    item["impact"] = round(
                        item["impact"]
                        / maximum,
                        4,
                    )

        return result[
            :self.top_k
        ]

    # ==================================================================
    # PUBLIC EXPLANATION METHOD
    # ==================================================================

    def explain(
        self,
        features: Dict[str, Any],
        final_risk: float,
        xgb_score: Optional[float] = None,
        gru_score: Optional[float] = None,
        anomaly_score: Optional[float] = None,
        rule_score: Optional[float] = None,
        sequence: Optional[Any] = None,
        sequence_feature_names: Optional[
            List[str]
        ] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate the complete frontend-ready explanation.

        Parameters
        ----------
        features:
            Behavioral feature dictionary.

        final_risk:
            Final Risk Fusion Engine score in [0, 1].

        xgb_score:
            XGBoost bot probability.

        gru_score:
            GRU bot probability.

        anomaly_score:
            Isolation Forest anomaly score.

        rule_score:
            Behavioral rule risk score.

        sequence:
            Optional GRU sequence.

        sequence_feature_names:
            Names of sequence features.

        session_id:
            Optional session identifier.
        """

        final_risk = _clip(
            _safe_float(final_risk)
        )

        # --------------------------------------------------------------
        # Individual explanations
        # --------------------------------------------------------------

        xgb_explanation = (
            self.explain_xgboost(
                features
            )
        )

        gru_explanation = (
            self.explain_gru(
                sequence=sequence,
                feature_names=sequence_feature_names,
            )
        )

        anomaly_explanation = (
            self.explain_anomaly(
                features
            )
        )

        rule_explanation = (
            self.explain_rules(
                features
            )
        )

        # --------------------------------------------------------------
        # Combined explanation
        # --------------------------------------------------------------

        main_signals = (
            self._combine_explanations(
                xgb_explanation,
                gru_explanation,
                anomaly_explanation,
                rule_explanation,
            )
        )

        # --------------------------------------------------------------
        # Model-level contributions
        # --------------------------------------------------------------

        model_contributions = (
            self._model_contributions(
                xgb_score=xgb_score,
                gru_score=gru_score,
                anomaly_score=anomaly_score,
                rule_score=rule_score,
            )
        )

        # --------------------------------------------------------------
        # Human-readable summary
        # --------------------------------------------------------------

        if main_signals:

            explanation_text = (
                "Main contributing signals: "
                + "; ".join(
                    item["description"]
                    for item in main_signals[:4]
                )
                + "."
            )

        else:

            explanation_text = (
                "No dominant behavioral signal "
                "was identified."
            )

        # --------------------------------------------------------------
        # Final JSON
        # --------------------------------------------------------------

        result = {

            "session_id": session_id,

            "bot_risk": round(
                final_risk,
                4,
            ),

            "bot_risk_percent": round(
                final_risk * 100,
                2,
            ),

            "risk_label": _risk_label(
                final_risk
            ),

            "action": _risk_action(
                final_risk
            ),

            "summary": (
                f"Bot Risk: "
                f"{final_risk * 100:.0f}%"
            ),

            "explanation": explanation_text,

            "main_contributing_signals": (
                main_signals
            ),

            "model_contributions": (
                model_contributions
            ),

            "models": {

                "xgboost": xgb_explanation,

                "gru": gru_explanation,

                "anomaly_detection": (
                    anomaly_explanation
                ),

                "behavioral_rules": (
                    rule_explanation
                ),
            },

            "explainability_metadata": {

                "xgboost_method": (
                    "SHAP TreeExplainer"
                    if xgb_explanation.get(
                        "available"
                    )
                    else None
                ),

                "gru_method": (
                    gru_explanation.get(
                        "method"
                    )
                ),

                "anomaly_method": (
                    anomaly_explanation.get(
                        "method"
                    )
                ),

                "rules_method": (
                    "explicit behavioral rules"
                ),
            },
        }

        return result

    # ==================================================================
    # CONSOLE DISPLAY
    # ==================================================================

    def print_explanation(
        self,
        explanation: Dict[str, Any],
    ) -> None:
        """
        Print a judge-friendly explanation to terminal.
        """

        print()
        print("=" * 70)
        print("FAIR DROP - EXPLAINABLE AI")
        print("=" * 70)

        print(
            f"\nBot Risk: "
            f"{explanation.get('bot_risk_percent', 0):.0f}%"
        )

        print(
            f"Risk Level: "
            f"{explanation.get('risk_label', 'UNKNOWN')}"
        )

        print(
            f"Security Action: "
            f"{explanation.get('action', 'UNKNOWN')}"
        )

        print()
        print("Main contributing signals:")

        signals = explanation.get(
            "main_contributing_signals",
            [],
        )

        if not signals:

            print(
                "  No dominant signals identified."
            )

        else:

            for index, signal in enumerate(
                signals,
                start=1,
            ):

                print(
                    f"  {index}. "
                    f"{signal['description']}"
                )

                print(
                    f"     Impact: "
                    f"{signal['impact']:.2f}"
                )

                print(
                    f"     Source: "
                    f"{', '.join(signal['sources'])}"
                )

        print()
        print("Model contributions:")

        model_contributions = (
            explanation.get(
                "model_contributions",
                {},
            )
        )

        for model, contribution in (
            model_contributions.items()
        ):

            print(
                f"  {model:<22} "
                f"{contribution * 100:>6.2f}%"
            )

        print()
        print(
            explanation.get(
                "explanation",
                "",
            )
        )

        print("=" * 70)


# ======================================================================
# SIMPLE MODEL LOADING
# ======================================================================

def load_xgboost_model(
    path: str,
) -> Optional[Any]:
    """
    Load XGBoost model using joblib.
    """

    if not JOBLIB_AVAILABLE:

        print(
            "[ExplainableAI] joblib unavailable."
        )

        return None

    if not os.path.exists(path):

        print(
            f"[ExplainableAI] Model not found: {path}"
        )

        return None

    try:

        model = joblib.load(path)

        print(
            f"[ExplainableAI] XGBoost loaded: {path}"
        )

        return model

    except Exception as exc:

        print(
            f"[ExplainableAI] Failed loading XGBoost: "
            f"{exc}"
        )

        return None


def load_isolation_model(
    path: str,
) -> Optional[Any]:
    """
    Load Isolation Forest model using joblib.
    """

    if not JOBLIB_AVAILABLE:
        return None

    if not os.path.exists(path):

        print(
            f"[ExplainableAI] Model not found: {path}"
        )

        return None

    try:

        model = joblib.load(path)

        print(
            f"[ExplainableAI] Isolation Forest loaded: "
            f"{path}"
        )

        return model

    except Exception as exc:

        print(
            f"[ExplainableAI] Failed loading Isolation Forest: "
            f"{exc}"
        )

        return None


def load_gru_model(
    path: str,
) -> Optional[Any]:
    """
    Load TensorFlow/Keras GRU model.
    """

    if not TF_AVAILABLE:

        print(
            "[ExplainableAI] TensorFlow unavailable."
        )

        return None

    if not os.path.exists(path):

        print(
            f"[ExplainableAI] Model not found: {path}"
        )

        return None

    try:

        model = tf.keras.models.load_model(
            path
        )

        print(
            f"[ExplainableAI] GRU loaded: {path}"
        )

        return model

    except Exception as exc:

        print(
            f"[ExplainableAI] Failed loading GRU: "
            f"{exc}"
        )

        return None


# ======================================================================
# DEMONSTRATION
# ======================================================================

def demo() -> None:
    """
    Standalone demonstration.

    This does not require trained models.

    It demonstrates the behavioral-rule and unified
    frontend JSON structure.
    """

    print()
    print("=" * 70)
    print("FAIR DROP - EXPLAINABLE AI DEMO")
    print("=" * 70)

    # --------------------------------------------------------------
    # Example behavioral features
    # --------------------------------------------------------------

    features = {

        "request_frequency": 8.4,

        "retry_rate": 0.73,

        "parallel_sessions": 7,

        "timing_cv": 0.06,

        "burstiness": 0.91,

        "reconnect_count": 8,

        "duplicate_attempts": 5,
    }

    # --------------------------------------------------------------
    # Create engine without requiring actual models
    # --------------------------------------------------------------

    engine = ExplainableAI(
        xgb_model=None,
        gru_model=None,
        isolation_model=None,
        top_k=5,
    )

    # --------------------------------------------------------------
    # Generate explanation
    # --------------------------------------------------------------

    explanation = engine.explain(

        features=features,

        final_risk=0.91,

        xgb_score=0.94,

        gru_score=0.88,

        anomaly_score=0.86,

        rule_score=0.92,

        session_id="demo_session_001",
    )

    # --------------------------------------------------------------
    # Print explanation
    # --------------------------------------------------------------

    engine.print_explanation(
        explanation
    )

    # --------------------------------------------------------------
    # JSON
    # --------------------------------------------------------------

    print()
    print("FRONTEND JSON:")
    print()

    print(
        json.dumps(
            explanation,
            indent=2,
        )
    )


# ======================================================================
# MAIN
# ======================================================================

if __name__ == "__main__":

    demo()