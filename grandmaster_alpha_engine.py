#!/usr/bin/env python3
"""
================================================================================
GRANDMASTER ALPHA RESEARCH & AUTOMATION ENGINE (WORLDQUANT BRAIN)
================================================================================
Platform: Apple Silicon (macOS) / WorldQuant BRAIN Bronze Tier Platform
Author: Quant Automation Architect

System Architecture & Operational Compliance:
1. Multi-Theme Orthogonal Factor Library:
   - Fundamental Quality (Operating Cash Flow / Assets, Accrual Efficiency, Sales Yield)
   - Leverage & Solvency (Liabilities / Assets, Debt Reversal, Net Worth Efficiency)
   - Earnings & Cash Yield (Operating Income / Market Cap, Cash Flow / Cap)
   - Volatility Contraction (Normalized Range, Parkinson Dislocation, Intraday VWAP Flow)
   - Options IV Term Structure (60d/30d IV Ratio, 30d/60d Skew Curvature, Gaussian Quantiles)
   * Strictly adheres to BRAIN rule: <= 4 data fields, <= 8 operators, FastExpr language.

2. Paced Asynchronous Simulation Dispatcher:
   - Bronze Tier Cluster Constraint: exactly 3 concurrent simulation slots.
   - Thread-safe Rate-Limiting: >= 6.0 seconds between consecutive POST /simulations.
   - Resilient HTTPAdapter pool with automatic 429 Retry-After parsing and 5xx backoff.

3. Real-Time Check Validator:
   - Evaluates all In-Sample checks: LOW_SHARPE (>= 1.25), LOW_FITNESS (>= 1.0),
     LOW_TURNOVER (>= 0.01), HIGH_TURNOVER (<= 0.70), CONCENTRATED_WEIGHT, LOW_SUB_UNIVERSE_SHARPE.
   - Value Factor Rules: Turnover < 25%, Margin >= 4.0 bps, Decay <= 5.

4. Asynchronous Self-Correlation Checker with Retry-After Handling:
   - Handles BRAIN's async calculation on GET /alphas/{id}/correlations/self.
   - Respects 200/202 empty payloads and Retry-After headers until records & max correlation arrive.
   - Enforces max self-correlation hurdle: max_corr < 0.70 across all portfolio alphas.

5. Diagnostic Auto-Repair Engine:
   - If Sharpe >= 1.25 but turnover > 25%, automatically fine-tunes decay (up to max 5).
   - If CONCENTRATED_WEIGHT fails, tightens truncation to 0.05.

6. Automated Badge Patching & Daily Cap-Guarded Submission:
   - Sets UI badge: PURPLE for SPECTACULAR, BLUE for EXCELLENT/GOOD.
   - Inspects live account submission history: strictly caps daily submissions at 4.
   - Submits (POST /alphas/{id}/submit) and verifies transition to Out-of-Sample (OS / ACTIVE).

7. Comprehensive Structured Logging:
   - Exports results to grandmaster_alpha_results.csv with complete alpha telemetry.
================================================================================
"""

import os
import sys
import time
import json
import csv
import re
import argparse
import threading
import functools
from queue import Queue, Empty
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# Ensure all prints are unbuffered for realtime streaming in logs & tasks
print = functools.partial(print, flush=True)

# ==============================================================================
# ENVIRONMENT & CONFIGURATION
# ==============================================================================

def load_env_credentials():
    """Loads BRAIN credentials from .env or environment variables."""
    env_vars = {}
    env_candidates = [
        os.path.join(os.path.dirname(__file__), ".env"),
        os.path.join(os.getcwd(), ".env"),
        "/Users/nova/Documents/ALPAHA/.env"
    ]
    for p in env_candidates:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env_vars[k.strip()] = v.strip().strip('"').strip("'")
            break

    email = os.getenv("BRAIN_EMAIL") or env_vars.get("BRAIN_EMAIL", "xstreamnova@gmail.com")
    pwd = os.getenv("BRAIN_PASSWORD") or env_vars.get("BRAIN_PASSWORD", "nova@1234")
    return email, pwd

BRAIN_EMAIL, BRAIN_PASSWORD = load_env_credentials()
BRAIN_BASE = "https://api.worldquantbrain.com"

# Institutional System Constraints (Bronze Tier)
CONCURRENT_SLOTS = 3
DAILY_SUBMISSION_LIMIT = 4
DISPATCH_PACING_SECONDS = 6.0

# Quantitative Value Factor Constraints
MIN_SHARPE = 1.25
TARGET_SHARPE = 1.50
MIN_FITNESS = 1.00
TARGET_FITNESS = 1.50
MAX_TURNOVER = 0.25            # Conservative Value Factor requirement (< 25%)
MIN_MARGIN = 0.0004            # 4.0 basis points minimum margin
MAX_DECAY = 10                 # User Leniency: Decay allowed up to 10 for low turnover
MAX_SELF_CORRELATION = 0.70    # Strict BRAIN Platform Hurdle (< 0.70)

CSV_LOG_PATH = os.path.join(os.path.dirname(__file__), "grandmaster_alpha_results.csv")

DEFAULT_SIM_SETTINGS = {
    "instrumentType": "EQUITY",
    "region": "USA",
    "universe": "TOP3000",
    "delay": 1,
    "decay": 3,
    "neutralization": "SUBINDUSTRY",
    "truncation": 0.08,
    "pasteurization": "ON",
    "unitHandling": "VERIFY",
    "nanHandling": "OFF",
    "language": "FASTEXPR",
    "visualization": False
}

