"""EXPLAIN and PROFILE helpers, used by the benchmark script."""

from __future__ import annotations

from typing import Any


def count_db_hits(plan: dict | None) -> int:
    """Sum the database hits of a PROFILE plan, including all its children."""
    if not plan:
        return 0
    total = int(plan.get("dbHits", 0) or 0)
    for child in plan.get("children", []) or []:
        total += count_db_hits(child)
    return total


def operators(plan: dict | None) -> list[str]:
    """Operator names of a plan, from the root down (depth first)."""
    if not plan:
        return []
    names = [plan.get("operatorType", "?")]
    for child in plan.get("children", []) or []:
        names += operators(child)
    return names


def explain(session: Any, query: str, **params: Any) -> list[str]:
    """Return the operators of the estimated plan (the query is not executed)."""
    summary = session.run("EXPLAIN " + query, **params).consume()
    return operators(summary.plan)


def profile(session: Any, query: str, **params: Any) -> dict:
    """Execute the query with PROFILE and return rows, database hits and elapsed milliseconds."""
    result = session.run("PROFILE " + query, **params)
    rows = len(list(result))
    summary = result.consume()
    return {
        "rows": rows,
        "db_hits": count_db_hits(summary.profile),
        "ms": summary.result_consumed_after,
        "operators": operators(summary.profile),
    }
