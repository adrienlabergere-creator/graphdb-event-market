"""Project scorecard: checks the 100-point grading checklist automatically.

Usage:
    python scripts/scorecard.py             # full check (runs pylint, black and pytest)
    python scripts/scorecard.py --fast      # skip the slow checks
    python scripts/scorecard.py --markdown  # print the checklist as a Markdown table
    python scripts/scorecard.py --min 80    # exit with code 1 if the total is below 80

An automatic check proves that a criterion is structurally satisfied (file, command, count).
It cannot judge quality: the quality of the modeling, the queries and the defense is graded by humans.
Criteria that need a human decision are tracked in docs/scorecard_manual.yml.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yaml

ROOT = Path(__file__).resolve().parent.parent
MANUAL_FILE = ROOT / "docs" / "scorecard_manual.yml"
TEAM_SIZE = 5
CheckResult = tuple["bool | None", str]

_CACHE: dict[str, subprocess.CompletedProcess] = {}


# --------------------------------------------------------------------------- helpers
def run(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    """Run a command from the repository root (cached; never raises)."""
    key = " ".join(cmd)
    if key not in _CACHE:
        try:
            _CACHE[key] = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            _CACHE[key] = subprocess.CompletedProcess(cmd, 127, "", str(exc))
    return _CACHE[key]


def read(rel: str) -> str:
    """Return the text of a file relative to the repository root ('' if missing)."""
    path = ROOT / rel
    return path.read_text(encoding="utf-8", errors="ignore") if path.is_file() else ""


def code_files(folder: str, suffixes: tuple[str, ...] = (".py", ".cypher")) -> list[Path]:
    """List source files of a folder, excluding this script."""
    base = ROOT / folder
    if not base.is_dir():
        return []
    return [p for p in sorted(base.rglob("*")) if p.suffix in suffixes and p.name != Path(__file__).name]


def sources(folders: tuple[str, ...] = ("app", "scripts")) -> str:
    """Concatenate the text of all source files of the given folders."""
    texts = [p.read_text(encoding="utf-8", errors="ignore") for f in folders for p in code_files(f)]
    return "\n".join(texts)


def any_file(*patterns: str) -> bool:
    """True if at least one glob pattern matches a file."""
    return any(path.is_file() for pattern in patterns for path in ROOT.glob(pattern))


def test_functions(path: Path) -> int:
    """Count the test functions of a test file."""
    return len(re.findall(r"^def test_", path.read_text(encoding="utf-8", errors="ignore"), re.M))


def compose_services() -> dict:
    """Services declared in docker-compose.yml."""
    try:
        data = yaml.safe_load(read("docker-compose.yml")) or {}
    except yaml.YAMLError:
        return {}
    return data.get("services") or {}


def api_paths() -> list[str]:
    """Business routes (under /api) exposed by the FastAPI app, or [] if it cannot be imported.

    The OpenAPI schema is used rather than ``app.routes``: since FastAPI 0.120 an included router stays
    a lazy ``_IncludedRouter`` object in that list, so filtering on ``APIRoute`` silently returned nothing.
    """
    sys.path.insert(0, str(ROOT))
    try:
        # pylint: disable=import-outside-toplevel
        from app.main import app

        paths = app.openapi().get("paths", {})
    except Exception:  # pylint: disable=broad-exception-caught
        return []
    return sorted(path for path in paths if path.startswith("/api"))


def git_lines(*args: str) -> list[str]:
    """Output lines of a git command."""
    result = run(["git", *args])
    return [line for line in result.stdout.splitlines() if line.strip()]


def pylint_score() -> float | None:
    """Score reported by pylint on app and scripts (None if pylint is unavailable)."""
    out = run([sys.executable, "-m", "pylint", "app", "scripts"])
    match = re.search(r"rated at (-?[\d.]+)/10", out.stdout)
    return float(match.group(1)) if match else None


def pytest_run() -> tuple[int, int | None]:
    """Return pytest's exit code and the total coverage percentage."""
    out = run([sys.executable, "-m", "pytest", "-q", "--cov=app", "--cov-report=term"])
    match = re.search(r"^TOTAL\s+\d+\s+\d+\s+(\d+)%", out.stdout, re.M)
    return out.returncode, int(match.group(1)) if match else None


