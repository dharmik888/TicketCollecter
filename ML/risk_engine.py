"""
FAIR DROP - HYBRID AI RISK ENGINE
=================================

Combines:

    XGBoost           -> aggregate behavioral risk
    GRU               -> temporal behavioral risk
    Isolation Forest  -> anomaly / novelty risk
    Rules             -> explicit behavioral violations

Produces:

    bot_risk_score: 0 - 100

Policies:

    LOW        -> NORMAL_QUEUE
    MEDIUM     -> MONITOR
    HIGH       -> RATE_LIMIT_OR_CHALLENGE
    VERY_HIGH  -> CHALLENGE_AND_MONITOR / TEMPORARY_QUARANTINE

Important:
High risk does NOT automatically mean permanent ban.
The system uses model agreement + temporal persistence
to reduce false positives.
"""

from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
import json


# ============================================================
# CONFIGURATION
# ============================================================

# Fusion weights
XGB_WEIGHT = 0.35
GRU_WEIGHT = 0.35
ANOMALY_WEIGHT = 0.15
RULE_WEIGHT = 0.15

# Verify weights
assert abs(
    XGB_WEIGHT
    + GRU_WEIGHT
    + ANOMALY_WEIGHT
    + RULE_WEIGHT
    - 1.0
) < 1e-9


# ------------------------------------------------------------
# Risk thresholds
# ------------------------------------------------------------

LOW_THRESHOLD = 30.0
MEDIUM_THRESHOLD = 60.0
HIGH_THRESHOLD = 80.0

# Quarantine requires stronger evidence
QUARANTINE_THRESHOLD = 85.0

# ------------------------------------------------------------
# Model agreement
# ------------------------------------------------------------

MIN_AGREEMENT_FOR_STRONG_ACTION = 0.70

# ------------------------------------------------------------
# Temporal smoothing
# ------------------------------------------------------------

CURRENT_RISK_WEIGHT = 0.70
PREVIOUS_RISK_WEIGHT = 0.30

# ------------------------------------------------------------
# Persistence
# ------------------------------------------------------------

HIGH_RISK_PERSISTENCE_THRESHOLD = 75.0
REQUIRED_HIGH_RISK_EVENTS = 3

# ------------------------------------------------------------
# Recovery
# ------------------------------------------------------------

CHALLENGE_RELEASE_THRESHOLD = 45.0
QUARANTINE_RELEASE_THRESHOLD = 65.0


# ============================================================
# RESULT OBJECT
# ============================================================

@dataclass
class RiskResult:

    bot_risk_score: float

    signals: Dict[str, float]

    fusion_weights: Dict[str, float]

    policy_level: str

    action: str

    confidence: str

    model_agreement: float

    persistent_high_risk: bool

    allow_queue: bool

    monitor: bool

    rate_limit: bool

    challenge_required: bool

    quarantine: bool

    explanation: list

    risk_history: Optional[list] = None


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 1.0
) -> float:

    return max(
        minimum,
        min(maximum, float(value))
    )


# ============================================================
# MODEL AGREEMENT
# ============================================================

def calculate_model_agreement(
    xgb_probability: float,
    gru_probability: float,
    anomaly_score: float,
    rule_violation_score: float
) -> float:

    values = [
        xgb_probability,
        gru_probability,
        anomaly_score,
        rule_violation_score
    ]

    mean_value = sum(values) / len(values)

    mean_absolute_deviation = sum(
        abs(value - mean_value)
        for value in values
    ) / len(values)

    agreement = 1.0 - mean_absolute_deviation

    return clamp(agreement)


# ============================================================
# HIGH-RISK PERSISTENCE
# ============================================================

def check_persistence(
    risk_history: Optional[list]
) -> bool:

    if not risk_history:
        return False

    high_risk_count = sum(
        1
        for score in risk_history
        if score >= HIGH_RISK_PERSISTENCE_THRESHOLD
    )

    return high_risk_count >= REQUIRED_HIGH_RISK_EVENTS


# ============================================================
# TEMPORAL SMOOTHING
# ============================================================

def smooth_risk(
    current_risk: float,
    previous_risk: Optional[float]
) -> float:

    if previous_risk is None:
        return current_risk

    previous_risk_normalized = clamp(
        previous_risk / 100.0
    )

    smoothed = (
        CURRENT_RISK_WEIGHT * current_risk
        +
        PREVIOUS_RISK_WEIGHT * previous_risk_normalized
    )

    return clamp(smoothed)


# ============================================================
# EXPLANATION ENGINE
# ============================================================

