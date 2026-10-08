"""
Durable Job State Machine & Transition Rules
Enforces valid state lifecycle transitions according to Phase 2 specification.
"""

from enum import Enum
from typing import Set, Dict
from ..core.errors import AppException


class JobState(str, Enum):
    QUEUED = "queued"
    PREPARING = "preparing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IllegalStateTransitionError(AppException):
    def __init__(self, from_state: str, to_state: str, reason: str = ""):
        detail = f"Illegal job state transition from '{from_state}' to '{to_state}'."
        if reason:
            detail += f" Reason: {reason}"
        super().__init__(
            status_code=400,
            title="Illegal State Transition",
            detail=detail,
            code="ILLEGAL_STATE_TRANSITION",
        )


class JobStateMachine:
    VALID_TRANSITIONS: Dict[JobState, Set[JobState]] = {
        JobState.QUEUED: {
            JobState.PREPARING,
            JobState.CANCELLED,
        },
        JobState.PREPARING: {
            JobState.RUNNING,
            JobState.QUEUED,     # Lease expired, worker prep failed (retry)
            JobState.FAILED,     # Unrecoverable error
            JobState.CANCELLED,  # Cancelled by user
        },
        JobState.RUNNING: {
            JobState.COMPLETED,  # Synthesis succeeded
            JobState.QUEUED,     # Lease expired or transient error retry
            JobState.FAILED,     # Unrecoverable error or max retries exhausted
            JobState.CANCELLED,  # Cancelled by user
        },
        JobState.COMPLETED: set(),  # Terminal state
        JobState.FAILED: {
            JobState.QUEUED,     # Manual retry only
        },
        JobState.CANCELLED: set(),  # Terminal state
    }

    TERMINAL_STATES: Set[JobState] = {
        JobState.COMPLETED,
        JobState.CANCELLED,
    }

    @classmethod
    def is_terminal(cls, state: str) -> bool:
        try:
            return JobState(state) in cls.TERMINAL_STATES
        except ValueError:
            return False

    @classmethod
    def can_transition(cls, from_state: str, to_state: str) -> bool:
        try:
            source = JobState(from_state)
            target = JobState(to_state)
            return target in cls.VALID_TRANSITIONS.get(source, set())
        except ValueError:
            return False

    @classmethod
    def validate_transition(cls, from_state: str, to_state: str, reason: str = "") -> None:
        if not cls.can_transition(from_state, to_state):
            raise IllegalStateTransitionError(from_state, to_state, reason)
