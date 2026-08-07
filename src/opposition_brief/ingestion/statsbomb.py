"""Minimal, cache-aware access to the official StatsBomb Open Data layout."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.request import urlopen

from opposition_brief.models import MatchMetadata, RawEvent

OPEN_DATA_BASE_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
DEFAULT_COMPETITION_ID = 43  # FIFA World Cup
DEFAULT_SEASON_ID = 106  # 2022
DEFAULT_TEAM = "Argentina"
DEMO_MATCH_COUNT = 5


def _read_json(path: Path) -> object:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _download(relative_path: str, cache_root: Path) -> Path:
    """Download one Open Data JSON document once; never clone the full dataset."""
    destination = cache_root / relative_path
    if destination.exists():
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urlopen(f"{OPEN_DATA_BASE_URL}/{relative_path}", timeout=30) as response:
            destination.write_bytes(response.read())
    except OSError as error:
        raise RuntimeError(
            f"Could not retrieve StatsBomb Open Data file {relative_path}: {error}. "
            "Re-run with network access or supply --input-dir."
        ) from error
    return destination


def list_competitions(cache_root: Path, offline: bool = False) -> list[dict[str, object]]:
    """Return official competition/season records, reading cache first."""
    path = cache_root / "competitions.json"
    if not path.exists():
        if offline:
            raise RuntimeError("competitions.json is not cached; cannot list competitions offline.")
        path = _download("competitions.json", cache_root)
    data = _read_json(path)
    return data if isinstance(data, list) else []


def _metadata(match: dict[str, object]) -> MatchMetadata:
    def nested_name(key: str) -> str | None:
        value = match.get(key)
        if not isinstance(value, dict):
            return None
        # Open Data's match files use provider-specific names such as
        # ``home_team_name``; local fixtures may use the compact ``name`` form.
        candidate = value.get("name") or value.get(f"{key}_name")
        return candidate if isinstance(candidate, str) else None

    return MatchMetadata(
        match_id=int(match["match_id"]),
        match_date=str(match.get("match_date")) if match.get("match_date") else None,
        competition=nested_name("competition"),
        season=nested_name("season"),
        home_team=nested_name("home_team"),
        away_team=nested_name("away_team"),
    )


def load_local_bundle(
    input_dir: Path, team: str
) -> tuple[list[MatchMetadata], dict[int, list[RawEvent]]]:
    """Read a small StatsBomb-shaped bundle: matches.json and events/<id>.json."""
    matches_data = _read_json(input_dir / "matches.json")
    if not isinstance(matches_data, list):
        raise TypeError("matches.json must contain a list of StatsBomb match records.")
    matches = [_metadata(item) for item in matches_data if isinstance(item, dict)]
    selected = [match for match in matches if team in {match.home_team, match.away_team}]
    if len(selected) < 3:
        raise ValueError(
            f"{team!r} has only {len(selected)} local matches; at least three are required."
        )
    selected = sorted(
        selected, key=lambda match: (match.match_date or "", match.match_id), reverse=True
    )[:DEMO_MATCH_COUNT]
    events = {
        match.match_id: _read_events(input_dir / "events" / f"{match.match_id}.json")
        for match in selected
    }
    return selected, events


def _read_events(path: Path) -> list[RawEvent]:
    data = _read_json(path)
    if not isinstance(data, list):
        raise TypeError(f"{path} must contain an event list.")
    return [item for item in data if isinstance(item, dict)]


def prepare_demo_bundle(
    cache_root: Path,
    team: str = DEFAULT_TEAM,
    competition_id: int = DEFAULT_COMPETITION_ID,
    season_id: int = DEFAULT_SEASON_ID,
    offline: bool = False,
) -> tuple[list[MatchMetadata], dict[int, list[RawEvent]]]:
    """Select three recent matches and retrieve only their match, lineup, and event files."""
    matches_path = cache_root / "matches" / str(competition_id) / f"{season_id}.json"
    if not matches_path.exists():
        if offline:
            raise RuntimeError("Requested match list is not cached; cannot build offline.")
        matches_path = _download(f"matches/{competition_id}/{season_id}.json", cache_root)
    matches_data = _read_json(matches_path)
    if not isinstance(matches_data, list):
        raise TypeError("StatsBomb match list did not contain a list.")
    candidates = [_metadata(item) for item in matches_data if isinstance(item, dict)]
    selected = [match for match in candidates if team in {match.home_team, match.away_team}]
    if len(selected) < 3:
        raise ValueError(
            f"{team!r} has only {len(selected)} available matches in this competition/season."
        )
    selected = sorted(
        selected, key=lambda match: (match.match_date or "", match.match_id), reverse=True
    )[:DEMO_MATCH_COUNT]
    payloads: dict[int, list[RawEvent]] = {}
    for match in selected:
        events_path = cache_root / "events" / f"{match.match_id}.json"
        lineup_path = cache_root / "lineups" / f"{match.match_id}.json"
        if not events_path.exists() and offline:
            raise RuntimeError(
                f"Events for match {match.match_id} are not cached; cannot build offline."
            )
        if not events_path.exists():
            events_path = _download(f"events/{match.match_id}.json", cache_root)
        if not lineup_path.exists() and not offline:
            _download(f"lineups/{match.match_id}.json", cache_root)
        payloads[match.match_id] = _read_events(events_path)
    return selected, payloads
