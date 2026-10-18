"""Guardrails of the agent (see docs/llm_guardrails.md). Every function is pure and tested without LLM or database."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

MAX_LIMIT = 200
DEFAULT_LIMIT = 100
MAX_DEPTH = 6
MAX_STEPS = 5
QUERY_TIMEOUT_S = 10

CONTRACT = Path(__file__).resolve().parents[2] / "docs" / "GRAPH_CONTRACT.md"

FORBIDDEN = (
    "CREATE", "MERGE", "SET", "DELETE", "DETACH", "REMOVE", "DROP", "LOAD", "FOREACH", "CALL", "GRANT",
    "DENY", "REVOKE",
)  # fmt: skip
CLAUSE_START = ("MATCH", "OPTIONAL", "WITH", "UNWIND", "RETURN")
RELATION_ENDPOINTS = {
    "OCCURRED_IN": {("Event", "Country")},
    "HAS_THEME": {("Event", "Theme")},
    "MENTIONS": {("Event", "Commodity"), ("Event", "Currency")},
    "ON_DAY": {("Event", "TradingDay")},
    "PRICE_ON": {("PriceSeries", "TradingDay")},
    "TRACKS": {("PriceSeries", "Commodity"), ("PriceSeries", "Currency")},
    "PRECEDES": {("Event", "Event")},
    "CORRELATES_WITH": {("Theme", "PriceSeries")},
    "ABOUT_EVENT": {("Claim", "Event")},
    "ABOUT_SERIES": {("Claim", "PriceSeries")},
}

CAUSAL_REWRITES = {
    r"\bwas caused by\b": "was associated with",
    r"\bcaused\b": "was followed by",
    r"\bcauses\b": "is followed by",
    r"\bbecause of\b": "in association with",
    r"\bled to\b": "was followed by",
    r"\bleads to\b": "is followed by",
    r"\bresulted in\b": "was followed by",
    r"\bdue to\b": "in association with",
    r"\btriggered\b": "preceded",
    r"\bdrove\b": "was associated with",
    r"\bas a result of\b": "after",
}

ADVICE_PATTERNS = (
    r"\bshould i (buy|sell|invest|short|trade)\b",
    r"\b(buy|sell) (or|and) (sell|buy)\b",
    r"\b(place|execute|submit) (an? )?(order|trade)\b",
    r"\bfinancial advice\b",
    r"\bwhat should i (buy|sell|invest)\b",
    r"\bis (it|now) a good time to (buy|sell|invest|short|trade)\b",
    r"\bgo (long|short) on\b",
    r"\bdois-je (acheter|vendre|investir)\b",
    r"\bconseil (financier|d'investissement)\b",
)


class GuardrailError(ValueError):
    """Raised when a query or an answer breaks a guardrail. The message says which one."""


@lru_cache
def load_schema(path: Path = CONTRACT) -> dict[str, set[str]]:
    """Labels, relationship types and properties declared in docs/GRAPH_CONTRACT.md."""
    labels, rel_types, props = set(), set(), set()
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        if re.fullmatch(r"`\w+`", cells[0]):
            labels.add(cells[0].strip("`"))
            props.update(re.findall(r"`(\w+)`", cells[1]))
        elif "[:" in cells[0]:
            rel_types.update(re.findall(r"\[:(\w+)\]", cells[0]))
            props.update(re.findall(r"`(\w+)`", cells[1]))
    return {"labels": labels, "relationships": rel_types, "properties": props}


def strip_comments(query: str) -> str:
    """Remove Cypher comments while preserving quoted strings and identifiers."""
    tokens = r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:``|[^`])*`|//[^\n]*|/\*.*?\*/"

    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        if token.startswith(("//", "/*")):
            return " " + "\n" * token.count("\n")
        return token

    return re.sub(tokens, replace, query, flags=re.S)


def _blank_strings(query: str) -> str:
    """Remove comments and replace string literals by empty ones, so keywords inside text are not analysed."""
    return re.sub(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"", "''", strip_comments(query))


def check_read_only(query: str) -> None:
    """Guardrail 1: only read clauses, a single statement, no CALL."""
    clean = _blank_strings(query)
    if ";" in clean.strip().rstrip(";"):
        raise GuardrailError("Only one statement is allowed")
    words = re.findall(r"[A-Za-z_]+", clean.upper())
    if not words or words[0] not in CLAUSE_START:
        raise GuardrailError("The query must start with MATCH, OPTIONAL MATCH, WITH, UNWIND or RETURN")
    forbidden = sorted({w for w in words if w in FORBIDDEN})
    if forbidden:
        raise GuardrailError(f"Forbidden keyword(s): {', '.join(forbidden)}")


def check_schema(query: str, schema: dict[str, set[str]] | None = None) -> None:
    """Guardrail 2: labels, relationship types and properties must exist in the graph contract."""
    schema = schema or load_schema()
    clean = _blank_strings(query)
    for label in re.findall(r"\(\s*\w*\s*:\s*(\w+)", clean):
        if label not in schema["labels"]:
            raise GuardrailError(f"Unknown label: {label}")
    for group in re.findall(r"\[\s*\w*\s*:\s*([\w|:]+)", clean):
        for rel in re.split(r"[|:]", group):
            if rel and rel not in schema["relationships"]:
                raise GuardrailError(f"Unknown relationship type: {rel}")
    # `date.truncate(...)` is a function call, not a property access, so it is left out.
    for prop in re.findall(r"\b[A-Za-z_]\w*\.(\w+)\b(?!\s*\()", clean) + re.findall(r"\{\s*(\w+)\s*:", clean):
        if prop not in schema["properties"]:
            raise GuardrailError(f"Unknown property: {prop}")
    check_relationship_endpoints(clean)


def check_relationship_endpoints(clean: str) -> None:
    """Reject a typed one-hop pattern when its labels or direction contradict the contract."""
    # When both endpoint labels are explicit, the contract also defines which direction is valid.
    pattern = r"\(([^)]*)\)\s*(<-|-)\s*\[([^]]*)\]\s*(->|-)\s*\(([^)]*)\)"
    for match in re.finditer(f"(?={pattern})", clean):
        left, left_arrow, rel_body, right_arrow, right = match.groups()
        left_label = re.search(r":\s*(\w+)", left.split("{", 1)[0])
        right_label = re.search(r":\s*(\w+)", right.split("{", 1)[0])
        rel_type = re.search(r":\s*(\w+)", rel_body)
        if not (left_label and right_label and rel_type) or "*" in rel_body:
            continue
        allowed = RELATION_ENDPOINTS.get(rel_type.group(1))
        if allowed is None:
            continue
        pair = (left_label.group(1), right_label.group(1))
        if left_arrow == "<-" and right_arrow == "-":
            pair = pair[::-1]
        elif (left_arrow, right_arrow) != ("-", "->") and pair[::-1] in allowed:
            continue
        if pair not in allowed:
            raise GuardrailError(f"Invalid endpoints or direction for {rel_type.group(1)}: {pair}")


def check_depth(query: str) -> None:
    """Guardrail 3a: every variable-length pattern has an upper bound of MAX_DEPTH or less."""
    for body in re.findall(r"\[[^\]]*?\*([^\]]*)\]", _blank_strings(query)):
        match = re.fullmatch(r"\s*(\d*)\s*(\.\.)?\s*(\d*)\s*", body.split("{")[0])
        upper = match.group(3) if match else ""
        if not upper or int(upper) > MAX_DEPTH:
            raise GuardrailError(f"Traversal depth must be bounded to {MAX_DEPTH} or less")


def enforce_limit(query: str) -> str:
    """Guardrail 3b: add a LIMIT when missing and cap the existing one.

    Comments are stripped first: a query ending with `// ...` would otherwise swallow the injected LIMIT.
    """
    query = strip_comments(query).strip().rstrip(";").strip()
    match = re.search(r"\bLIMIT\s+(\d+)\s*$", query, flags=re.I)
    if match is None:
        return f"{query} LIMIT {DEFAULT_LIMIT}"
    if int(match.group(1)) > MAX_LIMIT:
        return query[: match.start(1)] + str(MAX_LIMIT)
    return query


def validate_cypher(query: str) -> str:
    """Run every query guardrail and return the query to execute (with a bounded LIMIT)."""
    check_read_only(query)
    check_schema(query)
    check_depth(query)
    return enforce_limit(query)


def is_financial_advice(question: str) -> bool:
    """Guardrail 7: requests for advice or orders are refused."""
    text = question.lower()
    return any(re.search(pattern, text) for pattern in ADVICE_PATTERNS)


def find_causal_wording(text: str) -> list[str]:
    """Causal expressions found in a text."""
    return [m.group(0) for pattern in CAUSAL_REWRITES for m in re.finditer(pattern, text, flags=re.I)]


def rewrite_causal(text: str) -> str:
    """Guardrail 6: replace causal expressions by neutral ones (longest expressions first)."""
    for pattern, neutral in CAUSAL_REWRITES.items():
        text = re.sub(pattern, neutral, text, flags=re.I)
    return text
