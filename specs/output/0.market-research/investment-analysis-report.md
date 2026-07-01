# Investment Analysis Excel — Structure & Formula Report

> **File:** `Investment Analysis.xlsx`  
> **Sheet:** `Investment (Shares)` (only sheet)  
> **Dimensions:** A1:Y50 (active data through row 32)  
> **Fee Verification:** Added 2026-06-14 (cross-checked against Bursa official sources and broker fee schedules)  
> **Reviewed:** 2026-06-14

---

## 1. Overview

The workbook tracks a Malaysia Bursa stock portfolio across **16 shares**, calculating purchase costs (including all transaction fees), recording dividend payments per tranche, summing total dividend profit, and computing dividend yield (ROI). A separate **Calculator panel** on the right (columns S–Y) provides interactive BUY cost and SELL scenario analysis for any one selected stock at a time.

---

## 2. Sheet Layout Map

| Region | Columns | Rows | Purpose |
|--------|---------|------|---------|
| Labels | A | 1–31 | Row descriptions |
| Portfolio data | B–Q | 1–31 | 16 stocks |
| Spacer | R | — | Blank separator |
| Calculator panel | S–Y | 3–50 | BUY/SELL analysis tool |

---

## 3. Global Constant

| Cell | Value | Purpose |
|------|-------|---------|
| **A1** | `5000` | Default number of shares held for every stock. Used as fallback in all share-count calculations. Can be overridden per stock via **row 1, columns B–Q** (currently all blank, so every stock uses 5,000 shares). |

---

## 4. Portfolio Table — Column Structure (B through Q)

### 4.1 Stocks Tracked

| Col | Code | Name | Sector |
|-----|------|------|--------|
| B | 1023 | CIMB | Banking |
| C | 1155 | MAYBANK | Banking |
| D | 1066 | RHBBANK | Banking |
| E | 1015 | AMBANK | Banking |
| F | 5139 | AEONCR | Other Financial |
| G | 5031 | TIMECOM | Telco |
| H | 6262 | INNO | Plantation |
| I | 5012 | TAANN | Plantation |
| J | 4006 | ORIENT | Automotive |
| K | 6432 | APOLLO | Food & Beverages |
| L | 2836 | CARLSBG | Food & Beverages |
| M | 5211 | SUNWAY | Industrial |
| N | 8621 | LPI | Insurance |
| O | 7210 | FM | Transportation & Logistics |
| P | 5246 | WPRTS | Transportation & Logistics |
| Q | 5209 | GASMSIA | Gas, Water & Multi-Utilities |

> **Note:** SUNWAY (col M) is tagged `Volatile (Fluctuation)` in row 2 instead of `Dividend`, signalling it is held for capital gain rather than income.

### 4.2 Row-by-Row Description

---

#### Row 1 — Per-Stock Share Count Override
**Value:** All blank (B1:Q1)  
**Effect:** Every stock defaults to the global count in **A1** (5,000 shares).  
**How to use:** Enter a number here to override the share count for that column only (e.g., put `2000` in B1 to track 2,000 CIMB shares instead of 5,000).

---

#### Row 2 — Category Tag
**Values:** `Dividend` for cols B–L, N–Q; `Volatile (Fluctuation)` for col M (SUNWAY).  
Purely informational labels.

---

#### Row 3 — Share Name
**Values:** Stock name with Bursa code (e.g., `CIMB 1023`).  
Referenced by the Calculator's HLOOKUP.

---

#### Row 4 — Type of Stock (Sector)
**Values:** Hard-coded sector text per column. Informational only.

---

#### Row 5 — Share Price (MYR)
**Values:** Manually entered current market price per share.  

| Stock | Price (MYR) |
|-------|-------------|
| CIMB | 8.38 |
| MAYBANK | 11.94 |
| RHBBANK | 8.08 |
| AMBANK | 6.08 |
| AEONCR | 5.80 |
| TIMECOM | 5.98 |
| INNO | 1.96 |
| TAANN | 4.63 |
| ORIENT | 7.04 |
| APOLLO | 6.05 |
| CARLSBG | 17.84 |
| SUNWAY | 5.63 |
| LPI | 15.44 |
| FM | 0.60 |
| WPRTS | 5.67 |
| GASMSIA | 4.68 |

---

#### Row 6 — INITIAL Share Price / Purchase Cost (MYR)
**Formula (all cols):** `=IF(B5="","", IF(B$1<>"", B$1*B5, $A$1*B5))`