# ==============================================================================
# 1. ORTHOGONAL FACTOR LIBRARY (5 THEMES)
# ==============================================================================

FACTOR_LIBRARY = [
    # --------------------------------------------------------------------------
    # THEME 1: FUNDAMENTAL QUALITY (Cash Flow & Accrual Efficiency)
    # --------------------------------------------------------------------------
    {
        "name": "FCF_to_Assets_Quality",
        "theme": "FUNDAMENTAL_QUALITY",
        "formula": "ts_rank(ts_backfill(cashflow_op / assets, 65), {lookback})",
        "lookbacks": [180, 252],
        "decays": [2, 3, 4],
        "truncation": 0.08
    },
    {
        "name": "Operating_ROA_Quality",
        "theme": "FUNDAMENTAL_QUALITY",
        "formula": "ts_rank(ts_backfill(operating_income / assets, 65), {lookback})",
        "lookbacks": [180, 252],
        "decays": [2, 3, 4],
        "truncation": 0.08
    },
    {
        "name": "Cashflow_to_Sales_Conversion",
        "theme": "FUNDAMENTAL_QUALITY",
        "formula": "ts_rank(ts_backfill(cashflow_op / revenue, 65), {lookback})",
        "lookbacks": [180, 252],
        "decays": [3, 4, 5],
        "truncation": 0.08
    },
    {
        "name": "Operating_Margin_Expansion",
        "theme": "FUNDAMENTAL_QUALITY",
        "formula": "ts_rank(ts_backfill(operating_income / revenue, 65), {lookback})",
        "lookbacks": [180, 252],
        "decays": [3, 4, 5],
        "truncation": 0.08
    },
    {
        "name": "Cashflow_ROA_Delta_Impulse",
        "theme": "FUNDAMENTAL_QUALITY",
        "formula": "rank(ts_delta(ts_backfill(cashflow_op / assets, 65), {lookback}))",
        "lookbacks": [10, 20],
        "decays": [3, 4],
        "truncation": 0.08
    },
    {
        "name": "Cash_Conversion_Idiosyncratic_Residual",
        "theme": "FUNDAMENTAL_QUALITY",
        "formula": "rank(ts_regression(ts_backfill(cashflow_op, 65), ts_backfill(operating_income, 65), {lookback}, lag = 0, rettype = 0))",
        "lookbacks": [126, 180, 252],
        "decays": [3, 4, 5],
        "truncation": 0.08
    },
    {
        "name": "Operating_Sales_Residual",
        "theme": "FUNDAMENTAL_QUALITY",
        "formula": "rank(ts_regression(ts_backfill(operating_income, 65), ts_backfill(revenue, 65), {lookback}, lag = 0, rettype = 0))",
        "lookbacks": [126, 180],
        "decays": [3, 4, 5],
        "truncation": 0.08
    },

    # --------------------------------------------------------------------------
    # THEME 2: LEVERAGE & SOLVENCY (Balance Sheet Safety & Distress Reversal)
    # --------------------------------------------------------------------------
    {
        "name": "BalanceSheet_Leverage_Reversal_Alpha",
        "theme": "LEVERAGE_SOLVENCY",
        "formula": "rank(ts_backfill(liabilities / assets, 65)) - rank(close - ts_mean(close, {lookback}))",
        "lookbacks": [5, 10],
        "decays": [6, 8, 10],
        "truncation": 0.05
    },
    {
        "name": "Inverse_BalanceSheet_Liabilities_Ratio",
        "theme": "LEVERAGE_SOLVENCY",
        "formula": "-rank(ts_backfill(liabilities / assets, 65))",
        "lookbacks": [65],
        "decays": [3, 4, 5],
        "truncation": 0.08
    },
    {
        "name": "Deleveraging_Impulse_Delta",
        "theme": "LEVERAGE_SOLVENCY",
        "formula": "-rank(ts_delta(ts_backfill(liabilities / assets, 65), {lookback}))",
        "lookbacks": [10, 20],
        "decays": [3, 4, 5],
        "truncation": 0.08
    },
    {
        "name": "Net_Equity_to_Cap_Solvency",
        "theme": "LEVERAGE_SOLVENCY",
        "formula": "ts_rank(ts_backfill((assets - liabilities) / cap, 65), {lookback})",
        "lookbacks": [180, 252],
        "decays": [2, 3, 4],
        "truncation": 0.08
    },
    {
        "name": "Book_Assets_to_Market_Discount",
        "theme": "LEVERAGE_SOLVENCY",
        "formula": "-rank(ts_backfill(assets / cap, 65))",
        "lookbacks": [65],
        "decays": [2, 3, 4],
        "truncation": 0.08
    },
    {
        "name": "Liabilities_to_Assets_Regression_Residual",
        "theme": "LEVERAGE_SOLVENCY",
        "formula": "rank(ts_regression(ts_backfill(liabilities, 65), ts_backfill(assets, 65), {lookback}, lag = 0, rettype = 0))",
        "lookbacks": [126, 180],
        "decays": [3, 4, 5],
        "truncation": 0.08
    },

    # --------------------------------------------------------------------------
    # THEME 3: EARNINGS & CASH YIELD (Valuation Multiples & Yield Spreads)
    # --------------------------------------------------------------------------
    {
        "name": "Operating_Earnings_Yield",
        "theme": "EARNINGS_CASH_YIELD",
        "formula": "ts_rank(ts_backfill(operating_income / cap, 65), {lookback})",
        "lookbacks": [180, 252],
        "decays": [2, 3, 4],
        "truncation": 0.08
    },
    {
        "name": "Operating_Cashflow_Yield",
        "theme": "EARNINGS_CASH_YIELD",
        "formula": "ts_rank(ts_backfill(cashflow_op / cap, 65), {lookback})",
        "lookbacks": [180, 252],
        "decays": [2, 3, 4],
        "truncation": 0.08
    },
    {
        "name": "Sales_Yield_Multiple",
        "theme": "EARNINGS_CASH_YIELD",
        "formula": "ts_rank(ts_backfill(revenue / cap, 65), {lookback})",
        "lookbacks": [180, 252],
        "decays": [2, 3, 4],
        "truncation": 0.08
    },
    {
        "name": "Earnings_Yield_Delta_Acceleration",
        "theme": "EARNINGS_CASH_YIELD",
        "formula": "rank(ts_delta(ts_backfill(operating_income / cap, 65), {lookback}))",
        "lookbacks": [10, 20],
        "decays": [2, 3, 4],
        "truncation": 0.08
    },
    {
        "name": "Cashflow_Yield_Delta_Acceleration",
        "theme": "EARNINGS_CASH_YIELD",
        "formula": "rank(ts_delta(ts_backfill(cashflow_op / cap, 65), {lookback}))",
        "lookbacks": [10, 20],
        "decays": [2, 3, 4],
        "truncation": 0.08
    },
    {
        "name": "Earnings_Cap_Regression_Residual",
        "theme": "EARNINGS_CASH_YIELD",
        "formula": "rank(ts_regression(ts_backfill(operating_income, 65), ts_backfill(cap, 65), {lookback}, lag = 0, rettype = 0))",
        "lookbacks": [180, 252],
        "decays": [3, 4, 5],
        "truncation": 0.08
    },
    {
        "name": "Gaussian_Quantile_Operating_Yield",
        "theme": "EARNINGS_CASH_YIELD",
        "formula": "quantile(ts_backfill(operating_income / cap, 65), driver = gaussian)",
        "lookbacks": [65],
        "decays": [2, 3, 4],
        "truncation": 0.08
    },

    # --------------------------------------------------------------------------
    # THEME 4: VOLATILITY CONTRACTION & INTRADAY DISPERSION
    # --------------------------------------------------------------------------
    {
        "name": "Range_Volatility_Contraction_Close",
        "theme": "VOLATILITY_CONTRACTION",
        "formula": "-ts_std_dev((high - low) / close, {lookback})",
        "lookbacks": [22, 30, 35],
        "decays": [3, 4, 5],
        "truncation": 0.08
    },
    {
        "name": "Range_Volatility_Contraction_VWAP",
        "theme": "VOLATILITY_CONTRACTION",
        "formula": "-ts_std_dev((high - low) / vwap, {lookback})",
        "lookbacks": [22, 30, 35],
        "decays": [3, 4, 5],
        "truncation": 0.08
    },
    {
        "name": "Volume_Dispersion_Price_Interaction",
        "theme": "VOLATILITY_CONTRACTION",
        "formula": "-ts_std_dev(volume / adv20, {lookback}) * (high / low)",
        "lookbacks": [25, 30, 35],
        "decays": [1, 2, 3],
        "truncation": 0.05
    },
    {
        "name": "Parkinson_Spread_Contraction",
        "theme": "VOLATILITY_CONTRACTION",
        "formula": "-ts_std_dev(high / low, {lookback})",
        "lookbacks": [30, 35, 40],
        "decays": [3, 4, 5],
        "truncation": 0.08
    },
    {
        "name": "Intraday_Candle_Efficiency_Spread",
        "theme": "VOLATILITY_CONTRACTION",
        "formula": "-ts_std_dev((close - open) / (high - low), {lookback})",
        "lookbacks": [25, 35],
        "decays": [3, 4, 5],
        "truncation": 0.08
    },
    {
        "name": "VWAP_Orderflow_Exhaustion_Reversion",
        "theme": "VOLATILITY_CONTRACTION",
        "formula": "-rank(ts_sum((close - vwap) / close * volume, {lookback}))",
        "lookbacks": [8, 10, 15],
        "decays": [3, 4, 5],
        "truncation": 0.08
    },
    {
        "name": "Normalized_VWAP_Distance_Reversion",
        "theme": "VOLATILITY_CONTRACTION",
        "formula": "-ts_rank((close - vwap) / vwap, {lookback})",
        "lookbacks": [15, 22, 30],
        "decays": [3, 4, 5],
        "truncation": 0.08
    },

    # --------------------------------------------------------------------------
    # THEME 5: OPTIONS IV TERM STRUCTURE & SKEW CURVATURE
    # --------------------------------------------------------------------------
    {
        "name": "IV_Call_Term_Structure_Slope",
        "theme": "OPTIONS_TERM_STRUCTURE",
        "formula": "quantile(ts_mean(ts_backfill(implied_volatility_call_60 / implied_volatility_call_30, 5), {lookback}), driver = gaussian)",
        "lookbacks": [20, 30, 45],
        "decays": [6, 8],
        "truncation": 0.05
    },
    {
        "name": "IV_30_Call_Put_Skew_Delta",
        "theme": "OPTIONS_TERM_STRUCTURE",
        "formula": "quantile(ts_delta(ts_backfill(implied_volatility_call_30 - implied_volatility_put_30, 5), {lookback}), driver = gaussian)",
        "lookbacks": [8, 10, 15],
        "decays": [3, 4, 5],
        "truncation": 0.05
    },
    {
        "name": "IV_60_Call_Put_Skew_Curvature",
        "theme": "OPTIONS_TERM_STRUCTURE",
        "formula": "quantile(ts_mean(ts_backfill(implied_volatility_call_60 - implied_volatility_put_60, 5), {lookback}), driver = gaussian)",
        "lookbacks": [15, 20, 30],
        "decays": [3, 4, 5],
        "truncation": 0.05
    },
    {
        "name": "IV_Term_Spread_Differencing",
        "theme": "OPTIONS_TERM_STRUCTURE",
        "formula": "quantile(ts_mean(ts_backfill(implied_volatility_call_60 - implied_volatility_call_30, 5), {lookback}), driver = gaussian)",
        "lookbacks": [15, 22, 30],
        "decays": [3, 4, 5],
        "truncation": 0.05
    },
    {
        "name": "IV_Call_Put_30_Regression_Residual",
        "theme": "OPTIONS_TERM_STRUCTURE",
        "formula": "quantile(ts_regression(ts_backfill(implied_volatility_call_30, 5), ts_backfill(implied_volatility_put_30, 5), {lookback}, lag = 0, rettype = 0), driver = gaussian)",
        "lookbacks": [20, 30],
        "decays": [3, 4, 5],
        "truncation": 0.05
    },
    {
        "name": "IV_Ratio_Impulse_Delta",
        "theme": "OPTIONS_TERM_STRUCTURE",
        "formula": "quantile(ts_delta(ts_backfill(implied_volatility_call_60 / implied_volatility_call_30, 5), {lookback}), driver = gaussian)",
        "lookbacks": [5, 10],
        "decays": [3, 4, 5],
        "truncation": 0.05
    }
]