# --------------------------------------------------------------------------- checks: Docker
def chk_compose_services() -> CheckResult:
    """docker-compose.yml declares at least 3 services."""
    count = len(compose_services())
    return count >= 3, f"{count} services"


def chk_dockerfile() -> CheckResult:
    """Each service has a build context or an image, and a Dockerfile exists."""
    services = compose_services()
    missing = [name for name, svc in services.items() if not (svc.get("image") or svc.get("build"))]
    return (ROOT / "Dockerfile").is_file() and bool(services) and not missing, f"missing image/build: {missing}"


def chk_env_example() -> CheckResult:
    """.env.example exists, .env is ignored and not tracked."""
    tracked = git_lines("ls-files")
    env_tracked = [f for f in tracked if f == ".env" or f.endswith("/.env")]
    ignored = ".env" in read(".gitignore").splitlines()
    ok = (ROOT / ".env.example").is_file() and ignored and not env_tracked
    return ok, f"tracked .env files: {env_tracked}, ignored: {ignored}"


def chk_registry() -> CheckResult:
    """README links a public registry image (no placeholder left)."""
    match = re.search(r"(ghcr\.io|docker\.io|hub\.docker\.com)/\S+", read("README.md"))
    return bool(match) and "OWNER" not in match.group(0), match.group(0) if match else "no registry link"


# --------------------------------------------------------------------------- checks: Neo4j
def chk_schema_size() -> CheckResult:
    """At least 3 node labels and 3 relationship types appear in the code."""
    text = sources()
    labels = set(re.findall(r"\(\w*:([A-Z][A-Za-z]+)", text))
    rels = set(re.findall(r"\[\w*:([A-Z][A-Z_]+)", text))
    return len(labels) >= 3 and len(rels) >= 3, f"{len(labels)} labels, {len(rels)} relationship types"


def chk_constraints() -> CheckResult:
    """At least 2 constraints are created."""
    count = len(re.findall(r"CREATE CONSTRAINT", sources(), re.I))
    return count >= 2, f"{count} constraints"


def chk_indexes() -> CheckResult:
    """At least 1 index is created."""
    count = len(re.findall(r"CREATE\s+(?:RANGE\s+|TEXT\s+|FULLTEXT\s+|VECTOR\s+|POINT\s+)?INDEX", sources(), re.I))
    return count >= 1, f"{count} indexes"


def chk_ingestion() -> CheckResult:
    """An ingestion script exists."""
    return any_file("scripts/ingest*.py"), "scripts/ingest*.py"


def chk_dataset_doc() -> CheckResult:
    """docs/DATASETS.md documents at least 2 sources with links and has no TODO left."""
    text = read("docs/DATASETS.md")
    links = len(re.findall(r"https?://", text))
    return links >= 2 and "TODO" not in text, f"{links} links"


# --------------------------------------------------------------------------- checks: FastAPI
def chk_endpoints() -> CheckResult:
    """At least 4 /api endpoints and at least 3 files running MATCH queries."""
    paths = api_paths()
    match_files = [p for p in code_files("app", (".py",)) if "MATCH" in p.read_text(encoding="utf-8")]
    return len(paths) >= 4 and len(match_files) >= 3, f"{len(paths)} /api routes, {len(match_files)} files with MATCH"


def chk_pydantic() -> CheckResult:
    """At least 4 Pydantic models are defined."""
    count = len(re.findall(r"class \w+\((?:\w+, *)*BaseModel", sources(("app",))))
    return count >= 4, f"{count} models"


def chk_swagger() -> CheckResult:
    """/docs answers 200."""
    sys.path.insert(0, str(ROOT))
    try:
        # pylint: disable=import-outside-toplevel
        from fastapi.testclient import TestClient

        from app.main import app

        status = TestClient(app).get("/docs").status_code
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return False, f"cannot import app: {exc}"
    return status == 200, f"/docs -> {status}"


def chk_error_handling() -> CheckResult:
    """Routers raise HTTPException with meaningful status codes."""
    text = sources(("app",))
    return "HTTPException" in text and bool(re.search(r"status_code=4\d\d", text)), "HTTPException with 4xx codes"


# --------------------------------------------------------------------------- checks: Cypher, GDS, agent
def chk_pathfinding() -> CheckResult:
    """Pathfinding or GDS in at least 2 files of the app."""
    files = [p for p in code_files("app", (".py",)) if re.search(r"shortestPath|allShortestPaths|gds\.", p.read_text())]
    return len(files) >= 2, f"{len(files)} files"


