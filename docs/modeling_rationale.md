# Modeling rationale

Owner: role A. The contract is in `docs/GRAPH_CONTRACT.md`; the diagram is `docs/graph_schema.png`.

## Chosen model

The graph links **what happened** (events) to **what the markets did** (prices) through a shared calendar.

- `Event` nodes carry the facts of one event (date, title, CAMEO code, tone, mentions) and connect to a `Country` (`OCCURRED_IN`), a `Theme` (`HAS_THEME`) and a `TradingDay` (`ON_DAY`).
- `PriceSeries` nodes (Brent, EURUSD, US 10-year yield...) connect to the days they have a price for (`PRICE_ON`, with `close` and `ret_1d` on the relationship) and to the `Commodity` or `Currency` they follow (`TRACKS`).
- `TradingDay` is the meeting point: an event and a price move are linked by sharing a day, and a window of days is a simple traversal.
- `Claim` nodes hold the relations that the analytics or the agent **propose** (`status` hypothesis, verified or rejected, with a method and a confidence). `CORRELATES_WITH` stores a computed statistic between a theme and a series and never states a cause.
- Eight uniqueness constraints protect the keys used by `MERGE`, so ingestion is idempotent. Three indexes (`Event.date`, `PriceSeries.ticker`, `Claim.status`) support range filters and the most frequent lookups.

## Rejected alternatives

| Decision | Alternative rejected | Why |
|---|---|---|
| `Claim` is a node | Put `confidence` and `status` as properties on a relationship `(:Event)-[:AFFECTS]->(:PriceSeries)` | A proposed relation has evidence on two sides, a method, a status that changes over time and a history. A relationship property cannot be linked to its evidence, and it would blur verified facts and hypotheses. |
| `TradingDay` is a node | Store `date` as a property on events and compare dates in queries | Events happen every calendar day, prices only on trading days. A shared node makes the join explicit, handles weekends and holidays (`is_trading_day`), and turns "events in the 3 days before a move" into a traversal. |
| `PRICE_ON` carries `close` and `ret_1d` | One `Observation` node per price point | Halves the number of nodes and keeps the pattern `(series)-[:PRICE_ON]->(day)` short. The cost is that a single price point cannot be linked to anything else, which we do not need. |
| `Country` and `Theme` are nodes | Properties `country` and `theme` on `Event` | Core questions ("tension events in this country", "which themes co-occur with this series") are aggregations over these dimensions. Nodes give indexed hops and let the graph algorithms see them. |
| Central-bank events derived from rate series | A hand-written list of decisions | A derived list is reproducible and auditable. The trade-off is that it contains only rate changes, not "no change" decisions. |
| Countries as ISO3 codes, euro area as `EUR` | Keep the FIPS codes of GDELT | ISO3 is the standard shared with other datasets. `EUR` is a pseudo-country so the ECB events have a place; it is documented in the contract. |

## Anti-genericity appendix

The first table is a basic schema generated automatically from the project description, kept unmodified. The second compares it with ours.

**Generated schema (unmodified):** nodes `Event {id, title, date, description, country}` and `Asset {symbol, name, price_history}`; one relationship `(:Event)-[:AFFECTS {impact, confidence}]->(:Asset)`.

| Aspect | Generated schema | Our schema | Why we differ |
|---|---|---|---|
| Relation between event and market | A direct `AFFECTS` edge stating an impact | No direct causal edge. A temporal link through `TradingDay`, a computed `CORRELATES_WITH` statistic, and `Claim` nodes for anything proposed | The project must never present a correlation as a cause. An `AFFECTS` edge would state one. |
| Provenance and status of a proposed relation | `confidence` on the edge, no status, no method | `Claim` node with `status`, `method`, `confidence`, `rationale`, linked to its event and series | Hypotheses must be distinguishable from verified facts and traceable to their evidence. |
| Time alignment of events and prices | `date` property on events, `price_history` as a list property on assets | `TradingDay` nodes shared by events and prices, with `is_trading_day` and `event_count` | A list property cannot be traversed, indexed or aggregated by the graph algorithms; weekends and holidays are handled explicitly. |
| Constraints and indexes | None | 8 uniqueness constraints and 3 indexes | Constraints make `MERGE` idempotent and protect keys; indexes support the frequent filters. |
| Descriptive dimensions | `country` as a string property | `Country` and `Theme` nodes | Aggregations and graph algorithms need these as nodes. |
