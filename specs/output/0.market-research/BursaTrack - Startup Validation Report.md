# Startup Validation Report: BursaTrack — Bursa Malaysia Portfolio Tracker for Dividend Investors

**Target Market:** Malaysia (retail equity investors on Bursa Malaysia)

**Verdict: CONDITIONAL GO — Strong personal tool. Unproven as a business.**

BursaTrack solves a real, specific, daily problem and the founder is the perfect reference user. Build it. But before treating it as a startup rather than a side project, three things need to be stress-tested: KLSE Screener is a more dangerous incumbent than the discovery document acknowledges, Malaysian consumers' willingness to pay for SaaS tools is a structural headwind, and the price data dependency is genuinely unresolved. The path from "tool I use every day" to "business with paying customers" requires at least one of these to break in your favour, and right now none of them are confirmed.

---

## 1. Problem Validity

*Is the problem real, specific, and frequent enough?*

This is the strongest part of the pitch. The problem is not manufactured — the founder lives it every morning. Spending 10–15 minutes manually updating prices across 16 stocks is a documented daily friction with a clear cost (stale data, decision risk, time). The bug found in the Excel file's row 28 formula is not anecdotal colour — it is evidence of exactly the kind of silent compounding failure the discovery document describes. The workaround (a spreadsheet not designed to be a portfolio management system) is clearly inadequate at scale. The problem is real, frequent (daily), and the consequence of failure (wrong investment decisions) is meaningful.

The one caveat: the discovery document frames this as a broadly shared problem across Malaysian retail investors. That may be true, but what has been proven is that *one* specific investor with 16 positions, 3–4 years of history, and a dividend income strategy has this problem acutely. The question of how many others share the same profile and the same pain level is unverified by user research — it is an inference, not evidence.

**Strength: 4/5**

**Key gap:** No interviews with other Malaysian retail investors to confirm the pain is shared at the same intensity beyond the founder.

---

## 2. Market Assessment

*Who has this problem in Malaysia, and is that a market?*

The macro numbers are genuinely encouraging. Malaysia has approximately 2.4 million active retail investors with 147,091 new CDS accounts opened in just the first half of 2025 — a 67% jump year-on-year. Young investors (18–35) represent 20% of the active base, roughly 490,000 people, and that cohort is growing fastest. The market is real and expanding.

The problem is with the denominator. BursaTrack is not for all 2.4 million retail investors — it is for dividend-focused investors with multi-stock portfolios who currently use spreadsheets and check their portfolio daily. That is a meaningful subset, but it has not been sized bottom-up. If roughly 20–30% of active investors fit this behavioural profile, the addressable segment is perhaps 400,000–700,000 people. That sounds large until you account for Malaysian consumer pricing norms.

Malaysian retail investors have extremely low demonstrated willingness to pay for portfolio analytics tools. The dominant tools in this market — KLSE Screener, MalaysiaStock.Biz — are free or freemium with minimal paid conversion. MalaysiaStock.Biz moved behind a paywall in August 2024; it is not yet clear whether that was a successful transition or a slow-motion exit. Sharesight, which is genuinely capable, charges AUD 32/month — it has essentially no meaningful Malaysian user base at that price point. The working assumption in the discovery document is that BursaTrack can capture paying users, but there is zero evidence the Malaysian retail investor cohort will pay RM15–30/month for a tool they currently use for free (or in Excel, which they already own).

**Strength: 3/5**

**Key gap:** No validation that the target segment will pay for this. The free-tool expectation in Malaysian consumer software is a serious structural headwind.

---

## 3. Competitive Landscape

*Is anyone else solving this in Malaysia, and what does that mean?*

This is where the discovery document is most optimistic and most incomplete. The competition is more dangerous than acknowledged.

**KLSE Screener** is the biggest risk and is barely mentioned. It is a mature, deeply embedded, Bursa-native app with a large and loyal Malaysian user base. It has portfolio tracking with realised and unrealised P&L, dividend reports with ex-dates and historical records, real-time Bursa data, news, and both iOS and Android apps. It is free. This is not a generic global tracker with a Bursa search bar — it is built specifically for Malaysian investors and has been for years. The specific gap BursaTrack proposes to fill (correct per-broker fee modelling and per-tranche dividend logging) is real, but it is narrow. KLSE Screener could ship that feature in a sprint if they decided it mattered.

