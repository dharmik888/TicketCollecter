import numpy as np
import pandas as pd
import os
import uuid
from dataclasses import dataclass, field
from collections import Counter
from typing import Optional


# ============================================================
# FAIR DROP
# Behavioral Traffic Simulator
#
# Generates realistic event sequences for:
#   1. Human
#   2. Aggressive bot
#   3. Rapid retry bot
#   4. Multi-session bot
#   5. Distributed bot
#   6. Stealth bot
#   7. Adaptive bot
#
# Pipeline:
#
# Traffic Profile
#       ↓
# Behavior Policy
#       ↓
# State Machine
#       ↓
# Event Sequence
#       ↓
# Feature Extraction
#       ↓
# ML Dataset
# ============================================================


# ============================================================
# 0. CONFIGURATION
# ============================================================

SEED = 42
rng = np.random.default_rng(SEED)

OUTPUT_DIR = "ML/data"

EVENT_OUTPUT = os.path.join(
    OUTPUT_DIR,
    "traffic_events.csv"
)

FEATURE_OUTPUT = os.path.join(
    OUTPUT_DIR,
    "traffic_behavior_dataset.csv"
)


# Number of users per traffic type
USERS_PER_TYPE = 500

# Sessions generated for normal/single-session users
MIN_SESSIONS = 1
MAX_SESSIONS = 2

# Simulation duration
SIMULATION_DURATION_SEC = 300


TRAFFIC_TYPES = [
    "human",
    "aggressive_bot",
    "rapid_retry_bot",
    "multi_session_bot",
    "distributed_bot",
    "stealth_bot",
    "adaptive_bot"
]


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


SESSION_STATES = [
    "BROWSING",
    "QUEUE",
    "REQUESTING",
    "RETRYING",
    "DISCONNECTED",
    "COMPLETED",
    "ABANDONED"
]


# ============================================================
# 1. EVENT OBJECT
# ============================================================

@dataclass
class Event:

    timestamp: float

    session_id: str
    user_id: str

    event_type: str

    inter_event_time_ms: float

    request_status: str = "none"

    retry_count: int = 0
    request_number: int = 0

    active_sessions: int = 1

    queue_position: int = -1

    session_age_sec: float = 0.0

    time_since_last_request_ms: float = -1.0

    time_since_last_failure_ms: float = -1.0

    traffic_type: str = "human"

    is_bot: int = 0

    bot_cluster_id: Optional[str] = None

    # Additional behavioral information
    mouse_events: int = 0
    keyboard_events: int = 0
    scroll_events: int = 0


# ============================================================
# 2. USER
# ============================================================

@dataclass
class User:

    user_id: str

    traffic_type: str

    bot_cluster_id: Optional[str] = None

    sessions: list = field(default_factory=list)

    # Personality / behavioral parameters
    activity_level: float = 1.0

    patience: float = 1.0

    retry_tendency: float = 1.0

    human_variability: float = 1.0

    aggressiveness: float = 1.0

    adaptation_rate: float = 0.0


# ============================================================
# 3. SESSION
# ============================================================

@dataclass
class Session:

    session_id: str

    user_id: str

    traffic_type: str

    bot_cluster_id: Optional[str]

    start_time: float

    current_time: float

    state: str = "BROWSING"

    connected: bool = True

    active: bool = True

    request_count: int = 0

    retry_count: int = 0

    failure_count: int = 0

    success_count: int = 0

    reconnect_count: int = 0

    refresh_count: int = 0

    queue_join_count: int = 0

    queue_poll_count: int = 0

    mouse_events: int = 0

    keyboard_events: int = 0

    scroll_events: int = 0

    last_request_time: Optional[float] = None

    last_failure_time: Optional[float] = None

    last_event_time: Optional[float] = None

    request_times: list = field(default_factory=list)

    retry_latencies: list = field(default_factory=list)

    inter_event_times: list = field(default_factory=list)

    event_history: list = field(default_factory=list)


# ============================================================
# 4. DROP ENVIRONMENT
# ============================================================

class DropEnvironment:

    """
    Represents the ticket/seat drop environment.

    The environment changes according to traffic pressure.
    """

    def __init__(
        self,
        seat_capacity=500,
        initial_queue_capacity=10000
    ):

        self.seat_capacity = seat_capacity

        self.seats_remaining = seat_capacity

        self.queue_capacity = initial_queue_capacity

        self.active_sessions = 0

        self.total_requests = 0

        self.successful_requests = 0

        self.failed_requests = 0

        self.queue_length = 0

    # --------------------------------------------------------
    # Traffic pressure
    # --------------------------------------------------------

    @property
    def pressure(self):

        if self.active_sessions == 0:
            return 0.0

        return min(
            self.active_sessions / 5000,
            1.0
        )

    # --------------------------------------------------------
    # Request processing
    # --------------------------------------------------------

    def process_request(self):

        self.total_requests += 1

        pressure = self.pressure

        # Base failure probability
        failure_probability = (
            0.05
            + pressure * 0.40
        )

        # If seats are gone
        if self.seats_remaining <= 0:

            self.failed_requests += 1

            return "sold_out"

        # Random request outcome
        if rng.random() < failure_probability:

            self.failed_requests += 1

            return "failure"

        # Successful request
        self.successful_requests += 1

        self.seats_remaining -= 1

        return "success"

    # --------------------------------------------------------
    # Queue
    # --------------------------------------------------------

    def join_queue(self):

        self.queue_length += 1

        return self.queue_length

    def poll_queue(self):

        if self.queue_length > 0:

            # Queue slowly moves
            self.queue_length = max(
                0,
                self.queue_length - rng.integers(0, 4)
            )

        return self.queue_length