def chk_with_unwind() -> CheckResult:
    """WITH, UNWIND and an aggregation or subquery are used."""
    text = sources()
    ok = bool(re.search(r"\bUNWIND\b", text) and re.search(r"\bWITH\b", text))
    ok = ok and bool(re.search(r"CALL\s*\{|count\(|collect\(|avg\(|sum\(", text))
    return ok, "UNWIND + WITH + aggregation/subquery"


def chk_gds_algorithms() -> CheckResult:
    """A GDS projection and at least 2 distinct algorithms."""
    text = sources()
    algos = set(
        re.findall(r"gds\.(pageRank|louvain|leiden|nodeSimilarity|betweenness|wcc|labelPropagation|degree)", text)
    )
    return "gds.graph.project" in text and len(algos) >= 2, f"algorithms: {sorted(algos)}"


def chk_ml_workflow() -> CheckResult:
    """A tested prediction workflow exists, using GDS or the documented NumPy model."""
    gds_pipeline = bool(re.search(r"gds\.(beta\.)?pipeline|linkPrediction|nodeClassification", sources()))
    workflow = read("app/services/analytics/link_prediction.py")
    tests = read("tests/test_analytics.py")
    numpy_workflow = all(
        marker in workflow for marker in ("def train_and_evaluate", "def run_workflow", "def store_claims", "auc_test")
    ) and all(marker in tests for marker in ("test_train_and_evaluate", "test_store_claims"))
    return gds_pipeline or numpy_workflow, "GDS pipeline or tested NumPy prediction with Claim output"


def chk_agent() -> CheckResult:
    """A LangGraph agent exists."""
    return "langgraph" in read("requirements.txt") and "StateGraph" in sources(("app",)), "langgraph + StateGraph"


# --------------------------------------------------------------------------- checks: docs
def chk_graph_diagram() -> CheckResult:
    """A graph schema diagram is committed."""
    return (
        any_file("docs/graph_schema.png", "docs/graph_schema.svg", "docs/graph_schema.drawio", "docs/graph_schema.pdf"),
        "docs/graph_schema.*",
    )


def chk_architecture_diagram() -> CheckResult:
    """A system architecture diagram is committed."""
    return (
        any_file("docs/architecture.png", "docs/architecture.svg", "docs/architecture.drawio", "docs/architecture.pdf"),
        "docs/architecture.*",
    )


def chk_rationale() -> CheckResult:
    """Modeling rationale with rejected alternatives and the anti-genericity appendix, no TODO left."""
    text = read("docs/modeling_rationale.md")
    ok = "Rejected alternatives" in text and "Anti-genericity" in text and "TODO" not in text and len(text) > 1500
    return ok, f"{len(text)} characters"


def chk_readme() -> CheckResult:
    """README has the required sections, at least 2 screenshots and no TODO left."""
    text = read("README.md")
    headings = " ".join(re.findall(r"^#+ (.+)$", text, re.M)).lower()
    needed = (
        "description",
        "installation",
        "api",
        "screenshot",
        "schema",
        "architecture",
        "dataset",
        "rationale",
        "disclaimer",
    )
    missing = [w for w in needed if w not in (text.lower() if w == "disclaimer" else headings)]
    shots = [p for p in (ROOT / "docs" / "screenshots").glob("*") if p.suffix in (".png", ".jpg", ".jpeg")]
    return (
        not missing and len(shots) >= 2 and "TODO" not in text,
        f"missing sections: {missing}, screenshots: {len(shots)}",
    )


def chk_notebook() -> CheckResult:
    """demo.ipynb is valid and has at least 5 cells with code."""
    try:
        cells = json.loads(read("demo.ipynb")).get("cells", [])
    except json.JSONDecodeError:
        return False, "invalid or missing notebook"
    code = [c for c in cells if c.get("cell_type") == "code"]
    return len(cells) >= 5 and len(code) >= 2, f"{len(cells)} cells, {len(code)} code cells"


# --------------------------------------------------------------------------- checks: clean code, Makefile
def chk_pylint() -> CheckResult:
    """pylint score is at least 9.5 and .pylintrc exists."""
    score = pylint_score()
    if score is None:
        return None, "pylint unavailable"
    return (ROOT / ".pylintrc").is_file() and score >= 9.5, f"pylint {score}/10"