def generate_explanation(
    xgb_probability: float,
    gru_probability: float,
    anomaly_score: float,
    rule_violation_score: float,
    agreement: float
) -> list:

    explanations = []

    if xgb_probability >= 0.70:

        explanations.append(
            "strong aggregate behavioral bot signal"
        )

    elif xgb_probability >= 0.50:

        explanations.append(
            "moderate aggregate behavioral risk"
        )


    if gru_probability >= 0.70:

        explanations.append(
            "strong temporal behavioral bot signal"
        )

    elif gru_probability >= 0.50:

        explanations.append(
            "moderate temporal behavioral risk"
        )


    if anomaly_score >= 0.70:

        explanations.append(
            "behavior is significantly unusual"
        )

    elif anomaly_score >= 0.50:

        explanations.append(
            "behavior shows moderate anomaly"
        )


    if rule_violation_score >= 0.70:

        explanations.append(
            "multiple strong behavioral rule violations"
        )

    elif rule_violation_score >= 0.50:

        explanations.append(
            "suspicious behavioral rule violations"
        )


    if agreement >= 0.80:

        explanations.append(
            "multiple risk signals strongly agree"
        )

    elif agreement < 0.50:

        explanations.append(
            "risk signals show significant disagreement"
        )


    if not explanations:

        explanations.append(
            "no strong individual risk signal"
        )

    return explanations


# ============================================================
# POLICY ENGINE
# ============================================================

def determine_policy(
    risk_score: float,
    agreement: float,
    persistent_high_risk: bool
):

    # --------------------------------------------------------
    # LOW
    # --------------------------------------------------------

    if risk_score < LOW_THRESHOLD:

        return {
            "level": "LOW",
            "action": "NORMAL_QUEUE",
            "confidence": "LOW_RISK",
            "allow_queue": True,
            "monitor": False,
            "rate_limit": False,
            "challenge_required": False,
            "quarantine": False
        }


    # --------------------------------------------------------
    # MEDIUM
    # --------------------------------------------------------

    if risk_score < MEDIUM_THRESHOLD:

        return {
            "level": "MEDIUM",
            "action": "MONITOR",
            "confidence": "MONITORED",
            "allow_queue": True,
            "monitor": True,
            "rate_limit": False,
            "challenge_required": False,
            "quarantine": False
        }


    # --------------------------------------------------------
    # HIGH
    # --------------------------------------------------------

    if risk_score < HIGH_THRESHOLD:

        if agreement >= MIN_AGREEMENT_FOR_STRONG_ACTION:

            action = "RATE_LIMIT_OR_CHALLENGE"

            rate_limit = True
            challenge = True

        else:

            action = "MONITOR_AND_COLLECT_EVIDENCE"

            rate_limit = False
            challenge = False

        return {
            "level": "HIGH",
            "action": action,
            "confidence": "SUSPICIOUS",
            "allow_queue": True,
            "monitor": True,
            "rate_limit": rate_limit,
            "challenge_required": challenge,
            "quarantine": False
        }


    # --------------------------------------------------------
    # VERY HIGH
    # --------------------------------------------------------

    # Strong evidence required before quarantine.
    if (
        risk_score >= QUARANTINE_THRESHOLD
        and agreement >= MIN_AGREEMENT_FOR_STRONG_ACTION
        and persistent_high_risk
    ):

        return {
            "level": "VERY_HIGH",
            "action": "TEMPORARY_QUARANTINE",
            "confidence": "HIGH_RISK",
            "allow_queue": False,
            "monitor": True,
            "rate_limit": True,
            "challenge_required": True,
            "quarantine": True
        }


    # --------------------------------------------------------
    # VERY HIGH BUT NOT ENOUGH EVIDENCE
    # --------------------------------------------------------

    return {
        "level": "VERY_HIGH",
        "action": "CHALLENGE_AND_MONITOR",
        "confidence": "HIGH_RISK_PENDING_CONFIRMATION",
        "allow_queue": True,
        "monitor": True,
        "rate_limit": True,
        "challenge_required": True,
        "quarantine": False
    }


# ============================================================
# MAIN RISK ENGINE
# ============================================================