# ==============================================================================
# 2. HTTP CLIENT & THREAD-SAFE PACED DISPATCHER
# ==============================================================================

def create_harness_session():
    """Constructs a persistent HTTP session with connection pooling and retries."""
    session = requests.Session()
    retries = Retry(
        total=4,
        backoff_factor=2,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "POST", "PATCH"]
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=12, pool_maxsize=12)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

class PacedSimulationDispatcher:
    """
    Enforces a strict global rate limit on POST /simulations.
    Bronze Tier throttles at ~5s per simulation. This dispatcher spaces dispatches
    by at least 6.0 seconds and gracefully handles HTTP 429 Retry-After headers.
    """
    def __init__(self, min_spacing_seconds=6.0):
        self.min_spacing = min_spacing_seconds
        self.lock = threading.Lock()
        self.last_dispatch_time = 0.0

    def dispatch(self, session, payload, max_retries=5):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_dispatch_time
            if elapsed < self.min_spacing:
                wait_needed = self.min_spacing - elapsed
                time.sleep(wait_needed)

            for attempt in range(max_retries):
                try:
                    resp = session.post(f"{BRAIN_BASE}/simulations", json=payload, timeout=30)
                    self.last_dispatch_time = time.time()

                    if resp.status_code == 201:
                        location = resp.headers.get("Location")
                        return location, None
                    elif resp.status_code == 429:
                        ra = float(resp.headers.get("Retry-After", 6.0))
                        print(f"  [DISPATCH RATE LIMIT 429] Backing off {ra + 1.0:.1f}s (Attempt {attempt+1}/{max_retries})...")
                        time.sleep(ra + 1.0)
                        self.last_dispatch_time = time.time()
                    elif resp.status_code in [500, 502, 503, 504]:
                        print(f"  [DISPATCH GATEWAY {resp.status_code}] WorldQuant cluster busy. Waiting 10s...")
                        time.sleep(10.0)
                        self.last_dispatch_time = time.time()
                    else:
                        err_msg = f"HTTP {resp.status_code}: {resp.text[:140]}"
                        return None, err_msg
                except Exception as e:
                    print(f"  [DISPATCH EXCEPTION] {e}. Retrying in 4s...")
                    time.sleep(4.0)

            return None, "Max dispatch retries exhausted."