**Logic:**
- If share price (row 5) is blank → blank (no position held).
- If a per-stock override count exists in row 1 → use that count × share price.
- Otherwise → use the global 5,000 (A1) × share price.

This is the **raw purchase consideration** before fees. Currently all stocks use 5,000 × price.

| Stock | Initial Amount (MYR) |
|-------|---------------------|
| CIMB | 41,900.00 |
| MAYBANK | 59,700.00 |
| RHBBANK | 40,400.00 |
| AMBANK | 30,400.00 |
| AEONCR | 29,000.00 |
| TIMECOM | 29,900.00 |
| INNO | 9,800.00 |
| TAANN | 23,150.00 |
| ORIENT | 35,200.00 |
| APOLLO | 30,250.00 |
| CARLSBG | 89,200.00 |
| SUNWAY | 28,150.00 |
| LPI | 77,200.00 |
| FM | 3,000.00 |
| WPRTS | 28,350.00 |
| GASMSIA | 23,400.00 |

---

#### Row 7 — Brokerage Fees (MYR)
**Formula:** `=IFERROR(IF(B$6=0,"", IF(B$6*0.1%<8, 8, B$6*0.1%)), "")`

**Rate:** 0.10% of initial amount, **minimum MYR 8**.

| Stock | Fee (MYR) |
|-------|----------|
| CIMB | 41.90 |
| MAYBANK | 59.70 |
| RHBBANK | 40.40 |
| AMBANK | 30.40 |
| AEONCR | 29.00 |
| TIMECOM | 29.90 |
| INNO | 9.80 |
| TAANN | 23.15 |
| ORIENT | 35.20 |
| APOLLO | 30.25 |
| CARLSBG | 89.20 |
| SUNWAY | 28.15 |
| LPI | 77.20 |
| FM | 8.00 ← minimum applied |
| WPRTS | 28.35 |
| GASMSIA | 23.40 |

> FM (0.60 × 5,000 = MYR 3,000 → 0.1% = MYR 3.00 < MYR 8) → minimum MYR 8 applied.

---

#### Row 8 — Clearing Fees (MYR)
**Formula:** `=IFERROR(IF(B$6=0,"", B$6*0.03%), "")`

**Rate:** 0.03% of initial amount. No minimum.

| Stock | Fee (MYR) |
|-------|----------|
| CIMB | 12.57 |
| MAYBANK | 17.91 |
| RHBBANK | 12.12 |
| AMBANK | 9.12 |
| AEONCR | 8.70 |
| TIMECOM | 8.97 |
| INNO | 2.94 |
| TAANN | 6.95 |
| ORIENT | 10.56 |
| APOLLO | 9.08 |
| CARLSBG | 26.76 |
| SUNWAY | 8.45 |
| LPI | 23.16 |
| FM | 0.90 |
| WPRTS | 8.51 |
| GASMSIA | 7.02 |

---

#### Row 9 — Stamp Duty (MYR)
**Formula:** `=IFERROR(IF(B$6=0,"", IF(B$6>=1000, ROUNDUP(B$6/1000,0), 1)), "")`

**Rate:** MYR 1 per MYR 1,000 of contract value (rounded up), minimum MYR 1. This matches Bursa's stamp duty schedule.

| Stock | Duty (MYR) |
|-------|-----------|
| CIMB | 42 |
| MAYBANK | 60 |
| RHBBANK | 41 |
| AMBANK | 31 |
| AEONCR | 29 |
| TIMECOM | 30 |
| INNO | 10 |
| TAANN | 24 |
| ORIENT | 36 |
| APOLLO | 31 |
| CARLSBG | 90 |
| SUNWAY | 29 |
| LPI | 78 |
| FM | 3 |
| WPRTS | 29 |
| GASMSIA | 24 |

---

#### Row 10 — FINAL Share Price / All-In Cost (MYR)
**Formula:** `=IF(B$6=0,"", B$6+SUM(B$7:B$9))`

Total cost of acquiring the position = Initial Amount + Brokerage + Clearing + Stamp Duty.