def calculate_risk(
    xgb_probability: float,
    gru_probability: float,
    anomaly_score: float,
    rule_violation_score: float,
    previous_risk: Optional[float] = None,
    risk_history: Optional[list] = None
) -> RiskResult:

    # --------------------------------------------------------
    # 1. Validate and clamp inputs
    # --------------------------------------------------------

    xgb_probability = clamp(xgb_probability)

    gru_probability = clamp(gru_probability)

    anomaly_score = clamp(anomaly_score)

    rule_violation_score = clamp(
        rule_violation_score
    )


    # --------------------------------------------------------
    # 2. Weighted risk fusion
    # --------------------------------------------------------

    raw_risk = (

        XGB_WEIGHT * xgb_probability

        +

        GRU_WEIGHT * gru_probability

        +

        ANOMALY_WEIGHT * anomaly_score

        +

        RULE_WEIGHT * rule_violation_score
    )


    # --------------------------------------------------------
    # 3. Temporal smoothing
    # --------------------------------------------------------

    smoothed_risk = smooth_risk(
        raw_risk,
        previous_risk
    )


    risk_score = smoothed_risk * 100.0


    # --------------------------------------------------------
    # 4. Update history
    # --------------------------------------------------------

    if risk_history is None:

        risk_history = []

    updated_history = (
        risk_history.copy()
    )

    updated_history.append(
        round(risk_score, 2)
    )

    # Keep only recent history
    updated_history = updated_history[-10:]


    # --------------------------------------------------------
    # 5. Persistence detection
    # --------------------------------------------------------

    persistent_high_risk = check_persistence(
        updated_history
    )


    # --------------------------------------------------------
    # 6. Model agreement
    # --------------------------------------------------------

    agreement = calculate_model_agreement(

        xgb_probability,

        gru_probability,

        anomaly_score,

        rule_violation_score
    )


    # --------------------------------------------------------
    # 7. Policy
    # --------------------------------------------------------

    policy = determine_policy(

        risk_score,

        agreement,

        persistent_high_risk
    )


    # --------------------------------------------------------
    # 8. Explanation
    # --------------------------------------------------------

    explanation = generate_explanation(

        xgb_probability,

        gru_probability,

        anomaly_score,

        rule_violation_score,

        agreement
    )


    # --------------------------------------------------------
    # 9. Return result
    # --------------------------------------------------------

    return RiskResult(

        bot_risk_score=round(
            risk_score,
            2
        ),

        signals={
            "xgboost_probability": round(
                xgb_probability,
                4
            ),

            "gru_probability": round(
                gru_probability,
                4
            ),

            "anomaly_score": round(
                anomaly_score,
                4
            ),

            "rule_violation_score": round(
                rule_violation_score,
                4
            )
        },

        fusion_weights={
            "xgboost": XGB_WEIGHT,
            "gru": GRU_WEIGHT,
            "anomaly": ANOMALY_WEIGHT,
            "rules": RULE_WEIGHT
        },

        policy_level=policy["level"],

        action=policy["action"],

        confidence=policy["confidence"],

        model_agreement=round(
            agreement,
            4
        ),

        persistent_high_risk=persistent_high_risk,

        allow_queue=policy["allow_queue"],

        monitor=policy["monitor"],

        rate_limit=policy["rate_limit"],

        challenge_required=policy["challenge_required"],

        quarantine=policy["quarantine"],

        explanation=explanation,

        risk_history=updated_history
    )


# ============================================================
# JSON CONVERSION
# ============================================================

def risk_to_json(
    result: RiskResult
) -> str:

    return json.dumps(
        asdict(result),
        indent=2
    )


# ============================================================
# TEST CASES
# ============================================================

def run_demo():

    print("=" * 70)
    print("FAIR DROP - HYBRID AI RISK ENGINE")
    print("=" * 70)


    # --------------------------------------------------------
    # TEST 1 - Genuine human
    # --------------------------------------------------------

    print("\n[TEST 1] Genuine Human")

    result = calculate_risk(

        xgb_probability=0.08,

        gru_probability=0.05,

        anomaly_score=0.10,

        rule_violation_score=0.00
    )

    print(risk_to_json(result))


    # --------------------------------------------------------
    # TEST 2 - Suspicious but probably legitimate
    # --------------------------------------------------------

    print("\n[TEST 2] Moderately Suspicious")

    result = calculate_risk(

        xgb_probability=0.45,

        gru_probability=0.35,

        anomaly_score=0.30,

        rule_violation_score=0.10
    )

    print(risk_to_json(result))


    # --------------------------------------------------------
    # TEST 3 - Strong bot evidence
    # --------------------------------------------------------

    print("\n[TEST 3] Strong Bot Evidence")

    result = calculate_risk(

        xgb_probability=0.92,

        gru_probability=0.88,

        anomaly_score=0.76,

        rule_violation_score=0.65
    )

    print(risk_to_json(result))


    # --------------------------------------------------------
    # TEST 4 - Persistent extremely high risk
    # --------------------------------------------------------

    print("\n[TEST 4] Persistent High Risk")

    history = [
        91.0,
        93.0,
        95.0
    ]

    result = calculate_risk(

        xgb_probability=0.97,

        gru_probability=0.99,

        anomaly_score=0.91,

        rule_violation_score=0.95,

        previous_risk=95.0,

        risk_history=history
    )

    print(risk_to_json(result))


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    run_demo()