def chk_black() -> CheckResult:
    """black --check passes."""
    result = run([sys.executable, "-m", "black", "--check", "-l", "120", "app", "scripts", "tests"])
    return (None, "black unavailable") if result.returncode == 127 else (result.returncode == 0, "black --check")


def chk_docstrings() -> CheckResult:
    """pylint finds no missing docstring."""
    cmd = [sys.executable, "-m", "pylint", "--disable=all", "--enable=C0114,C0115,C0116", "app", "scripts"]
    result = run(cmd)
    return (None, "pylint unavailable") if result.returncode == 127 else (result.returncode == 0, "docstring check")


def makefile_targets() -> set[str]:
    """Targets declared in the Makefile."""
    return set(re.findall(r"^([A-Za-z][\w-]*):", read("Makefile"), re.M))


def chk_make_required() -> CheckResult:
    """The required Makefile commands exist."""
    needed = {"help", "install", "run", "docker-run", "test", "lint", "clean"}
    missing = sorted(needed - makefile_targets())
    return not missing, f"missing targets: {missing}"


def chk_make_functional() -> CheckResult:
    """make help works and every target parses in dry-run mode."""
    targets = sorted(makefile_targets())
    if not targets:
        return False, "no Makefile"
    if run(["make", "help"]).returncode != 0:
        return False, "make help fails"
    broken = [t for t in targets if run(["make", "-n", t]).returncode != 0]
    return not broken, f"broken targets: {broken}"


def chk_make_documented() -> CheckResult:
    """README documents the make commands."""
    count = len(re.findall(r"make [a-z-]+", read("README.md")))
    return count >= 4, f"{count} make commands in README"


# --------------------------------------------------------------------------- checks: tests, CI
def chk_tests_exist() -> CheckResult:
    """At least 10 tests including Neo4j-marked ones."""
    files = sorted((ROOT / "tests").glob("test_*.py"))
    total = sum(test_functions(f) for f in files)
    has_neo4j = any("mark.neo4j" in f.read_text() for f in files)
    return total >= 10 and has_neo4j, f"{total} tests, neo4j-marked: {has_neo4j}"


def chk_container_tests() -> CheckResult:
    """Container health tests exist for Neo4j and FastAPI."""
    path = ROOT / "tests" / "test_container_health.py"
    return path.is_file() and test_functions(path) >= 2, "tests/test_container_health.py"


def chk_cypher_tests() -> CheckResult:
    """Cypher tests exist and run with make test."""
    files = list((ROOT / "tests").glob("test_cypher*.py"))
    return bool(files) and sum(test_functions(f) for f in files) >= 2, f"{len(files)} files"


def chk_coverage() -> CheckResult:
    """Coverage is at least 60 percent."""
    _, cov = pytest_run()
    return (None, "pytest unavailable") if cov is None else (cov >= 60, f"coverage {cov}%")


def chk_tests_pass() -> CheckResult:
    """All tests pass."""
    code, cov = pytest_run()
    return (None, "pytest unavailable") if cov is None else (code == 0, f"exit code {code}")


def workflow_texts() -> list[str]:
    """Text of every GitHub Actions workflow."""
    return [p.read_text(encoding="utf-8") for p in (ROOT / ".github" / "workflows").glob("*.y*ml")]


def chk_lint_workflow() -> CheckResult:
    """A workflow runs pylint."""
    return any("pylint" in t for t in workflow_texts()), "workflow with pylint"


def chk_test_workflow() -> CheckResult:
    """A workflow runs pytest with coverage."""
    return any("pytest" in t and "--cov" in t for t in workflow_texts()), "workflow with pytest --cov"


def chk_badges() -> CheckResult:
    """README shows at least 2 badges, without placeholder."""
    text = read("README.md")
    return text.count("badge.svg") >= 2 and "OWNER" not in text, f"{text.count('badge.svg')} badges"


def chk_proxy_auth() -> CheckResult:
    """A reverse proxy service exists or an API key protects sensitive endpoints."""
    proxy = any(re.search(r"nginx|traefik", str(svc.get("image", ""))) for svc in compose_services().values())
    auth = bool(re.search(r"APIKeyHeader|Security\(", sources(("app",))))
    return proxy or auth, f"proxy: {proxy}, api-key auth: {auth}"