# ============================================================
# 5. UTILITY FUNCTIONS
# ============================================================

def human_delay(user):

    """
    Human reaction time.

    Uses log-normal distribution because human reaction
    times are naturally right-skewed.
    """

    base = rng.lognormal(
        mean=np.log(1.2),
        sigma=0.65
    )

    variability = rng.normal(
        1.0,
        0.25 * user.human_variability
    )

    variability = max(
        variability,
        0.25
    )

    return np.clip(
        base * variability,
        0.15,
        15.0
    )


def bot_delay(mean=0.8, variability=0.25):

    delay = rng.lognormal(
        mean=np.log(mean),
        sigma=variability
    )

    return np.clip(
        delay,
        0.05,
        15.0
    )


def generate_human_actions(user):

    activity = user.activity_level

    mouse = rng.poisson(
        max(1, 4 * activity)
    )

    keyboard = rng.poisson(
        max(1, 1.2 * activity)
    )

    scroll = rng.poisson(
        max(1, 0.7 * activity)
    )

    return mouse, keyboard, scroll


def generate_bot_actions(user):

    activity = user.activity_level

    mouse = rng.poisson(
        max(0.1, 2 * activity)
    )

    keyboard = rng.poisson(
        max(0.1, 0.5 * activity)
    )

    scroll = rng.poisson(
        max(0.1, 0.3 * activity)
    )

    return mouse, keyboard, scroll


# ============================================================
# 6. BEHAVIOR PROFILES
# ============================================================

def create_user(
    traffic_type,
    user_number,
    cluster_id=None
):

    user_id = f"user_{user_number:07d}"

    # --------------------------------------------------------
    # HUMAN
    # --------------------------------------------------------

    if traffic_type == "human":

        return User(
            user_id=user_id,
            traffic_type=traffic_type,
            activity_level=rng.lognormal(
                0,
                0.35
            ),
            patience=rng.uniform(
                0.7,
                1.5
            ),
            retry_tendency=rng.uniform(
                0.4,
                1.2
            ),
            human_variability=rng.uniform(
                0.8,
                1.3
            ),
            aggressiveness=rng.uniform(
                0.3,
                1.0
            )
        )

    # --------------------------------------------------------
    # AGGRESSIVE BOT
    # --------------------------------------------------------

    if traffic_type == "aggressive_bot":

        return User(
            user_id=user_id,
            traffic_type=traffic_type,
            activity_level=rng.uniform(
                2,
                4
            ),
            patience=rng.uniform(
                0.2,
                0.6
            ),
            retry_tendency=rng.uniform(
                1.5,
                3
            ),
            human_variability=rng.uniform(
                0.2,
                0.5
            ),
            aggressiveness=rng.uniform(
                2,
                4
            )
        )

    # --------------------------------------------------------
    # RAPID RETRY
    # --------------------------------------------------------

    if traffic_type == "rapid_retry_bot":

        return User(
            user_id=user_id,
            traffic_type=traffic_type,
            activity_level=rng.uniform(
                1,
                2.5
            ),
            patience=rng.uniform(
                0.1,
                0.4
            ),
            retry_tendency=rng.uniform(
                2,
                4
            ),
            human_variability=rng.uniform(
                0.15,
                0.4
            ),
            aggressiveness=rng.uniform(
                1,
                2
            )
        )

    # --------------------------------------------------------
    # MULTI SESSION
    # --------------------------------------------------------

    if traffic_type == "multi_session_bot":

        return User(
            user_id=user_id,
            traffic_type=traffic_type,
            activity_level=rng.uniform(
                1,
                2
            ),
            patience=rng.uniform(
                0.3,
                0.8
            ),
            retry_tendency=rng.uniform(
                1,
                2
            ),
            human_variability=rng.uniform(
                0.3,
                0.7
            ),
            aggressiveness=rng.uniform(
                1,
                2
            )
        )

    # --------------------------------------------------------
    # DISTRIBUTED
    # --------------------------------------------------------

    if traffic_type == "distributed_bot":

        return User(
            user_id=user_id,
            traffic_type=traffic_type,
            bot_cluster_id=cluster_id,
            activity_level=rng.uniform(
                0.7,
                1.3
            ),
            patience=rng.uniform(
                0.6,
                1.2
            ),
            retry_tendency=rng.uniform(
                0.8,
                1.5
            ),
            human_variability=rng.uniform(
                0.7,
                1.1
            ),
            aggressiveness=rng.uniform(
                0.7,
                1.5
            )
        )

    # --------------------------------------------------------
    # STEALTH
    # --------------------------------------------------------

    if traffic_type == "stealth_bot":

        return User(
            user_id=user_id,
            traffic_type=traffic_type,
            activity_level=rng.uniform(
                0.7,
                1.3
            ),
            patience=rng.uniform(
                0.7,
                1.3
            ),
            retry_tendency=rng.uniform(
                0.7,
                1.4
            ),
            human_variability=rng.uniform(
                0.65,
                0.95
            ),
            aggressiveness=rng.uniform(
                0.7,
                1.4
            )
        )

    # --------------------------------------------------------
    # ADAPTIVE
    # --------------------------------------------------------

    if traffic_type == "adaptive_bot":

        return User(
            user_id=user_id,
            traffic_type=traffic_type,
            activity_level=rng.uniform(
                0.8,
                1.8
            ),
            patience=rng.uniform(
                0.4,
                1.2
            ),
            retry_tendency=rng.uniform(
                1,
                2
            ),
            human_variability=rng.uniform(
                0.3,
                0.9
            ),
            aggressiveness=rng.uniform(
                1,
                2
            ),
            adaptation_rate=rng.uniform(
                0.1,
                0.4
            )
        )

    raise ValueError(
        f"Unknown traffic type: {traffic_type}"
    )