**Portseido** covers Malaysia explicitly (listed as a Malaysia Portfolio Tracker), has dividend tracking, beautiful mobile UI, and supports 85+ exchanges. It does not correctly model the Malaysian fee stack — but a free tier exists, it works on mobile, and it is already in the market.

**MalaysiaStock.Biz** has portfolio tracking and dividend history and has been in the market for over a decade, though it now requires a subscription.

**A standalone Malaysia fee calculator app already exists** on Google Play — it correctly calculates brokerage, clearing fee, and stamp duty per Bursa Malaysia's rules. This is not a portfolio tracker, but it undercuts the claim that the fee calculation gap is completely unaddressed.

**Bursa Anywhere** (official Bursa app) covers CDS account visibility and corporate action alerts including dividends.

No graveyard of failed Malaysian portfolio tracker startups was found, which could mean the market is untested — or that the problem is adequately served by free tools and no one has found a path to monetisation worth trying.

**Strength: 2/5**

**Key gap:** KLSE Screener is a free, Bursa-native, mobile-first incumbent with portfolio tracking and dividend data already. The discovery document does not address why a user would switch from KLSE Screener to BursaTrack, or why KLSE Screener would not simply add the missing features.

---

## 4. Solution Fit

*Does this solution actually solve the problem?*

For the founder personally: yes, cleanly. The Excel file is essentially a working specification and the solution ports it into a web application. The fee logic is verified, the data model is understood, and the behaviour change required (open BursaTrack instead of Excel) is modest given that the Excel experience is already painful enough to motivate switching.

For a broader user: more complicated. The solution requires users to manually enter every position, every lot, and every historical dividend — or import from CSV, which requires a clean export from whatever they use today. That is a non-trivial onboarding barrier for anyone who isn't already living in Excel. Farah (the Emerging Income Investor persona) wants things to "just work" — but BursaTrack requires significant upfront data entry before it provides any value. That first 30 minutes of onboarding is where the product will be won or lost for every user who isn't the founder.

The price data dependency (yfinance/Yahoo Finance unofficial API) is explicitly flagged as the highest risk, and the research confirms it: Yahoo's official API was shut down in 2017, and the community-maintained yfinance library explicitly warns that "occasional disruptions may occur." This is not a hypothetical risk — it has broken before. On a day when the API fails during market hours, BursaTrack becomes an offline log. That is recoverable with a manual fallback, but it creates exactly the friction that drives users back to their broker app.

One important flag from research: a recent source suggests brokerage fees in Malaysia may be subject to 6% SST, while the discovery package's fee verification concluded SST was exempt for Bursa equity trades. Bursa Malaysia published an updated SST FAQ in July 2025. This should be re-verified before the fee calculator ships — a discrepancy here would directly undermine the product's core accuracy claim.

**Strength: 4/5**

**Key gap:** Onboarding friction is high for anyone who doesn't already have a clean, complete transaction history. The price data dependency is structurally unresolved. SST treatment on brokerage fees needs re-verification against the July 2025 Bursa FAQ.

---

## 5. Disconfirming Evidence

- **KLSE Screener already exists and is free.** It is Bursa-native, has dividend reports, portfolio P&L, real-time data, and mobile apps. The discovery document does not confront this directly.
- **No evidence of willingness to pay.** The dominant free tools in this exact market (KLSE Screener, formerly MalaysiaStock.Biz) have trained Malaysian retail investors to expect portfolio analytics at zero cost. MalaysiaStock.Biz's move to a paywall in August 2024 is an ongoing natural experiment worth watching.
- **A fee calculator app already exists on Google Play** that handles brokerage + clearing + stamp duty for Bursa trades. The gap is narrower than the document implies.
- **The Yahoo Finance API is unofficial** and has experienced outages. Every serious portfolio app that relies on it carries this tail risk with no institutional recourse.
- **No failed-startup evidence found** — but this cuts both ways. Either no one has tried (untested market), or existing free tools have been sufficient enough that paid alternatives never found traction.
- **Portseido already covers Malaysia** and has a free tier. It lacks correct Malaysian fee modelling, but it is already in users' hands and is expanding.
- **SST on brokerage fees** — if the July 2025 Bursa FAQ shows SST now applies, the fee calculations in the existing Excel model and the planned app are both wrong. This needs immediate verification.

