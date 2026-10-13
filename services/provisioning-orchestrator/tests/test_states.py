import itertools

import pytest
from provisioning_orchestrator.states import TRANSITIONS, IllegalTransitionError, State, check_transition


def test_happy_path_is_allowed() -> None:
    path = [
        State.REQUESTED,
        State.VALIDATING,
        State.REPOSITORY_CREATED,
        State.INFRASTRUCTURE_PLANNED,
        State.AWAITING_APPROVAL,
        State.PROVISIONING,
        State.INFRASTRUCTURE_READY,
        State.APPLICATION_BUILDING,
        State.DEPLOYING,
        State.SUCCEEDED,
    ]
    for a, b in itertools.pairwise(path):
        check_transition(a, b)


def test_platform_branch_is_allowed() -> None:
    check_transition(State.VALIDATING, State.PLATFORM_PROVISIONING)
    check_transition(State.PLATFORM_PROVISIONING, State.REPOSITORY_CREATED)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (State.REPOSITORY_CREATED, State.SUCCEEDED),  # can't skip infrastructure
        (State.INFRASTRUCTURE_PLANNED, State.PROVISIONING),  # can't skip approval
        (State.FAILED, State.SUCCEEDED),  # a failure is never turned into success
        (State.PROVISIONING, State.CANCELLED),  # can't cancel while applying
        (State.CLEANED_UP, State.REQUESTED),
    ],
)
def test_illegal_transitions(a: State, b: State) -> None:
    with pytest.raises(IllegalTransitionError):
        check_transition(a, b)


def test_every_state_has_an_entry() -> None:
    assert set(TRANSITIONS) == set(State)