# ============================================================
# 7. SIMULATOR
# ============================================================

class TrafficSimulator:

    def __init__(self):

        self.environment = DropEnvironment()

        self.events = []

        self.sessions = []

        self.users = []

        self.current_time = 0.0

    # --------------------------------------------------------
    # Record event
    # --------------------------------------------------------

    def record_event(
    self,
    session,
    event_type,
    inter_event_time=0,
    request_status="none",
    queue_position=-1
):

        now = session.current_time

        if session.last_event_time is None:

            inter_event = 0

        else:

            inter_event = (
                now -
                session.last_event_time
            ) * 1000

        if (
            session.last_request_time
            is not None
        ):

            time_since_request = (
                now -
                session.last_request_time
            ) * 1000

        else:

            time_since_request = -1

        if (
            session.last_failure_time
            is not None
        ):

            time_since_failure = (
                now -
                session.last_failure_time
            ) * 1000

        else:

            time_since_failure = -1

        event = Event(

            timestamp=now,

            session_id=session.session_id,

            user_id=session.user_id,

            event_type=event_type,

            inter_event_time_ms=inter_event,

            request_status=request_status,

            retry_count=session.retry_count,

            request_number=session.request_count,

            active_sessions=self.environment.active_sessions,

            queue_position=queue_position,

            session_age_sec=(
                now -
                session.start_time
            ),

            time_since_last_request_ms=(
                time_since_request
            ),

            time_since_last_failure_ms=(
                time_since_failure
            ),

            traffic_type=session.traffic_type,

            is_bot=int(
                session.traffic_type
                != "human"
            ),

            bot_cluster_id=(
                session.bot_cluster_id
            ),

            mouse_events=session.mouse_events,

            keyboard_events=session.keyboard_events,

            scroll_events=session.scroll_events
        )

        self.events.append(event)

        session.event_history.append(
            event_type
        )

        session.inter_event_times.append(
            inter_event
        )

        session.last_event_time = now

    # --------------------------------------------------------
    # Advance time
    # --------------------------------------------------------

    def advance_time(
        self,
        session,
        delay
    ):

        session.current_time += delay

    # --------------------------------------------------------
    # Start session
    # --------------------------------------------------------

    def start_session(
        self,
        user,
        session_number=0
    ):

        session_id = (
            f"session_"
            f"{uuid.uuid4().hex[:10]}"
        )

        session = Session(

            session_id=session_id,

            user_id=user.user_id,

            traffic_type=user.traffic_type,

            bot_cluster_id=user.bot_cluster_id,

            start_time=self.current_time,

            current_time=self.current_time
        )

        self.sessions.append(
            session
        )

        user.sessions.append(
            session
        )

        self.environment.active_sessions += 1

        self.record_event(
            session,
            "session_start",
            0
        )

        return session

    # ========================================================
    # HUMAN SESSION
    # ========================================================

    def simulate_human(
        self,
        user,
        session
    ):

        max_events = rng.integers(
            10,
            45
        )

        for _ in range(max_events):

            if not session.active:
                break

            # ----------------------------------------------
            # Human delay
            # ----------------------------------------------

            delay = human_delay(user)

            self.advance_time(
                session,
                delay
            )

            # ----------------------------------------------
            # Human actions
            # ----------------------------------------------

            mouse, keyboard, scroll = (
                generate_human_actions(user)
            )

            session.mouse_events += mouse
            session.keyboard_events += keyboard
            session.scroll_events += scroll

            # ----------------------------------------------
            # Occasionally browse
            # ----------------------------------------------

            probability = rng.random()

            if probability < 0.20:

                self.record_event(
                    session,
                    "wait"
                )

                continue

            # ----------------------------------------------
            # Refresh
            # ----------------------------------------------

            if probability < 0.25:

                session.refresh_count += 1

                self.record_event(
                    session,
                    "refresh"
                )

                continue

            # ----------------------------------------------
            # Queue join
            # ----------------------------------------------

            if probability < 0.40:

                position = (
                    self.environment.join_queue()
                )

                session.queue_join_count += 1

                self.record_event(
                    session,
                    "queue_join",
                    queue_position=position
                )

                continue

            # ----------------------------------------------
            # Queue poll
            # ----------------------------------------------

            if probability < 0.50:

                position = (
                    self.environment.poll_queue()
                )

                session.queue_poll_count += 1

                self.record_event(
                    session,
                    "queue_poll",
                    queue_position=position
                )

                continue

            # ----------------------------------------------
            # Request
            # ----------------------------------------------

            self.make_request(
                user,
                session
            )

            # ----------------------------------------------
            # Humans sometimes abandon
            # ----------------------------------------------

            if (
                rng.random()
                < 0.025 * user.patience
            ):

                session.state = "ABANDONED"

                break

        self.end_session(
            session
        )

    # ========================================================
    # REQUEST
    # ========================================================

    def make_request(
        self,
        user,
        session
    ):

        session.request_count += 1

        session.request_times.append(
            session.current_time
        )

        self.record_event(
            session,
            "request"
        )

        status = (
            self.environment.process_request()
        )

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        if status == "success":

            session.success_count += 1

            session.last_request_time = (
                session.current_time
            )

            self.record_event(
                session,
                "request_success",
                request_status="success"
            )

            return True

        # ----------------------------------------------------
        # SOLD OUT
        # ----------------------------------------------------

        if status == "sold_out":

            session.failure_count += 1

            session.last_failure_time = (
                session.current_time
            )

            self.record_event(
                session,
                "request_failure",
                request_status="sold_out"
            )

            session.active = False

            return False

        # ----------------------------------------------------
        # FAILURE
        # ----------------------------------------------------

        session.failure_count += 1

        session.last_failure_time = (
            session.current_time
        )

        self.record_event(
            session,
            "request_failure",
            request_status="failure"
        )

        return False

    # ========================================================
    # AGGRESSIVE BOT
    # ========================================================

    def simulate_aggressive_bot(
        self,
        user,
        session
    ):

        max_events = rng.integers(
            30,
            80
        )

        for _ in range(max_events):

            delay = bot_delay(
                mean=0.25,
                variability=0.20
            )

            self.advance_time(
                session,
                delay
            )

            self.make_request(
                user,
                session
            )

            # Aggressive bot retries almost immediately

            if (
                session.failure_count > 0
                and rng.random() < 0.75
            ):

                session.retry_count += 1

                self.record_event(
                    session,
                    "retry"
                )

            if rng.random() < 0.08:

                session.refresh_count += 1

                self.record_event(
                    session,
                    "refresh"
                )

        self.end_session(
            session
        )

    # ========================================================
    # RAPID RETRY BOT
    # ========================================================

    def simulate_rapid_retry_bot(
        self,
        user,
        session
    ):

        max_events = rng.integers(
            20,
            60
        )

        for _ in range(max_events):

            delay = bot_delay(
                mean=0.45,
                variability=0.25
            )

            self.advance_time(
                session,
                delay
            )

            success = self.make_request(
                user,
                session
            )

            if not success:

                retry_delay = rng.uniform(
                    0.05,
                    0.5
                )

                self.advance_time(
                    session,
                    retry_delay
                )

                session.retry_count += 1

                retry_latency = (
                    retry_delay * 1000
                )

                session.retry_latencies.append(
                    retry_latency
                )

                self.record_event(
                    session,
                    "retry"
                )

        self.end_session(
            session
        )

    # ========================================================
    # MULTI SESSION BOT
    # ========================================================

    def simulate_multi_session_user(
        self,
        user
    ):

        number_sessions = rng.integers(
            3,
            8
        )

        sessions = []

        for i in range(
            number_sessions
        ):

            sessions.append(
                self.start_session(
                    user,
                    i
                )
            )

        # Interleave activity across sessions

        max_rounds = rng.integers(
            15,
            35
        )

        for _ in range(max_rounds):

            for session in sessions:

                if not session.active:
                    continue

                delay = bot_delay(
                    mean=0.5,
                    variability=0.35
                )

                self.advance_time(
                    session,
                    delay
                )

                self.make_request(
                    user,
                    session
                )

                if rng.random() < 0.25:

                    session.retry_count += 1

                    self.record_event(
                        session,
                        "retry"
                    )

        for session in sessions:

            self.end_session(
                session
            )

    # ========================================================
    # DISTRIBUTED BOT
    # ========================================================

    def simulate_distributed_users(
        self,
        users
    ):

        """
        All users belong to the same coordinated cluster.

        Individual sessions remain relatively normal.

        The coordination occurs across users.
        """

        sessions = []

        for user in users:

            session = self.start_session(
                user
            )

            sessions.append(
                session
            )

        rounds = rng.integers(
            15,
            30
        )

        for _ in range(rounds):

            # Cluster-level synchronization
            cluster_delay = rng.uniform(
                1,
                5
            )

            for session in sessions:

                if not session.active:
                    continue

                # Individual jitter
                jitter = rng.normal(
                    0,
                    0.5
                )

                delay = max(
                    0.2,
                    cluster_delay + jitter
                )

                self.advance_time(
                    session,
                    delay
                )

                self.make_request(
                    None,
                    session
                )

        for session in sessions:

            self.end_session(
                session
            )

    # ========================================================
    # STEALTH BOT
    # ========================================================

    def simulate_stealth_bot(
        self,
        user,
        session
    ):

        max_events = rng.integers(
            15,
            45
        )

        for _ in range(max_events):

            # Human-like timing
            delay = human_delay(user)

            # But slightly lower variability
            delay *= rng.uniform(
                0.85,
                1.15
            )

            self.advance_time(
                session,
                delay
            )

            # Human-like actions
            mouse, keyboard, scroll = (
                generate_human_actions(user)
            )

            session.mouse_events += mouse
            session.keyboard_events += keyboard
            session.scroll_events += scroll

            probability = rng.random()

            if probability < 0.15:

                self.record_event(
                    session,
                    "wait"
                )

            elif probability < 0.22:

                session.refresh_count += 1

                self.record_event(
                    session,
                    "refresh"
                )

            elif probability < 0.35:

                position = (
                    self.environment.join_queue()
                )

                session.queue_join_count += 1

                self.record_event(
                    session,
                    "queue_join",
                    queue_position=position
                )

            else:

                self.make_request(
                    user,
                    session
                )

            # Bot attempts to remain successful
            # without obvious bursts.

        self.end_session(
            session
        )

    # ========================================================
    # ADAPTIVE BOT
    # ========================================================

    def simulate_adaptive_bot(
        self,
        user,
        session
    ):

        rate = 1.0

        max_events = rng.integers(
            25,
            70
        )

        previous_failures = 0

        for _ in range(max_events):

            # ----------------------------------------------
            # Adapt based on previous failure rate
            # ----------------------------------------------

            recent_failures = (
                session.failure_count
                - previous_failures
            )

            previous_failures = (
                session.failure_count
            )

            if recent_failures >= 2:

                # Server appears hostile/congested
                rate *= (
                    1 -
                    user.adaptation_rate
                )

            else:

                # Slowly increase pressure
                rate *= (
                    1 +
                    user.adaptation_rate * 0.35
                )

            rate = np.clip(
                rate,
                0.25,
                3.0
            )

            # Higher rate = shorter delay

            mean_delay = (
                1.5 / rate
            )

            delay = bot_delay(
                mean=mean_delay,
                variability=0.45
            )

            self.advance_time(
                session,
                delay
            )

            # Sometimes intentionally behave
            # like a human

            if rng.random() < 0.15:

                mouse, keyboard, scroll = (
                    generate_human_actions(user)
                )

                session.mouse_events += mouse
                session.keyboard_events += keyboard
                session.scroll_events += scroll

                self.record_event(
                    session,
                    "wait"
                )

            else:

                self.make_request(
                    user,
                    session
                )

            # Reconnect occasionally

            if (
                session.failure_count > 0
                and rng.random() < 0.08
            ):

                session.reconnect_count += 1

                session.connected = False

                self.record_event(
                    session,
                    "reconnect"
                )

                self.advance_time(
                    session,
                    rng.uniform(
                        0.5,
                        3
                    )
                )

                session.connected = True

        self.end_session(
            session
        )

    # ========================================================
    # END SESSION
    # ========================================================

    def end_session(
        self,
        session
    ):

        if not session.active:
            return

        session.state = "COMPLETED"

        self.record_event(
            session,
            "session_end"
        )

        session.active = False

        self.environment.active_sessions = max(
            0,
            self.environment.active_sessions - 1
        )

    # ========================================================
    # RUN SINGLE SESSION
    # ========================================================

    def run_user(
        self,
        user
    ):

        traffic_type = user.traffic_type

        # Multi-session is handled separately

        if traffic_type == "multi_session_bot":

            self.simulate_multi_session_user(
                user
            )

            return

        session = self.start_session(
            user
        )

        if traffic_type == "human":

            self.simulate_human(
                user,
                session
            )

        elif traffic_type == "aggressive_bot":

            self.simulate_aggressive_bot(
                user,
                session
            )

        elif traffic_type == "rapid_retry_bot":

            self.simulate_rapid_retry_bot(
                user,
                session
            )

        elif traffic_type == "stealth_bot":

            self.simulate_stealth_bot(
                user,
                session
            )

        elif traffic_type == "adaptive_bot":

            self.simulate_adaptive_bot(
                user,
                session
            )

        else:

            self.end_session(
                session
            )

    # ========================================================
    # RUN SIMULATION
    # ========================================================

    def run(
        self,
        users_per_type=USERS_PER_TYPE
    ):

        user_counter = 0

        # ----------------------------------------------------
        # Normal traffic
        # ----------------------------------------------------

        for traffic_type in [
            "human",
            "aggressive_bot",
            "rapid_retry_bot",
            "multi_session_bot",
            "stealth_bot",
            "adaptive_bot"
        ]:

            for _ in range(
                users_per_type
            ):

                user = create_user(
                    traffic_type,
                    user_counter
                )

                user_counter += 1

                self.users.append(
                    user
                )

                self.run_user(
                    user
                )

        # ----------------------------------------------------
        # Distributed traffic
        # ----------------------------------------------------

        cluster_id = "cluster_001"

        distributed_users = []

        for _ in range(
            users_per_type
        ):

            user = create_user(
                "distributed_bot",
                user_counter,
                cluster_id
            )

            user_counter += 1

            self.users.append(
                user
            )

            distributed_users.append(
                user
            )

        self.simulate_distributed_users(
            distributed_users
        )

        return self.events


