"""Static HTML output for the opposition brief."""

from .html import write_report
from .reviewed_html import write_reviewed_report

__all__ = ["write_report", "write_reviewed_report"]