# --------------------------------------------------------------------------- checks: Git
def chk_branches() -> CheckResult:
    """At least 2 non-main branches or 2 merged PRs are visible."""
    branches = {b.replace("origin/", "") for b in git_lines("branch", "-a", "--format=%(refname:short)")}
    others = branches - {"main", "HEAD", "origin"}
    merges = git_lines("log", "--merges", "--oneline")
    return len(others) >= 2 or len(merges) >= 2, f"branches: {sorted(others)}, merges: {len(merges)}"


def chk_gitignore() -> CheckResult:
    """.gitignore covers secrets, caches and virtualenvs."""
    text = read(".gitignore")
    return all(item in text for item in (".env", "__pycache__", ".venv")), ".gitignore"


def author_shares() -> dict[str, float]:
    """Share of commits per author e-mail (merge commits excluded)."""
    counts = Counter(git_lines("log", "--no-merges", "--format=%ae"))
    total = sum(counts.values())
    return {author: n / total for author, n in counts.items()} if total else {}


def chk_balance() -> CheckResult:
    """All team members commit, none under 12 percent, none over 40 percent."""
    shares = author_shares()
    if not shares:
        return False, "no commits"
    ok = len(shares) >= TEAM_SIZE and min(shares.values()) >= 0.12 and max(shares.values()) <= 0.40
    detail = ", ".join(f"{a.split('@')[0]}: {s:.0%}" for a, s in sorted(shares.items(), key=lambda x: -x[1]))
    return ok, detail


def chk_merged_prs() -> CheckResult:
    """Each member has a substantial merged PR (needs the GitHub CLI; otherwise filled manually)."""
    result = run(["gh", "pr", "list", "--state", "merged", "--limit", "200", "--json", "author,additions,deletions"])
    if result.returncode != 0:
        return None, "gh unavailable: fill docs/scorecard_manual.yml"
    lines: Counter = Counter()
    for pr in json.loads(result.stdout or "[]"):
        lines[pr["author"]["login"]] = max(lines[pr["author"]["login"]], pr["additions"] + pr["deletions"])
    big = [author for author, size in lines.items() if size >= 50]
    return len(big) >= TEAM_SIZE, f"authors with a PR of 50+ changed lines: {sorted(big)}"


def chk_commit_messages() -> CheckResult:
    """At least 90 percent of commit subjects follow the convention."""
    subjects = git_lines("log", "--no-merges", "--format=%s")
    if not subjects:
        return False, "no commits"
    pattern = re.compile(r"^(feat|fix|test|docs|refactor|chore)(\([a-z0-9_-]+\))?: .{5,}")
    good = sum(1 for s in subjects if pattern.match(s))
    return good / len(subjects) >= 0.9, f"{good}/{len(subjects)} follow the convention"


# --------------------------------------------------------------------------- criteria table
@dataclass
class Criterion:
    """One line of the grading checklist."""

    cid: str
    category: str
    text: str
    points: int
    owner: str
    check: Callable[[], CheckResult] | None


