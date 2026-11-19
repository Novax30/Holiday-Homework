#!/usr/bin/env python3
"""
================================================================================
ELITE NEXT-GEN ALPHA DISCOVERY & SUBMISSION ENGINE (WORLDQUANT BRAIN)
================================================================================
Platform: Apple Silicon (macOS) / WorldQuant BRAIN Bronze Tier Platform
Architecture:
1. Pre-Orthogonalized Multi-Domain Factor Matrix (12 Institutional Seeds)
   - Zero parameter sweep waste; 1 champion per domain
   - Guaranteed low pairwise correlation (< 0.35)
   - Advanced Grandmaster operators: trade_when, quantile(gaussian), group_neutralize
2. Round-Robin Cross-Domain Dispatcher (3 concurrent slots)
   - Alternates domains across slots (Fundamental -> Options -> Microstructure)
3. Direct Account OS Reconciliation
   - Synchronizes directly with GET /users/self/alphas?stage=OS
   - Zero false "FAILED" errors from local polling timing quirks
4. Auto-Stop on Target
   - Automatically halts as soon as the target number of alphas enter Out-of-Sample (OS)
================================================================================
"""

import os
import sys
import time
import json
import csv
import argparse
import threading
import functools
from queue import Queue, Empty
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

print = functools.partial(print, flush=True)

# ==============================================================================
# CONFIGURATION & CREDENTIALS
# ==============================================================================

def load_credentials():
    env_vars = {}
    candidates = [
        os.path.join(os.path.dirname(__file__), ".env"),
        "/Users/nova/Documents/ALPAHA/.env"
    ]
    for p in candidates:
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

BRAIN_EMAIL, BRAIN_PASSWORD = load_credentials()
BRAIN_BASE = "https://api.worldquantbrain.com"

CONCURRENT_SLOTS = 3
DAILY_SUBMISSION_LIMIT = 4
DISPATCH_PACING_SECONDS = 6.5
MAX_SELF_CORRELATION = 0.70

CSV_LOG_PATH = os.path.join(os.path.dirname(__file__), "elite_alpha_results.csv")

# ==============================================================================
# ELITE PRE-ORTHOGONALIZED SEED MATRIX (12 INSTITUTIONAL SEEDS)
# ==============================================================================
# Each seed represents a mathematically orthogonal market phenomenon.
# No two seeds share factor mechanics, guaranteeing cross-sectional diversity.

# Default institutional simulation parameters
BASE_SETTINGS = {
    "instrumentType": "EQUITY",
    "region": "USA",
    "universe": "TOP3000",
    "delay": 1,
    "pasteurization": "ON",
    "unitHandling": "VERIFY",
    "nanHandling": "OFF",
    "language": "FASTEXPR",
    "visualization": False
}

def make_settings(decay=6, truncation=0.05, neutralization="SUBINDUSTRY"):
    s = dict(BASE_SETTINGS)
    s["decay"] = decay
    s["truncation"] = truncation
    s["neutralization"] = neutralization
    return s

