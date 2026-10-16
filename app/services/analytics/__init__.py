"""Analytics services: Cypher queries, correlations, paths, Graph Data Science and a simple ML workflow.

Every function takes an open Neo4j session as its first argument and returns plain Python lists and dictionaries.
"""

from app.services.analytics.correlation import compute_theme_correlations, store_correlations
from app.services.analytics.gds import run_gds
from app.services.analytics.link_prediction import run_workflow, store_claims
from app.services.analytics.paths import paths_between_countries, paths_event_to_series
from app.services.analytics.queries import (
    events_before_moves,
    theme_impact,
    timeline,
    top_countries,
    top_events,
)

__all__ = [
    "compute_theme_correlations",
    "events_before_moves",
    "paths_between_countries",
    "paths_event_to_series",
    "run_gds",
    "run_workflow",
    "store_claims",
    "store_correlations",
    "theme_impact",
    "timeline",
    "top_countries",
    "top_events",
]
