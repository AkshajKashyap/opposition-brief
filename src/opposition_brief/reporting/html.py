"""Deterministic static HTML report with traceable source evidence."""

from __future__ import annotations

from html import escape
from pathlib import Path

from opposition_brief.analysis.metrics import AnalysisResult, event_evidence
from opposition_brief.models import MatchMetadata, ValidationWarning
from opposition_brief.observations import CandidateObservation, build_candidate_observations


def _table(
    rows: list[dict[str, object]],
    columns: list[tuple[str, str]],
    empty_message: str = "No qualifying events in the supplied matches.",
) -> str:
    if not rows:
        return f'<p class="empty">{escape(empty_message)}</p>'
    head = "".join(f"<th>{escape(label)}</th>" for _, label in columns)
    body = "".join(
        "<tr>"
        + "".join(f"<td>{escape(str(row.get(key, '—')))}</td>" for key, _ in columns)
        + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _candidate_observations(
    result: AnalysisResult, selected_match_count: int
) -> list[tuple[CandidateObservation, list[dict[str, object]]]]:
    events = {event.source_event_id: event for event in result.progressions + result.losses}
    return [
        (
            observation,
            [
                event_evidence(events[event_id])
                for event_id in observation.supporting_event_ids
                if event_id in events
            ][:5],
        )
        for observation in build_candidate_observations(result, selected_match_count)
    ]


def render_report(
    team: str,
    matches: list[MatchMetadata],
    result: AnalysisResult,
    warnings: list[ValidationWarning],
) -> str:
    """Render a reproducible report without timestamps, random IDs, or an LLM."""
    coverage = "".join(f"<li>{escape(match.label)} (ID {match.match_id})</li>" for match in matches)
    warning_rows = [
        {
            "match": warning.match_id,
            "event": warning.event_id or "—",
            "field": warning.field,
            "message": warning.message,
        }
        for warning in warnings
    ]
    player_rows = [
        {
            **row,
            "completion_rate": f"{row['completion_rate']}%",
            "forward_distance": f"{row['forward_distance']:.1f}",
            "sample_note": "Small sample" if row["small_sample"] else "",
        }
        for row in result.player_involvement
    ]
    observations = _candidate_observations(result, len(matches))
    observation_html = (
        "".join(
            f'<article class="observation"><h3>{escape(observation.title)}</h3>'
            f"<p><strong>Computed fact:</strong> {escape(observation.computed_claim)}</p>"
            f"<p><strong>Candidate interpretation:</strong> {escape(observation.interpretation)}</p>"
            + _table(
                evidence,
                [
                    ("match", "Match"),
                    ("period", "Period"),
                    ("timestamp", "Timestamp"),
                    ("player", "Player"),
                    ("action", "Action"),
                    ("start", "Start"),
                    ("end", "End"),
                    ("outcome", "Outcome"),
                ],
            )
            + "</article>"
            for observation, evidence in observations
        )
        or '<p class="empty">No observations could be generated from qualifying events.</p>'
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{escape(team)} opposition brief</title>
<style>
body {{ font-family: Arial, sans-serif; max-width: 1180px; margin: 32px auto; color: #172033; line-height: 1.45; padding: 0 20px; }}
h1 {{ color: #0d3b2e; }} h2 {{ margin-top: 32px; border-bottom: 2px solid #d6e5df; padding-bottom: 6px; }}
table {{ border-collapse: collapse; width: 100%; font-size: .92rem; margin: 12px 0; }} th, td {{ border: 1px solid #d8dee9; padding: 8px; text-align: left; }} th {{ background: #edf5f1; }}
.notice {{ background: #fff7dc; padding: 12px; border-left: 4px solid #cc9a06; }} .observation {{ background: #f6f8fb; padding: 8px 16px; margin: 14px 0; }} .empty {{ color: #657386; font-style: italic; }}
</style></head><body>
<h1>{escape(team)} — Opposition Brief</h1>
<p>This is a descriptive, evidence-linked first report. Coordinates are normalized to 0–100 × 0–100.</p>
<h2>Coverage</h2><p>{len(matches)} matches observed; {len(result.match_ids)} contain events for {escape(team)}.</p><ul>{coverage}</ul>
<h2>Data quality warnings</h2><p>{len(warnings)} non-fatal warnings were retained during normalization.</p>{_table(warning_rows, [("match", "Match"), ("event", "Event"), ("field", "Field"), ("message", "Warning")], "No data-quality warnings were recorded.")}
<h2>Progression routes</h2><p>Completed passes or carries advancing at least 10 normalized units and reducing straight-line distance to goal by at least 10.</p>{_table(result.progression_routes, [("channel", "Channel"), ("origin_third", "Origin third"), ("destination_third", "Destination third"), ("match_id", "Match"), ("completed_progressions", "Completed")])}
<h2>Progressive player involvement</h2><p>Forward distance is the total for completed progressive actions. “Small sample” means fewer than three attempts.</p>{_table(player_rows, [("player", "Player"), ("attempted", "Attempted"), ("completed", "Completed"), ("completion_rate", "Completion rate"), ("forward_distance", "Forward distance"), ("matches_observed", "Matches"), ("sample_note", "Note")])}
<h2>Possession-loss locations</h2><p>Includes incomplete passes, dispossessions, miscontrols, and incomplete dribbles; it does not by itself measure pressing vulnerability.</p>{_table(result.possession_losses, [("zone", "Pitch zone"), ("match_id", "Match"), ("losses", "Losses")])}
<h2>Candidate observations and evidence</h2>{observation_html}
<h2>Limitations</h2><div class="notice"><ul><li>This report uses three matches and event data only; it cannot establish tactical intent.</li><li>Progression is a transparent geometric rule, not a possession-value model.</li><li>Event-defined losses do not identify the cause of a turnover or fully measure pressure.</li><li>Review the linked match, period, and timestamp before drawing a coaching conclusion.</li></ul></div>
</body></html>"""


def write_report(
    output_path: Path,
    team: str,
    matches: list[MatchMetadata],
    result: AnalysisResult,
    warnings: list[ValidationWarning],
) -> Path:
    """Write the static report and return its resolved path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_report(team, matches, result, warnings), encoding="utf-8")
    return output_path.resolve()