# ============================================================
# 8. EVENT DATAFRAME
# ============================================================

def events_to_dataframe(
    events
):

    rows = []

    for event in events:

        rows.append({

            "timestamp":
                event.timestamp,

            "session_id":
                event.session_id,

            "user_id":
                event.user_id,

            "bot_cluster_id":
                event.bot_cluster_id,

            "event_type":
                event.event_type,

            "inter_event_time_ms":
                event.inter_event_time_ms,

            "request_status":
                event.request_status,

            "retry_count":
                event.retry_count,

            "request_number":
                event.request_number,

            "active_sessions":
                event.active_sessions,

            "queue_position":
                event.queue_position,

            "session_age_sec":
                event.session_age_sec,

            "time_since_last_request_ms":
                event.time_since_last_request_ms,

            "time_since_last_failure_ms":
                event.time_since_last_failure_ms,

            "mouse_events":
                event.mouse_events,

            "keyboard_events":
                event.keyboard_events,

            "scroll_events":
                event.scroll_events,

            "traffic_type":
                event.traffic_type,

            "is_bot":
                event.is_bot
        })

    df = pd.DataFrame(rows)

    return df


# ============================================================
# 9. FEATURE ENGINEERING
# ============================================================

def calculate_entropy(values):

    if len(values) == 0:
        return 0.0

    counts = Counter(values)

    probabilities = np.array(
        list(counts.values()),
        dtype=float
    )

    probabilities /= probabilities.sum()

    return float(
        -np.sum(
            probabilities *
            np.log2(probabilities)
        )
    )


