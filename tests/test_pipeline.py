"""Deterministic coverage for the first report vertical slice."""

from __future__ import annotations

from pathlib import Path

from opposition_brief.analysis.metrics import (
    build_analysis,
    channel_for_y,
    is_possession_loss,
    is_progressive_attempt,
    third_for_x,
)
from opposition_brief.cli import main
from opposition_brief.ingestion.statsbomb import load_local_bundle
from opposition_brief.models import MatchMetadata, NormalizedEvent
from opposition_brief.normalization.statsbomb import (
    normalize_events,
    normalize_location,
    timestamp_to_seconds,
)
from opposition_brief.reporting.html import write_report

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "demo"


def _events() -> tuple[list[NormalizedEvent], list[object], list[MatchMetadata]]:
    matches, payloads = load_local_bundle(FIXTURE_DIR, "Meridian FC")
    normalized = [normalize_events(payloads[match.match_id], match) for match in matches]
    return (
        [event for result in normalized for event in result.events],
        [warning for result in normalized for warning in result.warnings],
        matches,
    )


def test_timestamp_and_coordinate_normalization() -> None:
    assert timestamp_to_seconds("01:02:03.500") == 3723.5
    assert timestamp_to_seconds("not-a-time") is None
    assert normalize_location([60, 40]) == (50.0, 50.0)
    assert normalize_location(["bad", 40]) == (None, None)


def test_required_field_validation_is_retained() -> None:
    match = MatchMetadata(1, "2024-01-01", "Test", "2024", "A", "B")
    result = normalize_events([{"id": "bad", "timestamp": "broken", "location": [10]}], match)
    assert len(result.events) == 1
    assert {warning.field for warning in result.warnings} >= {
        "type",
        "team",
        "timestamp",
        "location",
    }


def test_progression_channels_and_loss_definitions() -> None:
    events, _, _ = _events()
    completed_pass = next(event for event in events if event.source_event_id == "101-pass-1")
    failed_pass = next(event for event in events if event.source_event_id == "101-pass-2")
    loss = next(event for event in events if event.source_event_id == "103-dribble-1")
    assert is_progressive_attempt(completed_pass)
    assert is_progressive_attempt(failed_pass)
    assert is_possession_loss(loss)
    assert channel_for_y(10) == "Left"
    assert channel_for_y(50) == "Central"
    assert channel_for_y(90) == "Right"
    assert third_for_x(10) == "Defensive third"
    assert third_for_x(50) == "Middle third"
    assert third_for_x(90) == "Attacking third"


def test_aggregates_all_three_matches() -> None:
    events, _, _ = _events()
    result = build_analysis(events, "Meridian FC")
    assert result.match_ids == [101, 102, 103]
    assert len(result.progressions) == 4
    assert len(result.progressive_attempts) == 5
    assert sum(int(row["losses"]) for row in result.possession_losses) == 4
    assert result.player_involvement[0]["player"] == "Alex Forward"
    assert result.player_involvement[0]["small_sample"] is False


def test_report_is_deterministic(tmp_path: Path) -> None:
    events, warnings, matches = _events()
    result = build_analysis(events, "Meridian FC")
    first = write_report(tmp_path / "first.html", "Meridian FC", matches, result, warnings)  # type: ignore[arg-type]
    second = write_report(tmp_path / "second.html", "Meridian FC", matches, result, warnings)  # type: ignore[arg-type]
    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")
    assert "Candidate interpretation" in first.read_text(encoding="utf-8")
    assert "101" in first.read_text(encoding="utf-8")


def test_cli_smoke_uses_local_fixture(tmp_path: Path, capsys: object) -> None:
    output = tmp_path / "brief.html"
    code = main(
        [
            "build-demo-report",
            "--input-dir",
            str(FIXTURE_DIR),
            "--team",
            "Meridian FC",
            "--output",
            str(output),
        ]
    )
    assert code == 0
    assert output.exists()