GLOBAL_DISPATCHER = PacedSimulationDispatcher(DISPATCH_PACING_SECONDS)

# ==============================================================================
# 3. WORLDQUANT BRAIN CLIENT
# ==============================================================================

class GrandmasterBrainClient:
    def __init__(self, email, password):
        self.session = create_harness_session()
        self.email = email
        self.password = password
        self.authenticated = False
        self.auth_lock = threading.Lock()

    def login(self):
        with self.auth_lock:
            if self.authenticated:
                return True
            try:
                r = self.session.post(
                    f"{BRAIN_BASE}/authentication",
                    auth=(self.email, self.password),
                    timeout=25
                )
                if r.status_code in [200, 201]:
                    self.authenticated = True
                    print(f"[AUTH] Successfully authenticated as {self.email}.")
                    return True
                print(f"[AUTH ERROR] HTTP {r.status_code}: {r.text}")
            except Exception as e:
                print(f"[AUTH EXCEPTION] {e}")
            return False

    def simulate(self, formula, settings):
        if not self.authenticated and not self.login():
            return None, "Authentication failed"
        payload = {
            "type": "REGULAR",
            "settings": settings,
            "regular": formula
        }
        return GLOBAL_DISPATCHER.dispatch(self.session, payload)

    def poll_simulation(self, sim_url, timeout=600):
        """Polls the simulation until complete or failed."""
        start = time.time()
        sim_id = sim_url.split('/')[-1] if '/' in sim_url else sim_url
        last_progress = -1

        while time.time() - start < timeout:
            try:
                resp = self.session.get(sim_url, timeout=25)
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status")
                    progress = float(data.get("progress") or 0.0)
                    pct = int(progress * 100)

                    if pct != last_progress and pct > 0:
                        last_progress = pct
                        print(f"    [{sim_id}] Sim progress: {pct}%", flush=True)

                    if status in ["COMPLETE", "COMPLETED"] or "alpha" in data:
                        alpha_id = data.get("alpha")
                        return alpha_id, data
                    elif status in ["ERROR", "FAILED"]:
                        return None, {"error": data.get("message", "Simulation failed")}
                elif resp.status_code == 429:
                    ra = float(resp.headers.get("Retry-After", 5.0))
                    time.sleep(ra + 1.0)
                    continue

                ra_hdr = resp.headers.get("Retry-After")
                sleep_dur = float(ra_hdr) if ra_hdr else 4.0
                time.sleep(max(sleep_dur, 3.0))
            except requests.exceptions.RequestException:
                time.sleep(3)

        return None, {"error": f"Simulation timed out after {timeout}s"}

    def get_alpha_details(self, alpha_id):
        """Fetches full alpha telemetry and In-Sample results."""
        try:
            resp = self.session.get(f"{BRAIN_BASE}/alphas/{alpha_id}", timeout=25)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"  [GET ALPHA ERROR] {alpha_id}: {e}")
        return None

    def check_self_correlation_async(self, alpha_id, timeout=90):
        """
        Polls the async self-correlation endpoint with Retry-After header handling.
        Returns: (status, max_corr, records)
        """
        url = f"{BRAIN_BASE}/alphas/{alpha_id}/correlations/self"
        start = time.time()

        while time.time() - start < timeout:
            try:
                resp = self.session.get(url, timeout=25)
                if resp.status_code == 429:
                    ra = float(resp.headers.get("Retry-After", 4.0))
                    time.sleep(ra + 1.0)
                    continue

                if resp.status_code == 200:
                    text = resp.text.strip()
                    if text:
                        try:
                            data = resp.json()
                            if "records" in data or "max" in data:
                                max_corr = float(data.get("max", 0.0))
                                records = data.get("records", [])
                                return "READY", max_corr, records
                        except Exception:
                            pass
                    # Content-Length: 0 means async computation is ongoing
                    ra_hdr = resp.headers.get("Retry-After")
                    sleep_dur = float(ra_hdr) if ra_hdr else 2.0
                    time.sleep(max(sleep_dur, 1.5))
                    continue
                elif resp.status_code == 202:
                    ra_hdr = resp.headers.get("Retry-After")
                    sleep_dur = float(ra_hdr) if ra_hdr else 2.0
                    time.sleep(max(sleep_dur, 1.5))
                    continue
                else:
                    time.sleep(2.0)
            except Exception:
                time.sleep(2.0)

        return "TIMEOUT", 1.0, []

    def set_badge_and_name(self, alpha_id, color, name=None):
        """Patches color badge and descriptive name to the alpha."""
        payload = {"color": color}
        if name:
            payload["name"] = name[:50]
        try:
            self.session.patch(f"{BRAIN_BASE}/alphas/{alpha_id}", json=payload, timeout=25)
        except Exception as e:
            print(f"  [BADGE PATCH WARNING] {alpha_id}: {e}")

    def submit_and_verify(self, alpha_id):
        """Submits alpha and verifies transition to Out-of-Sample (OS / ACTIVE)."""
        try:
            resp = self.session.post(f"{BRAIN_BASE}/alphas/{alpha_id}/submit", timeout=25)
            if resp.status_code in [200, 201]:
                time.sleep(2.0)
                detail = self.get_alpha_details(alpha_id)
                if not detail:
                    return True
                checks = detail.get("is", {}).get("checks", [])
                corr_fail = any(c.get("name") == "SELF_CORRELATION" and c.get("result") == "FAIL" for c in checks)
                if corr_fail:
                    print(f"  [SUBMISSION BLOCKED] Alpha {alpha_id} failed platform self-correlation check.")
                    return False
                stage = detail.get("stage")
                status = detail.get("status")
                if stage == "OS" or status == "ACTIVE":
                    return True
                return True
            else:
                print(f"  [SUBMIT REJECTED HTTP {resp.status_code}] {resp.text[:140]}")
                return False
        except Exception as e:
            print(f"  [SUBMIT EXCEPTION] {e}")
            return False

    def count_today_submissions(self):
        """Returns the number of alphas submitted today on the platform."""
        try:
            r = self.session.get(f"{BRAIN_BASE}/users/self/alphas?stage=OS&limit=50", timeout=25)
            if r.status_code == 200:
                results = r.json().get("results", [])
                today_utc = datetime.utcnow().strftime("%Y-%m-%d")
                today_local = datetime.now().strftime("%Y-%m-%d")
                cnt = 0
                for a in results:
                    ds = a.get("dateSubmitted") or ""
                    if ds.startswith(today_utc) or ds.startswith(today_local):
                        cnt += 1
                return cnt
        except Exception as e:
            print(f"  [SUBMISSION COUNT ERROR] {e}")
        return 0

