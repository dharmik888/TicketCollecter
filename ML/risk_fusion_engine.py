"""
FAIR DROP - RISK FUSION ENGINE

Combines:
    1. XGBoost bot probability
    2. GRU temporal bot probability
    3. Isolation Forest anomaly score
    4. Rule violation score

into:
    - Bot risk score: 0-100
    - Risk level
    - Model agreement
    - Temporal persistence
    - Adaptive policy decision

All model inputs must be normalized to [0, 1].
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List


# ============================================================
# CONFIGURATION
# ============================================================

XGB_WEIGHT = 0.35
GRU_WEIGHT = 0.35
ANOMALY_WEIGHT = 0.15
RULE_WEIGHT = 0.15

# Risk thresholds
LOW_THRESHOLD = 30
MEDIUM_THRESHOLD = 60
HIGH_THRESHOLD = 80

# Persistence configuration
PERSISTENCE_RISK_THRESHOLD = 75
PERSISTENCE_OBSERVATIONS_REQUIRED = 3

# Quarantine configuration
QUARANTINE_RISK_THRESHOLD = 85
QUARANTINE_AGREEMENT_THRESHOLD = 0.70

# Number of historical risk observations to retain
MAX_HISTORY = 10


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class RiskHistory:
    """
    Maintains recent risk observations for one session.
    """

    scores: deque = field(
        default_factory=lambda: deque(maxlen=MAX_HISTORY)
    )

    def add(self, score: float) -> None:
        self.scores.append(float(score))

    def recent(self) -> List[float]:
        return list(self.scores)

    def high_risk_count(self) -> int:
        return sum(
            score >= PERSISTENCE_RISK_THRESHOLD
            for score in self.scores
        )

    def persistent_high_risk(self) -> bool:
        """
        Persistent high risk requires the latest
        N observations to all be >= threshold.
        """

        if len(self.scores) < PERSISTENCE_OBSERVATIONS_REQUIRED:
            return False

        recent_scores = list(self.scores)[
            -PERSISTENCE_OBSERVATIONS_REQUIRED:
        ]

        return all(
            score >= PERSISTENCE_RISK_THRESHOLD
            for score in recent_scores
        )


# ============================================================
# RISK FUSION ENGINE
# ============================================================

class RiskFusionEngine:
    """
    Central Fair Drop risk fusion engine.

    Combines independent ML/rule signals into
    one normalized risk score and policy decision.
    """

    def __init__(self):
        # session_id -> RiskHistory
        self.histories: Dict[str, RiskHistory] = {}

    # ========================================================
    # INPUT VALIDATION
    # ========================================================

    @staticmethod
    def clamp(value: float) -> float:
        """
        Clamp model output into [0, 1].
        """

        try:
            value = float(value)
        except (TypeError, ValueError):
            return 0.0

        return max(0.0, min(1.0, value))

    # ========================================================
    # MODEL AGREEMENT
    # ========================================================

    @staticmethod
    def calculate_model_agreement(
        xgb_probability: float,
        gru_probability: float,
        anomaly_score: float,
        rule_violation_score: float,
    ) -> float:
        """
        Measures how closely the four signals agree.

        Agreement = 1 - normalized dispersion.

        If all signals are similar:
            agreement -> 1

        If signals strongly disagree:
            agreement -> 0
        """

        values = [
            xgb_probability,
            gru_probability,
            anomaly_score,
            rule_violation_score,
        ]

        minimum = min(values)
        maximum = max(values)

        agreement = 1.0 - (maximum - minimum)

        return max(0.0, min(1.0, agreement))

    # ========================================================
    # RISK LEVEL
    # ========================================================

    @staticmethod
    def get_risk_level(score: float) -> str:

        if score < LOW_THRESHOLD:
            return "LOW"

        if score < MEDIUM_THRESHOLD:
            return "MEDIUM"

        if score < HIGH_THRESHOLD:
            return "HIGH"

        return "VERY_HIGH"

    # ========================================================
    # POLICY ENGINE
    # ========================================================

    def determine_policy(
        self,
        score: float,
        agreement: float,
        persistent_high_risk: bool,
    ) -> Dict[str, Any]:

        # ----------------------------------------------------
        # LOW
        # ----------------------------------------------------

        if score < LOW_THRESHOLD:

            return {
                "name": "NORMAL_QUEUE",
                "action": "NORMAL_QUEUE",

                "allow_queue": True,
                "monitor": False,
                "rate_limit": False,
                "challenge_required": False,
                "quarantine": False,
            }

        # ----------------------------------------------------
        # MEDIUM
        # ----------------------------------------------------

        if score < MEDIUM_THRESHOLD:

            return {
                "name": "MONITOR",
                "action": "MONITOR",

                "allow_queue": True,
                "monitor": True,
                "rate_limit": False,
                "challenge_required": False,
                "quarantine": False,
            }

        # ----------------------------------------------------
        # HIGH
        # ----------------------------------------------------

        if score < HIGH_THRESHOLD:

            # If models disagree, gather more evidence.
            if agreement < QUARANTINE_AGREEMENT_THRESHOLD:

                return {
                    "name": "MONITOR_AND_COLLECT_EVIDENCE",
                    "action": "MONITOR_AND_COLLECT_EVIDENCE",

                    "allow_queue": True,
                    "monitor": True,
                    "rate_limit": False,
                    "challenge_required": False,
                    "quarantine": False,
                }

            return {
                "name": "RATE_LIMIT_OR_CHALLENGE",
                "action": "RATE_LIMIT_OR_CHALLENGE",

                "allow_queue": True,
                "monitor": True,
                "rate_limit": True,
                "challenge_required": True,
                "quarantine": False,
            }

        # ----------------------------------------------------
        # VERY HIGH
        # ----------------------------------------------------

        # Strong evidence + persistence required for quarantine.
        if (
            score >= QUARANTINE_RISK_THRESHOLD
            and agreement >= QUARANTINE_AGREEMENT_THRESHOLD
            and persistent_high_risk
        ):

            return {
                "name": "TEMPORARY_QUARANTINE",
                "action": "TEMPORARY_QUARANTINE",

                "allow_queue": False,
                "monitor": True,
                "rate_limit": True,
                "challenge_required": True,
                "quarantine": True,
            }

        # High risk but insufficient persistence/evidence.
        return {
            "name": "CHALLENGE_AND_MONITOR",
            "action": "CHALLENGE_AND_MONITOR",

            "allow_queue": True,
            "monitor": True,
            "rate_limit": True,
            "challenge_required": True,
            "quarantine": False,
        }

    # ========================================================
    # MAIN FUSION FUNCTION
    # ========================================================

    def evaluate(
        self,
        session_id: str,
        xgb_probability: float,
        gru_probability: float,
        anomaly_score: float,
        rule_violation_score: float,
    ) -> Dict[str, Any]:

        # ----------------------------------------------------
        # Normalize / clamp inputs
        # ----------------------------------------------------

        xgb_probability = self.clamp(xgb_probability)
        gru_probability = self.clamp(gru_probability)
        anomaly_score = self.clamp(anomaly_score)
        rule_violation_score = self.clamp(
            rule_violation_score
        )

        # ----------------------------------------------------
        # Weighted fusion
        # ----------------------------------------------------

        risk = (
            XGB_WEIGHT * xgb_probability
            + GRU_WEIGHT * gru_probability
            + ANOMALY_WEIGHT * anomaly_score
            + RULE_WEIGHT * rule_violation_score
        )

        risk = self.clamp(risk)

        # Convert 0-1 -> 0-100
        risk_score = round(risk * 100, 2)

        # ----------------------------------------------------
        # Model agreement
        # ----------------------------------------------------

        agreement = self.calculate_model_agreement(
            xgb_probability,
            gru_probability,
            anomaly_score,
            rule_violation_score,
        )

        agreement = round(agreement, 4)

        # ----------------------------------------------------
        # Risk history
        # ----------------------------------------------------

        if session_id not in self.histories:
            self.histories[session_id] = RiskHistory()

        history = self.histories[session_id]

        history.add(risk_score)

        persistent_high_risk = (
            history.persistent_high_risk()
        )

        # ----------------------------------------------------
        # Risk level
        # ----------------------------------------------------

        risk_level = self.get_risk_level(risk_score)

        # ----------------------------------------------------
        # Policy
        # ----------------------------------------------------

        policy = self.determine_policy(
            score=risk_score,
            agreement=agreement,
            persistent_high_risk=persistent_high_risk,
        )

        # ----------------------------------------------------
        # Explanation
        # ----------------------------------------------------

        explanation = self.generate_explanation(
            xgb_probability=xgb_probability,
            gru_probability=gru_probability,
            anomaly_score=anomaly_score,
            rule_violation_score=rule_violation_score,
            agreement=agreement,
            risk_score=risk_score,
            persistent_high_risk=persistent_high_risk,
        )

        # ----------------------------------------------------
        # Final response
        # ----------------------------------------------------

        return {
            "session_id": session_id,

            "risk": {
                "score": risk_score,
                "level": risk_level,
            },

            "signals": {
                "xgboost_probability": round(
                    xgb_probability, 4
                ),
                "gru_probability": round(
                    gru_probability, 4
                ),
                "anomaly_score": round(
                    anomaly_score, 4
                ),
                "rule_violation_score": round(
                    rule_violation_score, 4
                ),
            },

            "fusion": {
                "xgboost_weight": XGB_WEIGHT,
                "gru_weight": GRU_WEIGHT,
                "anomaly_weight": ANOMALY_WEIGHT,
                "rule_weight": RULE_WEIGHT,
            },

            "model_agreement": agreement,

            "persistence": {
                "high_risk_threshold": (
                    PERSISTENCE_RISK_THRESHOLD
                ),
                "required_observations": (
                    PERSISTENCE_OBSERVATIONS_REQUIRED
                ),
                "observations": len(history.scores),
                "high_risk_observations": (
                    history.high_risk_count()
                ),
                "persistent_high_risk": (
                    persistent_high_risk
                ),
                "risk_history": history.recent(),
            },

            "policy": policy,

            "explanation": explanation,
        }

    # ========================================================
    # EXPLANATION GENERATOR
    # ========================================================

    @staticmethod
    def generate_explanation(
        xgb_probability: float,
        gru_probability: float,
        anomaly_score: float,
        rule_violation_score: float,
        agreement: float,
        risk_score: float,
        persistent_high_risk: bool,
    ) -> List[str]:

        explanations = []

        # XGBoost
        if xgb_probability >= 0.80:
            explanations.append(
                "XGBoost detects strong aggregate "
                "bot-like behavior."
            )
        elif xgb_probability >= 0.50:
            explanations.append(
                "XGBoost detects moderately suspicious "
                "aggregate behavior."
            )

        # GRU
        if gru_probability >= 0.80:
            explanations.append(
                "GRU detects a strongly suspicious "
                "temporal behavior sequence."
            )
        elif gru_probability >= 0.50:
            explanations.append(
                "GRU detects moderately suspicious "
                "temporal behavior."
            )

        # Isolation Forest
        if anomaly_score >= 0.80:
            explanations.append(
                "Behavior is highly anomalous compared "
                "with legitimate human traffic."
            )
        elif anomaly_score >= 0.50:
            explanations.append(
                "Behavior differs noticeably from "
                "legitimate human traffic."
            )

        # Rules
        if rule_violation_score >= 0.80:
            explanations.append(
                "Multiple behavioral rules were violated."
            )
        elif rule_violation_score >= 0.50:
            explanations.append(
                "Some suspicious behavioral rules "
                "were triggered."
            )

        # Agreement
        if agreement >= 0.80:
            explanations.append(
                "The detection signals show strong "
                "model agreement."
            )
        elif agreement < 0.50:
            explanations.append(
                "The detection signals disagree, so "
                "additional evidence is preferred."
            )

        # Persistence
        if persistent_high_risk:
            explanations.append(
                "High risk has persisted across multiple "
                "observations."
            )

        # Default
        if not explanations:
            explanations.append(
                "No strong bot indicators were detected."
            )

        return explanations

    # ========================================================
    # SESSION MANAGEMENT
    # ========================================================

    def clear_session(self, session_id: str) -> None:
        """
        Remove stored risk history for a session.
        """

        self.histories.pop(session_id, None)

    def get_history(
        self,
        session_id: str,
    ) -> List[float]:

        if session_id not in self.histories:
            return []

        return self.histories[session_id].recent()


# ============================================================
# DEMO / TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 70)
    print("FAIR DROP - RISK FUSION ENGINE")
    print("=" * 70)

    engine = RiskFusionEngine()

    # --------------------------------------------------------
    # TEST 1 — Genuine Human
    # --------------------------------------------------------

    print("\n[TEST 1] GENUINE HUMAN")

    result = engine.evaluate(
        session_id="human_001",
        xgb_probability=0.08,
        gru_probability=0.05,
        anomaly_score=0.10,
        rule_violation_score=0.00,
    )

    print(result)

    # --------------------------------------------------------
    # TEST 2 — Moderately Suspicious
    # --------------------------------------------------------

    print("\n[TEST 2] MODERATELY SUSPICIOUS")

    result = engine.evaluate(
        session_id="suspicious_001",
        xgb_probability=0.45,
        gru_probability=0.35,
        anomaly_score=0.30,
        rule_violation_score=0.10,
    )

    print(result)

    # --------------------------------------------------------
    # TEST 3 — Strong Bot Evidence
    # --------------------------------------------------------

    print("\n[TEST 3] STRONG BOT EVIDENCE")

    result = engine.evaluate(
        session_id="bot_001",
        xgb_probability=0.92,
        gru_probability=0.88,
        anomaly_score=0.76,
        rule_violation_score=0.65,
    )

    print(result)

    # --------------------------------------------------------
    # TEST 4 — Persistent High Risk
    # --------------------------------------------------------

    print("\n[TEST 4] PERSISTENT HIGH RISK")

    session_id = "persistent_bot"

    for i in range(3):

        result = engine.evaluate(
            session_id=session_id,
            xgb_probability=0.97,
            gru_probability=0.99,
            anomaly_score=0.91,
            rule_violation_score=0.95,
        )

        print(
            f"Observation {i + 1}: "
            f"Risk={result['risk']['score']} | "
            f"Policy={result['policy']['action']} | "
            f"Quarantine="
            f"{result['policy']['quarantine']}"
        )

    print("\n" + "=" * 70)
    print("RISK FUSION ENGINE TEST COMPLETE")
    print("=" * 70)