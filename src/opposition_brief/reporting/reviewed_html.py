"""Standalone, print-friendly reviewed report export."""

from __future__ import annotations

from html import escape
from pathlib import Path

from opposition_brief.demo import DemoProject, evidence_events
from opposition_brief.models import MatchMetadata, NormalizedEvent
from opposition_brief.presentation import human_match_label, prepare_pattern_view, soccer_timestamp
from opposition_brief.review import ReviewedObservation


def _table(events: list[NormalizedEvent], matches: dict[int, MatchMetadata]) -> str:
    if not events:
        return "<p>No supporting source events are available.</p>"
    rows = "".join(
        "<tr>"
        f"<td>{escape(human_match_label(matches[event.match_id]))}</td>"
        f"<td>{escape(event.match_date or '—')}</td>"
        f"<td>{escape(soccer_timestamp(event.timestamp))}</td>"
        f"<td>{escape(event.player or 'Unknown')}</td><td>{escape(event.event_type or 'Unknown')}</td>"
        f"<td>{escape(_location(event.start_x, event.start_y))}</td>"
        f"<td>{escape(_location(event.end_x, event.end_y))}</td>"
        f"<td>{escape(event.outcome or '—')}</td></tr>"
        for event in events
    )
    return (
        "<table><thead><tr><th>Match</th><th>Date</th><th>Time</th><th>Player</th><th>Action</th>"
        "<th>Start</th><th>End</th><th>Outcome</th></tr></thead><tbody>"
        f"{rows}</tbody></table>"
    )


def _location(x: float | None, y: float | None) -> str:
    return f"({x:.1f}, {y:.1f})" if x is not None and y is not None else "—"


def render_reviewed_report(project: DemoProject, observations: list[ReviewedObservation]) -> str:
    """Render only analyst-selected findings and escape every editable field."""
    matches = {match.match_id: match for match in project.matches}
    coverage = "".join(f"<li>{escape(human_match_label(match))}</li>" for match in project.matches)
    sections = (
        "".join(
            f"<article><h3>{escape(prepare_pattern_view(project, item.observation).title)}</h3>"
            f'<p class="finding">{escape(prepare_pattern_view(project, item.observation).finding)}</p>'
            f"<p><strong>Analyst interpretation:</strong> {escape(item.review.interpretation)}</p>"
            f"<p><strong>Analyst note:</strong> {escape(item.review.analyst_note or 'None recorded.')}</p>"
            f"<p><strong>Limitation:</strong> {escape(' '.join(item.observation.limitations))}</p>"
            "<h4>Representative sequences</h4>"
            f"{_table(evidence_events(project, item.observation.supporting_event_ids)[:8], matches)}</article>"
            for item in observations
        )
        or "<p>No observations are currently Accepted or marked Needs revision.</p>"
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{escape(project.opponent)} reviewed brief</title>
<style>
:root {{ color-scheme: light; }}
html, body {{ background: #ffffff !important; color: #15231e !important; }}
body {{ font-family: Arial, Helvetica, sans-serif; max-width: 1050px; margin: 28px auto; line-height: 1.5; padding: 0 24px; }}
h1, h2, h3, h4 {{ color: #123c2c !important; }} h1 {{ margin-bottom: 0; }}
article {{ background: #ffffff !important; break-inside: avoid; border: 1px solid #9db8aa; border-left: 6px solid #176c4c; padding: 18px; margin: 22px 0; }}
.finding {{ color: #15231e !important; font-size: 1.08rem; font-weight: 700; }}
table {{ border-collapse: collapse; width: 100%; font-size: .9rem; background: #ffffff !important; }}
th, td {{ border: 1px solid #8ca79a; color: #15231e !important; padding: 8px; text-align: left; vertical-align: top; }}
th {{ background: #e6f1eb !important; color: #123c2c !important; }}
@media print {{ @page {{ margin: 14mm; }} body {{ max-width: none; margin: 0; padding: 0; }} article {{ page-break-inside: avoid; }} }}
</style></head><body>
<h1>{escape(project.opponent)} — Opposition Brief</h1>
<h2>Coverage</h2><p>{escape(project.competition)} · {escape(project.season)} · {len(project.matches)} matches</p><ul>{coverage}</ul>
<h2>Patterns for review</h2>{sections}
<h2>Limitations</h2><p>This is a three-match, event-data-only review. It cannot establish tactical intent, causal pressure mechanisms, or a correct tactical response. Match timestamps are provided for video review.</p>
</body></html>"""


def write_reviewed_report(
    output_path: Path, project: DemoProject, observations: list[ReviewedObservation]
) -> Path:
    """Write a standalone HTML reviewed report for local sharing or printing."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_reviewed_report(project, observations), encoding="utf-8")
    return output_path.resolve()
