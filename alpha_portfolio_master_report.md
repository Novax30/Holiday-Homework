# WorldQuant BRAIN: Active Portfolio Master Report

**User Account**: `xstreamnova@gmail.com` (Bronze Tier)  
**Date**: November 12, 2026 (Server Date)  
**Status**: **4 of 4 Daily Submissions Completed (Daily Cap Reached)**  
**Active Portfolio Size**: 7 Total Out-of-Sample (OS) Alphas  

---

## 1. Today's Completed Submissions (4/4 Max Daily Limit)

| # | Alpha ID | Factor Archetype | Expression | Decay | Trunc | Sharpe | Turn | Margin | Sub-Univ Sharpe | Grade | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **`A1xMbvjX`** | Operating Earnings Yield | `ts_rank(ts_backfill(operating_income / cap, 65), 252)` | 2 | 0.08 | 1.41 | 10.81% | 12.9 bps | 1.34 | Good | **ACTIVE (OS)** |
| 2 | **`MP6o0J1k`** | Operating Cash Flow Yield | `ts_rank(ts_backfill(cashflow_op / cap, 65), 252)` | 1 | 0.08 | 1.45 | 14.10% | 9.8 bps | 1.48 | Good | **ACTIVE (OS)** |
| 3 | **`E5QXxAQK`** | Financial Leverage + Reversal | `rank(ts_backfill(liabilities / assets, 65)) - rank(close - ts_mean(close, 5))` | 10 | 0.05 | 2.20 | 18.15% | 15.6 bps | 1.55 | **EXCELLENT** | **ACTIVE (OS)** |
| 4 | **`d5aAvx1w`** | IV Call Term Structure | `quantile(ts_mean(ts_backfill(implied_volatility_call_60 / implied_volatility_call_30, 5), 30), driver = gaussian)` | 8 | 0.05 | 1.64 | 7.70% | 17.1 bps | 0.73 | Good | **ACTIVE (OS)** |

---

## 2. Complete Active Portfolio Book (7 Live Alphas)

| # | Alpha ID | Submission Timestamp | Core Economic Driver | In-Sample Sharpe | Turnover | Trading Margin | Status |
|---|---|---|---|---|---|---|---|
| 1 | **`d5aAvx1w`** | 2026-11-12 17:29:59 EST | 60d/30d Call IV Slope (Expectation Premium) | **1.64** | **7.70%** | **17.1 bps** | `OS (ACTIVE)` |
| 2 | **`E5QXxAQK`** | 2026-11-12 17:26:39 EST | Balance Sheet Leverage + 5-Day Reversal | **2.20** | **18.15%** | **15.6 bps** | `OS (ACTIVE)` |
| 3 | **`MP6o0J1k`** | 2026-11-12 15:35:02 EST | Cash Flow Yield (Accrual-Free Liquidity) | **1.45** | **14.10%** | **9.8 bps** | `OS (ACTIVE)` |
| 4 | **`A1xMbvjX`** | 2026-11-12 09:24:02 EST | Operating Income Yield (Core Profitability) | **1.41** | **10.81%** | **12.9 bps** | `OS (ACTIVE)` |
| 5 | **`gJaJzaqv`** | 2026-11-10 12:41:07 EST | Volume Dispersion * Intraday Spread | **1.70** | **13.65%** | **39.1 bps** | `OS (ACTIVE)` |
| 6 | **`VkxeMkV5`** | 2026-11-10 11:48:03 EST | 30d Call-Put IV Skew (Hedging Demand) | **1.62** | **9.88%** | **12.6 bps** | `OS (ACTIVE)` |
| 7 | **`3qokPe5Z`** | 2026-11-06 13:15:12 EST | Parkinson Intraday Volatility Contraction | **1.68** | **10.34%** | **76.5 bps** | `OS (ACTIVE)` |

---

## 3. Compliance and Base Payment Checklist

* **Daily Submission Cap**: 4 / 4 achieved (strictly halted to avoid quota errors).
* **Pairwise Self-Correlation**: All pairwise correlations $< 0.70$ against all active account alphas.
* **Checks Status**: 0 Check Fails across all submissions.
* **Turnover**: $7.7\% - 18.2\%$ (well under the conservative $25\%$ limit).
* **Trading Margin**: $9.8\text{ bps} - 76.5\text{ bps}$ (all well above $4.0\text{ bps}$ platform requirement).
* **Decay**: Controlled within $\le 10$ days.