def safe_cv(values):

    values = np.asarray(
        values,
        dtype=float
    )

    values = values[
        values >= 0
    ]

    if len(values) < 2:
        return 0.0

    mean = values.mean()

    if mean == 0:
        return 0.0

    return float(
        values.std() /
        mean
    )


def extract_session_features(
    event_df
):

    feature_rows = []

    for session_id, group in event_df.groupby(
        "session_id"
    ):

        group = group.sort_values(
            "timestamp"
        )

        traffic_type = (
            group["traffic_type"]
            .iloc[0]
        )

        user_id = (
            group["user_id"]
            .iloc[0]
        )

        is_bot = (
            group["is_bot"]
            .iloc[0]
        )

        # ----------------------------------------------------
        # Request features
        # ----------------------------------------------------

        requests = (
            group["event_type"]
            == "request"
        ).sum()

        successes = (
            group["request_status"]
            == "success"
        ).sum()

        failures = (
            group["request_status"]
            .isin(
                ["failure", "sold_out"]
            )
        ).sum()

        retries = (
            group["event_type"]
            == "retry"
        ).sum()

        refreshes = (
            group["event_type"]
            == "refresh"
        ).sum()

        reconnects = (
            group["event_type"]
            == "reconnect"
        ).sum()

        queue_joins = (
            group["event_type"]
            == "queue_join"
        ).sum()

        queue_polls = (
            group["event_type"]
            == "queue_poll"
        ).sum()

        # ----------------------------------------------------
        # Timing
        # ----------------------------------------------------

        inter_times = (
            group[
                "inter_event_time_ms"
            ]
            .values
        )

        positive_times = inter_times[
            inter_times > 0
        ]

        if len(positive_times) > 0:

            avg_inter_event = (
                positive_times.mean()
            )

            std_inter_event = (
                positive_times.std()
            )

            timing_cv = safe_cv(
                positive_times
            )

            timing_entropy = (
                calculate_entropy(
                    np.round(
                        positive_times,
                        -2
                    )
                )
            )

        else:

            avg_inter_event = 0
            std_inter_event = 0
            timing_cv = 0
            timing_entropy = 0

        # ----------------------------------------------------
        # Session duration
        # ----------------------------------------------------

        duration = (
            group["timestamp"].max()
            -
            group["timestamp"].min()
        )

        # ----------------------------------------------------
        # Request rate
        # ----------------------------------------------------

        if duration > 0:

            requests_per_second = (
                requests /
                duration
            )

        else:

            requests_per_second = 0

        # ----------------------------------------------------
        # Burstiness
        # ----------------------------------------------------

        request_times = (
            group.loc[
                group["event_type"]
                == "request",
                "timestamp"
            ]
            .values
        )

        if len(request_times) >= 2:

            request_intervals = np.diff(
                request_times
            )

            request_interval_cv = (
                safe_cv(
                    request_intervals
                )
            )

        else:

            request_interval_cv = 0

        # ----------------------------------------------------
        # Retry behavior
        # ----------------------------------------------------

        retry_latencies = (
            group[
                "time_since_last_failure_ms"
            ]

        )

        retry_latencies = retry_latencies[
            retry_latencies >= 0
        ]

        if len(retry_latencies) > 0:

            mean_retry_latency = (
                retry_latencies.mean()
            )

            retry_latency_std = (
                retry_latencies.std()
            )

        else:

            mean_retry_latency = 0

            retry_latency_std = 0

        # ----------------------------------------------------
        # Human interaction
        # ----------------------------------------------------

        mouse = (
            group["mouse_events"]
            .sum()
        )

        keyboard = (
            group["keyboard_events"]
            .sum()
        )

        scroll = (
            group["scroll_events"]
            .sum()
        )

        total_human_actions = (
            mouse +
            keyboard +
            scroll
        )

        if requests > 0:

            human_action_ratio = (
                total_human_actions /
                requests
            )

        else:

            human_action_ratio = 0

        # ----------------------------------------------------
        # Event entropy
        # ----------------------------------------------------

        event_entropy = calculate_entropy(
            group["event_type"]
        )

        # ----------------------------------------------------
        # Burst score
        # ----------------------------------------------------

        if duration > 0:

            first_half = (
                group[
                    group["timestamp"]
                    <
                    (
                        group["timestamp"].min()
                        +
                        duration / 2
                    )
                ]
            )

            second_half = (
                group[
                    group["timestamp"]
                    >=
                    (
                        group["timestamp"].min()
                        +
                        duration / 2
                    )
                ]
            )

            first_requests = (
                first_half["event_type"]
                == "request"
            ).sum()

            second_requests = (
                second_half["event_type"]
                == "request"
            ).sum()

            burstiness = (
                abs(
                    first_requests -
                    second_requests
                )
                /
                max(
                    requests,
                    1
                )
            )

        else:

            burstiness = 0

        # ----------------------------------------------------
        # Cross-session information
        # ----------------------------------------------------

        user_session_count = (
            event_df[
                event_df["user_id"]
                == user_id
            ]["session_id"]
            .nunique()
        )

        # ----------------------------------------------------
        # Active session statistics
        # ----------------------------------------------------

        peak_active_sessions = (
            group[
                "active_sessions"
            ].max()
        )

        mean_active_sessions = (
            group[
                "active_sessions"
            ].mean()
        )

        # ----------------------------------------------------
        # Request/action relationship
        # ----------------------------------------------------

        if total_human_actions > 0:

            request_action_ratio = (
                requests /
                total_human_actions
            )

        else:

            request_action_ratio = (
                float(requests)
            )

        # ----------------------------------------------------
        # Save row
        # ----------------------------------------------------

        feature_rows.append({

            "session_id":
                session_id,

            "user_id":
                user_id,

            "traffic_type":
                traffic_type,

            "bot_cluster_id":
                group[
                    "bot_cluster_id"
                ].iloc[0],

            "requests":
                requests,

            "successful_requests":
                successes,

            "failed_requests":
                failures,

            "retry_count":
                retries,

            "refresh_count":
                refreshes,

            "reconnect_count":
                reconnects,

            "queue_join_count":
                queue_joins,

            "queue_poll_count":
                queue_polls,

            "requests_per_second":
                requests_per_second,

            "session_duration_sec":
                duration,

            "avg_inter_event_ms":
                avg_inter_event,

            "std_inter_event_ms":
                std_inter_event,

            "timing_cv":
                timing_cv,

            "timing_entropy":
                timing_entropy,

            "request_interval_cv":
                request_interval_cv,

            "mean_retry_latency_ms":
                mean_retry_latency,

            "retry_latency_std_ms":
                retry_latency_std,

            "event_entropy":
                event_entropy,

            "burstiness_score":
                burstiness,

            "mouse_events":
                mouse,

            "keyboard_events":
                keyboard,

            "scroll_events":
                scroll,

            "human_action_ratio":
                human_action_ratio,

            "request_action_ratio":
                request_action_ratio,

            "user_session_count":
                user_session_count,

            "peak_active_sessions":
                peak_active_sessions,

            "mean_active_sessions":
                mean_active_sessions,

            "success_rate":
                successes /
                max(
                    requests,
                    1
                ),

            "failure_rate":
                failures /
                max(
                    requests,
                    1
                ),

            "retry_rate":
                retries /
                max(
                    requests,
                    1
                ),

            "reconnect_rate":
                reconnects /
                max(
                    duration,
                    1
                ),

            "is_bot":
                is_bot
        })

    return pd.DataFrame(
        feature_rows
    )


