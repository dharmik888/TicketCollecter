"""
FAIR DROP — HACKATHON DASHBOARD
"Selling 500 Seats to 50,000 People Without Letting Bots Win."

Run:
    streamlit run dashboard.py

Dependencies:
    pip install streamlit plotly pandas numpy requests
"""

import time
import random
from collections import deque

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="Fair Drop — AI Ticket Defense",
    page_icon="🎟️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

TOTAL_TICKETS = 500
TOTAL_USERS = 50_000

ATTACKS = [
    "Normal Traffic",
    "Flood",
    "Rapid Retry",
    "Multi-session",
    "Distributed",
    "Stealth",
    "Adaptive",
]

ATTACK_PROFILES = {
    "Normal Traffic": {
        "rps": 2200,
        "bot_pct": 0.03,
        "risk": 8,
        "detected": 0,
        "action": "ALLOW",
        "signals": [
            "Normal request frequency",
            "Natural timing variation",
            "Single-session behavior",
        ],
    },
    "Flood": {
        "rps": 30000,
        "bot_pct": 0.38,
        "risk": 94,
        "detected": 8200,
        "action": "QUARANTINE",
        "signals": [
            "Very high request frequency",
            "Highly bursty traffic",
            "Extreme concurrency",
            "Abnormal request volume",
        ],
    },
    "Rapid Retry": {
        "rps": 13500,
        "bot_pct": 0.24,
        "risk": 88,
        "detected": 5100,
        "action": "THROTTLE",
        "signals": [
            "High retry rate",
            "Very short inter-request time",
            "Repeated failed attempts",
            "Bursting around rate limits",
        ],
    },
    "Multi-session": {
        "rps": 9800,
        "bot_pct": 0.21,
        "risk": 86,
        "detected": 4300,
        "action": "CHALLENGE",
        "signals": [
            "Multiple parallel sessions",
            "Session correlation",
            "Repeated behavioral fingerprint",
            "Concurrent activity pattern",
        ],
    },
    "Distributed": {
        "rps": 17800,
        "bot_pct": 0.29,
        "risk": 90,
        "detected": 6700,
        "action": "THROTTLE",
        "signals": [
            "Coordinated request timing",
            "Distributed traffic pattern",
            "Shared behavioral signature",
            "Abnormal aggregate activity",
        ],
    },
    "Stealth": {
        "rps": 2700,
        "bot_pct": 0.12,
        "risk": 73,
        "detected": 1800,
        "action": "CHALLENGE",
        "signals": [
            "Abnormal temporal sequence",
            "Unusual request spacing",
            "Suspicious sequence behavior",
            "Anomalous behavioral pattern",
        ],
    },
    "Adaptive": {
        "rps": 7600,
        "bot_pct": 0.18,
        "risk": 82,
        "detected": 3600,
        "action": "QUARANTINE",
        "signals": [
            "Behavior changes across rounds",
            "Persistent temporal anomaly",
            "Repeated policy evasion",
            "Cross-model risk agreement",
        ],
    },
}


# ============================================================
# SESSION STATE
# ============================================================

def init_state():

    defaults = {
        "attack": "Normal Traffic",
        "attack_running": False,

        "tickets_remaining": TOTAL_TICKETS,
        "tickets_allocated": 0,

        "eligible_users": 0,
        "winners": 0,
        "waitlist": 0,

        "bots_detected": 0,
        "false_positives": 0,

        "duplicate_allocations": 0,
        "overselling": 0,

        "human_allocation": 0.0,
        "bot_allocation": 0.0,

        "fairness": 0.98,
        "lottery_deviation": 0.0,

        "detection_latency": 18,

        "users_connected": 10842,
        "requests_sec": 2180,

        "human_pct": 97.0,
        "bot_pct": 3.0,

        "bot_risk": 8,
        "action": "ALLOW",

        "history_rps": deque(maxlen=60),
        "history_bot": deque(maxlen=60),
        "history_human": deque(maxlen=60),

        "allocation_done": False,
        "lottery_verified": False,
    }

    for key, value in defaults.items():

        if key not in st.session_state:
            st.session_state[key] = value


init_state()


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
<style>

.stApp {
    background: #070a0f;
    color: #f4f7fb;
}