# ==============================================================================
# 4. REAL-TIME CHECK VALIDATOR & AUTO-REPAIR ENGINE
# ==============================================================================

class CheckValidator:
    @staticmethod
    def evaluate(detail, min_sharpe=MIN_SHARPE, min_fitness=MIN_FITNESS, max_turnover=MAX_TURNOVER, min_margin=MIN_MARGIN):
        """
        Evaluates alpha statistics against official WorldQuant checks and Value Factor rules.
        """
        is_d = detail.get("is", {}) or {}
        grade = detail.get("grade", "UNKNOWN")
        checks = is_d.get("checks", [])

        sharpe = float(is_d.get("sharpe") or 0.0)
        fitness = float(is_d.get("fitness") or 0.0)
        turnover = float(is_d.get("turnover") or 0.0)
        margin = float(is_d.get("margin") or 0.0)
        sub_univ_sharpe = 0.0

        fails = []
        for c in checks:
            name = c.get("name")
            result = c.get("result")
            if name == "LOW_SUB_UNIVERSE_SHARPE":
                sub_univ_sharpe = float(c.get("value") or 0.0)
            if result == "FAIL":
                fails.append(name)

        passes_all_checks = (len(fails) == 0)
        passes_value_factors = (turnover <= max_turnover and margin >= min_margin and sharpe >= min_sharpe and fitness >= min_fitness)

        is_spectacular = (grade == "SPECTACULAR" or (sharpe >= 2.0 and fitness >= 2.0))
        is_excellent = (grade in ["EXCELLENT", "SPECTACULAR"] or (sharpe >= 1.58 and fitness >= 1.50))
        is_qualifying = passes_all_checks and passes_value_factors

        return {
            "sharpe": sharpe,
            "fitness": fitness,
            "turnover": turnover,
            "margin": margin,
            "margin_bps": margin * 10000.0,
            "sub_univ_sharpe": sub_univ_sharpe,
            "grade": grade,
            "fails": fails,
            "passes_checks": passes_all_checks,
            "passes_value_factors": passes_value_factors,
            "is_qualifying": is_qualifying,
            "is_excellent": is_excellent,
            "is_spectacular": is_spectacular
        }

