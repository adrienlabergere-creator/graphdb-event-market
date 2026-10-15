"""Apply scripts/schema.cypher (constraints and indexes) to Neo4j. Safe to run several times."""

from pathlib import Path

from app.database.connection import get_driver

SCHEMA_FILE = Path(__file__).with_name("schema.cypher")


def load_statements(path: Path = SCHEMA_FILE) -> list[str]:
    """Return the Cypher statements of a schema file (comments removed, one string per statement)."""
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if not line.strip().startswith("//")]
    return [statement.strip() for statement in "\n".join(lines).split(";") if statement.strip()]


def main() -> None:
    """Run every statement of the schema file against Neo4j."""
    statements = load_statements()
    with get_driver().session() as session:
        for statement in statements:
            session.run(statement).consume()
    print(f"Applied {len(statements)} schema statements.")


if __name__ == "__main__":
    main()
