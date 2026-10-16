"""A simple ML workflow: can the events of the previous days help to flag a large move of a price series?

Steps: build one row per trading day (features = event counts per theme over the last days), split chronologically
(past to train, future to test), fit a regularised logistic regression with numpy, measure the AUC on the test period,
then store a `Claim` (status `hypothesis`) for each theme whose weight is positive when the model beats chance.
A claim is a statistical association measured on a small sample. It is never a proven cause.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np

from app.services.analytics.queries import EVENTS_PER_DAY_BY_THEME, RETURNS, run_query

METHOD = "logistic_regression_numpy"
MIN_AUC = 0.55
MIN_TRAIN_DAYS = 40

STORE_CLAIM = """
MERGE (c:Claim {claim_id: $claim_id})
SET c.kind = 'theme_precedes_large_move', c.status = 'hypothesis', c.confidence = $confidence,
    c.method = $method, c.rationale = $rationale, c.created_at = datetime()
WITH c
MATCH (s:PriceSeries {series_id: $series_id})
MERGE (c)-[:ABOUT_SERIES]->(s)
"""

LINK_CLAIM_EVENT = """
MATCH (c:Claim {claim_id: $claim_id}), (e:Event {event_id: $event_id})
MERGE (c)-[:ABOUT_EVENT]->(e)
"""


def build_dataset(
    events: list[dict], returns: list[tuple[str, float]], lookback: int = 2
) -> tuple[list[str], np.ndarray, np.ndarray, list[str]]:
    """One row per return day. Features: events of each theme during the `lookback` days before that day.

    Returns (days, features, absolute returns, theme codes).
    """
    themes = sorted({row["theme"] for row in events})
    counts = {(row["theme"], row["day"]): row["n"] for row in events}
    days, features, moves = [], [], []
    for day, ret in returns:
        current = date.fromisoformat(day)
        window = [(current - timedelta(days=k)).isoformat() for k in range(1, lookback + 1)]
        features.append([sum(counts.get((theme, d), 0) for d in window) for theme in themes])
        days.append(day)
        moves.append(abs(ret))
    return days, np.asarray(features, dtype=float).reshape(len(days), len(themes)), np.asarray(moves), themes


def chronological_split(size: int, train_share: float = 0.7) -> int:
    """Index where the test period starts: the model never sees the future."""
    return int(size * train_share)


def fit_logistic(x: np.ndarray, y: np.ndarray, l2: float = 1.0, steps: int = 500, rate: float = 0.1) -> np.ndarray:
    """Logistic regression by gradient descent. Returns the weights, bias last. `x` must be standardised."""
    design = np.hstack([x, np.ones((len(x), 1))])
    weights = np.zeros(design.shape[1])
    for _ in range(steps):
        prob = 1.0 / (1.0 + np.exp(-np.clip(design @ weights, -30, 30)))
        gradient = design.T @ (prob - y) / len(y)
        gradient[:-1] += l2 * weights[:-1] / len(y)
        weights -= rate * gradient
    return weights


def predict(x: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Probability of a large move for each row."""
    design = np.hstack([x, np.ones((len(x), 1))])
    return 1.0 / (1.0 + np.exp(-np.clip(design @ weights, -30, 30)))


def auc(y_true: np.ndarray, scores: np.ndarray) -> float | None:
    """Area under the ROC curve (rank formula). None when only one class is present."""
    positives = int(y_true.sum())
    negatives = len(y_true) - positives
    if positives == 0 or negatives == 0:
        return None
    ranks = scores.argsort().argsort() + 1.0
    return float((ranks[y_true == 1].sum() - positives * (positives + 1) / 2) / (positives * negatives))


def train_and_evaluate(
    features: np.ndarray, moves: np.ndarray, quantile: float = 0.75, train_share: float = 0.7
) -> dict | None:
    """Fit on the past, evaluate on the future: weights per feature and test AUC (None if too little data)."""
    cut = chronological_split(len(moves), train_share)
    if cut < MIN_TRAIN_DAYS or len(moves) - cut < 10:
        return None
    threshold = float(np.quantile(moves[:cut], quantile))
    labels = (moves > threshold).astype(float)
    mean, std = features[:cut].mean(axis=0), features[:cut].std(axis=0)
    std[std == 0] = 1.0
    scaled = (features - mean) / std
    weights = fit_logistic(scaled[:cut], labels[:cut])
    test_scores = predict(scaled[cut:], weights)
    return {
        "weights": weights[:-1],
        "auc_test": auc(labels[cut:], test_scores),
        "train_days": cut,
        "test_days": len(moves) - cut,
        "threshold": threshold,
    }


def run_workflow(session: Any, series_id: str, start: str, end: str, lookback: int = 2) -> dict:
    """Load the data, train, evaluate, and return the candidate claims (nothing is written yet)."""
    margin = lookback + 1
    events = run_query(session, EVENTS_PER_DAY_BY_THEME, start=start, end=end, margin=margin)
    returns = [(r["day"], r["ret"]) for r in run_query(session, RETURNS, series_id=series_id, start=start, end=end)]
    _, features, moves, themes = build_dataset(events, returns, lookback)
    if not themes:
        return {"series_id": series_id, "model": None, "claims": []}
    model = train_and_evaluate(features, moves)
    claims = []
    if model and model["auc_test"] is not None and model["auc_test"] >= MIN_AUC:
        for theme, weight in zip(themes, model["weights"]):
            if weight > 0:
                claims.append(
                    {"theme": theme, "weight": round(float(weight), 4), "confidence": round(model["auc_test"], 3)}
                )
    claims.sort(key=lambda c: c["weight"], reverse=True)
    return {"series_id": series_id, "model": model, "claims": claims}


def claim_rationale(theme: str, series_id: str, confidence: float, lookback: int) -> str:
    """Neutral wording: an association measured on a held-out period, not a cause."""
    return (
        f"Days with more {theme} events in the {lookback} days before are associated with larger moves of "
        f"{series_id} (held-out AUC {confidence}). Statistical association on a short sample, not a proven cause."
    )


def store_claims(session: Any, result: dict, lookback: int = 2, evidence: dict | None = None) -> int:
    """Write the claims as `Claim` nodes with status hypothesis. `evidence` maps a theme to supporting event ids."""
    series_id = result["series_id"]
    for item in result["claims"]:
        claim_id = f"{series_id}-{item['theme']}-{METHOD}"
        session.run(
            STORE_CLAIM,
            claim_id=claim_id,
            confidence=item["confidence"],
            method=METHOD,
            rationale=claim_rationale(item["theme"], series_id, item["confidence"], lookback),
            series_id=series_id,
        )
        for event_id in (evidence or {}).get(item["theme"], []):
            session.run(LINK_CLAIM_EVENT, claim_id=claim_id, event_id=event_id)
    return len(result["claims"])
