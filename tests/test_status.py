"""Tests for the project status script."""

import textwrap

import pytest

from scripts import status


def write(tmp_path, body):
    """Write a tracker file and return its path."""
    path = tmp_path / "tasks.yml"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


BASE = """
team:
  Ann: {role: A, reviewer: Bob}
  Bob: {role: B, reviewer: Ann}
phases:
  0: {name: One, gate: g0, min_score: 0}
  1: {name: Two, gate: g1, min_score: 50}
tasks:
  - {id: T1, phase: 0, owner: Ann, title: first, criteria: [X1], depends_on: [], status: done, pr: "1"}
  - {id: T2, phase: 0, owner: Bob, title: second, criteria: [X2], depends_on: [T1], status: in_review, pr: "2"}
  - {id: T3, phase: 1, owner: Ann, title: third, criteria: [X3], depends_on: [T2], status: todo, pr: ""}
  - {id: T4, phase: 1, owner: Bob, title: fourth, criteria: [X4], depends_on: [], status: todo, pr: ""}
"""


def test_current_phase_and_progress(tmp_path):
    """The current phase is the lowest with unfinished work."""
    data = status.load(write(tmp_path, BASE))
    assert status.current_phase(data) == 0
    assert status.progress(data["tasks"]) == (1, 4)


def test_reviews_waiting_uses_reviewer_map(tmp_path):
    """A task in review is routed to the reviewer of its owner."""
    data = status.load(write(tmp_path, BASE))
    waiting = status.reviews_waiting(data)
    assert [(t["id"], r) for t, r in waiting] == [("T2", "Ann")]
    assert [t["id"] for t in status.reviews_to_do(data, "Ann")] == ["T2"]


def test_ready_and_blocked(tmp_path):
    """T3 waits for T2; T4 has no dependency."""
    data = status.load(write(tmp_path, BASE))
    assert [t["id"] for t in status.ready_tasks(data)] == ["T4"]
    assert status.next_for(data, "Ann") is None
    assert status.next_for(data, "Bob")["id"] == "T4"


def test_all_done(tmp_path):
    """No current phase when everything is done."""
    data = status.load(write(tmp_path, BASE.replace("status: todo", "status: done").replace("in_review", "done")))
    assert status.current_phase(data) is None
    assert "All tasks are done" in status.build_report(data, None, with_score=False)[0]


def test_invalid_status_and_dependency(tmp_path):
    """The loader rejects typos."""
    with pytest.raises(ValueError):
        status.load(write(tmp_path, BASE.replace("status: todo", "status: nope", 1)))
    with pytest.raises(ValueError):
        status.load(write(tmp_path, BASE.replace("depends_on: [T1]", "depends_on: [ZZ]")))


def test_real_tracker_is_valid():
    """The tracker shipped in the repository loads and covers five people."""
    data = status.load()
    assert len(data["team"]) == 5
    report = status.build_report(data, "Adrien", with_score=False)
    assert any(line.startswith("CURRENT PHASE 1") for line in report)
    assert any("[ ]" in line for line in report)
