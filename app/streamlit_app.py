"""Coach-first opposition brief built from the cached demo project."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from opposition_brief.demo import DemoProject, evidence_events, load_cached_demo_project
from opposition_brief.presentation import (
    ChartValue,
    EvidenceItem,
    PatternView,
    prepare_pattern_views,
)
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

DECISIONS = {
    "Not decided": ReviewStatus.UNREVIEWED,
    "Include in brief": ReviewStatus.ACCEPTED,
    "Needs context": ReviewStatus.NEEDS_REVISION,
    "Dismiss": ReviewStatus.REJECTED,
}
DECISION_LABELS = {status: label for label, status in DECISIONS.items()}


@st.cache_data(show_spinner="Preparing opposition brief…")
def _load_project(cache_root: str):
    return load_cached_demo_project(Path(cache_root))


def _initialise_reviews(project: DemoProject) -> dict[str, ReviewState]:
    reviews = st.session_state.setdefault("reviews", {})
    for observation in project.observations:
        reviews.setdefault(observation.observation_id, default_review_state(observation))
    return reviews


def _go_to_detail(observation_id: str) -> None:
    st.session_state["selected_pattern"] = observation_id
    st.session_state["stage"] = "Pattern detail"


def _go_to_brief() -> None:
    st.session_state["stage"] = "Opposition brief"


def _bar_chart(values: tuple[ChartValue, ...], title: str, axis_label: str) -> None:
    st.caption(title)
    st.bar_chart(
        [{"Area": item.label, "Share": item.value} for item in values],
        x="Area",
        y="Share",
        horizontal=True,
        x_label=axis_label,
        y_label=None,
    )


def _match_share_chart(values: tuple[ChartValue, ...]) -> None:
    st.bar_chart(
        [{"Match": item.label, "Share": item.value} for item in values],
        x="Match",
        y="Share",
        x_label=None,
        y_label="Share of relevant actions (%)",
    )


def _landing_page(project: DemoProject, patterns: list[PatternView]) -> None:
    dates = sorted(match.match_date for match in project.matches if match.match_date)
    st.title(project.opponent)
    st.subheader("Opposition brief")
    st.caption(f"{project.competition} {project.season} · {len(project.matches)} matches analyzed")
    if dates:
        st.caption(f"{dates[0]} to {dates[-1]}")
    st.header(f"{len(patterns)} patterns worth reviewing")
    st.write("A quick read on what this opponent repeatedly did in the matches available.")
    if not patterns:
        st.info("No patterns are available from the cached matches.")
        return
    for pattern in patterns:
        with st.container(border=True):
            st.subheader(pattern.title)
            st.write(pattern.finding)
            st.caption(f"{pattern.sample_label} · {pattern.matches_label}")
            if pattern.players:
                st.caption(f"{pattern.players_label}: {', '.join(pattern.players)}")
            _bar_chart(pattern.chart_values, pattern.chart_title, pattern.chart_axis_label)
            st.markdown("**Why review this?**")
            st.write(pattern.why_review)
            st.button(
                "Review sequences",
                key=f"open-{pattern.observation.observation_id}",
                icon=":material/play_circle:",
                on_click=_go_to_detail,
                args=(pattern.observation.observation_id,),
            )


def _evidence_cards(items: tuple[EvidenceItem, ...], empty_message: str) -> None:
    if not items:
        st.caption(empty_message)
        return
    for item in items:
        # PatternView intentionally exposes only coach-facing evidence fields.
        with st.container(border=True):
            st.markdown(f"**{item.match}**")
            st.caption(f"{item.date} · {item.timestamp} · {item.player}")
            st.write(item.description)


def _save_decision(pattern: PatternView, reviews: dict[str, ReviewState]) -> None:
    observation = pattern.observation
    state = reviews[observation.observation_id]
    prefix = f"review-{observation.observation_id}"
    status = DECISIONS[st.session_state[f"{prefix}-decision"]]
    interpretation = st.session_state.get(f"{prefix}-interpretation", "")
    note = st.session_state.get(f"{prefix}-note", "")
    reviews[observation.observation_id] = update_review(
        observation,
        state,
        status=status,
        title=state.title,
        interpretation=interpretation,
        analyst_note=note,
    )


def _decision_controls(pattern: PatternView, reviews: dict[str, ReviewState]) -> None:
    observation = pattern.observation
    state = reviews[observation.observation_id]
    prefix = f"review-{observation.observation_id}"
    st.header("Analyst decision")
    st.caption("Choose what should appear in the final report after reviewing the actions.")
    decision_key = f"{prefix}-decision"
    st.session_state.setdefault(decision_key, DECISION_LABELS[state.status])
    decision = st.selectbox("Decision", list(DECISIONS), key=decision_key)
    if DECISIONS[decision] in {ReviewStatus.ACCEPTED, ReviewStatus.NEEDS_REVISION}:
        st.session_state.setdefault(f"{prefix}-interpretation", state.interpretation)
        st.session_state.setdefault(f"{prefix}-note", state.analyst_note)
        st.text_area(
            "Analyst interpretation (optional)",
            key=f"{prefix}-interpretation",
            help="Adds your coaching context without changing the factual finding.",
        )
        st.text_area("Analyst note (optional)", key=f"{prefix}-note")
    _save_decision(pattern, reviews)
    st.caption("Keep the finding in context: " + " ".join(observation.limitations[:1]))


def _pattern_detail(
    project: DemoProject, patterns: list[PatternView], reviews: dict[str, ReviewState]
) -> None:
    if not patterns:
        _landing_page(project, patterns)
        return
    pattern_ids = [item.observation.observation_id for item in patterns]
    selected_id = st.session_state.get("selected_pattern", pattern_ids[0])
    pattern = next(
        (item for item in patterns if item.observation.observation_id == selected_id), patterns[0]
    )
    st.button("Back to opposition brief", icon=":material/arrow_back:", on_click=_go_to_brief)
    st.title(pattern.title)
    st.header("What we saw")
    st.write(pattern.finding)
    st.caption(f"{pattern.sample_label} · {pattern.matches_label}")
    st.header("Pattern share in each match")
    st.caption("Each bar uses that match's relevant actions as its denominator.")
    _match_share_chart(pattern.match_shares)
    st.header("Where it happened")
    supporting_events = evidence_events(project, pattern.observation.supporting_event_ids)
    if supporting_events:
        st.plotly_chart(evidence_pitch(supporting_events[:8]), width="stretch")
    else:
        st.caption("No locations are available for the representative actions.")
    if pattern.players:
        st.header("Who was involved")
        st.caption(pattern.players_label)
        st.write(", ".join(pattern.players))
    st.header("Representative actions")
    _evidence_cards(pattern.evidence, "No representative actions are available.")
    with st.expander("See other examples", icon=":material/compare_arrows:"):
        st.write(
            "These actions show occasions where the opponent used a different route. "
            "They help judge how consistent the pattern really is."
        )
        _evidence_cards(pattern.other_examples, "No other actions were selected for this pattern.")
    with st.expander("Data & methodology", icon=":material/info:"):
        st.write(
            "This brief uses three matches of event data. It describes recorded actions, not tactical "
            "intent, the cause of a turnover, or the correct response. Pitch locations are normalized "
            "to a 0–100 scale; timestamps are included to find actions in video."
        )
        if project.warnings:
            st.caption(
                f"{len(project.warnings)} data-quality note(s) were retained during preparation."
            )
    _decision_controls(pattern, reviews)


def _final_report(
    project: DemoProject, patterns: list[PatternView], reviews: dict[str, ReviewState]
) -> None:
    included = included_in_reviewed_report(project.observations, reviews)
    included_ids = {item.observation.observation_id for item in included}
    selected = [item for item in patterns if item.observation.observation_id in included_ids]
    st.title("Final report")
    st.caption("Patterns selected for the coaching brief.")
    if not selected:
        st.info("Choose Include in brief or Needs context on a pattern to prepare the report.")
    for pattern in selected:
        state = reviews[pattern.observation.observation_id]
        with st.container(border=True):
            st.subheader(pattern.title)
            st.write(pattern.finding)
            st.caption(f"{pattern.sample_label} · {pattern.matches_label}")
            st.markdown("**Analyst interpretation**")
            st.write(state.interpretation)
            if state.analyst_note:
                st.markdown("**Analyst note**")
                st.write(state.analyst_note)
    html = render_reviewed_report(project, included)
    st.download_button(
        "Download final report (HTML)",
        data=html,
        file_name="reviewed_opposition_brief.html",
        mime="text/html",
        icon=":material/download:",
    )


def main() -> None:
    st.set_page_config(
        page_title="Opposition Brief", page_icon=":material/sports_soccer:", layout="wide"
    )
    result = _load_project(str(DATA_ROOT))
    if result.project is None:
        st.error("The cached demo matches are not ready yet.")
        st.caption(result.message)
        st.code("opposition-brief build-demo-report", language="bash")
        return
    project = result.project
    patterns = prepare_pattern_views(project)
    reviews = _initialise_reviews(project)
    stages = ["Opposition brief", "Pattern detail", "Final report"]
    st.session_state.setdefault("stage", stages[0])
    if st.session_state["stage"] not in stages:
        st.session_state["stage"] = stages[0]
    with st.sidebar:
        st.caption("Match preparation")
        st.segmented_control("View", stages, key="stage", label_visibility="collapsed")
        st.caption("Data & methodology is available inside each pattern detail.")
    if st.session_state["stage"] == "Opposition brief":
        _landing_page(project, patterns)
    elif st.session_state["stage"] == "Pattern detail":
        _pattern_detail(project, patterns, reviews)
    else:
        _final_report(project, patterns, reviews)


if __name__ == "__main__":
    main()
