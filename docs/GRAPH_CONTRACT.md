# Graph contract (frozen when stage 1 is merged)

Owner: role A. After the freeze, a change goes through a PR approved by the lead and the owner. Stages 2 and 3 build on this document.

## Nodes

| Label | Key properties | Notes |
|---|---|---|
| `Event` | `event_id` (unique), `date`, `title`, `cameo_code`, `goldstein`, `avg_tone`, `num_mentions`, `source_url` | One node per event in the selected window. `event_id` is `GDELT-<id>` or `CB-<bank>-<date>` |
| `Country` | `iso3` (unique), `name` | ISO 3166 alpha-3. `EUR` stands for the euro area (central-bank events of the ECB) |
| `Theme` | `code` (unique), `label` | Event category used for aggregation: `CAMEO_13` to `CAMEO_19` (tension events) and `MONETARY_POLICY` |
| `Commodity` | `code` (unique), `name` | For example crude oil |
| `Currency` | `code` (unique), `name` | For example EURUSD base and quote currencies |
| `PriceSeries` | `series_id` (unique), `source`, `ticker`, `name`, `unit`, `kind` (`commodity`, `fx` or `rate`) | One per instrument |
| `TradingDay` | `date` (unique), `is_trading_day`, `event_count` | Calendar-day join key between events and prices. Created by events (`false`) or prices (`true`). `event_count` is recomputed after each event load |
| `Claim` | `claim_id` (unique), `kind`, `status`, `confidence`, `method`, `rationale`, `created_at` | A proposed relation. `status` in `hypothesis`, `verified`, `rejected` |

## Relationships

| Pattern | Properties | Meaning |
|---|---|---|
| `(:Event)-[:OCCURRED_IN]->(:Country)` | | Where the event happened |
| `(:Event)-[:HAS_THEME]->(:Theme)` | | Category of the event |
| `(:Event)-[:MENTIONS]->(:Commodity)` and `(:Event)-[:MENTIONS]->(:Currency)` | `weight` | What the event talks about. Defined by the contract, filled by stage 2 if the analysis needs it |
| `(:Event)-[:ON_DAY]->(:TradingDay)` | | Calendar alignment |
| `(:PriceSeries)-[:PRICE_ON]->(:TradingDay)` | `close`, `ret_1d` | One price point per day. `ret_1d` is a simple return, except for `rate` series where it is the change in percentage points |
| `(:PriceSeries)-[:TRACKS]->(:Commodity)` and `(:PriceSeries)-[:TRACKS]->(:Currency)` | | Which instrument the series follows (rate series track nothing) |
| `(:Event)-[:PRECEDES]->(:Event)` | `lag_days` | Temporal sequence of related events. Defined by the contract, filled by stage 2 if needed |
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