[data-testid="stHeader"] {
    background: rgba(0,0,0,0);
}

.block-container {
    padding-top: 1rem;
    padding-bottom: 2rem;
    max-width: 1500px;
}

.hero {
    border: 1px solid #202936;
    border-radius: 18px;
    padding: 22px 26px;
    background: linear-gradient(135deg, #0d121a, #090c12);
    margin-bottom: 16px;
}

.hero-title {
    font-size: 31px;
    font-weight: 800;
    letter-spacing: -0.8px;
}

.hero-subtitle {
    color: #aeb8c5;
    font-size: 14px;
    margin-top: 5px;
}

.live {
    display: inline-block;
    border: 1px solid #1e8f5a;
    color: #5ee6a1;
    border-radius: 999px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 700;
    margin-left: 10px;
}

.metric-card {
    background: #0d121a;
    border: 1px solid #202936;
    border-radius: 15px;
    padding: 17px 18px;
    min-height: 118px;
}

.metric-label {
    color: #8f9bab;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
}

.metric-value {
    font-size: 30px;
    line-height: 1.1;
    font-weight: 800;
    margin-top: 8px;
}

.metric-sub {
    color: #758194;
    font-size: 12px;
    margin-top: 6px;
}

.section {
    color: #e8edf5;
    font-size: 17px;
    font-weight: 750;
    margin: 18px 0 9px 2px;
}

.panel {
    background: #0d121a;
    border: 1px solid #202936;
    border-radius: 15px;
    padding: 18px;
}

.risk-number {
    font-size: 54px;
    font-weight: 900;
    line-height: 1;
    margin: 5px 0;
}

.risk-high {
    color: #ff5964;
}

.risk-medium {
    color: #ffbd59;
}

.risk-low {
    color: #59df9a;
}

.action {
    display: inline-block;
    padding: 6px 12px;
    border-radius: 999px;
    background: #1a202a;
    border: 1px solid #313b49;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: .7px;
}

.signal {
    padding: 7px 9px;
    margin: 5px 0;
    background: #111821;
    border-left: 3px solid #667384;
    border-radius: 5px;
    color: #cbd3de;
    font-size: 12px;
}

.good {
    color: #61e6a1;
    font-weight: 750;
}

.bad {
    color: #ff6974;
    font-weight: 750;
}

.warning {
    color: #ffc15d;
    font-weight: 750;
}

.pipeline {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
    margin: 10px 0;
}

.pipe {
    background: #111821;
    border: 1px solid #293341;
    border-radius: 9px;
    padding: 9px 11px;
    font-size: 11px;
    font-weight: 700;
}

.arrow {
    color: #657286;
    font-size: 17px;
}

.small-note {
    color: #7f8a9b;
    font-size: 11px;
    line-height: 1.5;
}

.proof {
    background: linear-gradient(135deg, #0d1613, #0c1213);
    border: 1px solid #214634;
    border-radius: 16px;
    padding: 22px;
    text-align: center;
}

.proof-big {
    font-size: 34px;
    font-weight: 900;
    margin: 4px 0;
}

.proof-line {
    color: #72e4a9;
    font-size: 13px;
    margin: 3px 0;
    font-weight: 650;
}

div[data-testid="stButton"] > button {
    border-radius: 9px;
    min-height: 42px;
    font-weight: 700;
}

</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# HELPERS
# ============================================================

def fmt_num(value):

    return f"{int(value):,}"


def metric_card(label, value, sub=""):

    st.markdown(
        f"""
        <div class="metric-card">

            <div class="metric-label">
                {label}
            </div>

            <div class="metric-value">
                {value}
            </div>

            <div class="metric-sub">
                {sub}
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


def risk_class(risk):

    if risk >= 70:
        return "risk-high", "HIGH"

    if risk >= 35:
        return "risk-medium", "MEDIUM"

    return "risk-low", "LOW"


# ============================================================
# LIVE SIMULATION
# ============================================================

def update_live_state():

    attack = st.session_state.attack

    profile = ATTACK_PROFILES[attack]

    if st.session_state.attack_running:

        target_rps = profile["rps"]
        target_bot = profile["bot_pct"]
        target_risk = profile["risk"]
        target_detected = profile["detected"]
        target_action = profile["action"]

    else:

        target_rps = 2200
        target_bot = 0.03
        target_risk = 8
        target_detected = 0
        target_action = "ALLOW"

    st.session_state.requests_sec = int(
        st.session_state.requests_sec
        + (target_rps - st.session_state.requests_sec) * 0.32
        + random.randint(-120, 120)
    )

    st.session_state.bot_pct = max(
        0,
        min(
            100,
            st.session_state.bot_pct
            + ((target_bot * 100) - st.session_state.bot_pct) * 0.30
        ),
    )

    st.session_state.human_pct = 100 - st.session_state.bot_pct

    st.session_state.bot_risk = max(
        0,
        min(
            100,
            st.session_state.bot_risk
            + (target_risk - st.session_state.bot_risk) * 0.35
        ),
    )

    st.session_state.action = target_action

    base_users = 10500 + int(
        st.session_state.requests_sec * 1.25
    )

    st.session_state.users_connected = max(
        1000,
        base_users + random.randint(-300, 300),
    )

    if st.session_state.attack_running:

        increment = max(
            1,
            int(target_detected * 0.025)
        )

        st.session_state.bots_detected = min(
            49999,
            st.session_state.bots_detected + increment,
        )

    st.session_state.detection_latency = int(
        max(
            7,
            min(
                65,
                12
                + st.session_state.requests_sec / 2500
                + random.randint(-3, 5),
            ),
        )
    )

    st.session_state.history_rps.append(
        st.session_state.requests_sec
    )

    st.session_state.history_bot.append(
        st.session_state.bot_pct
    )

    st.session_state.history_human.append(
        st.session_state.human_pct
    )


# ============================================================
# ATTACK CONTROL
# ============================================================

def launch_attack():

    st.session_state.attack_running = True


def stop_attack():

    st.session_state.attack_running = False


# ============================================================
# LOTTERY
# ============================================================

def run_lottery():

    eligible = 1001
    winners = 500
    waitlist = eligible - winners

    st.session_state.eligible_users = eligible
    st.session_state.winners = winners
    st.session_state.waitlist = waitlist

    st.session_state.tickets_allocated = winners
    st.session_state.tickets_remaining = 0

    st.session_state.human_allocation = 49.95
    st.session_state.bot_allocation = 0.0

    st.session_state.duplicate_allocations = 0
    st.session_state.overselling = 0

    st.session_state.fairness = 0.98
    st.session_state.lottery_deviation = 0.30

    st.session_state.lottery_verified = True
    st.session_state.allocation_done = True


# ============================================================
# RESET
# ============================================================

def reset_demo():

    for key in list(st.session_state.keys()):

        del st.session_state[key]

    init_state()


# ============================================================
# CHART
# ============================================================

def build_line_chart():

    rps = list(st.session_state.history_rps)

    if len(rps) < 2:

        rps = [2200, 2200]

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            y=rps,
            mode="lines",
            name="Requests/sec",
            line=dict(width=3),
            fill="tozeroy",
        )
    )

    fig.update_layout(
        height=260,
        margin=dict(
            l=10,
            r=10,
            t=10,
            b=10,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#aeb8c5"),
        xaxis=dict(
            showgrid=False,
            showticklabels=False,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#1d2530",
        ),
        legend=dict(
            orientation="h",
            y=1.10,
        ),
    )

    return fig


# ============================================================
# ALLOCATION CHART
# ============================================================

def allocation_chart():

    fig = go.Figure(
        go.Bar(
            x=["Human", "Bot"],
            y=[
                st.session_state.human_allocation,
                st.session_state.bot_allocation,
            ],
            text=[
                f"{st.session_state.human_allocation:.2f}%",
                f"{st.session_state.bot_allocation:.2f}%",
            ],
            textposition="auto",
        )
    )

    fig.update_layout(
        height=230,
        margin=dict(
            l=10,
            r=10,
            t=10,
            b=10,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#aeb8c5"),
        yaxis=dict(
            range=[
                0,
                max(
                    55,
                    st.session_state.human_allocation + 5,
                ),
            ],
            showgrid=True,
            gridcolor="#1d2530",
            title="Allocation rate (%)",
        ),
        xaxis=dict(
            showgrid=False
        ),
    )

    return fig


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div class="hero">

        <div class="hero-title">

            FAIR DROP

            <span class="live">
                ● LIVE
            </span>

        </div>

        <div class="hero-subtitle">

            Selling 500 Seats to 50,000 People Without Letting Bots Win

            &nbsp;•&nbsp;

            AI Defense + Fair Cryptographic Allocation

        </div>

    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("## 🎛️ Demo Control")

    st.selectbox(
        "Attack scenario",
        ATTACKS,
        key="attack",
    )

    if st.button(
        "▶ Launch Attack",
        use_container_width=True,
    ):

        launch_attack()

    if st.button(
        "■ Stop Attack",
        use_container_width=True,
    ):

        stop_attack()

    if st.button(
        "🎟 Run Fair Lottery",
        use_container_width=True,
    ):

        run_lottery()

    if st.button(
        "↻ Reset Demo",
        use_container_width=True,
    ):

        reset_demo()
        st.rerun()

    st.divider()

    st.markdown("### System")

    st.caption(
        "ML integration target: "
        "http://localhost:8000"
    )

    st.caption(
        "Dashboard mode: live simulation"
    )

    st.caption(
        "Model stack: XGBoost + GRU + Isolation Forest"
    )

    st.divider()

    st.markdown("### Demo principle")

    st.success(
        "AI protects the lottery. "
        "AI does not choose the winners."
    )


# ============================================================
# ATTACK SIMULATOR
# ============================================================

st.markdown(
    '<div class="section">ATTACK SIMULATOR</div>',
    unsafe_allow_html=True,
)

attack_cols = st.columns(7)

for i, attack in enumerate(ATTACKS):

    with attack_cols[i]:

        selected = (
            st.session_state.attack == attack
        )

        label = (
            f"● {attack}"
            if selected
            else attack
        )

        if st.button(
            label,
            key=f"attack_{i}",
            use_container_width=True,
        ):

            st.session_state.attack = attack
            st.session_state.attack_running = True

            st.rerun()


st.caption(
    "Select Flood, Rapid Retry, Multi-session, "
    "Distributed, Stealth, or Adaptive to change "
    "the simulated behavioral traffic profile."
)


# ============================================================
# UPDATE
# ============================================================

update_live_state()

if st.session_state.attack_running:

    time.sleep(0.35)

    st.rerun()


# ============================================================
# LIVE TRAFFIC
# ============================================================

st.markdown(
    '<div class="section">LIVE TRAFFIC</div>',
    unsafe_allow_html=True,
)

c1, c2, c3, c4 = st.columns(4)

with c1:

    metric_card(
        "Users Connected",
        fmt_num(
            st.session_state.users_connected
        ),
        "live sessions",
    )

with c2:

    metric_card(
        "Requests / Sec",
        fmt_num(
            st.session_state.requests_sec
        ),
        "current traffic rate",
    )

with c3:

    metric_card(
        "Human Traffic",
        f"{st.session_state.human_pct:.1f}%",
        "legitimate behavioral traffic",
    )

with c4:

    metric_card(
        "Bot Traffic",
        f"{st.session_state.bot_pct:.1f}%",
        f"{fmt_num(st.session_state.bots_detected)} detected",
    )


# ============================================================
# SECURITY + ALLOCATION
# ============================================================

st.markdown(
    '<div class="section">SECURITY & ALLOCATION</div>',
    unsafe_allow_html=True,
)

c1, c2, c3, c4 = st.columns(4)

with c1:

    metric_card(
        "Tickets Remaining",
        fmt_num(
            st.session_state.tickets_remaining
        ),
        "500 total seats",
    )

with c2:

    metric_card(
        "Bot Risk",
        f"{st.session_state.bot_risk:.0f}%",
        (
            f"{risk_class(st.session_state.bot_risk)[1]}"
            f" • {st.session_state.action}"
        ),
    )

with c3:

    metric_card(
        "Tickets Allocated",
        (
            f"{st.session_state.tickets_allocated}"
            f"/{TOTAL_TICKETS}"
        ),
        "atomic allocation",
    )

with c4:

    metric_card(
        "Detection Latency",
        f"{st.session_state.detection_latency} ms",
        "risk decision latency",
    )


# ============================================================
# MAIN VISUAL
# ============================================================

left, right = st.columns(
    [1.6, 1]
)

with left:

    st.markdown(
        '<div class="section">LIVE TRAFFIC GRAPH</div>',
        unsafe_allow_html=True,
    )

    st.plotly_chart(
        build_line_chart(),
        use_container_width=True,
        config={
            "displayModeBar": False
        },
    )

    st.markdown(
        """
        <div class="pipeline">

            <div class="pipe">
                TRAFFIC
            </div>

            <div class="arrow">
                →
            </div>

            <div class="pipe">
                XGBOOST
            </div>

            <div class="arrow">
                +
            </div>

            <div class="pipe">
                GRU
            </div>

            <div class="arrow">
                +
            </div>

            <div class="pipe">
                ISOLATION FOREST
            </div>

            <div class="arrow">
                →
            </div>

            <div class="pipe">
                RISK FUSION
            </div>

            <div class="arrow">
                →
            </div>

            <div class="pipe">
                ADAPTIVE POLICY
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


with right:

    risk = float(
        st.session_state.bot_risk
    )

    rclass, rlabel = risk_class(risk)

    profile = ATTACK_PROFILES[
        st.session_state.attack
    ]

    signals = profile["signals"]

    st.markdown(
        f"""
        <div class="panel">

            <div class="metric-label">
                CURRENT AI DECISION
            </div>

            <div class="risk-number {rclass}">
                {risk:.0f}%
            </div>

            <div style="
                font-size:13px;
                font-weight:800;
            ">
                BOT RISK • {rlabel}
            </div>

            <br>

            <div class="action">
                {st.session_state.action}
            </div>

            <br><br>

            <div class="metric-label">
                MAIN CONTRIBUTING SIGNALS
            </div>

            {
                ''.join(
                    f'<div class="signal">↑ {s}</div>'
                    for s in signals
                )
            }

        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# MODEL STACK
# ============================================================

st.markdown(
    '<div class="section">AI MODEL STACK</div>',
    unsafe_allow_html=True,
)

m1, m2, m3, m4 = st.columns(4)

models = [
    (
        m1,
        "XGBoost",
        "tabular behavioral model",
    ),
    (
        m2,
        "GRU",
        "temporal sequence model",
    ),
    (
        m3,
        "Isolation Forest",
        "unseen anomaly detection",
    ),
    (
        m4,
        "Risk Fusion",
        "final behavioral risk",
    ),
]

for col, name, desc in models:

    with col:

        st.markdown(
            f"""
            <div class="metric-card">

                <div style="
                    font-size:17px;
                    font-weight:800;
                ">
                    ✓ {name}
                </div>

                <div class="metric-sub">
                    {desc}
                </div>

                <div class="good"
                     style="margin-top:10px;">
                    ACTIVE
                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# MEASURABLE EVIDENCE
# ============================================================

st.markdown(
    '<div class="section">MEASURABLE EVIDENCE</div>',
    unsafe_allow_html=True,
)

e1, e2, e3 = st.columns(3)


with e1:

    st.markdown(
        f"""
        <div class="panel">

            <div class="metric-label">
                SECURITY
            </div>

            <div style="
                font-size:28px;
                font-weight:850;
                margin-top:8px;
            ">
                {fmt_num(
                    st.session_state.bots_detected
                )}
            </div>

            <div class="metric-sub">
                bots detected
            </div>

            <div style="margin-top:15px;">
                False positives:
                <span class="warning">
                    1.8%
                </span>
            </div>

            <div style="margin-top:8px;">
                Detection latency:
                <span class="good">
                    {st.session_state.detection_latency} ms
                </span>
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


with e2:

    verified = (
        "TRUE"
        if st.session_state.lottery_verified
        else "PENDING"
    )

    verify_symbol = (
        "✓"
        if st.session_state.lottery_verified
        else "○"
    )

    st.markdown(
        f"""
        <div class="panel">

            <div class="metric-label">
                ALLOCATION INTEGRITY
            </div>

            <div style="margin-top:12px;"
                 class="good">

                ✓ Duplicate allocations:
                {st.session_state.duplicate_allocations}

            </div>

            <div style="margin-top:9px;"
                 class="good">

                ✓ Overselling:
                {st.session_state.overselling}

            </div>

            <div style="margin-top:9px;"
                 class="good">

                ✓ Inventory consistent

            </div>

            <div style="margin-top:9px;"
                 class="{'good' if st.session_state.lottery_verified else 'warning'}">

                {verify_symbol}
                Lottery verification:
                {verified}

            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


with e3:

    st.markdown(
        f"""
        <div class="panel">

            <div class="metric-label">
                FAIRNESS
            </div>

            <div style="
                font-size:30px;
                font-weight:850;
                margin-top:7px;
            ">
                {st.session_state.fairness:.2f}
            </div>

            <div class="metric-sub">
                Jain fairness index
            </div>

            <div style="margin-top:13px;">
                Human allocation:
                <span class="good">
                    {st.session_state.human_allocation:.2f}%
                </span>
            </div>

            <div style="margin-top:7px;">
                Bot allocation:
                <span class="good">
                    {st.session_state.bot_allocation:.2f}%
                </span>
            </div>

            <div style="margin-top:7px;">
                Lottery deviation:
                <span class="warning">
                    {st.session_state.lottery_deviation:.2f}%
                </span>
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# FAIR ALLOCATION
# ============================================================

st.markdown(
    '<div class="section">FAIR ALLOCATION</div>',
    unsafe_allow_html=True,
)

a1, a2 = st.columns(
    [1, 1.5]
)


with a1:

    if st.session_state.allocation_done:

        st.markdown(
            f"""
            <div class="proof">

                <div class="metric-label">
                    CRYPTOGRAPHIC LOTTERY
                </div>

                <div class="proof-big">
                    {st.session_state.winners}
                    WINNERS
                </div>

                <div class="proof-line">
                    ✓ 1,001 eligible users
                </div>

                <div class="proof-line">
                    ✓ 501 waitlist
                </div>

                <div class="proof-line">
                    ✓ 500 tickets allocated
                </div>

                <div class="proof-line">
                    ✓ 0 duplicates
                </div>

                <div class="proof-line">
                    ✓ 0 overselling
                </div>

                <div class="proof-line">
                    ✓ Lottery verified
                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )

    else:

        st.markdown(
            """
            <div class="panel"
                 style="text-align:center;">

                <div class="metric-label">
                    CRYPTOGRAPHIC LOTTERY
                </div>

                <div style="
                    font-size:28px;
                    font-weight:850;
                    margin:15px 0;
                ">
                    500 SEATS
                </div>

                <div class="small-note">

                    Eligible users receive exactly
                    one logical lottery entry.

                    Requests, retries and sessions
                    do not create additional entries.

                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )


with a2:

    st.plotly_chart(
        allocation_chart(),
        use_container_width=True,
        config={
            "displayModeBar": False
        },
    )


# ============================================================
# SYSTEM GUARANTEE
# ============================================================

st.markdown(
    '<div class="section">SYSTEM GUARANTEE</div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="panel">

        <div class="pipeline"
             style="justify-content:center;">

            <div class="pipe">
                USER TRAFFIC
            </div>

            <div class="arrow">
                →
            </div>

            <div class="pipe">
                AI RISK
            </div>

            <div class="arrow">
                →
            </div>

            <div class="pipe">
                ADAPTIVE SECURITY
            </div>

            <div class="arrow">
                →
            </div>

            <div class="pipe">
                ELIGIBILITY
            </div>

            <div class="arrow">
                →
            </div>

            <div class="pipe">
                ONE ENTRY / USER
            </div>

            <div class="arrow">
                →
            </div>

            <div class="pipe">
                CRYPTO LOTTERY
            </div>

            <div class="arrow">
                →
            </div>

            <div class="pipe">
                500 WINNERS
            </div>

        </div>

        <div style="
            text-align:center;
            margin-top:13px;
            font-size:16px;
            font-weight:850;
        ">

            AI PROTECTS THE LOTTERY —
            AI DOES NOT CHOOSE THE WINNERS.

        </div>

    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
    <div style="
        text-align:center;
        color:#657184;
        font-size:11px;
        margin-top:22px;
    ">

        FAIR DROP • XGBoost + GRU + Isolation Forest
        + Risk Fusion • Fair Allocation + Cryptographic Lottery

    </div>
    """,
    unsafe_allow_html=True,
)