---

## 6. What Would Have to Be True

| Assumption | Cheapest Test |
|---|---|
| KLSE Screener's portfolio tracker is insufficient for dividend-focused investors | Spend 2 hours using it for your own 16 stocks. Document exactly what it cannot do that you need. |
| Malaysian retail investors will pay for a portfolio tool | Find 10 people who use Excel or Google Sheets for their Bursa portfolio. Ask them how much they'd pay monthly. If the answer is consistently "nothing," you have your answer. |
| yfinance provides reliable Bursa data for daily use | Run a monitoring script on all 16 target stocks across 20 consecutive trading days, logging failures, delays, and stale prices. Do this before writing a line of app code. |
| SST is exempt on brokerage for Bursa equity trades | Read the Bursa SST FAQ updated July 2025. This takes 10 minutes and must be confirmed before the fee calculator ships. |
| The onboarding (manual position entry or CSV import) is not a conversion killer | Time yourself importing your own 16 positions, all lots, and all historical dividends into a blank spreadsheet or prototype. If it takes more than 20 minutes, most users won't finish. |

---

## 7. Verdict Reasoning

Build BursaTrack as a personal tool — there is no question about that. The problem is real, the solution is well-specified, the Excel model is a working prototype, and the founder is the ideal first user. Shipping a v1 personal tracker is a weekend project, not a startup decision.

The startup question is separate and harder. The path to a business requires paying users, and that requires clearing two hurdles that are currently unvalidated: (1) convincing Malaysian retail investors that BursaTrack does something meaningfully different from KLSE Screener, and (2) convincing them to pay for it. Neither is impossible, but neither is assumed.

The strongest version of the BursaTrack business case rests on the correct Malaysian fee stack being a genuine, uncopyable differentiator — and on the hypothesis that dividend-focused investors who care about their true cost basis will pay a small monthly fee for accuracy and convenience that free tools don't provide. That hypothesis is coherent. It is not yet evidenced.

**The conditional:** do the five tests in Section 6 before investing more than a weekend in this. If KLSE Screener turns out to be a credible substitute for everything BursaTrack does, and if 10 conversations confirm Malaysian investors won't pay, the right call is to build this as a free personal tool and open-source it — not to build a startup around it. If those tests come back in your favour, the opportunity is real.

---

## Sources

- [Portseido Malaysia Portfolio Tracker](https://www.portseido.com/portfolio-tracker/malaysia/)
- [KLSE Screener on Google Play](https://play.google.com/store/apps/details?id=net.neobie.klse&hl=en)
- [Bursa Malaysia Retail Investor Insights](https://www.bursamalaysia.com/sites/5d809dcf39fba22790cad230/assets/6606811bcd34aa9cda9d94b2/Malaysian_Retail_Investor_Insights.pdf)
- [147,091 new CDS accounts opened in H1 2025 — The Edge Malaysia](https://theedgemalaysia.com/article/147091-new-cds-accounts-opened-1h-strong-interest-among-millennials-%E2%80%94-bursa-ceo)
- [Bursa Malaysia SST FAQ (updated July 2025)](https://www.bursamalaysia.com/sites/5d809dcf39fba22790cad230/assets/68638114e6414abcf48ef314/SST_-_FAQs_updated_1_July_2025.pdf)
- [Malaysia Stock Calculator App (Google Play)](https://play.google.com/store/apps/details?id=com.han.mystock&hl=en)
- [Bursa Brokerage Fee Calculator](https://calculatormalaysia.com/investment/bursa-brokerage-fee-calculator-malaysia/)
- [Sharesight — Track Bursa Malaysia Stocks](https://www.sharesight.com/blog/track-stocks-on-the-bursa-malaysia-exchange-with-sharesight/)
- [MalaysiaStock.Biz Portfolio](https://www.malaysiastock.biz/Login.aspx?Page=Portfolio)
- [yfinance / Yahoo Finance API documentation](https://www.quantvps.com/blog/yahoo-finance-api-documentation)
