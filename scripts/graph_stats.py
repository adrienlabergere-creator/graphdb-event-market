"""Print the size of the graph (nodes per label, relationships per type). Use it to fill docs/DATASETS.md.

Usage:
    python -m scripts.graph_stats
"""

from app.database.connection import get_driver

NODE_COUNTS = "MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS n ORDER BY n DESC"
REL_COUNTS = "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS n ORDER BY n DESC"


def main() -> None:
    """Query and print the counts."""
    with get_driver().session() as session:
        print("Nodes")
        for record in session.run(NODE_COUNTS):
            print(f"  {record['label']:<12} {record['n']}")
        print("Relationships")
        for record in session.run(REL_COUNTS):
            print(f"  {record['type']:<14} {record['n']}")


if __name__ == "__main__":
    main()
