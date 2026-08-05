"""Offline tests for evidence selection and analyst-controlled review behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from opposition_brief.analysis.metrics import AnalysisResult
from opposition_brief.demo import (
    DemoProject,
    build_local_demo_project,
    evidence_events,
    load_cached_demo_project,
)
from opposition_brief.observations import (
    CandidateObservation,
    EvidenceStrength,
    build_candidate_observations,
    evidence_strength,
)
from opposition_brief.reporting.reviewed_html import render_reviewed_report
from opposition_brief.review import (
    ReviewStatus,
    default_review_state,
    included_in_reviewed_report,
    update_review,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "demo"


def _project() -> DemoProject:
    return build_local_demo_project(FIXTURE_DIR, "Meridian FC")


def test_observation_model_rejects_invalid_identifiers() -> None:
    with pytest.raises(ValueError, match="require an ID"):
        CandidateObservation(
            observation_id="",
            category="Route",
            title="Title",
            computed_claim="Fact",
            interpretation="Interpretation",
            sample_size=1,
            matches_observed=(1,),
            evidence_strength=EvidenceStrength.LOW,
            supporting_event_ids=("one",),
            counterexample_event_ids=(),
            limitations=("Limit",),
        )
    with pytest.raises(ValueError, match="unique"):
        CandidateObservation(
            observation_id="valid",
            category="Route",
            title="Title",
            computed_claim="Fact",
            interpretation="Interpretation",
            sample_size=1,
            matches_observed=(1,),
            evidence_strength=EvidenceStrength.LOW,
            supporting_event_ids=("one", "one"),
            counterexample_event_ids=(),
            limitations=("Limit",),
        )


def test_observation_ids_and_evidence_selection_are_deterministic() -> None:
    project = _project()
    again = _project()
    assert [item.observation_id for item in project.observations] == [
        item.observation_id for item in again.observations
    ]
    route = project.observations[0]
    support = evidence_events(project, route.supporting_event_ids)
    counterexamples = evidence_events(project, route.counterexample_event_ids)
    assert route.observation_id == "progression-route-left"
    assert {event.source_event_id for event in support} == {
        "101-pass-1",
        "102-pass-1",
        "103-pass-1",
    }
    assert {event.source_event_id for event in counterexamples} == {"102-carry-1"}


def test_evidence_strength_boundaries_and_small_sample_warning() -> None:
    assert evidence_strength(5, 3, 3) is EvidenceStrength.LOW
    assert evidence_strength(6, 1, 3) is EvidenceStrength.LOW
    assert evidence_strength(6, 2, 3) is EvidenceStrength.MODERATE
    assert evidence_strength(12, 2, 3) is EvidenceStrength.MODERATE
    assert evidence_strength(12, 3, 3) is EvidenceStrength.STRONG
    turnover = _project().observations[2]
    assert turnover.is_small_sample
    assert "Small sample" in " ".join(turnover.limitations)


def test_review_state_preserves_immutable_computed_claim_and_analyst_edits() -> None:
    observation = _project().observations[0]
    claim = observation.computed_claim
    review = update_review(
        observation,
        default_review_state(observation),
        status=ReviewStatus.NEEDS_REVISION,
        title="Coach's route review",
        interpretation="Check this clip before briefing.",
        analyst_note="Ask the video coordinator for two examples.",
    )
    assert observation.computed_claim == claim
    assert review.title == "Coach's route review"
    assert review.interpretation == "Check this clip before briefing."
    assert review.analyst_note.startswith("Ask the video")
    assert not hasattr(review, "computed_claim")


def test_report_filtering_and_reviewed_html_escape_edits() -> None:
    project = _project()
    first, second, third = project.observations
    reviews = {
        first.observation_id: update_review(
            first,
            None,
            status=ReviewStatus.ACCEPTED,
            title="<Accepted route>",
            interpretation="Review <b>carefully</b> & compare.",
            analyst_note="A & B",
        ),
        second.observation_id: update_review(
            second,
            None,
            status=ReviewStatus.REJECTED,
            title="Rejected",
            interpretation="Not retained",
            analyst_note="",
        ),
        third.observation_id: update_review(
            third,
            None,
            status=ReviewStatus.NEEDS_REVISION,
            title="Needs revision",
            interpretation="More video needed",
            analyst_note="",
        ),
    }
    included = included_in_reviewed_report(project.observations, reviews)
    assert [item.observation.observation_id for item in included] == [
        first.observation_id,
        third.observation_id,
    ]
    html = render_reviewed_report(project, included)
    assert "&lt;Accepted route&gt;" in html
    assert "Review &lt;b&gt;carefully&lt;/b&gt; &amp; compare." in html
    assert "Rejected" not in html
    assert "Computed evidence (immutable)" in html


def test_empty_data_and_malformed_cached_artifacts_are_safe(tmp_path: Path) -> None:
    empty = AnalysisResult([], [], [], [], [], [], [])
    assert build_candidate_observations(empty, 0) == []
    malformed = load_cached_demo_project(tmp_path)
    assert malformed.project is None
    assert malformed.message is not None
    assert "build-demo-report" in malformed.message