| Stock | All-In Cost (MYR) |
|-------|------------------|
| CIMB | 41,996.47 |
| MAYBANK | 59,837.61 |
| RHBBANK | 40,493.52 |
| AMBANK | 30,470.52 |
| AEONCR | 29,066.70 |
| TIMECOM | 29,968.87 |
| INNO | 9,822.74 |
| TAANN | 23,204.10 |
| ORIENT | 35,281.76 |
| APOLLO | 30,320.33 |
| CARLSBG | 89,405.96 |
| SUNWAY | 28,215.60 |
| LPI | 77,378.36 |
| FM | 3,011.90 |
| WPRTS | 28,415.86 |
| GASMSIA | 23,454.42 |

---

#### Row 11 — Dividend Per Share (MYR) — Total Annual
**Formula:** `=SUM(B12:B19)`

Aggregates up to 8 individual dividend payments entered in rows 12–19.

| Stock | Div/Share (MYR) |
|-------|----------------|
| CIMB | 0.4675 |
| MAYBANK | 0.6200 |
| RHBBANK | 0.4300 |
| AMBANK | 0.3020 |
| AEONCR | 0.2750 |
| TIMECOM | 0.5951 |
| INNO | 0.1900 |
| TAANN | 0.3000 |
| ORIENT | 0.4000 |
| APOLLO | 0.3500 |
| CARLSBG | 1.0300 |
| SUNWAY | 0.0800 |
| LPI | 0.8000 |
| FM | 0.0450 |
| WPRTS | 0.2079 |
| GASMSIA | 0.2588 |

---

#### Rows 12–19 — Individual Dividend Payments (Per Share, MYR)
**Values:** Manually entered dividend per share for each declared payout.

Up to 8 payments labelled 1st through 8th. Stocks with fewer than 8 payments leave the remaining rows blank.

| Payout | CIMB | MAYBANK | RHBBANK | AMBANK | AEONCR | TIMECOM | INNO | TAANN | ORIENT | APOLLO | CARLSBG | SUNWAY | LPI | FM | WPRTS | GASMSIA |
|--------|------|---------|---------|--------|--------|---------|------|-------|--------|--------|---------|--------|-----|----|-------|---------|
| 1st | 0.2000 | 0.3200 | 0.2800 | 0.1030 | 0.1450 | 0.2745 | 0.0650 | 0.1000 | 0.2000 | 0.1500 | 0.3500 | 0.0400 | 0.3000 | 0.0150 | 0.0993 | 0.0600 |
| 2nd | 0.1975 | 0.3000 | 0.1500 | 0.1990 | 0.1300 | 0.1042 | 0.0250 | 0.1000 | 0.2000 | 0.2000 | 0.2500 | 0.0400 | 0.5000 | 0.0100 | 0.1086 | 0.0960 |
| 3rd | 0.0700 | — | — | — | — | 0.2164 | 0.0350 | 0.1000 | — | — | 0.2000 | — | — | 0.0200 | — | 0.1028 |
| 4th | — | — | — | — | — | — | 0.0650 | — | — | — | 0.2300 | — | — | — | — | — |
| 5th–8th | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |

---

#### Row 20 — "PROFIT" Section Header
Label only. No formula.

---

#### Rows 21–28 — Dividend Profit per Payout (MYR)
**Formula (rows 21–27):** `=IF(B12="","", IF(B$1<>"", B$1*B12, $A$1*B12))`

Each row multiplies the corresponding dividend per share (rows 12–19) by the share count, yielding the actual cash dividend received for that tranche.

- If row 12 is blank (no dividend declared) → blank.
- If per-stock override count in row 1 → use that; else use global A1 (5,000).

**⚠ Bug — Row 28 (8th Payout):**  
The formula for all stocks in row 28 reads:
```
=IF(B19="","", IF(B$1<>"", B$1*B12, $A$1*B19))
```
The true-branch references `B12` (1st dividend) instead of `B19` (8th dividend). It should be `B$1*B19`.  
**Current impact:** None — because B1:Q1 are all blank, the true-branch is never executed and the calculation falls through to `$A$1*B19` which is correct. However, if a per-stock share-count override is ever added to row 1, the 8th payout will silently calculate the wrong amount. **Recommend fixing to `$A$1*B19` → `B$1*B19`** across all stock columns in row 28.

Computed dividend profits:

