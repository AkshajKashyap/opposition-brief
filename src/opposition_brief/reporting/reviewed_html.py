"""Standalone, print-friendly reviewed report export."""

from __future__ import annotations

from html import escape
from pathlib import Path

from opposition_brief.demo import DemoProject
from opposition_brief.presentation import EvidenceItem, human_match_label, prepare_pattern_view
from opposition_brief.review import ReviewedObservation


def _table(events: tuple[EvidenceItem, ...]) -> str:
    if not events:
        return "<p>No representative actions are available.</p>"
    rows = "".join(
        "<tr>"
        f"<td>{escape(event.match)}</td><td>{escape(event.date)}</td>"
        f"<td>{escape(event.timestamp)}</td><td>{escape(event.player)}</td>"
        f"<td>{escape(event.description)}</td></tr>"
        for event in events
    )
    return (
        "<table><thead><tr><th>Match</th><th>Date</th><th>Time</th><th>Player</th>"
        "<th>Action</th></tr></thead><tbody>"
        f"{rows}</tbody></table>"
    )


def render_reviewed_report(project: DemoProject, observations: list[ReviewedObservation]) -> str:
    """Render only analyst-selected findings and escape every editable field."""
    coverage = "".join(f"<li>{escape(human_match_label(match))}</li>" for match in project.matches)
    sections = (
        "".join(
            f"<article><h3>{escape(view.title)}</h3>"
            f'<p class="finding">{escape(view.finding)}</p>'
            f"<p><strong>Analyst interpretation:</strong> {escape(item.review.interpretation)}</p>"
            f"<p><strong>Analyst note:</strong> {escape(item.review.analyst_note or 'None recorded.')}</p>"
            f"<p><strong>Limitation:</strong> {escape(' '.join(item.observation.limitations))}</p>"
            "<h4>Representative actions</h4>"
            f"{_table(view.evidence)}</article>"
            for item in observations
            for view in [prepare_pattern_view(project, item.observation)]
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