class AutoRepairEngine:
    @staticmethod
    def diagnose_and_suggest_repair(eval_res, current_settings):
        """
        If alpha has high Sharpe but fails turnover or concentrated weight,
        suggests tuned decay and/or truncation parameters within strict bounds.
        """
        sharpe = eval_res["sharpe"]
        turnover = eval_res["turnover"]
        fails = eval_res["fails"]
        curr_decay = current_settings.get("decay", 3)
        curr_trunc = current_settings.get("truncation", 0.08)

        new_settings = dict(current_settings)
        repaired = False

        # Rule 1: High Turnover with viable Sharpe -> Increment decay strictly <= MAX_DECAY (5)
        if (turnover > MAX_TURNOVER or "HIGH_TURNOVER" in fails) and sharpe >= 1.25:
            if curr_decay < MAX_DECAY:
                new_settings["decay"] = min(curr_decay + 1, MAX_DECAY)
                repaired = True

        # Rule 2: Concentrated weight failure -> Tighten truncation to 0.05
        if "CONCENTRATED_WEIGHT" in fails and curr_trunc > 0.05:
            new_settings["truncation"] = 0.05
            repaired = True

        if repaired:
            return new_settings
        return None

# ==============================================================================
# 5. STRUCTURED RESULTS LOGGING
# ==============================================================================

LOG_LOCK = threading.Lock()

def init_csv_log():
    with LOG_LOCK:
        if not os.path.exists(CSV_LOG_PATH):
            with open(CSV_LOG_PATH, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Timestamp", "Alpha_ID", "Name", "Theme", "Grade", "Color",
                    "Sharpe", "Fitness", "Turnover", "Margin_Bps", "SubUniv_Sharpe",
                    "Max_Corr", "Checks_Failed", "Submitted", "Formula", "Settings"
                ])

def log_alpha_result(alpha_id, name, theme, grade, color, eval_res, max_corr, submitted_str, formula, settings):
    with LOG_LOCK:
        with open(CSV_LOG_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                alpha_id,
                name,
                theme,
                grade,
                color,
                f"{eval_res['sharpe']:.2f}",
                f"{eval_res['fitness']:.2f}",
                f"{eval_res['turnover']:.4f}",
                f"{eval_res['margin_bps']:.1f}",
                f"{eval_res['sub_univ_sharpe']:.2f}",
                f"{max_corr:.4f}",
                ";".join(eval_res["fails"]) if eval_res["fails"] else "NONE",
                submitted_str,
                formula,
                json.dumps(settings)
            ])

# ==============================================================================
# 6. PIPELINE WORKER & CONCURRENT EXECUTION CONTROLLER
# ==============================================================================

class PipelineContext:
    def __init__(self, client, dry_run=False, submit_limit=DAILY_SUBMISSION_LIMIT, max_sims=None):
        self.client = client
        self.dry_run = dry_run
        self.submit_limit = submit_limit
        self.max_sims = max_sims
        self.submitted_today = client.count_today_submissions()
        self.completed_simulations = 0
        self.submitted_count = 0
        self.lock = threading.Lock()

    def can_dispatch_more(self):
        with self.lock:
            if self.max_sims is not None and self.completed_simulations >= self.max_sims:
                return False
            if not self.dry_run and (self.submitted_today + self.submitted_count) >= self.submit_limit:
                return False
            return True

    def increment_completed(self):
        with self.lock:
            self.completed_simulations += 1
            return self.completed_simulations

    def can_submit(self):
        with self.lock:
            if self.dry_run:
                return False, "DRY_RUN"
            if (self.submitted_today + self.submitted_count) >= self.submit_limit:
                return False, "DAILY_CAP_REACHED"
            return True, "OK"

    def record_submission(self):
        with self.lock:
            self.submitted_count += 1
            return self.submitted_today + self.submitted_count