| Payout | CIMB | MAYBANK | RHBBANK | AMBANK | AEONCR | TIMECOM | INNO | TAANN | ORIENT | APOLLO | CARLSBG | SUNWAY | LPI | FM | WPRTS | GASMSIA |
|--------|------|---------|---------|--------|--------|---------|------|-------|--------|--------|---------|--------|-----|----|-------|---------|
| 1st | 1,000 | 1,600 | 1,400 | 515 | 725 | 1,372.50 | 325 | 500 | 1,000 | 750 | 1,750 | 200 | 1,500 | 75 | 496.50 | 300 |
| 2nd | 987.50 | 1,500 | 750 | 995 | 650 | 521 | 125 | 500 | 1,000 | 1,000 | 1,250 | 200 | 2,500 | 50 | 543 | 480 |
| 3rd | 350 | — | — | — | — | 1,082 | 175 | 500 | — | — | 1,000 | — | — | 100 | — | 514 |
| 4th | — | — | — | — | — | — | 325 | — | — | — | 1,150 | — | — | — | — | — |
| 5th–8th | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |

---

#### Row 30 — Total Dividend Profit (MYR)
**Formula:** `=SUM(B21:B28)`

Sum of all dividend cash receipts across all payment tranches.

| Stock | Total Dividend (MYR) |
|-------|---------------------|
| CIMB | 2,337.50 |
| MAYBANK | 3,100.00 |
| RHBBANK | 2,150.00 |
| AMBANK | 1,510.00 |
| AEONCR | 1,375.00 |
| TIMECOM | 2,975.50 |
| INNO | 950.00 |
| TAANN | 1,500.00 |
| ORIENT | 2,000.00 |
| APOLLO | 1,750.00 |
| CARLSBG | 5,150.00 |
| SUNWAY | 400.00 |
| LPI | 4,000.00 |
| FM | 225.00 |
| WPRTS | 1,039.50 |
| GASMSIA | 1,294.00 |

---

#### Row 31 — ROI (Dividend Yield)
**Formula:** `=IFERROR(B30/B6, "")`

Dividend yield = Total Dividend Profit ÷ **Initial purchase amount (row 6)**.

> Note: The denominator is row 6 (pre-fee cost), not row 10 (all-in cost). This slightly overstates the yield because transaction fees are excluded from the cost base. The true yield against all-in cost would be `B30/B10`.

| Stock | ROI (%) |
|-------|---------|
| CIMB | 5.58% |
| MAYBANK | 5.19% |
| RHBBANK | 5.32% |
| AMBANK | 4.97% |
| AEONCR | 4.74% |
| TIMECOM | 9.95% |
| INNO | 9.69% |
| TAANN | 6.48% |
| ORIENT | 5.68% |
| APOLLO | 5.79% |
| CARLSBG | 5.77% |
| SUNWAY | 1.42% |
| LPI | 5.18% |
| FM | 7.50% |
| WPRTS | 3.67% |
| GASMSIA | 5.53% |

> ROI values in the spreadsheet are stored as decimals (e.g., 0.0558); the percentages above are derived by × 100.

---

## 5. Calculator Panel (Columns S–Y)

The Calculator is a self-contained tool for evaluating a BUY position and simulating SELL outcomes at multiple price points, for **one stock at a time**.

### 5.1 Input Cells

| Cell | Label | Current Value | Purpose |
|------|-------|---------------|---------|
| **T4** | Share Name | `CIMB 1023` | User types a stock name matching row 3 — drives the HLOOKUP |
| **T6** | Number of Shares | `5,000` | Shares to buy/sell in this scenario |
| **U5** | Price Adjuster | *(blank)* | Optional: subtract this from the looked-up price (e.g., to model a discounted entry price) |

### 5.2 Share Price Lookup (T5)
```
=IF($T$4="","*Input Share*",
   IF($U$5="",
      HLOOKUP($T$4,$B$3:$Q$5,3,FALSE),
      HLOOKUP($T$4,$B$3:$Q$5,3,FALSE)-$U$5
   )
)
```
Looks up the current share price from row 5 using the name in T4. Subtracts the Price Adjuster (U5) if one is entered.

### 5.3 BUY Section (Rows 9–11)

| Row | Col S | Col T | Col U | Col V | Col W | Col X |
|-----|-------|-------|-------|-------|-------|-------|
| 9 | "BUY" | — | — | — | — | — |
| 10 | "Share Price" | "Total Amount" | "Brokerage Fee" | "Clearing Fee" | "Stamp Duty" | "FINAL AMOUNT" |
| 11 | Price | Total Amount | Brokerage Fee | Clearing Fee | Stamp Duty | All-In Cost |

**Row 11 formulas:**

