"""Request lifecycle states and the only allowed transitions (see README, Workflow lifecycle)."""

from __future__ import annotations

from enum import StrEnum


class State(StrEnum):
    REQUESTED = "REQUESTED"
    VALIDATING = "VALIDATING"
    PLATFORM_PROVISIONING = "PLATFORM_PROVISIONING"
    REPOSITORY_CREATED = "REPOSITORY_CREATED"
    INFRASTRUCTURE_PLANNED = "INFRASTRUCTURE_PLANNED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    PROVISIONING = "PROVISIONING"
    INFRASTRUCTURE_READY = "INFRASTRUCTURE_READY"
    APPLICATION_BUILDING = "APPLICATION_BUILDING"
    DEPLOYING = "DEPLOYING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    CLEANUP_PENDING = "CLEANUP_PENDING"
    CLEANED_UP = "CLEANED_UP"


S = State

TRANSITIONS: dict[State, frozenset[State]] = {
    S.REQUESTED: frozenset({S.VALIDATING, S.FAILED, S.CANCELLED}),
    S.VALIDATING: frozenset({S.PLATFORM_PROVISIONING, S.REPOSITORY_CREATED, S.FAILED, S.CANCELLED}),
    S.PLATFORM_PROVISIONING: frozenset({S.REPOSITORY_CREATED, S.FAILED, S.CANCELLED}),
    S.REPOSITORY_CREATED: frozenset({S.INFRASTRUCTURE_PLANNED, S.FAILED, S.CANCELLED}),
    S.INFRASTRUCTURE_PLANNED: frozenset({S.AWAITING_APPROVAL, S.FAILED, S.CANCELLED}),
    S.AWAITING_APPROVAL: frozenset({S.PROVISIONING, S.CANCELLED, S.FAILED}),
    S.PROVISIONING: frozenset({S.INFRASTRUCTURE_READY, S.FAILED}),
    S.INFRASTRUCTURE_READY: frozenset({S.APPLICATION_BUILDING, S.FAILED}),
    S.APPLICATION_BUILDING: frozenset({S.DEPLOYING, S.FAILED}),
    S.DEPLOYING: frozenset({S.SUCCEEDED, S.FAILED}),
    S.SUCCEEDED: frozenset({S.CLEANUP_PENDING}),
    S.FAILED: frozenset({S.CLEANUP_PENDING}),
    S.CANCELLED: frozenset({S.CLEANUP_PENDING}),
    S.CLEANUP_PENDING: frozenset({S.CLEANED_UP}),
    S.CLEANED_UP: frozenset(),
}

TERMINAL = frozenset({S.CLEANED_UP})
ACTIVE = frozenset(set(State) - {S.SUCCEEDED, S.FAILED, S.CANCELLED, S.CLEANED_UP})
CANCELLABLE = frozenset({S.REQUESTED, S.VALIDATING, S.PLATFORM_PROVISIONING, S.REPOSITORY_CREATED,
                         S.INFRASTRUCTURE_PLANNED, S.AWAITING_APPROVAL})
CLEANABLE = frozenset({S.SUCCEEDED, S.FAILED, S.CANCELLED})

# The outcome groups reported separately in Backstage ("honest status").
OUTCOMES: dict[str, tuple[State, ...]] = {
    "validated": (S.REPOSITORY_CREATED,),
    "repository": (S.REPOSITORY_CREATED,),
    "infrastructure": (S.INFRASTRUCTURE_READY,),
    "application": (S.DEPLOYING,),
    "deployment": (S.SUCCEEDED,),
}


class IllegalTransitionError(Exception):
    def __init__(self, current: State, target: State) -> None:
        super().__init__(f"illegal transition {current} -> {target}")
        self.current = current
        self.target = target


def check_transition(current: State, target: State) -> None:
    if target not in TRANSITIONS[current]:
        raise IllegalTransitionError(current, target)