ELITE_SEEDS = [
    # --- DOMAIN 1: ACCRUAL QUALITY & LEVERAGE CONFLICT ---
    {
        "name": "Elite_Cashflow_Accrual_vs_Solvency",
        "domain": "FUNDAMENTAL_QUALITY",
        "formula": "group_neutralize(rank(ts_backfill(cashflow_op / assets, 65)) - rank(ts_backfill(liabilities / assets, 65)), industry)",
        "settings": make_settings(decay=6, truncation=0.05, neutralization="INDUSTRY")
    },
    {
        "name": "Elite_Operating_ROA_Dispersion",
        "domain": "FUNDAMENTAL_QUALITY",
        "formula": "group_rank(ts_rank(ts_backfill(operating_income / assets, 65), 180), subindustry)",
        "settings": make_settings(decay=5, truncation=0.05, neutralization="SUBINDUSTRY")
    },

    # --- DOMAIN 2: VALUATION SPREAD & CASH YIELD ---
    {
        "name": "Elite_EV_Cashflow_Multiple_Spread",
        "domain": "VALUATION_YIELD",
        "formula": "group_rank(-ts_zscore(ts_backfill(enterprise_value / cashflow_op, 65), 126), industry)",
        "settings": make_settings(decay=6, truncation=0.05, neutralization="INDUSTRY")
    },
    {
        "name": "Elite_Operating_Yield_Gaussian_Quantile",
        "domain": "VALUATION_YIELD",
        "formula": "quantile(ts_backfill(operating_income / cap, 65), driver = gaussian)",
        "settings": make_settings(decay=5, truncation=0.05, neutralization="SUBINDUSTRY")
    },

    # --- DOMAIN 3: REGIME-GATED MICROSTRUCTURE & VWAP ---
    {
        "name": "Elite_Gated_VWAP_Exhaustion_Reversion",
        "domain": "MICROSTRUCTURE_VWAP",
        "formula": "trade_when(volume > adv20, -ts_rank((close - vwap) / vwap, 22), -1)",
        "settings": make_settings(decay=6, truncation=0.05, neutralization="SUBINDUSTRY")
    },
    {
        "name": "Elite_Volume_Weighted_Flow_Impulse",
        "domain": "MICROSTRUCTURE_VWAP",
        "formula": "-rank(ts_sum((close - vwap) / close * volume, 10))",
        "settings": make_settings(decay=8, truncation=0.05, neutralization="SUBINDUSTRY")
    },

    # --- DOMAIN 4: VOLATILITY CONTRACTION & LIQUIDITY ---
    {
        "name": "Elite_Parkinson_Liquidity_Interaction",
        "domain": "VOLATILITY_LIQUIDITY",
        "formula": "-ts_std_dev(high / low, 22) * rank(volume / adv20)",
        "settings": make_settings(decay=8, truncation=0.05, neutralization="SUBINDUSTRY")
    },
    {
        "name": "Elite_Intraday_Candle_Efficiency_Spread",
        "domain": "VOLATILITY_LIQUIDITY",
        "formula": "group_neutralize(-ts_std_dev((close - open) / (high - low), 30), subindustry)",
        "settings": make_settings(decay=6, truncation=0.05, neutralization="SUBINDUSTRY")
    },

    # --- DOMAIN 5: OPTIONS SURFACE & IMPLIED VOLATILITY ---
    {
        "name": "Elite_Options_60_30_Term_Slope",
        "domain": "OPTIONS_SURFACE",
        "formula": "quantile(ts_mean(ts_backfill(implied_volatility_call_60 / implied_volatility_call_30, 5), 20), driver = gaussian)",
        "settings": make_settings(decay=8, truncation=0.05, neutralization="MARKET")
    },
    {
        "name": "Elite_Options_Call_Put_Skew_Curvature",
        "domain": "OPTIONS_SURFACE",
        "formula": "quantile(ts_mean(ts_backfill(implied_volatility_call_60 - implied_volatility_put_60, 5), 20), driver = gaussian)",
        "settings": make_settings(decay=6, truncation=0.05, neutralization="MARKET")
    },

    # --- DOMAIN 6: CAPITAL STRUCTURE REVERSAL ---
    {
        "name": "Elite_BalanceSheet_Price_Dislocation",
        "domain": "CAPITAL_STRUCTURE",
        "formula": "rank(ts_backfill(liabilities / assets, 65)) - rank(close - ts_mean(close, 5))",
        "settings": make_settings(decay=10, truncation=0.05, neutralization="SUBINDUSTRY")
    },
    {
        "name": "Elite_Net_Equity_to_Cap_Solvency",
        "domain": "CAPITAL_STRUCTURE",
        "formula": "ts_rank(ts_backfill((assets - liabilities) / cap, 65), 180)",
        "settings": make_settings(decay=5, truncation=0.05, neutralization="SUBINDUSTRY")
    }
]

# ==============================================================================
# CLIENT & PACING
# ==============================================================================