| Cell | Formula | Description |
|------|---------|-------------|
| S11 | `=IF($T$4="","",IF($T$6="","",$T$5))` | Echoes the looked-up share price |
| T11 | `=IF($T$4="","",$T$7)` | Total amount = T5 × T6 (via T7) |
| U11 | `=IFERROR(IF($T11="","",IF($T11*0.1%<8,8,$T11*0.1%)),"")` | Brokerage 0.1%, min 8 |
| V11 | `=IFERROR(IF($T11="","",$T11*0.03%),"")` | Clearing 0.03% |
| W11 | `=IFERROR(IF($T11="","",IF($T11>=1000,ROUNDUP($T11/1000,0),1)),"")` | Stamp Duty |
| X11 | `=IF($T11="","",SUM(T11:W11))` | All-in buy cost |

**Current BUY result (CIMB 1023, 5,000 shares):**

| | Value (MYR) |
|-|------------|
| Share Price | 8.38 |
| Total Amount | 41,900.00 |
| Brokerage Fee | 41.90 |
| Clearing Fee | 12.57 |
| Stamp Duty | 42.00 |
| **FINAL AMOUNT (all-in)** | **41,996.47** |

### 5.4 SELL Section (Rows 13–50)

| Row | Col S | Col T | Col U | Col V | Col W | Col X | Col Y |
|-----|-------|-------|-------|-------|-------|-------|-------|
| 13 | "SELL" | — | — | — | — | — | — |
| 14 | "Share Price" | "Total Amount" | "Brokerage Fee" | "Clearing Fee" | "Stamp Duty" | "FINAL AMOUNT" | "PROFIT/LOSS" |
| 15–50 | Price scenarios | Calculated | Calculated | Calculated | Calculated | Calculated | Calculated |

**Sell price scenarios (column S, rows 15–50):**

Rows 15–19 step by **+0.01** per row (fine-grained near the current price).  
Rows 20–32+ step by **+0.05** per row (broader view).

| Row | S formula | Price at CIMB 8.38 |
|-----|-----------|-------------------|
| 15 | `=$T$5+0.01` | 8.39 |
| 16 | `=$T$5+0.02` | 8.40 |
| 17 | `=$T$5+0.03` | 8.41 |
| 18 | `=$T$5+0.04` | 8.42 |
| 19 | `=$T$5+0.05` | 8.43 |
| 20 | `=$T$5+0.10` | 8.48 |
| 21 | `=$T$5+0.15` | 8.53 |
| 22 | `=$T$5+0.20` | 8.58 |
| ... | ... | ... |
| 32 | `=$T$5+0.70` | 9.08 |

**Array formulas (entered in T15:Y15, spill to T15:Y50):**

| Col | Formula | Description |
|-----|---------|-------------|
| T | `=IF($S$15:$S50="","",IF($T$6="","",$S$15:$S50*$T$6))` | Gross sell proceeds = price × shares |
| U | `=IFERROR(IF($T$15:$T50="","",IF($T$15:$T50*0.1%<8,8,$T$15:$T50*0.1%)),"")` | Brokerage 0.1%, min 8 |
| V | `=IFERROR(IF($T$15:$T50="","",$T$15:$T50*0.03%),"")` | Clearing 0.03% |
| W | `=IFERROR(IF($T$15:$T50="","",IF($T$15:$T50>=1000,ROUNDUP($T$15:$T50/1000,0),1)),"")` | Stamp Duty |
| X | `=IF($T$15:$T50="","",$T$15:$T50-($U$15:$U50+$V$15:$V50+$W$15:$W50))` | Net sell proceeds (after fees) |
| Y | `=IF($T$15:$T50="","",$X$15:$X50-$X$11)` | **Profit/Loss** = Net proceeds − BUY all-in cost (X11) |

**Current SELL analysis (CIMB 1023, 5,000 shares, bought at 41,996.47 all-in):**

