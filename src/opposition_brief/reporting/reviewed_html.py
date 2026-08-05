"""Standalone, print-friendly reviewed report export."""

from __future__ import annotations

from html import escape
from pathlib import Path

from opposition_brief.demo import DemoProject, evidence_events
from opposition_brief.models import NormalizedEvent
from opposition_brief.review import ReviewedObservation


def _table(events: list[NormalizedEvent]) -> str:
    if not events:
        return "<p>No supporting source events are available.</p>"
    rows = "".join(
        "<tr>"
        f"<td>{escape(event.match_label)}</td><td>{escape(event.timestamp or '—')}</td>"
        f"<td>{escape(event.player or 'Unknown')}</td><td>{escape(event.event_type or 'Unknown')}</td>"
        f"<td>{escape(_location(event.start_x, event.start_y))}</td>"
        f"<td>{escape(_location(event.end_x, event.end_y))}</td>"
        f"<td>{escape(event.outcome or '—')}</td></tr>"
        for event in events
    )
    return (
        "<table><thead><tr><th>Match</th><th>Timestamp</th><th>Player</th><th>Action</th>"
        "<th>Start</th><th>End</th><th>Outcome</th></tr></thead><tbody>"
        f"{rows}</tbody></table>"
    )


def _location(x: float | None, y: float | None) -> str:
    return f"({x:.1f}, {y:.1f})" if x is not None and y is not None else "—"


def render_reviewed_report(project: DemoProject, observations: list[ReviewedObservation]) -> str:
    """Render only analyst-selected findings and escape every editable field."""
    coverage = "".join(
        f"<li>{escape(match.label)} (ID {match.match_id})</li>" for match in project.matches
    )
    warning_text = (
        "No data-quality warnings were recorded."
        if not project.warnings
        else "<br>".join(escape(warning.message) for warning in project.warnings)
    )
    sections = (
        "".join(
            f"<article><h3>{escape(item.review.title)}</h3>"
            f"<p><strong>Status:</strong> {escape(item.review.status)}</p>"
            f"<p><strong>Computed evidence (immutable):</strong> {escape(item.observation.computed_claim)}</p>"
            f"<p><strong>Analyst interpretation:</strong> {escape(item.review.interpretation)}</p>"
            f"<p><strong>Analyst note:</strong> {escape(item.review.analyst_note or 'None recorded.')}</p>"
            f"<p><strong>Limitation:</strong> {escape(' '.join(item.observation.limitations))}</p>"
            "<h4>Supporting source events</h4>"
            f"{_table(evidence_events(project, item.observation.supporting_event_ids))}</article>"
            for item in observations
        )
        or "<p>No observations are currently Accepted or marked Needs revision.</p>"
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{escape(project.opponent)} reviewed brief</title>
<style>
body {{ font-family: Arial, sans-serif; max-width: 1050px; margin: 28px auto; color: #172033; line-height: 1.45; padding: 0 20px; }}
h1 {{ color: #0d3b2e; }} article {{ break-inside: avoid; border: 1px solid #d5e1dc; padding: 14px; margin: 18px 0; }}
table {{ border-collapse: collapse; width: 100%; font-size: .9rem; }} th, td {{ border: 1px solid #ccd6d2; padding: 7px; text-align: left; }} th {{ background: #edf5f1; }}
@media print {{ body {{ max-width: none; margin: 0; }} article {{ page-break-inside: avoid; }} }}
</style></head><body>
<h1>{escape(project.opponent)} — Reviewed Opposition Brief</h1>
<h2>Coverage</h2><p>{escape(project.competition)} · {escape(project.season)} · {len(project.matches)} matches</p><ul>{coverage}</ul>
<h2>Data-quality warnings</h2><p>{warning_text}</p>
<h2>Reviewed observations</h2>{sections}
<h2>Limitations</h2><p>This is a three-match, event-data-only review. It cannot establish tactical intent, causal pressure mechanisms, or a correct tactical response. Match timestamps are provided for video review.</p>
</body></html>"""


def write_reviewed_report(
    output_path: Path, project: DemoProject, observations: list[ReviewedObservation]
) -> Path:
    """Write a standalone HTML reviewed report for local sharing or printing."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_reviewed_report(project, observations), encoding="utf-8")
    return output_path.resolve()