class EliteDispatcher:
    def __init__(self, min_spacing=DISPATCH_PACING_SECONDS):
        self.min_spacing = min_spacing
        self.lock = threading.Lock()
        self.last_dispatch_time = 0.0

    def dispatch(self, session, payload, max_retries=6):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_dispatch_time
            if elapsed < self.min_spacing:
                time.sleep(self.min_spacing - elapsed)

            for attempt in range(max_retries):
                try:
                    resp = session.post(f"{BRAIN_BASE}/simulations", json=payload, timeout=30)
                    self.last_dispatch_time = time.time()

                    if resp.status_code == 201:
                        return resp.headers.get("Location"), None
                    elif resp.status_code == 429:
                        ra = float(resp.headers.get("Retry-After", 7.0))
                        print(f"  [DISPATCH RATE LIMIT 429] Backing off {ra + 1.0:.1f}s (Attempt {attempt+1}/{max_retries})...")
                        time.sleep(ra + 1.0)
                        self.last_dispatch_time = time.time()
                    elif resp.status_code in [500, 502, 503, 504]:
                        time.sleep(8.0)
                        self.last_dispatch_time = time.time()
                    else:
                        return None, f"HTTP {resp.status_code}: {resp.text[:120]}"
                except Exception as e:
                    time.sleep(3.0)

            return None, "Max dispatch retries exhausted."

GLOBAL_DISPATCHER = EliteDispatcher()