| Sell Price | Net Proceeds (MYR) | Profit/Loss (MYR) |
|------------|-------------------|-------------------|
| 8.39 | 41,853.47 | **−143.01** |
| 8.40 | 41,903.40 | **−93.07** |
| 8.41 | 41,952.34 | **−44.14** |
| **8.42** | **42,002.27** | **+5.80** ← Break-even |
| 8.43 | 42,052.21 | +55.74 |
| 8.48 | 42,301.88 | +305.41 |
| 8.53 | 42,551.56 | +555.08 |
| 8.58 | 42,801.23 | +804.76 |
| 8.63 | 43,049.91 | +1,053.43 |
| 8.68 | 43,299.58 | +1,303.11 |
| 8.73 | 43,549.26 | +1,552.78 |
| 8.78 | 43,798.93 | +1,802.46 |
| 8.83 | 44,047.61 | +2,051.13 |
| 8.88 | 44,297.28 | +2,300.81 |
| 8.93 | 44,546.96 | +2,550.49 |
| 8.98 | 44,796.63 | +2,800.16 |
| 9.03 | 45,045.31 | +3,048.83 |
| 9.08 | 45,294.98 | +3,298.51 |

> **Break-even sell price for CIMB:** ~MYR 8.42 (purchased at 8.38 — requires only a +0.04 move to cover all transaction fees).

---

## 6. Note in Cell S2

> *"It takes 2 Trading Days after I SELL Shares to receive the money"*

Reminder that settlement on Bursa is T+2 (trade date plus two business days).

---

## 7. Identified Issues

### 7.1 Bug — Row 28 (8th Payout) Formula

**Affected cells:** B28, C28, D28, E28, F28, G28, H28, I28, J28, K28, L28, M28, N28, O28, P28, Q28

**Current formula (e.g., B28):**
```excel
=IF(B19="","", IF(B$1<>"", B$1*B12, $A$1*B19))
```

**Correct formula should be:**
```excel
=IF(B19="","", IF(B$1<>"", B$1*B19, $A$1*B19))
```

The true-branch (`B$1*B12`) multiplies the per-stock share count by the **1st dividend** (B12) instead of the **8th dividend** (B19). The false-branch (`$A$1*B19`) is correct.

**Current status:** Dormant — since all of row 1 (B1:Q1) is blank, the true-branch is never taken, and the calculation is correct. However, this will silently compute wrong values if a per-stock override is ever added.

### 7.2 ROI Denominator — Pre-Fee vs. All-In Cost

Row 31 divides by the pre-fee initial amount (row 6) rather than the total all-in cost (row 10). The true yield is marginally lower:

| Stock | ROI vs. Initial | ROI vs. All-In |
|-------|----------------|----------------|
| CIMB | 5.58% | 5.57% |
| CARLSBG | 5.77% | 5.76% |

The difference is small (a few basis points) but worth noting for precision.

### 7.3 SELL Break-Even Excludes Buy Fees

The SELL Profit/Loss column (Y) compares net SELL proceeds (after sell fees) against the **BUY all-in cost** (X11, which includes buy fees). This is **correct** — total round-trip profit accounting is accurate.

---

## 8. Formula Dependency Summary

```
A1 (global shares)
│
├─► B1:Q1 (per-stock overrides, currently blank)
│       │
│       └─► Row 6 (Initial Amount) = shares × price
│               │
│               ├─► Row 7 (Brokerage 0.1%, min 8)
│               ├─► Row 8 (Clearing 0.03%)
│               ├─► Row 9 (Stamp Duty RM1/1000)
│               └─► Row 10 (All-In Cost = R6+R7+R8+R9)
│
├─► Rows 12–19 (dividend per share, manual entry)
│       │
│       └─► Row 11 (Total div/share = SUM R12:R19)
│               │
│               └─► Rows 21–28 (payout = shares × div/share)
│                       │
│                       └─► Row 30 (Total Dividend = SUM R21:R28)
│                               │
│                               └─► Row 31 (ROI = R30 / R6)
│
└─► Calculator Panel (S–Y)
        │
        ├─► T4 (stock name) → T5 (HLOOKUP price from B3:Q5)
        ├─► T6 (shares) → T7 (amount = T5×T6)
        ├─► U5 (price adjuster, optional)
        ├─► Row 11 S-X (BUY cost breakdown)
        └─► Rows 15–50 S-Y (SELL scenarios via array formulas)
                Y = Net SELL proceeds − X11 (all-in buy cost)
```

---

## 9. Summary Statistics

| Metric | Value |
|--------|-------|
| Stocks tracked | 16 |
| Default shares per stock | 5,000 |
| Total portfolio initial cost | MYR 582,250 |
| Total all-in buy cost | MYR 584,563 (approx.) |
| Total annual dividend income | MYR 34,856 |
| Highest dividend yield | TIMECOM 9.95% |
| Lowest dividend yield | SUNWAY 1.42% |
| Portfolio average yield | ~5.43% |
| CIMB break-even sell price | MYR 8.42 (buy: 8.38) |

