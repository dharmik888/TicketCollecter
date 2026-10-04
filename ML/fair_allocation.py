"""
FAIR DROP - FAIR ALLOCATION ENGINE
===================================

Purpose:
    Allocate a fixed number of tickets fairly without allowing:
        - request speed to determine winners
        - request flooding to create extra chances
        - duplicate registrations
        - duplicate ticket allocation
        - overselling

Core principle:
    ML DOES NOT SELECT TICKET WINNERS.

    ML / Risk Policy
          |
          v
    Eligible / Not Eligible
          |
          v
    Fair Allocation Engine
          |
          v
    Cryptographically randomized lottery
          |
          v
    Atomic ticket allocation

Allocation model:
    1. Registration window
    2. One entry per user per drop
    3. Registration freeze
    4. Cryptographically secure random lottery
    5. Winners + waitlist
    6. Atomic inventory allocation
    7. Idempotent ticket assignment
    8. Audit trail
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
import uuid

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_SEATS = 500

DEFAULT_REGISTRATION_WINDOW_SECONDS = 60

# Maximum number of requests that can be accepted from a
# logical participant during the registration window.
#
# IMPORTANT:
# This is NOT the number of lottery entries.
# A user still receives only ONE lottery entry.
MAX_REQUESTS_PER_USER = 30


# ============================================================
# ENUMS
# ============================================================

class DropStatus(str, Enum):
    CREATED = "CREATED"
    OPEN = "OPEN"
    FROZEN = "FROZEN"
    ALLOCATED = "ALLOCATED"
    CLOSED = "CLOSED"


class EntryStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    WINNER = "WINNER"
    WAITLIST = "WAITLIST"
    INVALIDATED = "INVALIDATED"


class TicketStatus(str, Enum):
    RESERVED = "RESERVED"
    CONFIRMED = "CONFIRMED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class LotteryEntry:
    user_id: str
    drop_id: str

    registered_at: float

    request_count: int = 1

    status: EntryStatus = EntryStatus.ELIGIBLE

    # Generated only after registration closes.
    random_key: Optional[str] = None

    # Used for auditing.
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class Ticket:
    ticket_id: str
    user_id: str
    drop_id: str

    status: TicketStatus

    allocated_at: float

    # Optional payment expiry.
    expires_at: Optional[float] = None


@dataclass
class AllocationResult:
    drop_id: str

    total_eligible: int

    seats_available: int

    winners: List[str]

    waitlist: List[str]

    tickets_allocated: int

    lottery_seed_commitment: str

    allocation_timestamp: float


@dataclass
class AuditEvent:
    event_type: str
    drop_id: str
    user_id: Optional[str]

    timestamp: float

    details: Dict = field(default_factory=dict)


# ============================================================
# FAIR ALLOCATION ENGINE
# ============================================================

class FairAllocationEngine:

    def __init__(
        self,
        seats: int = DEFAULT_SEATS,
        registration_window_seconds: int = DEFAULT_REGISTRATION_WINDOW_SECONDS,
    ):
        if seats <= 0:
            raise ValueError("seats must be greater than zero")

        if registration_window_seconds <= 0:
            raise ValueError(
                "registration_window_seconds must be greater than zero"
            )

        self.seats = seats
        self.registration_window_seconds = registration_window_seconds

        # ----------------------------------------------------
        # DROP STATE
        # ----------------------------------------------------

        self.drop_status: DropStatus = DropStatus.CREATED

        self.drop_id: Optional[str] = None

        self.registration_start: Optional[float] = None
        self.registration_end: Optional[float] = None

        # ----------------------------------------------------
        # PARTICIPANTS
        # ----------------------------------------------------

        # Key:
        #     (drop_id, user_id)
        #
        # This guarantees one logical entry per user/drop.

        self.entries: Dict[Tuple[str, str], LotteryEntry] = {}

        # ----------------------------------------------------
        # TICKETS
        # ----------------------------------------------------

        self.tickets: Dict[str, Ticket] = {}

        # Key:
        #     (drop_id, user_id)
        #
        # Prevents duplicate allocation.

        self.user_tickets: Dict[Tuple[str, str], str] = {}

        # ----------------------------------------------------
        # AUDIT
        # ----------------------------------------------------

        self.audit_log: List[AuditEvent] = []

        # ----------------------------------------------------
        # LOTTERY
        # ----------------------------------------------------

        self._lottery_seed: Optional[bytes] = None

        self._lottery_seed_commitment: Optional[str] = None

        # ----------------------------------------------------
        # THREAD SAFETY
        # ----------------------------------------------------

        self._lock = threading.RLock()


    # ========================================================
    # UTILITY
    # ========================================================

    @staticmethod
    def _now() -> float:
        return time.time()


    @staticmethod
    def _iso(timestamp: Optional[float] = None) -> str:

        if timestamp is None:
            timestamp = time.time()

        return datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc
        ).isoformat()


    def _audit(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        **details,
    ):

        self.audit_log.append(
            AuditEvent(
                event_type=event_type,
                drop_id=self.drop_id or "",
                user_id=user_id,
                timestamp=self._now(),
                details=details,
            )
        )


    # ========================================================
    # DROP CREATION
    # ========================================================

    def create_drop(
        self,
        drop_id: str,
        seats: Optional[int] = None,
    ) -> Dict:

        with self._lock:

            if self.drop_status != DropStatus.CREATED:
                raise RuntimeError(
                    "A drop has already been created."
                )

            if not drop_id:
                raise ValueError("drop_id cannot be empty")

            if seats is not None:

                if seats <= 0:
                    raise ValueError(
                        "seats must be greater than zero"
                    )

                self.seats = seats

            self.drop_id = drop_id

            self._audit(
                "DROP_CREATED",
                seats=self.seats,
            )

            return {
                "drop_id": self.drop_id,
                "seats": self.seats,
                "status": self.drop_status.value,
            }


    # ========================================================
    # OPEN REGISTRATION
    # ========================================================

    def open_registration(self) -> Dict:

        with self._lock:

            if self.drop_status != DropStatus.CREATED:
                raise RuntimeError(
                    "Registration can only be opened from CREATED state."
                )

            now = self._now()

            self.registration_start = now

            self.registration_end = (
                now + self.registration_window_seconds
            )

            self.drop_status = DropStatus.OPEN

            self._audit(
                "REGISTRATION_OPENED",
                registration_start=self._iso(
                    self.registration_start
                ),
                registration_end=self._iso(
                    self.registration_end
                ),
            )

            return {
                "drop_id": self.drop_id,
                "status": self.drop_status.value,
                "registration_start": self._iso(
                    self.registration_start
                ),
                "registration_end": self._iso(
                    self.registration_end
                ),
            }


    # ========================================================
    # REGISTRATION WINDOW CHECK
    # ========================================================

    def is_registration_open(self) -> bool:

        if self.drop_status != DropStatus.OPEN:
            return False

        if self.registration_end is None:
            return False

        return self._now() <= self.registration_end


    # ========================================================
    # REGISTER USER
    # ========================================================

    def register_user(
        self,
        user_id: str,
        eligible: bool = True,
        verification_passed: bool = True,
    ) -> Dict:

        """
        Register a user for the lottery.

        IMPORTANT:

        This function does NOT calculate ML risk.

        The ML/policy layer should already have produced:

            eligible = True / False

        The allocation engine only receives the eligibility decision.

        Repeated requests from the same user do NOT create
        additional lottery entries.
        """

        with self._lock:

            if self.drop_status != DropStatus.OPEN:

                return {
                    "success": False,
                    "reason": "REGISTRATION_NOT_OPEN",
                }

            if not self.is_registration_open():

                return {
                    "success": False,
                    "reason": "REGISTRATION_WINDOW_CLOSED",
                }

            if not user_id:

                return {
                    "success": False,
                    "reason": "INVALID_USER",
                }

            if not verification_passed:

                self._audit(
                    "REGISTRATION_REJECTED",
                    user_id=user_id,
                    reason="VERIFICATION_FAILED",
                )

                return {
                    "success": False,
                    "reason": "VERIFICATION_FAILED",
                }

            # ------------------------------------------------
            # Eligibility comes from the policy/security layer.
            # ------------------------------------------------

            if not eligible:

                self._audit(
                    "REGISTRATION_REJECTED",
                    user_id=user_id,
                    reason="NOT_ELIGIBLE",
                )

                return {
                    "success": False,
                    "reason": "NOT_ELIGIBLE",
                }

            key = (self.drop_id, user_id)

            # ------------------------------------------------
            # EXISTING USER
            # ------------------------------------------------

            if key in self.entries:

                entry = self.entries[key]

                entry.request_count += 1

                # Flooding does not create more entries.
                if entry.request_count > MAX_REQUESTS_PER_USER:

                    self._audit(
                        "REQUEST_FLOOD_DETECTED",
                        user_id=user_id,
                        request_count=entry.request_count,
                    )

                    return {
                        "success": True,
                        "registered": True,
                        "new_entry": False,
                        "reason": "ENTRY_ALREADY_EXISTS",
                        "request_count": entry.request_count,
                    }

                self._audit(
                    "DUPLICATE_REGISTRATION_ATTEMPT",
                    user_id=user_id,
                    request_count=entry.request_count,
                )

                return {
                    "success": True,
                    "registered": True,
                    "new_entry": False,
                    "reason": "ALREADY_REGISTERED",
                    "request_count": entry.request_count,
                }

            # ------------------------------------------------
            # FIRST REGISTRATION
            # ------------------------------------------------

            entry = LotteryEntry(
                user_id=user_id,
                drop_id=self.drop_id,
                registered_at=self._now(),
            )

            self.entries[key] = entry

            self._audit(
                "USER_REGISTERED",
                user_id=user_id,
                entry_id=entry.entry_id,
            )

            return {
                "success": True,
                "registered": True,
                "new_entry": True,
                "entry_id": entry.entry_id,
            }


    # ========================================================
    # FREEZE REGISTRATION
    # ========================================================

    def freeze_registration(self) -> Dict:

        with self._lock:

            if self.drop_status != DropStatus.OPEN:
                raise RuntimeError(
                    "Registration is not currently open."
                )

            self.drop_status = DropStatus.FROZEN

            self._audit(
                "REGISTRATION_FROZEN",
                total_entries=len(self.entries),
            )

            return {
                "drop_id": self.drop_id,
                "status": self.drop_status.value,
                "eligible_entries": len(self.entries),
            }


    # ========================================================
    # LOTTERY SEED
    # ========================================================

    def _generate_lottery_seed(self) -> bytes:

        """
        Generate a cryptographically secure random seed.

        This seed is created AFTER registration closes.

        Therefore participants cannot know their lottery position
        while registration is still open.
        """

        seed = secrets.token_bytes(32)

        commitment = hashlib.sha256(seed).hexdigest()

        self._lottery_seed = seed

        self._lottery_seed_commitment = commitment

        self._audit(
            "LOTTERY_SEED_GENERATED",
            seed_commitment=commitment,
        )

        return seed


    # ========================================================
    # RANDOM KEY
    # ========================================================

    def _generate_random_key(
        self,
        seed: bytes,
        user_id: str,
    ) -> str:

        """
        Generate deterministic random value for a participant.

        HMAC-SHA256 provides deterministic ordering after the
        seed is generated while keeping the seed secret before
        allocation.
        """

        message = user_id.encode("utf-8")

        digest = hmac.new(
            seed,
            message,
            hashlib.sha256,
        ).hexdigest()

        return digest


    # ========================================================
    # RUN LOTTERY
    # ========================================================

    def run_lottery(self) -> AllocationResult:

        with self._lock:

            if self.drop_status != DropStatus.FROZEN:
                raise RuntimeError(
                    "Registration must be frozen before lottery."
                )

            if self.drop_id is None:
                raise RuntimeError(
                    "No drop exists."
                )

            entries = list(self.entries.values())

            total_eligible = len(entries)

            # ------------------------------------------------
            # Generate secret lottery seed AFTER freeze.
            # ------------------------------------------------

            seed = self._generate_lottery_seed()

            # ------------------------------------------------
            # Assign random key to every participant.
            # ------------------------------------------------

            for entry in entries:

                entry.random_key = self._generate_random_key(
                    seed,
                    entry.user_id,
                )

            # ------------------------------------------------
            # Sort using random key.
            # ------------------------------------------------

            entries.sort(
                key=lambda entry: entry.random_key
            )

            # ------------------------------------------------
            # Select maximum 500 winners.
            # ------------------------------------------------

            winner_count = min(
                self.seats,
                len(entries),
            )

            winners = entries[:winner_count]

            waitlist = entries[winner_count:]

            # ------------------------------------------------
            # Mark statuses.
            # ------------------------------------------------

            for entry in winners:
                entry.status = EntryStatus.WINNER

            for entry in waitlist:
                entry.status = EntryStatus.WAITLIST

            # ------------------------------------------------
            # Allocate tickets atomically inside lock.
            # ------------------------------------------------

            allocated_users = []

            for entry in winners:

                ticket = self._allocate_ticket_atomic(
                    user_id=entry.user_id
                )

                if ticket is not None:

                    allocated_users.append(
                        entry.user_id
                    )

            self.drop_status = DropStatus.ALLOCATED

            self._audit(
                "LOTTERY_COMPLETED",
                total_eligible=total_eligible,
                winner_count=len(winners),
                waitlist_count=len(waitlist),
                tickets_allocated=len(allocated_users),
                seed_commitment=self._lottery_seed_commitment,
            )

            return AllocationResult(
                drop_id=self.drop_id,
                total_eligible=total_eligible,
                seats_available=self.seats,
                winners=[
                    entry.user_id
                    for entry in winners
                ],
                waitlist=[
                    entry.user_id
                    for entry in waitlist
                ],
                tickets_allocated=len(allocated_users),
                lottery_seed_commitment=(
                    self._lottery_seed_commitment or ""
                ),
                allocation_timestamp=self._now(),
            )


    # ========================================================
    # ATOMIC TICKET ALLOCATION
    # ========================================================

    def _allocate_ticket_atomic(
        self,
        user_id: str,
    ) -> Optional[Ticket]:

        """
        Allocate exactly one ticket to a user.

        This method is protected by the engine lock.

        In production with multiple backend processes, this
        same guarantee MUST be implemented using a database
        transaction / atomic UPDATE with row locking.

        Never rely only on Python locks across multiple servers.
        """

        key = (self.drop_id, user_id)

        # ----------------------------------------------------
        # Duplicate protection
        # ----------------------------------------------------

        if key in self.user_tickets:

            existing_ticket_id = self.user_tickets[key]

            return self.tickets.get(
                existing_ticket_id
            )

        # ----------------------------------------------------
        # Inventory protection
        # ----------------------------------------------------

        allocated_count = len(self.tickets)

        if allocated_count >= self.seats:

            self._audit(
                "INVENTORY_EXHAUSTED",
                user_id=user_id,
            )

            return None

        # ----------------------------------------------------
        # Create ticket
        # ----------------------------------------------------

        ticket_id = str(uuid.uuid4())

        ticket = Ticket(
            ticket_id=ticket_id,
            user_id=user_id,
            drop_id=self.drop_id,
            status=TicketStatus.RESERVED,
            allocated_at=self._now(),
        )

        self.tickets[ticket_id] = ticket

        self.user_tickets[key] = ticket_id

        self._audit(
            "TICKET_RESERVED",
            user_id=user_id,
            ticket_id=ticket_id,
        )

        return ticket


    # ========================================================
    # CONFIRM TICKET
    # ========================================================

    def confirm_ticket(
        self,
        ticket_id: str,
    ) -> bool:

        with self._lock:

            ticket = self.tickets.get(ticket_id)

            if ticket is None:
                return False

            if ticket.status != TicketStatus.RESERVED:
                return False

            ticket.status = TicketStatus.CONFIRMED

            self._audit(
                "TICKET_CONFIRMED",
                user_id=ticket.user_id,
                ticket_id=ticket.ticket_id,
            )

            return True


    # ========================================================
    # EXPIRE TICKET
    # ========================================================

    def expire_ticket(
        self,
        ticket_id: str,
    ) -> bool:

        with self._lock:

            ticket = self.tickets.get(ticket_id)

            if ticket is None:
                return False

            if ticket.status != TicketStatus.RESERVED:
                return False

            ticket.status = TicketStatus.EXPIRED

            self._audit(
                "TICKET_EXPIRED",
                user_id=ticket.user_id,
                ticket_id=ticket.ticket_id,
            )

            return True


    # ========================================================
    # WAITLIST ALLOCATION
    # ========================================================

    def allocate_next_waitlisted_user(
        self,
    ) -> Optional[Ticket]:

        """
        Allocate a released seat to the next waitlisted participant.

        The waitlist order was determined by the same lottery.
        """

        with self._lock:

            if self.drop_id is None:
                return None

            waitlisted = [
                entry
                for entry in self.entries.values()
                if entry.status == EntryStatus.WAITLIST
            ]

            if not waitlisted:
                return None

            # Already sorted by random key.
            waitlisted.sort(
                key=lambda entry: entry.random_key or ""
            )

            next_user = waitlisted[0]

            # Remove from waitlist.
            next_user.status = EntryStatus.WINNER

            ticket = self._allocate_ticket_atomic(
                user_id=next_user.user_id
            )

            if ticket:

                self._audit(
                    "WAITLIST_USER_ALLOCATED",
                    user_id=next_user.user_id,
                    ticket_id=ticket.ticket_id,
                )

            return ticket


    # ========================================================
    # INVENTORY STATUS
    # ========================================================

    def get_inventory_status(self) -> Dict:

        with self._lock:

            allocated = len(self.tickets)

            confirmed = sum(
                1
                for ticket in self.tickets.values()
                if ticket.status == TicketStatus.CONFIRMED
            )

            reserved = sum(
                1
                for ticket in self.tickets.values()
                if ticket.status == TicketStatus.RESERVED
            )

            expired = sum(
                1
                for ticket in self.tickets.values()
                if ticket.status == TicketStatus.EXPIRED
            )

            return {
                "total_seats": self.seats,
                "allocated": allocated,
                "confirmed": confirmed,
                "reserved": reserved,
                "expired": expired,
                "remaining_unallocated": max(
                    self.seats - allocated,
                    0,
                ),
            }


    # ========================================================
    # USER RESULT
    # ========================================================

    def get_user_result(
        self,
        user_id: str,
    ) -> Dict:

        with self._lock:

            if self.drop_id is None:
                return {
                    "user_id": user_id,
                    "status": "NO_DROP",
                }

            key = (self.drop_id, user_id)

            entry = self.entries.get(key)

            ticket_id = self.user_tickets.get(key)

            ticket = (
                self.tickets.get(ticket_id)
                if ticket_id
                else None
            )

            return {
                "user_id": user_id,
                "drop_id": self.drop_id,

                "registered": entry is not None,

                "entry_status": (
                    entry.status.value
                    if entry
                    else None
                ),

                "ticket_id": (
                    ticket.ticket_id
                    if ticket
                    else None
                ),

                "ticket_status": (
                    ticket.status.value
                    if ticket
                    else None
                ),
            }


    # ========================================================
    # FAIRNESS METRICS
    # ========================================================

    def fairness_metrics(self) -> Dict:

        """
        Calculate basic measurable fairness statistics.

        For N eligible participants and S seats:

            Expected allocation probability = S / N

        Every eligible participant has exactly one lottery entry.
        """

        with self._lock:

            eligible = len(self.entries)

            allocated = len(self.tickets)

            if eligible == 0:

                expected_probability = 0.0

            else:

                expected_probability = (
                    min(self.seats, eligible)
                    / eligible
                )

            duplicate_tickets = (
                allocated
                - len(self.user_tickets)
            )

            oversold = max(
                allocated - self.seats,
                0,
            )

            return {
                "eligible_users": eligible,

                "seats": self.seats,

                "tickets_allocated": allocated,

                "expected_allocation_probability": (
                    expected_probability
                ),

                "duplicate_ticket_count": (
                    duplicate_tickets
                ),

                "oversold_count": oversold,

                "inventory_consistent": (
                    allocated <= self.seats
                ),

                "duplicate_free": (
                    duplicate_tickets == 0
                ),

                "fairness_rule":
                    "ONE_ELIGIBLE_USER_ONE_LOTTERY_ENTRY",
            }


    # ========================================================
    # AUDIT LOG
    # ========================================================

    def get_audit_log(self) -> List[Dict]:

        with self._lock:

            return [
                {
                    "event_type": event.event_type,
                    "drop_id": event.drop_id,
                    "user_id": event.user_id,
                    "timestamp": self._iso(
                        event.timestamp
                    ),
                    "details": event.details,
                }
                for event in self.audit_log
            ]


    # ========================================================
    # LOTTERY VERIFICATION
    # ========================================================

    def reveal_lottery_seed(self) -> Optional[str]:

        """
        Reveal seed AFTER allocation for audit/demo purposes.

        In a real system this should only be exposed according
        to your audit policy.
        """

        with self._lock:

            if self._lottery_seed is None:
                return None

            return self._lottery_seed.hex()


    def verify_lottery(self) -> Dict:

        """
        Recalculate the lottery order using the revealed seed.

        This demonstrates that allocation can be independently
        verified after the lottery.
        """

        with self._lock:

            if self._lottery_seed is None:

                return {
                    "verified": False,
                    "reason": "LOTTERY_NOT_RUN",
                }

            entries = list(
                self.entries.values()
            )

            for entry in entries:

                expected_key = self._generate_random_key(
                    self._lottery_seed,
                    entry.user_id,
                )

                if entry.random_key != expected_key:

                    return {
                        "verified": False,
                        "reason": "RANDOM_KEY_MISMATCH",
                    }

            entries.sort(
                key=lambda entry: entry.random_key or ""
            )

            expected_winners = {
                entry.user_id
                for entry in entries[:self.seats]
            }

            actual_winners = {
                entry.user_id
                for entry in entries
                if entry.status == EntryStatus.WINNER
            }

            verified = (
                expected_winners == actual_winners
            )

            return {
                "verified": verified,
                "winner_count": len(actual_winners),
                "seed_commitment": (
                    self._lottery_seed_commitment
                ),
            }


# ============================================================
# DEMO
# ============================================================

def demo():

    print("=" * 70)
    print("FAIR DROP - FAIR ALLOCATION ENGINE")
    print("=" * 70)

    # --------------------------------------------------------
    # Create drop
    # --------------------------------------------------------

    engine = FairAllocationEngine(
        seats=500,
        registration_window_seconds=2,
    )

    engine.create_drop(
        drop_id="drop_001"
    )

    engine.open_registration()

    print("\n[1] Registration opened")

    # --------------------------------------------------------
    # Simulate legitimate users
    # --------------------------------------------------------

    print("\n[2] Registering legitimate users...")

    for i in range(1000):

        engine.register_user(
            user_id=f"user_{i:04d}",
            eligible=True,
            verification_passed=True,
        )

    # --------------------------------------------------------
    # Simulate request flooding
    # --------------------------------------------------------

    print("\n[3] Simulating repeated requests...")

    for _ in range(100):

        result = engine.register_user(
            user_id="aggressive_bot",
            eligible=True,
            verification_passed=True,
        )

    # --------------------------------------------------------
    # Simulate suspicious user rejected by policy
    # --------------------------------------------------------

    print("\n[4] Simulating policy rejection...")

    rejected = engine.register_user(
        user_id="quarantined_bot",
        eligible=False,
        verification_passed=True,
    )

    print("Rejected:", rejected)

    # --------------------------------------------------------
    # Freeze registration
    # --------------------------------------------------------

    frozen = engine.freeze_registration()

    print("\n[5] Registration frozen")
    print(frozen)

    # --------------------------------------------------------
    # Run lottery
    # --------------------------------------------------------

    result = engine.run_lottery()

    print("\n[6] Lottery completed")

    print(
        "Eligible users:",
        result.total_eligible
    )

    print(
        "Winners:",
        len(result.winners)
    )

    print(
        "Waitlist:",
        len(result.waitlist)
    )

    print(
        "Tickets allocated:",
        result.tickets_allocated
    )

    print(
        "Seed commitment:",
        result.lottery_seed_commitment
    )

    # --------------------------------------------------------
    # Inventory
    # --------------------------------------------------------

    print("\n[7] Inventory")

    print(
        engine.get_inventory_status()
    )

    # --------------------------------------------------------
    # Fairness
    # --------------------------------------------------------

    print("\n[8] Fairness metrics")

    print(
        engine.fairness_metrics()
    )

    # --------------------------------------------------------
    # Check duplicate protection
    # --------------------------------------------------------

    print("\n[9] Duplicate protection")

    user_result = engine.get_user_result(
        result.winners[0]
    )

    print(user_result)

    # --------------------------------------------------------
    # Verify lottery
    # --------------------------------------------------------

    print("\n[10] Lottery verification")

    print(
        engine.verify_lottery()
    )

    # --------------------------------------------------------
    # Reveal seed
    # --------------------------------------------------------

    print("\n[11] Lottery seed")

    print(
        engine.reveal_lottery_seed()
    )

    # --------------------------------------------------------
    # Final audit
    # --------------------------------------------------------

    print("\n[12] Final audit summary")

    metrics = engine.fairness_metrics()

    print(
        f"Oversold: {metrics['oversold_count']}"
    )

    print(
        f"Duplicate tickets: "
        f"{metrics['duplicate_ticket_count']}"
    )

    print(
        f"Inventory consistent: "
        f"{metrics['inventory_consistent']}"
    )

    print(
        f"Duplicate free: "
        f"{metrics['duplicate_free']}"
    )

    print("\n" + "=" * 70)
    print("FAIR DROP ALLOCATION TEST COMPLETE")
    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    demo()