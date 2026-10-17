"""Fakes shared by the API and agent tests: no database and no model are needed."""

from app.models.agent import AnswerDraft, Plan


class FakeSession:
    """Answers each query with the rows registered for its `// name` marker (empty list otherwise)."""

    def __init__(self, rows=None, error=None):
        self.rows = rows or {}
        self.error = error
        self.queries = []

    def run(self, query, **params):  # pylint: disable=unused-argument
        """Record the query and return the canned rows."""
        text = getattr(query, "text", query)
        self.queries.append(text)
        if self.error:
            raise self.error
        for marker, rows in self.rows.items():
            if f"// {marker}" in text:
                return list(rows)
        return []


class FakeLLM:
    """Scripted model: returns the given plans in order, then `finish`, and a fixed answer."""

    def __init__(self, plans=(), answer=None, bad_compose=0):
        self.plans = list(plans)
        self.answer = answer or AnswerDraft(answer="BRENT moved after the event.", confidence=0.6)
        self.bad_compose = bad_compose
        self.compose_calls = 0

    def plan(self, question, history):  # pylint: disable=unused-argument
        """Next scripted plan."""
        return self.plans.pop(0) if self.plans else Plan(tool="finish")

    def compose(self, question, history):  # pylint: disable=unused-argument
        """Fixed answer, after `bad_compose` malformed outputs."""
        self.compose_calls += 1
        if self.compose_calls <= self.bad_compose:
            raise ValueError("malformed output")
        return self.answer


def series_rows(days=40, ret=0.01):
    """Return rows for the `returns` query: one per day."""
    return [
        {"day": f"2026-06-{d:02d}" if d < 30 else f"2026-07-{d - 29:02d}", "ret": ret * (d % 5)}
        for d in range(1, days + 1)
    ]


MOVE_ROWS = {
    "latest_day": [{"day": "2026-07-31"}],
    "timeline": [
        {"day": "2026-07-29", "events": 3, "close": 80.0, "ret_1d": 0.01},
        {"day": "2026-07-30", "events": 5, "close": 84.0, "ret_1d": 0.05},
    ],
    "events_before_moves": [
        {"event_id": "GDELT-1", "title": "A / B: fight", "mentions": 200},
        {"event_id": "GDELT-2", "title": "C / D: protest", "mentions": 100},
    ],
    "paths_event_to_series": [
        {"nodes": ["GDELT-1", "2026-07-29", "BRENT"], "relations": ["ON_DAY", "PRICE_ON"], "hops": 2}
    ],
}
