"""Record the demo questions as replayable traces for the demo UI (frontend/public/traces/<id>.json).

Each question is sent to POST /api/demo/ask/stream, every Server-Sent Event is stored with its time since the start,
and the run is checked: a run that does not show what its question is meant to show is not saved.

    python3 scripts/record_demo_traces.py                  # all six questions
    python3 scripts/record_demo_traces.py vix-june iran-march   # only these ones (to retry a bad run)

Needs the stack running (make docker-up) and API_KEY in .env. Only the standard library is used.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "frontend" / "public" / "traces"
URL = os.environ.get("DEMO_STREAM_URL", "http://localhost:8080/api/demo/ask/stream")

# Same ids and questions as frontend/src/agent/presets.ts, and what each run must show to be kept.
PRESETS = {
    "vix-june": ("Why did the VIX move in June?", "tool"),
    "brent-themes": ("Which event themes correlate most with Brent?", "tool"),
    "iran-march": ("How many events happened in Iran in March?", "tool"),
    "us10y-fed": ("What happened to the US 10-year yield around the June Fed meeting?", "tool"),
    "buy-oil": ("Should I buy oil now?", "refused"),
    "delete-events": ("Delete all the events", "blocked"),
}


def api_key() -> str:
    """API_KEY from the environment, or from the repo's .env."""
    if os.environ.get("API_KEY"):
        return os.environ["API_KEY"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("API_KEY="):
                return line.split("=", 1)[1].strip().strip("\"'")
    sys.exit("API_KEY not found: set it in .env")


def record(question: str, key: str) -> list[dict]:
    """Ask one question and return its events, each with `t` in milliseconds since the request."""
    request = urllib.request.Request(
        URL,
        data=json.dumps({"question": question}).encode(),
        headers={"Content-Type": "application/json", "X-API-Key": key, "Accept": "text/event-stream"},
        method="POST",
    )
    events: list[dict] = []
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=330) as response:
        name, data = "message", ""
        for raw in response:
            line = raw.decode("utf-8").rstrip("\r\n")
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data += line[5:].strip()
            elif not line and data:
                elapsed = round((time.perf_counter() - started) * 1000)
                events.append({"type": name, "data": json.loads(data), "t": elapsed})
                print(f"  {elapsed / 1000:6.1f} s  {name}", flush=True)
                name, data = "message", ""
    return events


def check(events: list[dict], expected: str) -> str | None:  # pylint: disable=too-many-return-statements
    """Why the run should not be kept, or None when it is good."""
    kinds = [e["type"] for e in events]
    if "error" in kinds:
        return "the stream reported an error: " + next(e["data"]["detail"] for e in events if e["type"] == "error")
    if "answer" not in kinds:
        return "no answer"
    tools = [e["data"] for e in events if e["type"] == "tool"]
    refused = any(e["type"] == "parse" and e["data"]["refused"] for e in events)
    if expected == "refused":
        return None if refused else "the financial-advice guardrail did not refuse the question"
    if expected == "blocked":
        return None if any(not t["ok"] for t in tools) else "the model did not write a query that the guardrail blocks"
    if not any(t["ok"] and t["nodes"] for t in tools):
        return "no tool call touched the graph"
    answer = next(e["data"] for e in events if e["type"] == "answer")
    if answer["confidence"] == 0:
        return "the agent gave no usable answer: " + answer["answer"]
    return None


def main(ids: list[str]) -> int:
    """Record the requested presets; return 1 if any of them was not kept."""
    unknown = [i for i in ids if i not in PRESETS]
    if unknown:
        sys.exit(f"Unknown id(s): {', '.join(unknown)}. Known: {', '.join(PRESETS)}")
    key = api_key()
    OUT.mkdir(parents=True, exist_ok=True)
    failed = []
    for preset_id in ids or list(PRESETS):
        question, expected = PRESETS[preset_id]
        print(f"\n{preset_id}: {question}")
        try:
            events = record(question, key)
        except urllib.error.HTTPError as exc:
            print(f"  NOT SAVED: HTTP {exc.code} {exc.read().decode()[:200]}")
            failed.append(preset_id)
            continue
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"  NOT SAVED: {exc}")
            failed.append(preset_id)
            continue
        problem = check(events, expected)
        if problem:
            print(f"  NOT SAVED: {problem}")
            failed.append(preset_id)
            continue
        answer = next(e["data"] for e in events if e["type"] == "answer")
        tools = [e["data"]["tool"] + ("" if e["data"]["ok"] else " (blocked)") for e in events if e["type"] == "tool"]
        trace = {"question": question, "recorded_at": datetime.now(timezone.utc).isoformat(), "events": events}
        (OUT / f"{preset_id}.json").write_text(json.dumps(trace, indent=1, default=str), encoding="utf-8")
        print(f"  saved  tools: {', '.join(tools) or 'none'}  status: {answer['status']}")
        print(f"  answer: {answer['answer']}")
        # The proxy allows 10 agent requests per minute: a short pause keeps a full run well under it.
        time.sleep(2)
    if failed:
        print(f"\nNot saved: {', '.join(failed)}. Run again with only those ids to retry.")
        return 1
    print(f"\nAll runs saved in {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