---

## 10. Fee Verification — Cross-Check Against Official Bursa Rates & Broker Schedules

> Sources: EY Malaysia Tax Alert (17 Jul 2023), Bursa Malaysia official fee schedule, i3investor, NST, Dividend Magic broker comparison (updated 2025), traders.my (updated Feb 2026).

---

### 10.1 Clearing Fee — 0.03%

| | Spreadsheet | Official Rate | Verdict |
|---|---|---|---|
| Rate | 0.03% of contract value | 0.03% of contract value | ✅ **CORRECT** |
| Cap | Not capped in formula | RM1,000 per contract | ✅ Not relevant (max in portfolio: RM26.76 for CARLSBG) |
| Applied on | BUY only (main table) + BUY & SELL (Calculator) | Both BUY and SELL | ✅ Calculator handles both correctly |

The clearing fee is charged by Bursa Malaysia Securities Clearing (BMSC) and is a mandatory regulatory charge uniform across all brokers. **The 0.03% rate is confirmed correct.**

---

### 10.2 Stamp Duty — RM1 per RM1,000 (0.10%), rounded up

**Rate history (important context):**

| Period | Rate | Cap |
|--------|------|-----|
| Before 1 Jan 2022 | 0.10% | RM200 per contract |
| 1 Jan 2022 – 12 Jul 2023 | **0.15%** | RM1,000 per contract |
| **13 Jul 2023 – 12 Jul 2028** | **0.10%** | RM1,000 per contract |

The current rate of **0.10% (RM1 per RM1,000)** was gazetted via *Stamp Duty (Remission) (No. 3) Order 2023 [P.U.(A) 208]* on 12 July 2023, confirmed by EY Malaysia's official tax alert.

| | Spreadsheet | Official Rate | Verdict |
|---|---|---|---|
| Rate | RM1 per RM1,000 rounded up = 0.10% | 0.10% (RM1 per RM1,000) | ✅ **CORRECT** |
| Rounding method | `ROUNDUP(amount/1000, 0)` — rounds up to nearest RM1 | Charged per RM1,000 or part thereof | ✅ **CORRECT** |
| Cap at RM1,000 | Not in formula | RM1,000 per contract | ✅ Not relevant (max in portfolio: RM90 for CARLSBG) |
| Applied on | BUY only (main table) + BUY & SELL (Calculator) | Both BUY and SELL | ✅ Calculator handles both correctly |

> ⚠️ **Expiry note:** The 0.10% remission is valid until **12 July 2028**. After that date it may revert to 0.15% unless the government extends it. Worth revisiting then.

> ⚠️ **traders.my discrepancy:** The traders.my fee comparison site (updated Feb 2026) incorrectly lists stamp duty as 0.15% for both M+ and Rakuten Trade. Based on the official gazette and EY Malaysia's tax alert, the correct current rate is 0.10%. The spreadsheet is right.

---

### 10.3 Brokerage Fee — 0.10%, minimum RM8

Brokerage is **not a fixed regulatory charge** — it varies by broker. The spreadsheet uses 0.10% with a minimum of RM8, which is a common traditional rate. Here is how it compares across major platforms:

| Broker | Rate | Minimum | Notes |
|--------|------|---------|-------|
| **MooMoo** | RM0 commission | RM3 platform fee per order | Flat RM3 per order regardless of size. Cheapest for large trades. |
| **Rakuten Trade** | 0% for RM0–RM100; RM2.88 flat for RM100–RM9,999; 0.10% for RM10K–RM100K; RM100 flat above RM100K | RM2.88 | Capped at RM100 for very large trades. Cheaper than spreadsheet for trades under RM10K. |
| **M+ Online (Malacca Securities)** | 0.08% for under RM50K; 0.05% above RM50K | RM8 | Lower rate than spreadsheet for normal trade sizes. |
| **Affin Hwang** | RM5 flat under RM10K; 0.08% for RM10K–RM100K; 0.05% above RM100K | RM5 | |
| **AM Equities** | 0.05% | RM8 | Lower rate. |
| **CGS-CIMB iTrade** | 0.42% | RM28 | Much higher — traditional full-service rate. |
| **CGS-CIMB Clicks** | 0.0388% | RM8.88 | Online arm of CIMB, lower than iTrade. |
| **Kenanga Trade** | 0.42% below RM100K; 0.21% above RM100K | RM28 | Full-service rate. |
| **TA Securities** | 0.12% | RM10 | |
| **Hong Leong (HLeBroking)** | 0.10% | RM8 | Matches spreadsheet exactly. |
| **Maybank Investment** | 0.10% | RM8 | Matches spreadsheet exactly. |

