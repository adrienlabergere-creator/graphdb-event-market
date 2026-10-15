"""Project status: where we are, what is next, what waits for a review.

Usage:
    python -m scripts.status                 # whole team
    python -m scripts.status --who Adrien    # same, plus the next task of that person
    python -m scripts.status --markdown      # Markdown output (for a PR description)
    python -m scripts.status --no-score      # skip the scorecard (faster)

The source of truth is docs/tasks.yml. Each person updates their own task in the PR that delivers it.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TASKS_FILE = ROOT / "docs" / "tasks.yml"
STATUSES = ("todo", "in_progress", "in_review", "done")


def load(path: Path = TASKS_FILE) -> dict:
    """Load and validate the tracker file."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    ids = {task["id"] for task in data.get("tasks", [])}
    for task in data.get("tasks", []):
        if task.get("status") not in STATUSES:
            raise ValueError(f"task {task['id']}: status must be one of {STATUSES}")
        for dep in task.get("depends_on", []):
            if dep not in ids:
                raise ValueError(f"task {task['id']}: unknown dependency {dep}")
    return data


def is_done(task: dict) -> bool:
    """True when the task is merged and ticked."""
    return task["status"] == "done"


def current_phase(data: dict) -> int | None:
    """Lowest phase that still has an unfinished task (None when everything is done)."""
    open_phases = [t["phase"] for t in data["tasks"] if not is_done(t)]
    return min(open_phases) if open_phases else None


def ready_tasks(data: dict) -> list[dict]:
    """Tasks that can be worked on now: not done, not in review, dependencies done."""
    done = {t["id"] for t in data["tasks"] if is_done(t)}
    return [
        t
        for t in data["tasks"]
        if t["status"] in ("todo", "in_progress") and all(dep in done for dep in t.get("depends_on", []))
    ]


def blocked_tasks(data: dict) -> list[tuple[dict, list[str]]]:
    """Unfinished tasks of the current phase waiting on dependencies, with the missing ids."""
    done = {t["id"] for t in data["tasks"] if is_done(t)}
    phase = current_phase(data)
    out = []
    for task in data["tasks"]:
        missing = [d for d in task.get("depends_on", []) if d not in done]
        if task["phase"] == phase and task["status"] == "todo" and missing:
            out.append((task, missing))
    return out


def reviews_waiting(data: dict) -> list[tuple[dict, str]]:
    """Tasks in review with the name of the person who must review them."""
    team = data.get("team", {})
    return [
        (t, team.get(t["owner"], {}).get("reviewer", "someone else"))
        for t in data["tasks"]
        if t["status"] == "in_review"
    ]


def next_for(data: dict, who: str) -> dict | None:
    """First ready task of a person (earliest phase first); team tasks count for everyone."""
    mine = [t for t in ready_tasks(data) if t["owner"] in (who, "All")]
    return sorted(mine, key=lambda t: t["phase"])[0] if mine else None


def reviews_to_do(data: dict, who: str) -> list[dict]:
    """Tasks in review that this person has to review."""
    return [t for t, reviewer in reviews_waiting(data) if reviewer == who]


def progress(tasks: list[dict]) -> tuple[int, int]:
    """Return (done, total)."""
    return sum(is_done(t) for t in tasks), len(tasks)


def fmt(task: dict) -> str:
    """One-line description of a task."""
    pr = f" (PR {task['pr']})" if task.get("pr") else ""
    return f"{task['id']:<3} [{task['status']}] {task['owner']}: {task['title']}{pr}"


def score_line(data: dict, phase: int | None) -> list[str]:
    """Score summary from the scorecard (imported lazily: it can be slow)."""
    from scripts.scorecard import evaluate  # pylint: disable=import-outside-toplevel

    rows = evaluate(fast=True)
    got = sum(r["crit"].points for r in rows if r["ok"])
    total = sum(r["crit"].points for r in rows)
    lines = [f"Score (fast checks): {got}/{total}"]
    if phase is not None:
        target = data["phases"][phase]["min_score"]
        lines[0] += f" - target at the end of this phase: {target}"
    return lines