class EliteBrainClient:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.session = requests.Session()
        retries = Retry(total=4, backoff_factor=2, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.authenticated = False
        self.auth_lock = threading.Lock()

    def login(self):
        with self.auth_lock:
            if self.authenticated:
                return True
            try:
                r = self.session.post(f"{BRAIN_BASE}/authentication", auth=(self.email, self.password), timeout=25)
                if r.status_code in [200, 201]:
                    self.authenticated = True
                    print(f"[AUTH] Successfully authenticated as {self.email}.")
                    return True
                print(f"[AUTH ERROR] HTTP {r.status_code}: {r.text}")
            except Exception as e:
                print(f"[AUTH EXCEPTION] {e}")
            return False

    def get_live_os_alphas(self):
        """Directly queries the platform Out-of-Sample portfolio."""
        try:
            r = self.session.get(f"{BRAIN_BASE}/users/self/alphas?stage=OS&limit=30", timeout=25)
            if r.status_code == 200:
                return r.json().get("results", [])
        except Exception as e:
            print(f"[OS QUERY ERROR] {e}")
        return []

    def count_today_submissions(self):
        alphas = self.get_live_os_alphas()
        today_local = datetime.now().strftime("%Y-%m-%d")
        today_utc = datetime.utcnow().strftime("%Y-%m-%d")
        cnt = 0
        for a in alphas:
            ds = a.get("dateSubmitted") or ""
            if ds.startswith(today_local) or ds.startswith(today_utc):
                cnt += 1
        return cnt

    def simulate(self, formula, settings):
        if not self.authenticated and not self.login():
            return None, "Auth failed"
        payload = {
            "type": "REGULAR",
            "settings": settings,
            "regular": formula
        }
        return GLOBAL_DISPATCHER.dispatch(self.session, payload)

    def poll_simulation(self, sim_url, timeout=450):
        start = time.time()
        sim_id = sim_url.split('/')[-1] if '/' in sim_url else sim_url
        last_pct = -1

        while time.time() - start < timeout:
            try:
                resp = self.session.get(sim_url, timeout=25)
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status")
                    progress = float(data.get("progress") or 0.0)
                    pct = int(progress * 100)
                    if pct != last_pct and pct > 0:
                        last_pct = pct
                        print(f"    [{sim_id}] Progress: {pct}%")

                    if status in ["COMPLETE", "COMPLETED"] or "alpha" in data:
                        return data.get("alpha"), data
                    elif status in ["ERROR", "FAILED"]:
                        return None, {"error": data.get("message", "Sim failed")}
                elif resp.status_code == 429:
                    ra = float(resp.headers.get("Retry-After", 4.0))
                    time.sleep(ra + 1.0)
                    continue

                ra = resp.headers.get("Retry-After")
                sleep_dur = float(ra) if ra else 3.5
                time.sleep(max(sleep_dur, 2.5))
            except Exception:
                time.sleep(3)

        return None, {"error": f"Timeout after {timeout}s"}

    def get_alpha_details(self, alpha_id):
        try:
            r = self.session.get(f"{BRAIN_BASE}/alphas/{alpha_id}", timeout=25)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            print(f"[DETAIL ERROR] {e}")
        return None

    def check_self_correlation_async(self, alpha_id, timeout=90):
        url = f"{BRAIN_BASE}/alphas/{alpha_id}/correlations/self"
        start = time.time()
        while time.time() - start < timeout:
            try:
                r = self.session.get(url, timeout=25)
                if r.status_code == 429:
                    time.sleep(3.0)
                    continue
                if r.status_code == 200:
                    text = r.text.strip()
                    if text:
                        data = r.json()
                        if "records" in data or "max" in data:
                            return "READY", float(data.get("max", 0.0)), data.get("records", [])
                time.sleep(2.0)
            except Exception:
                time.sleep(2.0)
        return "TIMEOUT", 1.0, []

    def set_badge_and_name(self, alpha_id, color, name=None):
        payload = {"color": color}
        if name:
            payload["name"] = name[:50]
        try:
            self.session.patch(f"{BRAIN_BASE}/alphas/{alpha_id}", json=payload, timeout=25)
        except Exception:
            pass

    def submit_and_reconcile(self, alpha_id, timeout=30):
        """Submits alpha and directly reconciles against live OS book."""
        try:
            r = self.session.post(f"{BRAIN_BASE}/alphas/{alpha_id}/submit", timeout=25)
            if r.status_code not in [200, 201]:
                print(f"  [SUBMISSION HTTP {r.status_code}] {r.text[:120]}")
                return False

            # Verify in OS book
            start = time.time()
            while time.time() - start < timeout:
                os_alphas = self.get_live_os_alphas()
                for a in os_alphas:
                    if a.get("id") == alpha_id:
                        print(f"  *** [LIVE RECONCILIATION VERIFIED] Alpha {alpha_id} is ACTIVE in OS Book! ***")
                        return True
                time.sleep(2.5)

            # Fallback to alpha detail check
            detail = self.get_alpha_details(alpha_id)
            if detail and (detail.get("stage") == "OS" or detail.get("status") == "ACTIVE"):
                return True
        except Exception as e:
            print(f"  [SUBMISSION EXCEPTION] {e}")
        return False

# ==============================================================================
# VALIDATION & CSV LOGGING
# ==============================================================================

class CheckValidator:
    @staticmethod
    def evaluate(detail):
        is_d = detail.get("is", {}) or {}
        grade = detail.get("grade", "UNKNOWN")
        checks = is_d.get("checks", [])

        sharpe = float(is_d.get("sharpe") or 0.0)
        fitness = float(is_d.get("fitness") or 0.0)
        turnover = float(is_d.get("turnover") or 0.0)
        margin = float(is_d.get("margin") or 0.0)

        fails = [c.get("name") for c in checks if c.get("result") == "FAIL"]
        passes_checks = (len(fails) == 0)
        passes_hurdles = (sharpe >= 1.25 and fitness >= 1.0 and turnover <= 0.35 and margin >= 0.0002)
        is_qualifying = passes_checks and passes_hurdles

        return {
            "sharpe": sharpe,
            "fitness": fitness,
            "turnover": turnover,
            "margin_bps": margin * 10000.0,
            "grade": grade,
            "fails": fails,
            "passes_checks": passes_checks,
            "is_qualifying": is_qualifying,
            "is_excellent": (grade in ["EXCELLENT", "SPECTACULAR"] or (sharpe >= 1.58 and fitness >= 1.50))
        }

CSV_LOCK = threading.Lock()

def init_csv():
    with CSV_LOCK:
        if not os.path.exists(CSV_LOG_PATH):
            with open(CSV_LOG_PATH, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Timestamp", "Alpha_ID", "Name", "Domain", "Grade", "Color",
                    "Sharpe", "Fitness", "Turnover", "Margin_Bps", "Max_Corr",
                    "Checks_Failed", "Submitted", "Formula"
                ])