# ============================================================
# 10. CROSS-SESSION FEATURES
# ============================================================

def add_cross_session_features(
    feature_df
):

    # --------------------------------------------------------
    # Number of sessions belonging to same user
    # --------------------------------------------------------

    session_counts = (
        feature_df
        .groupby("user_id")
        ["session_id"]
        .nunique()
        .rename(
            "sessions_per_user"
        )
    )

    feature_df = feature_df.merge(
        session_counts,
        on="user_id",
        how="left"
    )

    # --------------------------------------------------------
    # Cluster size
    # --------------------------------------------------------

    cluster_counts = (
        feature_df[
            feature_df[
                "bot_cluster_id"
            ].notna()
        ]
        .groupby(
            "bot_cluster_id"
        )["user_id"]
        .nunique()
        .rename(
            "cluster_size"
        )
    )

    feature_df = feature_df.merge(
        cluster_counts,
        on="bot_cluster_id",
        how="left"
    )

    feature_df[
        "cluster_size"
    ] = feature_df[
        "cluster_size"
    ].fillna(0)

    # --------------------------------------------------------
    # Multi-session flag
    # --------------------------------------------------------

    feature_df[
        "multi_session_behavior"
    ] = (
        feature_df[
            "sessions_per_user"
        ] > 1
    ).astype(int)

    # --------------------------------------------------------
    # Coordination signal
    #
    # Distributed bots have a cluster-level pattern.
    # --------------------------------------------------------

    cluster_stats = (
        feature_df[
            feature_df[
                "bot_cluster_id"
            ].notna()
        ]
        .groupby(
            "bot_cluster_id"
        )[
            "requests_per_second"
        ]
        .transform("std")
    )

    feature_df[
        "cluster_request_rate_std"
    ] = cluster_stats.fillna(0)

    return feature_df