def breakdown(data: dict) -> list[str]:
    """Progress per phase and per person."""
    tasks = data["tasks"]
    lines = ["", "Per phase:"]
    for number, info in sorted(data["phases"].items()):
        d, t = progress([x for x in tasks if x["phase"] == number])
        lines.append(f"  Phase {number} {info['name']:<24} {d}/{t}")
    lines.append("Per person:")
    for name in data.get("team", {}):
        d, t = progress([x for x in tasks if x["owner"] == name])
        lines.append(f"  {name:<8} {d}/{t}  (role {data['team'][name]['role']})")
    return lines


def build_report(data: dict, who: str | None, with_score: bool) -> list[str]:
    """Build the report as a list of lines."""
    tasks = data["tasks"]
    phase = current_phase(data)
    done, total = progress(tasks)
    lines = []
    if phase is None:
        lines.append("All tasks are done. Run the final rehearsal checks (make score, git shortlog -sn).")
    else:
        info = data["phases"][phase]
        lines.append(f"CURRENT PHASE {phase}: {info['name']}")
        lines.append(f"Gate to leave it: {info['gate']}")
    lines.append(f"Overall progress: {done}/{total} tasks done ({100 * done // total} percent)")
    if with_score:
        lines += score_line(data, phase)
    lines += breakdown(data)
    waiting = reviews_waiting(data)
    lines.append("")
    lines.append("Waiting for review:" + ("" if waiting else " nothing"))
    for task, reviewer in waiting:
        lines.append(f"  {fmt(task)}  -> reviewer: {reviewer}")
    lines.append("In progress:" + ("" if any(t["status"] == "in_progress" for t in tasks) else " nothing"))
    for task in tasks:
        if task["status"] == "in_progress":
            lines.append(f"  {fmt(task)}")
    blocked = blocked_tasks(data)
    lines.append("Blocked (dependencies not done):" + ("" if blocked else " nothing"))
    for task, missing in blocked:
        lines.append(f"  {fmt(task)}  <- waits for {', '.join(missing)}")
    if who:
        lines += person_section(data, who)
    return lines


def person_section(data: dict, who: str) -> list[str]:
    """Lines specific to one person: reviews to do and next task."""
    lines = ["", f"FOR {who.upper()}"]
    todo = reviews_to_do(data, who)
    lines.append("Reviews you owe:" + ("" if todo else " none"))
    for task in todo:
        lines.append(f"  {fmt(task)}")
    task = next_for(data, who)
    if task is None:
        lines.append("Next task: none ready (everything is done, in review, or blocked). Review a teammate's PR.")
    else:
        lines.append(f"Next task: {fmt(task)}")
        lines.append(f"  Rubric criteria: {', '.join(task.get('criteria', [])) or '-'}")
        lines.append(f"  Depends on: {', '.join(task.get('depends_on', [])) or 'nothing'}")
        for item in task.get("checklist", []):
            lines.append(f"  [ ] {item}")
        if task.get("handoff"):
            lines.append(f"  Hand-off: {task['handoff']}")
    return lines


def main() -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--who", help="first name of a team member")
    parser.add_argument("--markdown", action="store_true", help="Markdown output")
    parser.add_argument("--no-score", action="store_true", help="skip the scorecard")
    args = parser.parse_args()
    data = load()
    if args.who and args.who not in data.get("team", {}):
        print(f"Unknown name {args.who!r}. Known: {', '.join(data.get('team', {}))}")
        return 2
    lines = build_report(data, args.who, with_score=not args.no_score)
    if args.markdown:
        print("```text\n" + "\n".join(lines) + "\n```")
    else:
        print("\n".join(lines))
    counts = Counter(t["status"] for t in data["tasks"])
    return 0 if counts else 1


if __name__ == "__main__":
    raise SystemExit(main())