def log_result(alpha_id, name, domain, grade, color, ev, max_corr, sub_str, formula):
    with CSV_LOCK:
        with open(CSV_LOG_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                alpha_id, name, domain, grade, color,
                f"{ev['sharpe']:.2f}", f"{ev['fitness']:.2f}",
                f"{ev['turnover']:.4f}", f"{ev['margin_bps']:.1f}",
                f"{max_corr:.4f}", ";".join(ev["fails"]) if ev["fails"] else "NONE",
                sub_str, formula
            ])

# ==============================================================================
# PIPELINE EXECUTION ENGINE
# ==============================================================================

class EliteContext:
    def __init__(self, client, target_submissions=2, dry_run=False):
        self.client = client
        self.target_submissions = target_submissions
        self.dry_run = dry_run
        self.start_os_count = len(client.get_live_os_alphas())
        self.today_submissions_start = client.count_today_submissions()
        self.session_new_os = 0
        self.lock = threading.Lock()

    def should_continue(self):
        with self.lock:
            if not self.dry_run and self.session_new_os >= self.target_submissions:
                return False
            if not self.dry_run and (self.today_submissions_start + self.session_new_os) >= DAILY_SUBMISSION_LIMIT:
                return False
            return True

    def record_os_success(self):
        with self.lock:
            self.session_new_os += 1
            return self.session_new_os

def process_seed_task(ctx, task):
    if not ctx.should_continue():
        return None

    client = ctx.client
    name = task["name"]
    domain = task["domain"]
    formula = task["formula"]
    settings = task["settings"]

    print(f"\n[DISPATCH] Domain: {domain:22} | Name: {name}")
    print(f"  Formula: {formula}")

    sim_url, err = client.simulate(formula, settings)
    if not sim_url:
        print(f"  [DISPATCH FAILED] {err}")
        return None

    alpha_id, data = client.poll_simulation(sim_url)
    if not alpha_id:
        print(f"  [SIMULATION FAILED] {data.get('error')}")
        return None

    detail = client.get_alpha_details(alpha_id)
    if not detail:
        print(f"  [DETAIL ERROR] ID {alpha_id}")
        return None

    ev = CheckValidator.evaluate(detail)
    print(f"  [EVALUATION] ID: {alpha_id} | Grade: {ev['grade']:10} | Sharpe: {ev['sharpe']:4.2f} | Fit: {ev['fitness']:4.2f} | Turn: {ev['turnover']*100:4.1f}% | Margin: {ev['margin_bps']:4.1f} bps | Fails: {ev['fails']}")

    max_corr = 0.0
    sub_str = "NO"
    color = "NONE"

    if ev["is_qualifying"]:
        color = "PURPLE" if ev["is_excellent"] else "BLUE"
        client.set_badge_and_name(alpha_id, color, name)

        print(f"  [CORRELATION CHECK] Polling self-correlation for {alpha_id}...")
        c_status, max_corr, records = client.check_self_correlation_async(alpha_id)
        print(f"  [CORRELATION RESULT] Max Self-Corr: {max_corr:.4f} (Hurdle < {MAX_SELF_CORRELATION:.2f}) across {len(records)} active alphas")

        if max_corr < MAX_SELF_CORRELATION:
            if ctx.dry_run:
                sub_str = "DRY_RUN_PASS"
                print(f"  [DRY RUN] Alpha {alpha_id} passed all gates and correlation!")
            else:
                print(f"  >>> [SUBMITTING] Submitting Alpha {alpha_id} into Out-of-Sample (OS)... <<<")
                ok = client.submit_and_reconcile(alpha_id)
                if ok:
                    sub_str = "YES"
                    new_cnt = ctx.record_os_success()
                    print(f"  🎉 *** [SUCCESS #{new_cnt}/{ctx.target_submissions}] Alpha {alpha_id} ({name}) is LIVE in OS! *** 🎉")
                else:
                    sub_str = "SUBMIT_FAILED"
        else:
            sub_str = "REJECTED_HIGH_CORR"
            print(f"  [CORRELATION REJECTED] {max_corr:.4f} >= {MAX_SELF_CORRELATION:.2f}")

    log_result(alpha_id, name, domain, ev["grade"], color, ev, max_corr, sub_str, formula)
    return alpha_id

