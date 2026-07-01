# BursaTrack — Real-Time Data Options Research

**Scope:** Bursa Malaysia (XKLS) equity price data options, excluding the community-built yfinance/Yahoo Finance library
**Date:** 14 June 2026
**Purpose:** Identify viable price data sources for BursaTrack MVP, ranked by suitability

---

## Key Framing: What BursaTrack Actually Needs

Before evaluating providers, it is worth being precise about the data requirement. BursaTrack is a portfolio tracker for dividend investors, not a trading platform. The use cases are:

| Use Case | Data Required | Frequency |
|---|---|---|
| Morning portfolio value check | Previous day's closing price OR live delayed quote | Once daily |
| Intraday portfolio monitoring | 15-min delayed or live price | A few times during market hours |
| Buy/sell calculator before placing an order | Live or near-live price | On demand |
| Dividend yield calculations | EOD close (for yield-on-market calculations) | Daily |

**Conclusion:** True real-time tick-by-tick data is unnecessary for this product. End-of-day (EOD) data satisfies the primary use case (morning check), and 15-minute delayed data satisfies the intraday use case. This dramatically reduces cost and simplifies the architecture.

Bursa Malaysia trading hours: **Monday–Friday, 09:00–12:30 and 14:30–17:00 MYT (GMT+8)**

---

## Options Overview

| Provider | Type | Bursa Coverage Confirmed | Latency | Price (USD/mo) | Verdict |
|---|---|---|---|---|---|
| **EODHD** | Paid API | ✅ Confirmed | EOD + 15-min delayed intraday | $19.99–$99.99 | **Best overall for MVP** |
| **Twelve Data** | Paid API | ✅ Confirmed | 170ms WebSocket | $29–$229 | Good; Malaysia requires Grow+ |
| **iTick** | Paid API | ✅ Confirmed (limited tiers) | <100ms WebSocket | Free–$319 | Malaysia in paid tiers only |
| **Bursa Official Feed** | Institutional | ✅ Native | Real-time | Enterprise (contact) | Overkill; not developer-friendly |
| **ICE Data Services** | Institutional | ✅ Confirmed | Real-time Level 2 | Enterprise | Overkill |
| **Barchart Solutions** | Commercial | ✅ Confirmed | Intraday + historical | Custom pricing | No self-serve |
| **Nikizwan Bursa API** | Community | ✅ Confirmed | EOD only | Free | Fragile; no SLA |
| **Web scraping (i3investor, KLSE Screener)** | DIY/community | ✅ Works today | Variable | Free | Against ToS; fragile |
| **Apify KLSE Scraper** | Managed scraper | ✅ Confirmed | On-demand scrape | Pay-per-use | Fragile; no SLA |

---

## 1. EODHD (End of Day Historical Data)

