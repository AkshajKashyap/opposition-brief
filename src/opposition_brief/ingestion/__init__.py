"""Read only the StatsBomb Open Data files needed for a report."""

from .statsbomb import list_competitions, load_local_bundle, prepare_demo_bundle

__all__ = ["list_competitions", "load_local_bundle", "prepare_demo_bundle"]
