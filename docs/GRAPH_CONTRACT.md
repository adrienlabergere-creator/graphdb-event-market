# Graph contract (draft until stage 1 is merged, then frozen)

Owner: role A. This is the baseline the team must **defend and may change before the freeze**. After the freeze, changes go through a PR approved by the lead and the owner.

## Nodes

| Label | Key properties | Notes |
|---|---|---|
| `Event` | `event_id` (unique), `date`, `title`, `cameo_code`, `goldstein`, `avg_tone`, `num_mentions`, `source_url` | One node per event in the selected window |
| `Country` | `iso3` (unique), `name` | |
| `Theme` | `code` (unique), `label` | Event category used for aggregation |
| `Commodity` | `code` (unique), `name` | For example crude oil |
| `Currency` | `code` (unique), `name` | For example EURUSD base and quote currencies |
| `PriceSeries` | `series_id` (unique), `source` (FRED or market data), `ticker`, `name`, `unit` | One per instrument |
| `TradingDay` | `date` (unique), `is_trading_day` | Calendar-day join key between events and prices |
| `Claim` | `claim_id` (unique), `kind`, `status`, `confidence`, `method`, `rationale`, `created_at` | A proposed relation. `status` in `hypothesis`, `verified`, `rejected` |

## Relationships

| Pattern | Properties | Meaning |
|---|---|---|
| `(:Event)-[:OCCURRED_IN]->(:Country)` | | Where the event happened |
| `(:Event)-[:HAS_THEME]->(:Theme)` | | Category of the event |
| `(:Event)-[:MENTIONS]->(:Commodity)` and `(:Event)-[:MENTIONS]->(:Currency)` | `weight` | What the event talks about |
| `(:Event)-[:ON_DAY]->(:TradingDay)` | | Calendar alignment |
| `(:PriceSeries)-[:PRICE_ON]->(:TradingDay)` | `close`, `ret_1d` | One price point per day |
| `(:PriceSeries)-[:TRACKS]->(:Commodity)` and `(:PriceSeries)-[:TRACKS]->(:Currency)` | | Which instrument the series follows |
| `(:Event)-[:PRECEDES]->(:Event)` | `lag_days` | Temporal sequence of related events |
| `(:Theme)-[:CORRELATES_WITH]->(:PriceSeries)` | `corr`, `window_days`, `n`, `computed_at` | **Computed statistic, never a causal claim** |
| `(:Claim)-[:ABOUT_EVENT]->(:Event)` | | Evidence side |
| `(:Claim)-[:ABOUT_SERIES]->(:PriceSeries)` | | Market side |

## Constraints and indexes

See `scripts/schema.cypher` (8 uniqueness constraints, indexes on `Event.date`, `PriceSeries.ticker`, `Claim.status`). Role A adds a full-text or other index only with a benchmark that justifies it.

## Modeling decisions to defend

1. **`Claim` is a node, not a relationship property.** A proposed relation needs several pieces of evidence, a confidence, a status that changes over time and a method. A relationship property cannot carry that history. This is also how verified facts stay distinct from hypotheses.
2. **`TradingDay` is a node, not a date property.** Events happen on calendar days, prices exist on trading days. A shared day node makes the join explicit and handles weekends and holidays through `is_trading_day`.
3. **`PRICE_ON` carries the price as relationship properties** instead of one `Observation` node per point. It halves the number of nodes. The trade-off is that a price point cannot itself be linked to something else.
4. **`Country` and `Theme` are nodes**, because traversals such as "events in this country with this theme" are the core queries and need indexed hops.
5. **`CORRELATES_WITH` stores a computed statistic with its window and sample size.** It never states a cause.

Rejected alternatives and the comparison with a generic schema go in `docs/modeling_rationale.md`.
