# Datasets

Owner: role A. Everything below is reproducible with two commands (`make ingest`, then `make stats`).

## Sources

|Source|What we use|Link|
|-|-|-|
|GDELT 1.0 daily event files|Dated geopolitical events with actors, country, CAMEO code, Goldstein scale, tone, mention counts|http://data.gdeltproject.org/events/index.html|
|GDELT event codebook (CAMEO)|Meaning of the event codes and columns|http://data.gdeltproject.org/documentation/GDELT-Data_Format_Codebook.pdf|
|FRED (CSV endpoint)|Daily series: Brent (DCOILBRENTEU), WTI (DCOILWTICO), USD per EUR (DEXUSEU), JPY per USD (DEXJPUS), US 10-year yield (DGS10), Fed target rate upper bound (DFEDTARU), ECB deposit facility rate (ECBDFR)|https://fred.stlouisfed.org/|
|FRED terms of use|Conditions for reusing the series|https://fred.stlouisfed.org/docs/api/terms_of_use.html|

## Selection

* **Time window:** 1 February 2026 to 31 July 2026 for events (prices start one month earlier, on 1 January, so that the first returns exist). The window contains the 2026 Middle East tensions and the reaction of oil prices to them, so events and market moves co-occur often enough to be interesting.
* **Event filters:** only GDELT events with CAMEO root codes 13 to 19 (threaten, protest, exhibit force posture, reduce relations, coerce, assault, fight), located in one of 30 countries mapped from FIPS to ISO3 codes (`FIPS_TO_ISO3` in `scripts/ingest_events.py`), at least 20 mentions, the 25 most mentioned per day among the events dated that same day (a daily file also holds older events, which are dropped), on every day of the window (`--step 1`).
* **Central-bank events:** not hand-written. Every change of the Fed target rate (upper bound) or of the ECB deposit facility rate in the window becomes an event with theme `MONETARY_POLICY`, derived from the FRED series.
* **Series list:** Brent, WTI, EURUSD, USDJPY, US 10-year yield (five series, about one hundred and fifty observations each over the window).
- **Resulting size:** about 4,500 events and about 730 price points. The exact numbers are produced by `make stats` and pasted in the section "Measured size" below.

## Justification

* The geopolitical and central-bank events in GDELT and the policy-rate series are public and reproducible, so the graph can be rebuilt by anyone with two commands.
* The window is short on purpose: the downloads stay small, loading takes minutes, and the graph is still large enough for centrality, community detection and the benchmarks of stage 2.
* Using FRED policy rates to derive central-bank events avoids a hand-compiled list that nobody could audit.
* Limits we accept and state openly: GDELT is machine-coded from news and contains noise and duplicates; a temporal coincidence between an event and a price move is never presented as a cause.

## Licences and terms

* GDELT is free and open for any use; its terms ask that users cite the project. We cite it here and in the README.
* Each FRED series is published by its original provider (Board of Governors of the Federal Reserve System, U.S. Energy Information Administration, European Central Bank). The data are used for educational and analytical purposes only, in line with FRED's terms of use linked above. Raw downloads are cached in `data/raw/`, which is excluded from Git.

## Reproducing the data

```bash
cp .env.example .env              # set NEO4J_PASSWORD
docker compose up -d neo4j        # database with the GDS plugin
make schema                       # constraints and indexes
make ingest                       # FRED prices, then GDELT and central-bank events
make stats                        # counts to paste below
```

`make ingest` is idempotent: running it again creates no duplicate. Options: `python -m scripts.ingest_events --help`.

## Measured size

Output of `make stats` after the first load (window 2026-02-01 to 2026-07-31, every day):

```text
Nodes
  Event        4526
  TradingDay   202
  Country      31
  Theme        8
  PriceSeries  5
  Commodity    2
  Currency     2
Relationships
  OCCURRED_IN    4526
  HAS_THEME      4526
  ON_DAY         4526
  PRICE_ON       730
  TRACKS         4
```

Consistency checks: every event has exactly one country, one theme and one day (4,526 each). 4,526 = 181 days x 25 events + 1 central-bank event derived from FRED. `PRICE_ON` equals the number of price points loaded. `TRACKS` links the two commodity series and the two currency series to their entity; the US 10-year yield has none, as it is a rate. `TradingDay` (202) = the 181 days of the event window plus the January days that only carry prices. Every event is dated the day of its GDELT file: older events republished in a daily file are dropped.
