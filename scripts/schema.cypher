// Draft schema: contract baseline (see docs/GRAPH_CONTRACT.md).
// Role A finalizes it in task A1. Every statement must be idempotent (IF NOT EXISTS).

CREATE CONSTRAINT event_id IF NOT EXISTS FOR (e:Event) REQUIRE e.event_id IS UNIQUE;
CREATE CONSTRAINT country_iso3 IF NOT EXISTS FOR (c:Country) REQUIRE c.iso3 IS UNIQUE;
CREATE CONSTRAINT theme_code IF NOT EXISTS FOR (t:Theme) REQUIRE t.code IS UNIQUE;
CREATE CONSTRAINT commodity_code IF NOT EXISTS FOR (c:Commodity) REQUIRE c.code IS UNIQUE;
CREATE CONSTRAINT currency_code IF NOT EXISTS FOR (c:Currency) REQUIRE c.code IS UNIQUE;
CREATE CONSTRAINT series_id IF NOT EXISTS FOR (s:PriceSeries) REQUIRE s.series_id IS UNIQUE;
CREATE CONSTRAINT trading_day_date IF NOT EXISTS FOR (d:TradingDay) REQUIRE d.date IS UNIQUE;
CREATE CONSTRAINT claim_id IF NOT EXISTS FOR (c:Claim) REQUIRE c.claim_id IS UNIQUE;

CREATE INDEX event_date IF NOT EXISTS FOR (e:Event) ON (e.date);
CREATE INDEX series_ticker IF NOT EXISTS FOR (s:PriceSeries) ON (s.ticker);
CREATE INDEX claim_status IF NOT EXISTS FOR (c:Claim) ON (c.status);
