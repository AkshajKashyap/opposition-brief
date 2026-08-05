"""Analyst decision board for reviewing cached Opposition Brief demo data."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from opposition_brief.demo import DemoProject, evidence_events, load_cached_demo_project
from opposition_brief.models import NormalizedEvent
from opposition_brief.observations import CandidateObservation
from opposition_brief.reporting.reviewed_html import render_reviewed_report
from opposition_brief.review import (
    ReviewState,
    ReviewStatus,
    default_review_state,
    included_in_reviewed_report,
    update_review,
)
from opposition_brief.visualization.pitch import evidence_pitch

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data" / "raw" / "statsbomb"


@st.cache_data(show_spinner="Loading cached demo artifacts…")
def _load_project(cache_root: str):
    return load_cached_demo_project(Path(cache_root))


def _evidence_row(event: NormalizedEvent) -> dict[str, object]:
    return {
        "event_id": event.source_event_id or "—",
        "match": event.match_label,
        "date": event.match_date or "—",
        "period": event.period or "—",
        "timestamp": event.timestamp or "—",
        "player": event.player or "Unknown",
        "event type": event.event_type or "Unknown",
        "start": _location(event.start_x, event.start_y),
        "end": _location(event.end_x, event.end_y),
        "outcome": event.outcome or "—",
        "possession": event.possession_id or "—",
    }


def _location(x: float | None, y: float | None) -> str:
    return f"({x:.1f}, {y:.1f})" if x is not None and y is not None else "—"


def _filtered(
    events: list[NormalizedEvent], matches: list[int], players: list[str]
) -> list[NormalizedEvent]:
    return [
        event
        for event in events
        if event.match_id in matches and (not players or (event.player or "Unknown") in players)
    ]


def _initialise_reviews(observations: list[CandidateObservation]) -> dict[str, ReviewState]:
    reviews = st.session_state.setdefault("reviews", {})
    for observation in observations:
        reviews.setdefault(observation.observation_id, default_review_state(observation))
    return reviews


def _review_widgets(observation: CandidateObservation, reviews: dict[str, ReviewState]) -> None:
    state = reviews[observation.observation_id]
    prefix = f"review-{observation.observation_id}"
    st.markdown(f"### {state.title}")
    st.caption(f"{observation.category} · Evidence strength: **{observation.evidence_strength}**")
    st.markdown("**Computed evidence (immutable)**")
    st.info(observation.computed_claim)
    st.write(
        f"Sample: {observation.sample_size} supporting events across "
        f"{len(observation.matches_observed)} match(es): {', '.join(map(str, observation.matches_observed)) or 'none'}."
    )
    if observation.is_small_sample:
        st.warning("Small sample: this is a review prompt, not a stable tendency.")

    status_key, title_key = f"{prefix}-status", f"{prefix}-title"
    interpretation_key, note_key = f"{prefix}-interpretation", f"{prefix}-note"
    for key, value in (
        (status_key, str(state.status)),
        (title_key, state.title),
        (interpretation_key, state.interpretation),
        (note_key, state.analyst_note),
    ):
        st.session_state.setdefault(key, value)
    status = ReviewStatus(
        st.selectbox("Review status", [item.value for item in ReviewStatus], key=status_key)
    )
    title = st.text_input("Analyst title", key=title_key)
    interpretation = st.text_area(
        "Analyst interpretation / why it may matter", key=interpretation_key
    )
    note = st.text_area("Analyst note", key=note_key)
    reviews[observation.observation_id] = update_review(
        observation,
        state,
        status=status,
        title=title,
        interpretation=interpretation,
        analyst_note=note,
    )
    st.caption("Caution: " + " ".join(observation.limitations))
    if st.button("Open evidence explorer", key=f"{prefix}-open-evidence"):
        st.session_state["selected_observation"] = observation.observation_id
        st.session_state["section"] = "Evidence Explorer"
        st.rerun()


def _project_overview(project: DemoProject) -> None:
    st.header("Project Overview")
    st.caption("A cached, three-match event-data project. Interpret patterns through video review.")
    st.subheader(project.opponent)
    st.write(f"{project.competition} · {project.season}")
    dates = sorted(match.match_date for match in project.matches if match.match_date)
    if dates:
        st.write(f"Coverage: {dates[0]} to {dates[-1]} ({len(project.matches)} selected matches)")
    st.markdown("\n".join(f"- {match.label} (ID {match.match_id})" for match in project.matches))
    metrics = st.columns(5)
    metrics[0].metric("Normalized events", len(project.events))
    metrics[1].metric("Possessions", project.possession_count)
    metrics[2].metric("Completed progressions", len(project.analysis.progressions))
    metrics[3].metric("Possession losses", len(project.analysis.losses))
    metrics[4].metric("Validation warnings", len(project.warnings))
    st.subheader("Data limitations")
    st.info(
        "Three matches and event data can describe recorded actions, not tactical intent, pressure causes, "
        "or a correct tactical response. Use timestamps to review video before briefing staff."
    )
    st.subheader("Refresh demo artifacts")
    st.code("opposition-brief build-demo-report --offline", language="bash")
    if st.button("Reload cached artifacts"):
        _load_project.clear()
        st.rerun()


def _decision_board(project: DemoProject, reviews: dict[str, ReviewState]) -> None:
    st.header("Decision Board")
    st.caption(
        "Computed evidence is fixed. You control the title, interpretation, note, and review status."
    )
    if not project.observations:
        st.info("No candidate observations can be derived from the cached data.")
        return
    for observation in project.observations:
        with st.container(border=True):
            _review_widgets(observation, reviews)


def _evidence_explorer(project: DemoProject) -> None:
    st.header("Evidence Explorer")
    st.caption(
        "Representative events support a pattern. Counterexamples are comparison events, not refutations."
    )
    if not project.observations:
        st.info("No observations are available for evidence review.")
        return
    ids = [observation.observation_id for observation in project.observations]
    selected_id = st.session_state.get("selected_observation", ids[0])
    if selected_id not in ids:
        selected_id = ids[0]
    observation = next(item for item in project.observations if item.observation_id == selected_id)
    observation = st.selectbox(
        "Candidate observation",
        project.observations,
        index=ids.index(selected_id),
        format_func=lambda item: item.title,
    )
    st.session_state["selected_observation"] = observation.observation_id
    support = evidence_events(project, observation.supporting_event_ids)
    counterexamples = evidence_events(project, observation.counterexample_event_ids)
    candidates = support + counterexamples
    match_options = sorted({event.match_id for event in candidates})
    player_options = sorted({event.player or "Unknown" for event in candidates})
    filter_columns = st.columns(2)
    selected_matches = filter_columns[0].multiselect(
        "Matches", match_options, default=match_options
    )
    selected_players = filter_columns[1].multiselect("Players", player_options)
    support = _filtered(support, selected_matches, selected_players)
    counterexamples = _filtered(counterexamples, selected_matches, selected_players)
    support.sort(
        key=lambda event: (event.match_date or "", event.period or 0, event.timestamp_seconds or -1)
    )
    counterexamples.sort(
        key=lambda event: (event.match_date or "", event.period or 0, event.timestamp_seconds or -1)
    )
    left, right = st.columns(2)
    with left:
        st.subheader("Representative supporting evidence")
        st.dataframe(
            [_evidence_row(event) for event in support], hide_index=True, use_container_width=True
        )
    with right:
        st.subheader("Comparison / counterexample evidence")
        st.caption(
            "These events show other recorded routes, players, or zones. They do not disprove the pattern."
        )
        st.dataframe(
            [_evidence_row(event) for event in counterexamples],
            hide_index=True,
            use_container_width=True,
        )
    all_visible = support + counterexamples
    visible_ids = [event.source_event_id for event in all_visible if event.source_event_id]
    selected_event_ids = st.multiselect(
        "Evidence rows shown on pitch",
        visible_ids,
        default=visible_ids[: min(8, len(visible_ids))],
        format_func=lambda event_id: _event_label(project, event_id),
    )
    selected_events = evidence_events(project, tuple(selected_event_ids))
    if selected_events:
        st.plotly_chart(evidence_pitch(selected_events), use_container_width=True)
    else:
        st.info("Select one or more evidence rows to display them on the pitch.")


def _event_label(project: DemoProject, event_id: str) -> str:
    event = next((item for item in project.events if item.source_event_id == event_id), None)
    if event is None:
        return event_id
    return f"{event.match_label} · {event.timestamp or '—'} · {event.player or 'Unknown'} · {event.event_type or 'Unknown'}"


def _report_review(project: DemoProject, reviews: dict[str, ReviewState]) -> None:
    st.header("Report Review")
    st.caption("Only Accepted and Needs revision observations are included in the reviewed brief.")
    included = included_in_reviewed_report(project.observations, reviews)
    html = render_reviewed_report(project, included)
    components.html(html, height=850, scrolling=True)
    st.download_button(
        "Download reviewed standalone HTML",
        data=html,
        file_name="reviewed_opposition_brief.html",
        mime="text/html",
    )
    review_export = [
        {
            "observation_id": state.observation_id,
            "status": state.status.value,
            "title": state.title,
            "interpretation": state.interpretation,
            "analyst_note": state.analyst_note,
        }
        for state in reviews.values()
    ]
    st.download_button(
        "Download review state (JSON)",
        data=json.dumps(review_export, indent=2),
        file_name="opposition_brief_review_state.json",
        mime="application/json",
    )


def main() -> None:
    st.set_page_config(page_title="Opposition Brief", page_icon="⚽", layout="wide")
    st.title("Opposition Brief")
    result = _load_project(str(DATA_ROOT))
    if result.project is None:
        st.error(result.message)
        st.code("opposition-brief build-demo-report", language="bash")
        return
    project = result.project
    reviews = _initialise_reviews(project.observations)
    sections = ["Project Overview", "Decision Board", "Evidence Explorer", "Report Review"]
    if st.session_state.get("section") not in sections:
        st.session_state["section"] = sections[0]
    section = st.sidebar.radio("Workflow", sections, key="section")
    if section == "Project Overview":
        _project_overview(project)
    elif section == "Decision Board":
        _decision_board(project, reviews)
    elif section == "Evidence Explorer":
        _evidence_explorer(project)
    else:
        _report_review(project, reviews)


if __name__ == "__main__":
    main()
