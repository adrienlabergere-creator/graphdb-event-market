"""Run the analytics end to end on the loaded graph and print a summary.

Usage:
    python -m scripts.run_analytics --series BRENT --store     # --store writes CORRELATES_WITH and Claim nodes
"""

from __future__ import annotations

import argparse

from app.database.connection import get_driver
from app.services.analytics import (
    compute_theme_correlations,
    events_before_moves,
    run_gds,
    run_workflow,
    store_claims,
    store_correlations,
)
from app.services.analytics.constants import DEFAULT_END, DEFAULT_SERIES, DEFAULT_START


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--series", default=DEFAULT_SERIES)
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    parser.add_argument("--store", action="store_true", help="write correlations and claims to the graph")
    parser.add_argument("--skip-gds", action="store_true")
    args = parser.parse_args()
    with get_driver().session() as session:
        rows = compute_theme_correlations(session, args.series, args.start, args.end)
        print("Strongest correlations (theme, lag, corr, n):")
        for row in rows[:8]:
            print(f"  {row['theme']:<16} lag {row['lag_days']} corr {row['corr']:+.3f} n {row['n']}")
        result = run_workflow(session, args.series, args.start, args.end)
        model = result["model"]
        auc_test = round(model["auc_test"] or 0, 3) if model else None
        print(f"ML: {len(result['claims'])} claim(s), held-out AUC {auc_test}")
        if args.store:
            stored = store_correlations(session, rows, args.start, args.end)
            evidence = {}
            for claim in result["claims"]:
                found = events_before_moves(session, args.series, args.start, args.end, theme=claim["theme"], limit=3)
                evidence[claim["theme"]] = [r["event_id"] for r in found]
            print(f"Stored {stored} correlations and {store_claims(session, result, evidence=evidence)} claims.")
        if not args.skip_gds:
            gds = run_gds(session, limit=10)
            print("PageRank:", [(r["iso3"], round(r["score"], 3)) for r in gds["pagerank"]])
            print("Communities:", [r["countries"] for r in gds["communities"]][:4])


if __name__ == "__main__":
    main()