CRITERIA: list[Criterion] = [
    Criterion("DK1", "Docker", "docker-compose.yml with at least 3 services", 2, "D", chk_compose_services),
    Criterion("DK2", "Docker", "Proper Dockerfile or official image per service", 2, "D", chk_dockerfile),
    Criterion("DK3", "Docker", ".env.example, no secret committed", 2, "D", chk_env_example),
    Criterion("DK4", "Docker", "At least one image on a public registry (link in README)", 2, "D", chk_registry),
    Criterion("DK5", "Docker", "Docker Compose starts cleanly from a fresh clone", 1, "D", None),
    Criterion("NJ1", "Neo4j", "Schema: at least 3 labels, 3 relationship types", 3, "A", chk_schema_size),
    Criterion("NJ2", "Neo4j", "At least 2 constraints", 2, "A", chk_constraints),
    Criterion("NJ3", "Neo4j", "Appropriate indexes", 2, "A", chk_indexes),
    Criterion("NJ4", "Neo4j", "Dataset ingestion script", 2, "A", chk_ingestion),
    Criterion("NJ5", "Neo4j", "Dataset source documented and justified", 1, "A", chk_dataset_doc),
    Criterion("FA1", "FastAPI", "At least 4 endpoints, 3 advanced graph queries", 2, "C", chk_endpoints),
    Criterion("FA2", "FastAPI", "Pydantic validation", 2, "C", chk_pydantic),
    Criterion("FA3", "FastAPI", "Swagger /docs works", 1, "C", chk_swagger),
    Criterion("FA4", "FastAPI", "Proper error handling", 1, "C", chk_error_handling),
    Criterion("AC1", "Advanced Cypher", "Pathfinding / GDS in at least 2 endpoints", 4, "B", chk_pathfinding),
    Criterion("AC2", "Advanced Cypher", "Complex pattern matching", 3, "B", None),
    Criterion("AC3", "Advanced Cypher", "WITH, UNWIND, subqueries, aggregations", 2, "A", chk_with_unwind),
    Criterion("OP1", "Optimization", "Optimized queries and before/after benchmarks", 5, "B", None),
    Criterion("GD1", "GDS and Agentic", "GDS projection and at least 2 algorithms", 2, "B", chk_gds_algorithms),
    Criterion("GD2", "GDS and Agentic", "ML prediction / classification workflow", 3, "B", chk_ml_workflow),
    Criterion("GD3", "GDS and Agentic", "LangGraph agent with tools and structured output", 4, "C", chk_agent),
    Criterion("GD4", "GDS and Agentic", "LLM reliability and guardrails (evaluated)", 4, "C", None),
    Criterion("SC1", "Schemas", "Neo4j graph schema diagram", 2, "A", chk_graph_diagram),
    Criterion("SC2", "Schemas", "System architecture diagram", 2, "D", chk_architecture_diagram),
    Criterion("SC3", "Schemas", "Modeling rationale and anti-genericity appendix", 3, "A", chk_rationale),
    Criterion("DC1", "Documentation", "Complete README with screenshots", 3, "C", chk_readme),
    Criterion("DC2", "Documentation", "Demonstration notebook", 2, "A", chk_notebook),
    Criterion("CC1", "Clean code", ".pylintrc, pylint >= 9.5, make lint", 2, "E", chk_pylint),
    Criterion("CC2", "Clean code", "PEP 8 and clean architecture", 1, "E", chk_black),
    Criterion("CC3", "Clean code", "Docstrings everywhere", 1, "E", chk_docstrings),
    Criterion("MK1", "Makefile", "Required commands present", 1, "D", chk_make_required),
    Criterion("MK2", "Makefile", "Commands functional, make help clear", 1, "D", chk_make_functional),
    Criterion("MK3", "Makefile", "Usage documented in README", 1, "D", chk_make_documented),
    Criterion("TS1", "Tests", "Unit, API and Neo4j tests", 3, "E", chk_tests_exist),
    Criterion("TS2", "Tests", "Container health checks", 2, "E", chk_container_tests),
    Criterion("TS3", "Tests", "Cypher tests run by make test", 2, "E", chk_cypher_tests),
    Criterion("TS4", "Tests", "Coverage at least 60 percent", 2, "E", chk_coverage),
    Criterion("TS5", "Tests", "All tests pass, coverage report generated", 1, "E", chk_tests_pass),
    Criterion("SE1", "SE practices", "Lint workflow", 1, "E", chk_lint_workflow),
    Criterion("SE2", "SE practices", "Test workflow with coverage", 1, "E", chk_test_workflow),
    Criterion("SE3", "SE practices", "Badges in README", 1, "E", chk_badges),
    Criterion("SE4", "SE practices", "Documented code reviews (2+ constructive comments per PR)", 1, "E", None),
    Criterion("SE5", "SE practices", "Reverse proxy or authentication on a sensitive endpoint", 3, "D", chk_proxy_auth),
    Criterion("SE6", "SE practices", "EXPLAIN / PROFILE demonstration", 2, "B", None),
    Criterion("GT1", "Git", "Branch workflow (feature branches, PRs)", 2, "All", chk_branches),
    Criterion("GT2", "Git", "Proper .gitignore", 1, "All", chk_gitignore),
    Criterion("GT3", "Git", "Balanced contributions", 3, "All", chk_balance),
    Criterion("GT4", "Git", "At least 1 substantial merged PR per member", 3, "All", chk_merged_prs),
    Criterion("GT5", "Git", "Clear commit messages", 1, "All", chk_commit_messages),
]

SLOW = {"CC1", "CC2", "CC3", "TS4", "TS5"}