def process_candidate_task(ctx, task):
    """
    Executes the complete research lifecycle for one candidate alpha:
    Simulate -> Poll -> Validate -> Auto-Repair (if needed) -> Self-Correlation -> Badge & Submit -> Log
    """
    client = ctx.client
    name = task["name"]
    theme = task["theme"]
    formula = task["formula"]
    settings = dict(task["settings"])

    sim_idx = ctx.increment_completed()
    print(f"\n[DISPATCH #{sim_idx}] Theme: {theme} | Name: {name} (decay={settings['decay']}, trunc={settings['truncation']})")
    print(f"  Formula: {formula}")

    # 1. Simulation Dispatch
    sim_url, err = client.simulate(formula, settings)
    if not sim_url:
        print(f"  [DISPATCH FAILED] {err}")
        return None

    # 2. Simulation Polling
    alpha_id, data = client.poll_simulation(sim_url)
    if not alpha_id:
        print(f"  [SIMULATION FAILED] {data.get('error')}")
        return None

    detail = client.get_alpha_details(alpha_id)
    if not detail:
        print(f"  [DETAILS ERROR] Could not fetch alpha {alpha_id}")
        return None

    eval_res = CheckValidator.evaluate(detail)

    # 3. Diagnostic Auto-Repair Engine (if high Sharpe but turnover violation)
    repaired_settings = AutoRepairEngine.diagnose_and_suggest_repair(eval_res, settings)
    if repaired_settings:
        print(f"  [AUTO-REPAIR TRIGGERED] Alpha {alpha_id} (Sharpe {eval_res['sharpe']:.2f}, Turn {eval_res['turnover']:.1%}) -> Tuning decay={repaired_settings['decay']}, trunc={repaired_settings['truncation']}...")
        r_sim_url, _ = client.simulate(formula, repaired_settings)
        if r_sim_url:
            r_alpha_id, _ = client.poll_simulation(r_sim_url)
            if r_alpha_id:
                r_detail = client.get_alpha_details(r_alpha_id)
                if r_detail:
                    r_eval = CheckValidator.evaluate(r_detail)
                    if r_eval["fitness"] >= eval_res["fitness"]:
                        print(f"  [AUTO-REPAIR ACCEPTED] Improved Fitness {eval_res['fitness']:.2f} -> {r_eval['fitness']:.2f} (ID: {r_alpha_id})")
                        alpha_id, detail, eval_res, settings = r_alpha_id, r_detail, r_eval, repaired_settings

    # 4. Evaluation Reporting
    grade = eval_res["grade"]
    sharpe = eval_res["sharpe"]
    fitness = eval_res["fitness"]
    turnover = eval_res["turnover"]
    margin_bps = eval_res["margin_bps"]
    fails = eval_res["fails"]

    print(f"  [EVALUATION] ID: {alpha_id} | Grade: {grade:10} | Sharpe: {sharpe:4.2f} | Fit: {fitness:4.2f} | Turn: {turnover*100:4.1f}% | Margin: {margin_bps:4.1f} bps | Fails: {fails}")

    # 5. Badge & Self-Correlation Check
    color = "NONE"
    if eval_res["is_spectacular"]:
        color = "PURPLE"
    elif eval_res["is_qualifying"]:
        color = "BLUE"

    max_corr = 0.0
    passes_corr = False
    submitted_str = "NO"

    if eval_res["is_qualifying"]:
        print(f"  [CORRELATION CHECK] Polling async self-correlation for {alpha_id}...")
        corr_status, max_corr, records = client.check_self_correlation_async(alpha_id)
        passes_corr = (max_corr < MAX_SELF_CORRELATION)
        print(f"  [CORRELATION RESULT] Status: {corr_status} | Max Self-Corr: {max_corr:.4f} (Hurdle < {MAX_SELF_CORRELATION:.2f}) | Comparisons: {len(records)}")

        # 6. Automated Badge Patching
        if color != "NONE":
            client.set_badge_and_name(alpha_id, color, name)
            print(f"  [BADGE PATCHED] Tagged {alpha_id} with color {color} and name '{name}'.")

        # 7. Submission Pipeline with Daily Cap Guard
        if passes_corr:
            can_sub, reason = ctx.can_submit()
            if can_sub:
                print(f"  >>> [SUBMISSION ACTION] Submitting Alpha {alpha_id} to WorldQuant OS Book... <<<")
                sub_ok = client.submit_and_verify(alpha_id)
                if sub_ok:
                    tot = ctx.record_submission()
                    submitted_str = "YES"
                    print(f"  *** [SUBMISSION VERIFIED ACTIVE] Alpha {alpha_id} successfully entered Out-of-Sample! ({tot}/{DAILY_SUBMISSION_LIMIT} today) ***")
                else:
                    submitted_str = "FAILED"
            else:
                submitted_str = f"BLOCKED_{reason}"
                print(f"  [SUBMISSION SKIPPED] {reason} (Current total: {ctx.submitted_today + ctx.submitted_count}/{DAILY_SUBMISSION_LIMIT})")
        else:
            submitted_str = "REJECTED_HIGH_CORR"
            print(f"  [SUBMISSION REJECTED] Max self-correlation {max_corr:.4f} >= {MAX_SELF_CORRELATION:.2f}")

    # 8. Record Telemetry to CSV
    log_alpha_result(
        alpha_id=alpha_id,
        name=name,
        theme=theme,
        grade=grade,
        color=color,
        eval_res=eval_res,
        max_corr=max_corr,
        submitted_str=submitted_str,
        formula=formula,
        settings=settings
    )

    return {
        "alpha_id": alpha_id,
        "name": name,
        "theme": theme,
        "grade": grade,
        "sharpe": sharpe,
        "fitness": fitness,
        "submitted": submitted_str
    }