**Verdict on the spreadsheet's 0.10% / RM8 minimum:**

✅ Accurately represents the rate at **Hong Leong** and **Maybank Investment**.  
⚠️ **Overstates** brokerage if using MooMoo (RM3 flat), Rakuten Trade (RM2.88 flat for under RM10K), M+ (0.08%), or AM Equities (0.05%).  
✅ **Understates** brokerage if using traditional brokers like Kenanga or CGS iTrade (0.42%).

For the position sizes in the spreadsheet (mostly RM29,000–RM89,000 per stock), here is what the brokerage fee actually works out to under each platform:

| Stock | Initial Amount | Spreadsheet (0.10%, min RM8) | MooMoo (RM3) | Rakuten (0.10%) | M+ (0.08%) |
|-------|---------------|------------------------------|--------------|-----------------|------------|
| CIMB | RM41,900 | RM41.90 | RM3.00 | RM41.90 | RM33.52 |
| MAYBANK | RM59,700 | RM59.70 | RM3.00 | RM59.70 | RM47.76 |
| CARLSBG | RM89,200 | RM89.20 | RM3.00 | RM89.20 | RM71.36 |
| FM | RM3,000 | **RM8.00** (min applied) | RM3.00 | **RM2.88** (flat) | **RM8.00** (min applied) |

**Recommendation:** If you are using MooMoo or Rakuten Trade, the brokerage figures in the spreadsheet are **overstated**. Consider updating cell A1's brokerage logic or adding a broker-specific rate input cell to make the cost calculation more accurate for your actual broker.

---

### 10.4 Sales and Services Tax (SST) on Brokerage

| | Spreadsheet | Official Rule | Verdict |
|---|---|---|---|
| SST on brokerage | Not applied | **Exempt** for Bursa equity share trading | ✅ **CORRECT** |

Brokerage fees for the trading of listed shares on Bursa Malaysia are **exempt from SST**, confirmed by Bursa Malaysia's own FAQ and reported by NST and i3investor. The spreadsheet correctly excludes SST. (Note: some of Bursa's own administrative services attract 8% SST, but retail brokerage commissions do not.)

---

### 10.5 Settlement Period Note (Cell S2)

| | Spreadsheet | Official Rule | Verdict |
|---|---|---|---|
| Settlement | "2 Trading Days" | T+2 (trade date + 2 business days) | ✅ **CORRECT** |

Bursa Malaysia equity market operates on a T+2 settlement cycle. Cash from a sell trade is available on the second business day after the trade date.

---

### 10.6 Overall Fee Verification Summary

| Fee | Spreadsheet Value | Correct Value | Status |
|-----|-------------------|---------------|--------|
| Clearing fee | 0.03% | 0.03% (max RM1,000) | ✅ Correct |
| Stamp duty rate | RM1/RM1,000 = 0.10% | 0.10% until 12 Jul 2028 | ✅ Correct |
| Stamp duty rounding | ROUNDUP to nearest RM1 | Per RM1,000 or part thereof | ✅ Correct |
| Stamp duty cap | Not in formula | RM1,000 per contract | ✅ Immaterial at current position sizes |
| Brokerage rate | 0.10% | Varies by broker (0.05%–0.42%) | ⚠️ Matches Hong Leong / Maybank only |
| Brokerage minimum | RM8 | Varies (RM2.88–RM28) | ⚠️ Matches Hong Leong / Maybank only |
| SST on brokerage | Not applied | Exempt | ✅ Correct |
| Settlement period | T+2 | T+2 | ✅ Correct |
| Fees on BUY | ✅ Included | Required | ✅ Correct |
| Fees on SELL | ✅ Included (Calculator) | Required | ✅ Correct |

**Bottom line:** The clearing fee and stamp duty are both correctly implemented. The only area to revisit is the brokerage rate — update it to match your actual broker to get accurate cost calculations. If you use MooMoo (RM3 flat), the current formula significantly overstates your brokerage cost on every trade.
