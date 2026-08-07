"""Small Plotly pitch view used for event evidence review."""

from __future__ import annotations

import plotly.graph_objects as go

from opposition_brief.models import NormalizedEvent
from opposition_brief.presentation import soccer_timestamp


def evidence_pitch(events: list[NormalizedEvent]) -> go.Figure:
    """Draw selected evidence rows on the normalized 100 by 100 pitch."""
    figure = go.Figure()
    figure.add_shape(type="rect", x0=0, y0=0, x1=100, y1=100, line={"color": "#ffffff"})
    figure.add_shape(type="line", x0=50, y0=0, x1=50, y1=100, line={"color": "#ffffff"})
    figure.add_shape(type="circle", x0=40, y0=40, x1=60, y1=60, line={"color": "#ffffff"})
    figure.add_annotation(
        x=96,
        y=94,
        ax=72,
        ay=94,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        text="Attacking direction",
        showarrow=True,
        arrowhead=3,
        arrowwidth=2,
        arrowcolor="#ffffff",
        font={"color": "#ffffff"},
    )
    for event in events:
        if event.start_x is None or event.start_y is None:
            continue
        label = (
            f"{soccer_timestamp(event.timestamp)} · {event.player or 'Unknown player'} · "
            f"{event.event_type or 'Action'}"
        )
        figure.add_trace(
            go.Scatter(
                x=[event.start_x],
                y=[event.start_y],
                mode="markers",
                marker={"color": "#ffcf4a", "size": 9},
                name=label,
                hovertemplate=f"{label}<extra></extra>",
                showlegend=False,
            )
        )
        if event.end_x is not None and event.end_y is not None:
            figure.add_trace(
                go.Scatter(
                    x=[event.start_x, event.end_x],
                    y=[event.start_y, event.end_y],
                    mode="lines",
                    line={"color": "#35a7a0", "width": 2},
                    hovertemplate=f"{label}<extra></extra>",
                    showlegend=False,
                )
            )
            figure.add_annotation(
                x=event.end_x,
                y=event.end_y,
                ax=event.start_x,
                ay=event.start_y,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                text="",
                showarrow=True,
                arrowhead=3,
                arrowwidth=2,
                arrowcolor="#35a7a0",
            )
    figure.update_layout(
        height=560,
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
        paper_bgcolor="#173c32",
        plot_bgcolor="#27734e",
        xaxis={"range": [0, 100], "visible": False, "constrain": "domain"},
        yaxis={"range": [100, 0], "visible": False, "scaleanchor": "x", "scaleratio": 1},
    )
    return figure
