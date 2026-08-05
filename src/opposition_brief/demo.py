"""Cache-only data preparation shared by Streamlit and offline tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from opposition_brief.analysis.metrics import AnalysisResult, build_analysis
from opposition_brief.ingestion.statsbomb import DEFAULT_TEAM, prepare_demo_bundle
from opposition_brief.models import MatchMetadata, NormalizedEvent, ValidationWarning
from opposition_brief.normalization.statsbomb import normalize_events
from opposition_brief.observations import CandidateObservation, build_candidate_observations


@dataclass(frozen=True)
class DemoProject:
    opponent: str
    matches: list[MatchMetadata]
    events: list[NormalizedEvent]
    warnings: list[ValidationWarning]
    analysis: AnalysisResult
    observations: list[CandidateObservation]

    @property
    def competition(self) -> str:
        return next((match.competition for match in self.matches if match.competition), "Unknown")

    @property
    def season(self) -> str:
        return next((match.season for match in self.matches if match.season), "Unknown")

    @property
    def possession_count(self) -> int:
        return len(
            {event.possession_id for event in self.events if event.possession_id is not None}
        )


@dataclass(frozen=True)
class DemoLoadResult:
    project: DemoProject | None
    message: str | None


def load_cached_demo_project(
    cache_root: Path = Path("data/raw/statsbomb"), team: str = DEFAULT_TEAM
) -> DemoLoadResult:
    """Build display artifacts from cached files only, never causing a Streamlit download."""
    try:
        matches, payloads = prepare_demo_bundle(cache_root, team=team, offline=True)
        return DemoLoadResult(_assemble_project(team, matches, payloads), None)
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        return DemoLoadResult(
            None,
            "Demo artifacts are unavailable or malformed. Run "
            "`opposition-brief build-demo-report` from the repository root, then refresh. "
            f"Details: {error}",
        )


def build_local_demo_project(input_dir: Path, team: str) -> DemoProject:
    """Prepare a deterministic project from a local bundle for tests or demos."""
    from opposition_brief.ingestion.statsbomb import load_local_bundle

    matches, payloads = load_local_bundle(input_dir, team)
    return _assemble_project(team, matches, payloads)


def _assemble_project(
    team: str, matches: list[MatchMetadata], payloads: dict[int, list[dict[str, object]]]
) -> DemoProject:
    events: list[NormalizedEvent] = []
    warnings: list[ValidationWarning] = []
    for match in matches:
        normalized = normalize_events(payloads[match.match_id], match)
        events.extend(normalized.events)
        warnings.extend(normalized.warnings)
    analysis = build_analysis(events, team)
    return DemoProject(
        opponent=team,
        matches=matches,
        events=events,
        warnings=warnings,
        analysis=analysis,
        observations=build_candidate_observations(analysis, len(matches)),
    )


def evidence_events(project: DemoProject, event_ids: tuple[str, ...]) -> list[NormalizedEvent]:
    """Return source events in deterministic timestamp order, ignoring absent IDs safely."""
    wanted = set(event_ids)
    return sorted(
        (event for event in project.events if event.source_event_id in wanted),
        key=lambda event: (
            event.match_date or "",
            event.period or 0,
            event.timestamp_seconds if event.timestamp_seconds is not None else -1,
            event.source_event_id or "",
        ),
    )