**Website:** [eodhd.com](https://eodhd.com)
**Type:** Commercial paid API
**Bursa Coverage:** Confirmed — hundreds of KLSE-listed stocks verified including CIMB, Maybank, RHB, Public Bank, Telekom, and others using `[ticker].KLSE` format

### What It Provides
- End-of-day historical prices (15+ years for major KLSE stocks)
- Intraday data (1m, 5m, 1h candles) with 15-minute delay for non-US markets
- Real-time WebSocket API (available on higher-tier plans)
- Fundamentals: revenue, EPS, P/E, dividend history, payout dates
- Corporate actions: dividends, splits, rights issues

### Pricing

| Plan | Price | Key Limits | KLSE Included? |
|---|---|---|---|
| Free | $0 | 20 API calls/day, EOD only | ✅ Yes |
| All World EOD | $19.99/mo | Unlimited EOD calls, all exchanges | ✅ Yes |
| All-In-One | $99.99/mo | EOD + fundamentals + intraday + news | ✅ Yes |
| Real-Time Add-on | ~$29.99/mo extra | WebSocket live prices | ✅ Yes |

### Why It Suits BursaTrack

EODHD is the strongest option for the MVP because its `All World EOD` plan ($19.99/month) gives unlimited EOD calls across all 60+ exchanges including KLSE. For a portfolio tracker, EOD closing prices satisfy the primary use case: the morning dashboard showing yesterday's close × lots held. The free tier (20 calls/day) is sufficient to run the reliability spike on all 16 target stocks before committing to any spend.

The dividend history endpoint is a bonus — it could eventually populate historical dividend data automatically rather than requiring manual entry.

### Risks
- EOD data means prices are always "yesterday's close" during market hours — the dashboard cannot show live intraday moves on the free/EOD tier
- Real-time upgrade adds ~$30/month on top of the base plan
- No public uptime SLA on lower-tier plans

### Recommendation for BursaTrack
**Use EODHD.** Start with the free tier for the technical spike. If reliability is confirmed over 20 trading days, upgrade to `All World EOD` at $19.99/month for the MVP. Revisit intraday/real-time only if user feedback confirms it is a blocker.

---

## 2. Twelve Data

**Website:** [twelvedata.com](https://twelvedata.com)
**Type:** Commercial paid API
**Bursa Coverage:** ✅ Confirmed — [Bursa Malaysia exchange page](https://twelvedata.com/exchanges/XKLS) explicitly listed

### What It Provides
- Real-time WebSocket with ~170ms latency
- REST API for historical and current price data
- Dividend, split, earnings data
- Technical indicators (100+)
- Python, JavaScript, and other SDK support

### Pricing

| Plan | Price (monthly) | API Credits/min | WS Credits | Markets | Notes |
|---|---|---|---|---|---|
| Basic | Free | 8 (800/day cap) | 8 trial | 3 (US, forex, crypto only) | ❌ Malaysia NOT included |
| Grow | $29–$79 | 55–377 | 8 trial | 20–27 | ⚠️ Need to verify KLSE included |
| Pro | $99–$229 | 610–1,597 | 500–1,500 | 70–75 | ✅ Malaysia confirmed at this tier |
| Ultra | $329–$999 | 2,584–10,946 | 2,500–10,000 | 84 | ✅ 99.95% SLA |

### Key Detail on Malaysia Access
The free Basic plan covers only US equities, forex, and crypto — **Malaysia is not available on the free tier.** Based on Twelve Data's exchange tier list, KLSE appears to be unlocked at the Grow tier (~$29/month) for EOD data, and the Pro tier (~$99/month) for real-time. Confirmation requires checking their [exchange tier matrix](https://twelvedata.com/exchanges?level=grow) directly.

### Why It Suits BursaTrack
Strong developer experience, official Python SDK, WebSocket support for eventual real-time features, and a well-documented API. If you anticipate building toward a multi-user product where real-time prices are a differentiator, Twelve Data's Pro plan gives you the infrastructure to get there without switching providers.

### Risks
- KLSE access is paywalled from day one — no free reliability testing without paying $29+/month
- Credit model can be confusing: each symbol per API call consumes 1 credit, so fetching 16 stocks = 16 credits per call
- Pricing increases significantly once real-time WebSocket is needed (Pro tier)

### Recommendation for BursaTrack
**Second choice.** Better developer experience than EODHD but starts costing money immediately for KLSE access. Use if the product roadmap includes real-time features and you want a single provider to grow into.

---

## 3. iTick

**Website:** [itick.org](https://itick.org/en)
**Type:** Commercial paid API (Hong Kong-based provider)
**Bursa Coverage:** ✅ Confirmed for paid tiers — Maybank, Public Bank, Tenaga Nasional cited explicitly. The free tier covers HK stocks, US stocks, and China A-shares only.

### What It Provides
- Real-time WebSocket with <100ms latency (institutional-grade)
- REST API for historical OHLCV, tick data, order book snapshots
- Fundamentals, corporate actions, technical indicators
- Focused on quantitative trading use cases

### Pricing

| Plan | Price (monthly, 20% off) | REST Calls/min | WS Connections | WS Subscriptions | Malaysia? |
|---|---|---|---|---|---|
| Free | $0 | 5 | 1 | 3 | ❌ HK/US/A-shares only |
| Base | $79 | 120 | 3 | 200 | ✅ Confirmed |
| Professional | $159 | 600 | 6 | 500 | ✅ Confirmed |
| Premium | $319 | 1,200 | 12 | 2,000 | ✅ Confirmed |

### Why It Suits BursaTrack
iTick is explicitly positioned for fintech developers building mobile/web apps on Bursa Malaysia data. It mentions the fintech use case directly (REST + mobile integration) and has sub-100ms latency for any future real-time features. The Base plan at $79/month allows 200 simultaneous WebSocket subscriptions — far more than needed for 16 stocks.

### Risks
- No free tier for KLSE — reliability testing requires paying $79/month minimum
- Less name recognition than EODHD or Twelve Data; community/forum evidence is limited
- Provider is Hong Kong-based; if they lose Bursa Malaysia data licensing, there is no recourse
- $79/month is high for a personal tool phase

### Recommendation for BursaTrack
**Third choice for MVP; viable for multi-user scale.** The pricing makes sense once you have paying users who can offset the cost. Too expensive to justify during personal-tool phase when EODHD at $19.99/month provides the same EOD data.

---

## 4. Official Bursa Malaysia Data Feed

**Website:** [bursamalaysia.com/trade/our_products_services/bursa_connectivity_services](https://www.bursamalaysia.com/trade/our_products_services/bursa_connectivity_services)
**Type:** Official exchange data — institutional

### What It Provides
- Native Level 1 and Level 2 market data direct from the exchange
- Co-location and low-latency connectivity to 900+ global data centres
- CDS API Gateway (account management only — not price data)
- Historical Data Package available separately

### Pricing
**Enterprise pricing only — contact required.** One reference found market data fees of approximately $39 USD/month via resellers, but direct exchange connectivity is almost certainly institutional-tier (thousands of USD/month plus setup fees). The Bursa Connectivity Services page instructs developers to email `[email protected]` — no self-serve option exists.

### Why It Does Not Suit BursaTrack (Yet)
This is the only source of truly official, zero-latency, fully licensed Bursa Malaysia price data. But the commercial model is designed for stockbrokers and institutional participants, not individual developers building personal tools. The cost, contract requirements, and lack of self-serve access make it impractical for MVP.

**Revisit only if:** BursaTrack scales to a commercial product with thousands of paying users and data licensing becomes a business-critical requirement.

---

## 5. ICE Data Services

**Website:** [developer.ice.com/fixed-income-data-services/catalog/bursa-malaysia](https://developer.ice.com/fixed-income-data-services/catalog/bursa-malaysia)
**Type:** Institutional financial data vendor

### What It Provides
- Bursa Malaysia data in native format or normalized via ICE Consolidated Feed
- Level 2 market depth (full order book)
- Streaming equities, fixed income, indices, options
- Historical and EOD data

### Assessment
Institutional-grade, enterprise pricing, no self-serve. ICE Data Services is used by banks, asset managers, and professional trading desks. Not relevant for BursaTrack at any stage of its current roadmap. Listed here for completeness.

---

## 6. Community / DIY Options

These options exist and work today but carry meaningful reliability and legal risk.

### Nikizwan Bursa Price API
- [nikizwan.com/bursa-price-api](https://nikizwan.com/bursa-price-api/)
- Individual developer's API providing daily OHLCV time series for KLSE stocks, 15+ years of history
- Free, no SLA, no guarantee of continued maintenance
- Suitable for: historical data experiments, backtesting
- Not suitable for: production portfolio tracker where stale data = wrong portfolio values

### Scraping i3investor / KLSE Screener
- Multiple open-source GitHub projects exist (`klse-stockquote-api`, `bursa-scraper`)
- Apify's KLSE Fundamentals scraper provides managed scraping with API access
- **Legal risk:** scraping is against the ToS of most financial websites
- **Reliability risk:** site structure changes break scrapers with no warning
- **Not recommended** for any production use

### KLSE2U.com Free Realtime Tools
- Free web-based real-time quote tools for KLSE
- No API; display only — not useful for programmatic access

---

## Recommended Architecture for BursaTrack

### Phase 1: MVP (Personal Tool)

**Primary source:** EODHD `All World EOD` — $19.99/month

**Data flow:**
1. After market close each day (17:00 MYT), cron job calls EODHD EOD endpoint for all 16 stocks
2. Store closing prices in your own database (Supabase or SQLite)
3. Portfolio dashboard reads from your database — no live API call on page load
4. Manual price refresh button triggers a fresh EODHD call on demand during market hours (returns previous close during trading, or latest if intraday plan)

**Fallback:** Manual price entry field — if EODHD is down, the user can type in today's price. This was already identified as a required feature in the Product Brief and should be built from day one regardless of which API is chosen.

**Cost at Phase 1:** ~$20/month (RM ~90/month), below the RM50 target in the discovery document — achievable if hosting is on Vercel free tier and database is on Supabase free tier.

### Phase 2: Intraday Prices (After Habit Validated)

**Upgrade to:** EODHD All-In-One ($99.99/month) or Twelve Data Pro ($99/month)

This gives 15-minute delayed intraday data — sufficient to show a "as-of 15 min ago" price during market hours. True real-time is not necessary for a dividend portfolio tracker and would add cost with minimal user value.

### Phase 3: Multi-User Product (After Paying Users Confirmed)

**Revisit:** Twelve Data Pro or iTick Base

At scale, per-user API calls require a more robust rate-limit and cost structure. Both Twelve Data and iTick are designed for this pattern (WebSocket subscriptions that fan out to many users from a single server connection).

---

## Technical Spike Checklist

Before writing any app code, run this spike over 20 consecutive trading days:

```python
# Suggested spike script (EODHD free tier)
import requests, datetime, time

STOCKS = ["1023.KLSE","1155.KLSE","1066.KLSE","1015.KLSE",
          "5139.KLSE","5031.KLSE","6262.KLSE","5012.KLSE",
          "4006.KLSE","6432.KLSE","2836.KLSE","5211.KLSE",
          "8621.KLSE","7210.KLSE","5246.KLSE","5209.KLSE"]

API_KEY = "your_free_api_key"
results = []

for ticker in STOCKS:
    url = f"https://eodhd.com/api/eod/{ticker}?api_token={API_KEY}&fmt=json&limit=1"
    r = requests.get(url)
    results.append({
        "ticker": ticker,
        "status": r.status_code,
        "date": r.json()[0]["date"] if r.status_code == 200 else None,
        "close": r.json()[0]["close"] if r.status_code == 200 else None,
        "checked_at": datetime.datetime.now().isoformat()
    })
    time.sleep(0.5)  # stay under rate limit

# Log results daily and check:
# 1. Did all 16 tickers return data?
# 2. Is the date current (yesterday's close)?
# 3. Any status codes other than 200?
```

Log results daily. If any ticker returns stale data (date more than 1 trading day behind) or fails on more than 1 out of 20 days, reconsider the provider before building.

---

## Summary Recommendation

For BursaTrack at its current stage — a personal portfolio tracker with a path to a small commercial product — the correct choice is:

**Start with EODHD (free tier for spike → $19.99/month All World EOD for MVP)**

It is the cheapest confirmed option with full KLSE coverage, provides both EOD and historical data in the same plan, has a dividend history endpoint that could replace manual dividend entry later, and allows reliable testing at zero cost before spending anything. The architecture of caching EOD prices in your own database means the app is not tightly coupled to any single API provider — switching to Twelve Data or iTick later requires only changing the data-ingestion cron job, not rewriting the application.

---

## TL;DR Summary

**The key reframe:** BursaTrack doesn't need true real-time data. End-of-day closing prices satisfy the morning portfolio check (the primary daily habit), and 15-minute delayed quotes satisfy any intraday use. This cuts cost dramatically.

**The clear winner for MVP is EODHD:**
- Free tier to run the reliability spike on all 16 stocks at zero cost
- $19.99/month for unlimited EOD data across all 60+ exchanges once confirmed working
- Includes dividend history as an endpoint (could eventually replace manual dividend logging)
- Architecture recommendation: cache prices in your own database after market close, so the app never makes a live API call on page load — fast, cheap, resilient

**The progression:**

| Phase | Provider | Cost | Trigger |
|---|---|---|---|
| Spike | EODHD (free tier) | $0 | Now — test all 16 stocks over 20 trading days |
| MVP | EODHD All World EOD | $19.99/month | Spike passes; well under RM50/month target |
| Multi-user | Twelve Data Pro or iTick Base | $79–$99/month | Paying users confirmed; WebSocket real-time needed |

**One flag to resolve immediately:** The Bursa Malaysia SST FAQ was updated in July 2025 and one source suggests brokerage fees may now be subject to 6% SST. The original fee verification in this project concluded SST was exempt for Bursa equity trades. Verify the July 2025 Bursa SST FAQ document before the fee calculator is built — a discrepancy here directly undermines the product's core accuracy claim.

---

## Sources

- [EODHD KLSE Exchange Page](https://eodhd.com/exchange/KLSE)
- [Twelve Data — Bursa Malaysia Exchange](https://twelvedata.com/exchanges/XKLS)
- [Twelve Data Pricing](https://twelvedata.com/pricing)
- [Twelve Data Data Delays Documentation](https://support.twelvedata.com/en/articles/5203307-data-delays)
- [iTick Pricing Page](https://itick.org/en/pricing)
- [iTick Malaysia Stock API Integration Guide](https://blog.itick.org/en/stock-api/malaysia-stock-api-quantitative-integration)
- [Bursa Malaysia Connectivity Services](https://www.bursamalaysia.com/trade/our_products_services/bursa_connectivity_services)
- [Bursa Malaysia Historical Data Package](https://www.bursamalaysia.com/historical-data-package)
- [ICE Data Services — Bursa Malaysia](https://developer.ice.com/fixed-income-data-services/catalog/bursa-malaysia)
- [Barchart Solutions — Bursa Malaysia (XKLS)](https://www.barchart.com/solutions/data/market/MDEX)
- [Nikizwan Bursa Price API](https://nikizwan.com/bursa-price-api/)
- [Apify KLSE Fundamentals Scraper](https://apify.com/lewxiangang/klse-fundamentals)
- [GitHub: klse-stockquote-api](https://github.com/vvel0x/klse-stockquote-api)
- [GitHub: bursa-scraper](https://github.com/tan-yong-sheng/bursa-scraper)
- [Bursa Malaysia API Gateway Announcement](https://www.bursamalaysia.com/cn/about_bursa/media_centre/bursa-malaysia-introduces-api-gateway-for-enhanced-investors-onboarding-experience)