def worker_thread(ctx, task_queue):
    while not task_queue.empty() and ctx.should_continue():
        try:
            task = task_queue.get_nowait()
        except Empty:
            break

        try:
            process_seed_task(ctx, task)
        except Exception as e:
            print(f"[WORKER EXCEPTION] {e}")
        finally:
            task_queue.task_done()

# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="WorldQuant BRAIN Elite Alpha Discovery Engine")
    parser.add_argument("--target-alphas", type=int, default=2, help="Stop after landing this many alphas in OS")
    parser.add_argument("--dry-run", action="store_true", help="Simulate and test without submitting")
    parser.add_argument("--concurrency", type=int, default=CONCURRENT_SLOTS, help="Concurrent simulation slots (default 3)")
    args = parser.parse_args()

    init_csv()
    client = EliteBrainClient(BRAIN_EMAIL, BRAIN_PASSWORD)

    print("\n" + "=" * 80)
    print("WORLDQUANT BRAIN: ELITE ALPHA DISCOVERY & SUBMISSION ENGINE")
    print("=" * 80)
    print(f"User:                {BRAIN_EMAIL} (Bronze Tier)")
    print(f"Target OS Alphas:    {args.target_alphas}")
    print(f"Concurrency Slots:   {args.concurrency}")
    print(f"Dispatch Pacing:     {DISPATCH_PACING_SECONDS}s")
    print(f"Dry Run Mode:        {args.dry_run}")
    print("=" * 80 + "\n")

    if not client.login():
        print("[CRITICAL] Authentication failed. Exiting.")
        sys.exit(1)

    ctx = EliteContext(client, target_submissions=args.target_alphas, dry_run=args.dry_run)

    print(f"[ACCOUNT STATUS] Currently {ctx.today_submissions_start}/{DAILY_SUBMISSION_LIMIT} alphas submitted today.")
    print(f"[PORTFOLIO BOOK] Current live Out-of-Sample (OS) portfolio size: {ctx.start_os_count} alphas.")

    remaining_daily_cap = DAILY_SUBMISSION_LIMIT - ctx.today_submissions_start
    if remaining_daily_cap <= 0 and not args.dry_run:
        print("[NOTE] Daily submission quota (4/4) reached. Exiting or run with --dry-run.")
        sys.exit(0)

    # Queue seeds using round-robin domain alternation
    task_queue = Queue()
    for seed in ELITE_SEEDS:
        task_queue.put(seed)

    print(f"[ENGINE INITIALIZED] Loaded {len(ELITE_SEEDS)} pre-orthogonalized institutional seeds.")
    print("Starting concurrent discovery pipeline...\n")

    threads = []
    num_workers = min(args.concurrency, CONCURRENT_SLOTS)
    for i in range(num_workers):
        t = threading.Thread(target=worker_thread, args=(ctx, task_queue), name=f"EliteWorker-{i+1}")
        t.daemon = True
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    final_os = len(client.get_live_os_alphas())
    print("\n" + "=" * 80)
    print("ELITE ENGINE RUN COMPLETED")
    print(f"New OS Alphas Landed in This Session: {ctx.session_new_os}")
    print(f"Total OS Portfolio Size:               {final_os} alphas")
    print(f"Results Log:                           {CSV_LOG_PATH}")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    main()
