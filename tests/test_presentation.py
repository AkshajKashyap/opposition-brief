"""Coach-facing presentation tests, independent of Streamlit rendering."""

from __future__ import annotations

from pathlib import Path

from opposition_brief.demo import build_local_demo_project
from opposition_brief.presentation import (
    human_match_label,
    percentage,
    prepare_pattern_views,
    soccer_timestamp,
)
from opposition_brief.visualization.pitch import evidence_pitch

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "demo"


def _project():
    return build_local_demo_project(FIXTURE_DIR, "Meridian FC")


def test_percentages_and_match_labels_are_human_readable() -> None:
    project = _project()
    assert percentage(3, 4) == 75
    assert percentage(3, 0) == 0
    assert human_match_label(project.matches[0]) == "Meridian FC vs Riverside · 2024-01-15"
    assert soccer_timestamp("00:23:41.000") == "23:41"
    assert soccer_timestamp("malformed") == "malformed"


def test_pattern_cards_add_relative_context_without_exposing_technical_ids() -> None:
    views = prepare_pattern_views(_project())
    route, player, loss = views
    assert route.title == "Left progression was Meridian FC's most common route"
    assert "75%" in route.finding
    assert route.matches_label == "Observed in 3 of 3 matches"
    assert [item.value for item in route.chart_values] == [75, 0, 25]
    assert player.title == "Alex Forward led Meridian FC for completed progression"
    assert [(item.label, item.value) for item in player.chart_values] == [
        ("Alex Forward", 3),
        ("Blair Mid", 1),
    ]
    assert player.players_label == "Leader in completed progressive actions"
    assert [(item.label, item.value) for item in loss.chart_values] == [
        ("Attacking third / Left", 50),
        ("Middle third / Central", 25),
        ("Middle third / Right", 25),
    ]
    assert "Other zones" not in [item.label for item in loss.chart_values]
    assert all("101" not in item.match for view in views for item in view.evidence)
    assert all(item.timestamp.count(":") == 1 for view in views for item in view.evidence)


def test_pattern_detail_uses_within_match_shares_and_readable_actions() -> None:
    route = prepare_pattern_views(_project())[0]
    assert [item.value for item in route.match_shares] == [100, 50, 100]
    evidence = route.evidence[0]
    assert evidence.match == "Meridian FC vs Northside · 2024-01-01"
    assert evidence.timestamp == "4:10"
    assert evidence.description == "Completed a forward pass to Blair Mid."
    assert not hasattr(evidence, "start")
    assert not hasattr(evidence, "end")


def test_pitch_explains_attacking_direction_with_arrowheads() -> None:
    project = _project()
    figure = evidence_pitch(project.analysis.progressions[:1])
    assert figure.layout.annotations[0].text == "Attacking direction"
    assert all(annotation.arrowhead == 3 for annotation in figure.layout.annotations)