# ============================================================
# 11. VALIDATION
# ============================================================

def validate_dataset(
    event_df,
    feature_df
):

    print("\n")
    print("=" * 70)
    print("SIMULATION VALIDATION")
    print("=" * 70)

    print(
        "\nEvent dataset shape:",
        event_df.shape
    )

    print(
        "Feature dataset shape:",
        feature_df.shape
    )

    print(
        "\nTraffic distribution:"
    )

    print(
        feature_df[
            "traffic_type"
        ].value_counts()
    )

    print(
        "\nBinary distribution:"
    )

    print(
        feature_df[
            "is_bot"
        ].value_counts()
    )

    print(
        "\nAverage behavior:"
    )

    columns = [

        "requests_per_second",

        "retry_rate",

        "failure_rate",

        "timing_cv",

        "timing_entropy",

        "mean_retry_latency_ms",

        "event_entropy",

        "burstiness_score",

        "human_action_ratio",

        "sessions_per_user"
    ]

    print(
        feature_df
        .groupby(
            "traffic_type"
        )[columns]
        .mean()
        .round(3)
    )

    print(
        "\nMissing values:"
    )

    print(
        feature_df
        .isna()
        .sum()
        .sort_values(
            ascending=False
        )
        .head(20)
    )


# ============================================================
# 12. MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("FAIR DROP TRAFFIC SIMULATOR")
    print("=" * 70)

    print(
        "\nGenerating behavioral traffic..."
    )

    simulator = TrafficSimulator()

    events = simulator.run(
        users_per_type=USERS_PER_TYPE
    )

    # --------------------------------------------------------
    # Event dataset
    # --------------------------------------------------------

    event_df = events_to_dataframe(
        events
    )

    # --------------------------------------------------------
    # Feature dataset
    # --------------------------------------------------------

    feature_df = extract_session_features(
        event_df
    )

    feature_df = add_cross_session_features(
        feature_df
    )

    # --------------------------------------------------------
    # Create output directory
    # --------------------------------------------------------

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    event_df.to_csv(
        EVENT_OUTPUT,
        index=False
    )

    feature_df.to_csv(
        FEATURE_OUTPUT,
        index=False
    )

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    validate_dataset(
        event_df,
        feature_df
    )

    print()
    print(
        f"Event data saved to:\n"
        f"{EVENT_OUTPUT}"
    )

    print()
    print(
        f"Feature data saved to:\n"
        f"{FEATURE_OUTPUT}"
    )

    print()
    print("=" * 70)
    print("SIMULATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":

    main()