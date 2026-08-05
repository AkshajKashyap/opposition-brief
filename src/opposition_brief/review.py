"""Analyst-owned review state kept separate from immutable computed observations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from opposition_brief.observations import CandidateObservation


class ReviewStatus(StrEnum):
    UNREVIEWED = "Unreviewed"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    NEEDS_REVISION = "Needs revision"


@dataclass(frozen=True)
class ReviewState:
    """Editable analyst fields only; computed claims do not exist in this model."""

    observation_id: str
    status: ReviewStatus
    title: str
    interpretation: str
    analyst_note: str = ""


@dataclass(frozen=True)
class ReviewedObservation:
    observation: CandidateObservation
    review: ReviewState


def default_review_state(observation: CandidateObservation) -> ReviewState:
    return ReviewState(
        observation_id=observation.observation_id,
        status=ReviewStatus.UNREVIEWED,
        title=observation.title,
        interpretation=observation.interpretation,
    )


def update_review(
    observation: CandidateObservation,
    previous: ReviewState | None,
    *,
    status: ReviewStatus,
    title: str,
    interpretation: str,
    analyst_note: str,
) -> ReviewState:
    """Return analyst edits while deliberately preserving the immutable computation."""
    if previous is not None and previous.observation_id != observation.observation_id:
        raise ValueError("Review state does not belong to this observation.")
    return ReviewState(
        observation_id=observation.observation_id,
        status=status,
        title=title.strip() or observation.title,
        interpretation=interpretation.strip() or observation.interpretation,
        analyst_note=analyst_note.strip(),
    )


def included_in_reviewed_report(
    observations: list[CandidateObservation], review_states: dict[str, ReviewState]
) -> list[ReviewedObservation]:
    """Include only accepted items and items awaiting a requested revision."""
    included: list[ReviewedObservation] = []
    for observation in observations:
        review = review_states.get(observation.observation_id, default_review_state(observation))
        if review.status in {ReviewStatus.ACCEPTED, ReviewStatus.NEEDS_REVISION}:
            included.append(ReviewedObservation(observation, review))
    return included
