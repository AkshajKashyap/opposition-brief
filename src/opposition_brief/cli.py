"""Command-line entry points for the first StatsBomb report vertical slice."""

from __future__ import annotations

import argparse
from pathlib import Path

from opposition_brief.analysis.metrics import build_analysis
from opposition_brief.ingestion.statsbomb import (
    DEFAULT_COMPETITION_ID,
    DEFAULT_SEASON_ID,
    DEFAULT_TEAM,
    list_competitions,
    load_local_bundle,
    prepare_demo_bundle,
)
from opposition_brief.normalization.statsbomb import normalize_events
from opposition_brief.reporting.html import write_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build an evidence-linked soccer opposition brief."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser(
        "list-competitions", help="List cached or official StatsBomb competitions."
    )
    listing.add_argument("--data-dir", type=Path, default=Path("data/raw/statsbomb"))
    listing.add_argument("--offline", action="store_true")
    build = commands.add_parser("build-demo-report", help="Build a three-match static HTML report.")
    build.add_argument("--team", default=DEFAULT_TEAM)
    build.add_argument("--competition-id", type=int, default=DEFAULT_COMPETITION_ID)
    build.add_argument("--season-id", type=int, default=DEFAULT_SEASON_ID)
    build.add_argument("--data-dir", type=Path, default=Path("data/raw/statsbomb"))
    build.add_argument(
        "--input-dir", type=Path, help="Local bundle containing matches.json and events/<id>.json."
    )
    build.add_argument("--offline", action="store_true")
    build.add_argument(
        "--output", type=Path, default=Path("reports/generated/opposition_brief.html")
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run a command; return a process-friendly status code."""
    args = _parser().parse_args(argv)
    try:
        if args.command == "list-competitions":
            for item in list_competitions(args.data_dir, offline=args.offline):
                print(
                    f"{item.get('competition_id')} / {item.get('season_id')}: {item.get('competition_name')} — {item.get('season_name')}"
                )
            return 0
        if args.input_dir:
            matches, payloads = load_local_bundle(args.input_dir, args.team)
        else:
            matches, payloads = prepare_demo_bundle(
                args.data_dir, args.team, args.competition_id, args.season_id, args.offline
            )
        events = []
        warnings = []
        for match in matches:
            normalized = normalize_events(payloads[match.match_id], match)
            events.extend(normalized.events)
            warnings.extend(normalized.warnings)
        result = build_analysis(events, args.team)
        path = write_report(args.output, args.team, matches, result, warnings)
        print(f"Report written: {path}")
        print(
            f"Processed {len(matches)} matches, {len(events)} events, {len(warnings)} data-quality warnings."
        )
        return 0
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        print(f"Error: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