def load_manual() -> dict:
    """Manual statuses from docs/scorecard_manual.yml."""
    try:
        return yaml.safe_load(read(str(MANUAL_FILE.relative_to(ROOT)))) or {}
    except yaml.YAMLError:
        return {}


def evaluate(fast: bool) -> list[dict]:
    """Evaluate every criterion and return one result row per criterion."""
    manual = load_manual()
    rows = []
    for crit in CRITERIA:
        status, note, kind = None, "", "manual"
        if crit.check is not None and not (fast and crit.cid in SLOW):
            status, note = crit.check()
            kind = "auto"
        if status is None:
            entry = manual.get(crit.cid) or {}
            status = bool(entry.get("done"))
            note = note or entry.get("evidence", "") or "waiting for a human check"
            kind = "manual"
        rows.append({"crit": crit, "ok": status, "kind": kind, "note": note})
    return rows


def secret_findings() -> list[str]:
    """Tracked files that look like they contain a credential."""
    pattern = re.compile(r"(?i)(api[_-]?key|password|secret|token)\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{16,}")
    hits = []
    for name in git_lines("ls-files"):
        if name == ".env.example" or name.endswith((".png", ".jpg", ".pdf", ".lock")):
            continue
        if pattern.search(read(name)):
            hits.append(name)
    return hits


def print_report(rows: list[dict]) -> int:
    """Print the report and return the total number of points earned."""
    auto = sum(r["crit"].points for r in rows if r["ok"] and r["kind"] == "auto")
    manual = sum(r["crit"].points for r in rows if r["ok"] and r["kind"] == "manual")
    auto_max = sum(r["crit"].points for r in rows if r["crit"].check is not None)
    for row in rows:
        crit = row["crit"]
        mark = "PASS" if row["ok"] else "TODO"
        print(f"{crit.cid:<4} {crit.owner:<4} {crit.points:>2}  {mark:<4} {crit.text[:58]:<58} {row['note'][:60]}")
    print()
    print(f"Automatic checks : {auto}/{auto_max} points (structure only, quality is graded by humans)")
    print(f"Manual checks    : {manual}/{100 - auto_max} points claimed in docs/scorecard_manual.yml")
    print(f"TOTAL            : {auto + manual}/100")
    by_owner: Counter = Counter()
    for row in rows:
        if not row["ok"]:
            by_owner[row["crit"].owner] += row["crit"].points
    print("Points still missing by role: " + ", ".join(f"{k}: {v}" for k, v in sorted(by_owner.items())))
    risks = []
    secrets = secret_findings()
    if secrets:
        risks.append(f"-5 per exposed secret: {secrets}")
    if not any(r["ok"] for r in rows if r["crit"].cid == "GD3"):
        risks.append("-15 missing agentic component (GD3)")
    if not any(r["ok"] for r in rows if r["crit"].cid == "CC1"):
        risks.append("-8 pylint below 9.5 or .pylintrc missing (CC1)")
    if not any(r["ok"] for r in rows if r["crit"].cid == "MK2"):
        risks.append("-3 non-functional Makefile (MK2)")
    print("Penalty risks    : " + ("; ".join(risks) if risks else "none detected"))
    return auto + manual


def print_markdown() -> None:
    """Print the checklist as a Markdown table (for SCORECARD.md)."""
    print("# Scorecard (100 points)\n")
    print("Generated by `make score-md`. Live status: `make score`. Owner letters are the roles in PLAYBOOK.md.\n")
    print("| ID | Category | Criterion | Pts | Owner | Check | Evidence (PR / file) |")
    print("|---|---|---|---:|---|---|---|")
    for crit in CRITERIA:
        kind = "auto" if crit.check is not None else "manual"
        print(f"| {crit.cid} | {crit.category} | {crit.text} | {crit.points} | {crit.owner} | {kind} | |")
    print(f"\nTotal: {sum(c.points for c in CRITERIA)} points.")


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fast", action="store_true", help="skip pylint, black and pytest")
    parser.add_argument("--markdown", action="store_true", help="print the checklist as Markdown")
    parser.add_argument("--min", type=int, default=0, help="fail if the total is below this value")
    args = parser.parse_args()
    if args.markdown:
        print_markdown()
        return 0
    total = print_report(evaluate(args.fast))
    return 1 if total < args.min else 0


if __name__ == "__main__":
    sys.exit(main())