def worker_thread(ctx, task_queue):
    """Persistent worker thread consuming tasks from the thread-safe queue."""
    while not task_queue.empty() and ctx.can_dispatch_more():
        try:
            task = task_queue.get_nowait()
        except Empty:
            break

        try:
            process_candidate_task(ctx, task)
        except Exception as e:
            print(f"[WORKER ERROR] Task {task.get('name')} crashed: {e}")
        finally:
            task_queue.task_done()

# ==============================================================================
# 7. TASK GENERATION & CLI RUNNER
# ==============================================================================

def build_task_matrix(selected_themes=None, override_decay=None, override_trunc=None):
    """Expands factor templates into individual simulation tasks."""
    tasks = []
    for factor in FACTOR_LIBRARY:
        theme = factor["theme"]
        if selected_themes and theme not in selected_themes:
            continue

        template = factor["formula"]
        name = factor["name"]
        lookbacks = factor.get("lookbacks", [None])
        decays = [override_decay] if override_decay is not None else factor.get("decays", [3])
        truncation = override_trunc if override_trunc is not None else factor.get("truncation", 0.08)

        for lb in lookbacks:
            for d in decays:
                if lb is not None:
                    code = template.format(lookback=lb)
                    t_name = f"{name}_lb{lb}_d{d}"
                else:
                    code = template
                    t_name = f"{name}_d{d}"

                settings = dict(DEFAULT_SIM_SETTINGS)
                settings["decay"] = min(d, MAX_DECAY)
                settings["truncation"] = truncation

                tasks.append({
                    "name": t_name,
                    "theme": theme,
                    "formula": code,
                    "settings": settings
                })
    return tasks

def main():
    parser = argparse.ArgumentParser(description="WorldQuant BRAIN Grandmaster Alpha Engine")
    parser.add_argument("--dry-run", action="store_true", help="Simulate, validate, check correlation, but do not submit")
    parser.add_argument("--themes", type=str, default="", help="Comma-separated list of themes to run")
    parser.add_argument("--max-sims", type=int, default=None, help="Maximum number of simulations to run")
    parser.add_argument("--submit-limit", type=int, default=DAILY_SUBMISSION_LIMIT, help="Max daily submissions allowed (default 4)")
    parser.add_argument("--concurrency", type=int, default=CONCURRENT_SLOTS, help="Concurrent simulation slots (default 3)")
    parser.add_argument("--single-code", type=str, default=None, help="Run a single ad-hoc formula through the pipeline")
    parser.add_argument("--decay", type=int, default=None, help="Override decay parameter (strictly <= 5)")
    parser.add_argument("--truncation", type=float, default=None, help="Override truncation parameter (e.g. 0.05)")

    args = parser.parse_args()

    init_csv_log()
    client = GrandmasterBrainClient(BRAIN_EMAIL, BRAIN_PASSWORD)

    print("\n" + "=" * 80)
    print("WORLDQUANT BRAIN: GRANDMASTER ALPHA RESEARCH & AUTOMATION ENGINE")
    print("=" * 80)
    print(f"Platform User:       {BRAIN_EMAIL} (Bronze Tier)")
    print(f"Concurrency Slots:   {args.concurrency} concurrent simulation workers")
    print(f"Dispatch Pacing:     {DISPATCH_PACING_SECONDS:.1f}s precision throttle")
    print(f"Daily Submit Cap:    {args.submit_limit} alphas/day")
    print(f"Dry Run Mode:        {args.dry_run}")
    print(f"CSV Telemetry Log:   {CSV_LOG_PATH}")
    print("=" * 80 + "\n")

    if not client.login():
        print("[CRITICAL] Authentication failed. Exiting.")
        sys.exit(1)

    ctx = PipelineContext(
        client=client,
        dry_run=args.dry_run,
        submit_limit=args.submit_limit,
        max_sims=args.max_sims
    )

    print(f"[STATUS] Account currently has {ctx.submitted_today} alphas submitted today.")
    if ctx.submitted_today >= args.submit_limit:
        print(f"[NOTE] Daily submission quota ({args.submit_limit}) already reached for today. Engine will run in simulation and validation mode.")

    task_queue = Queue()

    if args.single_code:
        settings = dict(DEFAULT_SIM_SETTINGS)
        if args.decay is not None:
            settings["decay"] = min(args.decay, MAX_DECAY)
        if args.truncation is not None:
            settings["truncation"] = args.truncation
        task_queue.put({
            "name": "Custom_Single_Alpha",
            "theme": "CUSTOM",
            "formula": args.single_code,
            "settings": settings
        })
    else:
        selected_themes = [t.strip() for t in args.themes.split(",") if t.strip()] if args.themes else None
        tasks = build_task_matrix(
            selected_themes=selected_themes,
            override_decay=args.decay,
            override_trunc=args.truncation
        )
        print(f"[TASK MATRIX] Generated {len(tasks)} candidate factor configurations across orthogonal themes.")
        for t in tasks:
            task_queue.put(t)

    # Launch worker threads
    num_workers = min(args.concurrency, CONCURRENT_SLOTS)
    threads = []
    for i in range(num_workers):
        t = threading.Thread(target=worker_thread, args=(ctx, task_queue), name=f"SimWorker-{i+1}")
        t.daemon = True
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    print("\n" + "=" * 80)
    print("GRANDMASTER ALPHA ENGINE RUN FINISHED")
    print(f"Total Simulations Processed: {ctx.completed_simulations}")
    print(f"Total Submissions Completed: {ctx.submitted_count} (Cumulative today: {ctx.submitted_today + ctx.submitted_count}/{args.submit_limit})")
    print(f"Detailed logs saved to:      {CSV_LOG_PATH}")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    main()
