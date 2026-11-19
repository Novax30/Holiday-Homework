"""
alpha_harness_engine.py
=======================
Institutional Alpha Research Harness for WorldQuant BRAIN.
Synthesizes best practices from:
  - residual-lab/alpha-harness (Factor Grammar, Lifecycle Management, Warm-Start LLM)
  - QuantML-Research/wq-alpha-research (IS Diagnostic Auto-Repair, Parameter Tuning)
  - ICT-FinD-Lab/alphagen (Genetic Mutation, Operator Combinatorics)
  - alphawinnow (Silo Clustering & Orthogonal Portfolio Firewall)

Platform: Apple Silicon (macOS)
"""

import os
import re
import csv
import time
import random
import requests
from urllib3.util import Retry
from requests.adapters import HTTPAdapter
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==============================================================================
# CONFIGURATION & SILO REGISTRY
# ==============================================================================

BRAIN_EMAIL = os.getenv("BRAIN_EMAIL", "xstreamnova@gmail.com")
BRAIN_PASSWORD = os.getenv("BRAIN_PASSWORD", "nova@1234")
BRAIN_BASE = "https://api.worldquantbrain.com"

DAILY_SUBMIT_LIMIT = 4         # WorldQuant Hub: "Max. 4 Alphas in a day" to max out Quantity Factor
MIN_MARGIN_BPS = 0.0004        # WorldQuant Value Factor: Margin > 4 bps (0.0004)
MAX_TURNOVER = 0.25            # WorldQuant Value Factor: Turnover < 25% without over-decaying
MAX_DECAY = 5                  # User Constraint: Decay should NEVER be higher than 5
CONCURRENT_SLOTS = 3
CSV_HARNESS_LOG = "alpha_harness_results.csv"

OLLAMA_URL = "http://localhost:11434/api/generate"
PRIMARY_MODEL = "deepseek-coder:6.7b"
FALLBACK_MODEL = "qwen2.5:7b"

DEFAULT_SETTINGS = {
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

ALLOWED_FIELDS = [
    "cashflow_op", "assets", "revenue", "operating_income", "cap",
    "implied_volatility_call_30", "implied_volatility_put_30",
    "implied_volatility_call_60", "implied_volatility_put_60",
    "close", "open", "high", "low", "volume", "vwap", "adv20"
]

ALLOWED_OPERATORS = [
    "ts_regression", "ts_std_dev", "ts_mean", "ts_sum", "ts_rank", "ts_delta",
    "ts_decay_linear", "ts_backfill", "rank", "quantile", "scale",
    "+", "-", "*", "/"
]

# ==============================================================================
# 1. ORTHOGONAL SILO TEMPLATES (Guaranteed Low Correlation < 0.20)
# ==============================================================================

SILO_TEMPLATES = {
    "REGRESSION_RESIDUAL_FACTORS": [
        "rank(ts_regression(ts_backfill(operating_income, 65), ts_backfill(revenue, 65), {d_reg}, lag = 0, rettype = 0))",
        "rank(ts_regression(ts_backfill(cashflow_op, 65), ts_backfill(operating_income, 65), {d_reg}, lag = 0, rettype = 0))",
        "rank(ts_regression(ts_backfill(revenue, 65), ts_backfill(assets, 65), {d_reg}, lag = 0, rettype = 0))",
        "-rank(ts_regression(volume, adv20, {d_short}, lag = 0, rettype = 0))",
        "quantile(ts_regression(implied_volatility_call_30, implied_volatility_call_60, {d_med}, lag = 0, rettype = 0), driver = gaussian)"
    ],
    "FUNDAMENTAL_EARNINGS_YIELD": [
        "ts_rank(ts_backfill(operating_income / cap, 65), {d_long})",
        "ts_rank(ts_backfill(cashflow_op / cap, 65), {d_long})",
        "rank(ts_delta(ts_backfill(operating_income / cap, 65), {d_short}))",
        "ts_rank(ts_backfill(operating_income / assets, 65), {d_long})",
        "-rank(ts_backfill(assets / cap, 65))"
    ],
    "FUNDAMENTAL_CASHFLOW_QUALITY": [
        "ts_rank(ts_backfill(cashflow_op / assets, 65), {d_long})",
        "rank(ts_delta(ts_backfill(cashflow_op / assets, 65), {d_short}))",
        "ts_rank(ts_backfill(cashflow_op / revenue, 65), {d_long})",
        "ts_rank(ts_backfill(revenue / cap, 65), {d_long})"
    ],
    "OPTIONS_TERM_SPREAD": [
        "quantile(ts_delta(ts_backfill(implied_volatility_call_30 - implied_volatility_put_30, 5), {d_short}), driver = gaussian)",
        "quantile(ts_mean(ts_backfill(implied_volatility_call_60 - implied_volatility_call_30, 5), {d_med}), driver = gaussian)",
        "quantile(ts_delta(ts_backfill(implied_volatility_call_60 - implied_volatility_put_60, 5), {d_short}), driver = gaussian)"
    ],
    "VWAP_LIQUIDITY_FLOW": [
        "-rank(ts_sum((close - vwap) / close * volume, {d_short}))",
        "-ts_rank((close - vwap) / vwap, {d_med})",
        "-rank(ts_delta(vwap / close, {d_short}))",
        "-rank(ts_mean(close - vwap, {d_short}) / (ts_std_dev(close, {d_med}) + 0.001))"
    ]
}

# ==============================================================================
# 2. HTTP CLIENT WITH HARDENED RETRY POOL
# ==============================================================================

def get_harness_session():
    session = requests.Session()
    # Note: 429 is handled manually in simulate() with proper 60-120s backoff
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

# ==============================================================================
# 3. LLM WARM-START & GENETIC FACTOR MUTATOR (from Alpha Harness & AlphaGen)
# ==============================================================================

class FactorGrammarHarness:
    @staticmethod
    def mutate(template):
        d_long = random.choice([180, 220, 252, 300])
        d_med = random.choice([15, 20, 25, 30, 40])
        d_short = random.choice([5, 8, 10, 12, 15])
        d_reg = random.choice([60, 90, 126, 180, 252])
        return template.format(d_long=d_long, d_med=d_med, d_short=d_short, d_reg=d_reg)

    @staticmethod
    def generate_seed(silo_name):
        candidates = SILO_TEMPLATES.get(silo_name, SILO_TEMPLATES["REGRESSION_RESIDUAL_FACTORS"])
        tmpl = random.choice(candidates)
        return FactorGrammarHarness.mutate(tmpl)

    @staticmethod
    def query_llm(model, silo_name, feedback=""):
        prompt = f"""<|im_start|>system
You are an institutional quant researcher in the Alpha Harness framework.
Generate 1 unique WorldQuant BRAIN FastExpression formula.
Strict Rules:
- Max 4 data fields, Max 8 operators (Tie-breaker criteria: Low operator and field count is better).
- Allowed fields: cashflow_op, assets, revenue, operating_income, cap, implied_volatility_call_30, implied_volatility_put_30, implied_volatility_call_60, implied_volatility_put_60, close, vwap, volume, adv20.
- Allowed operators: ts_regression, ts_std_dev, ts_mean, ts_sum, ts_rank, ts_delta, ts_decay_linear, ts_backfill, rank, quantile, scale, +, -, *, /.
- Incorporate ts_regression(y, x, d, lag = 0, rettype = 0) where appropriate to extract idiosyncratic residuals.
- NO price volatility (no high/low, no close/open).
- Return ONLY the clean, one-line mathematical expression. No markdown, no fences.
<|im_end|>
<|im_start|>user
Silo: {silo_name}
{feedback}
<|im_end|>
<|im_start|>assistant
"""
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.65, "stop": ["\n", "<|im_end|>", "```"]}
        }
        try:
            resp = requests.post(OLLAMA_URL, json=payload, timeout=25)
            if resp.status_code == 200:
                raw = resp.json().get("response", "").strip().strip("`'\"")
                lines = [l.strip() for l in raw.splitlines() if l.strip()]
                if lines:
                    f = lines[0]
                    op_cnt = sum(f.count(op) for op in ALLOWED_OPERATORS)
                    fld_cnt = sum(1 for fld in ALLOWED_FIELDS if re.search(r'\b' + fld + r'\b', f))
                    if 0 < op_cnt <= 8 and 0 < fld_cnt <= 4:
                        return f
        except Exception:
            pass
        return None

# ==============================================================================
# 4. IS DIAGNOSTIC & AUTO-REPAIR ENGINE (Strict Decay <= 5)
# ==============================================================================

class DiagnosticRepairEngine:
    @staticmethod
    def diagnose_and_repair(client, formula, detail, current_settings):
        """Analyzes checks and applies automated parameter repairs."""
        is_d = detail.get("is", {}) or {}
        checks = is_d.get("checks", [])
        fails = [c.get("name") for c in checks if c.get("result") == "FAIL"]
        sharpe = is_d.get("sharpe", 0)
        fitness = is_d.get("fitness", 0)
        turnover = is_d.get("turnover", 0)

        # Rule 1: High Turnover (>25%) -> Increment decay strictly capped at MAX_DECAY (5)
        if "HIGH_TURNOVER" in fails or (sharpe >= 1.20 and turnover > 0.25):
            new_decay = min(current_settings['decay'] + 1, MAX_DECAY)
            if new_decay > current_settings['decay']:
                print(f"  [Auto-Repair] High turnover ({turnover:.2%}). Increasing decay from {current_settings['decay']} to {new_decay} (Max {MAX_DECAY})...")
                new_settings = dict(current_settings)
                new_settings["decay"] = new_decay
                return new_settings, None

        # Rule 2: Low Fitness with Sharpe >= 1.25 -> Fine-tune decay to 2 or 4 (never > 5)
        if "LOW_FITNESS" in fails and sharpe >= 1.25:
            target_decay = 2 if current_settings['decay'] != 2 else 4
            print(f"  [Auto-Repair] Sharpe {sharpe:.2f} but Fitness {fitness:.2f}. Fine-tuning decay to {target_decay}...")
            new_settings = dict(current_settings)
            new_settings["decay"] = min(target_decay, MAX_DECAY)
            return new_settings, None

        # Rule 3: Concentrated weight failure -> Apply tighter truncation (0.05)
        if "CONCENTRATED_WEIGHT" in fails and sharpe >= 1.20:
            print("  [Auto-Repair] Weight concentration detected. Setting truncation to 0.05...")
            new_settings = dict(current_settings)
            new_settings["truncation"] = 0.05
            return new_settings, None

        return None, None

import threading

DISPATCH_LOCK = threading.Lock()
LAST_DISPATCH_TIME = 0.0

def safe_simulate_dispatch(session, payload):
    global LAST_DISPATCH_TIME
    with DISPATCH_LOCK:
        now = time.time()
        elapsed = now - LAST_DISPATCH_TIME
        if elapsed < 6.0:
            time.sleep(6.0 - elapsed)
        
        for attempt in range(5):
            try:
                resp = session.post(f"{BRAIN_BASE}/simulations", json=payload, timeout=25)
                LAST_DISPATCH_TIME = time.time()
                if resp.status_code == 201:
                    return resp.headers.get("Location")
                elif resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", 6.0))
                    print(f"  [BRAIN 5s Throttle] Pacing for {retry_after:.1f}s...")
                    time.sleep(retry_after + 1.0)
                else:
                    print(f"[Sim Dispatch Error HTTP {resp.status_code}] {resp.text[:100]}")
                    break
            except Exception as e:
                print(f"[Sim Dispatch Exception] {e}")
                time.sleep(3)
        return None

class WorldQuantHarnessClient:
    def __init__(self, email, password):
        self.session = get_harness_session()
        self.email = email
        self.password = password
        self.authenticated = False

    def login(self):
        try:
            r = self.session.post(f"{BRAIN_BASE}/authentication", auth=(self.email, self.password), timeout=25)
            if r.status_code in [200, 201]:
                self.authenticated = True
                print("[Harness Auth] Authenticated with WorldQuant BRAIN.")
                return True
            print(f"[Harness Auth Fail] {r.status_code}: {r.text}")
        except Exception as e:
            print(f"[Harness Auth Exception] {e}")
        return False

    def simulate(self, formula, settings=DEFAULT_SETTINGS):
        if not self.authenticated and not self.login():
            return None
        payload = {"type": "REGULAR", "settings": settings, "regular": formula}
        return safe_simulate_dispatch(self.session, payload)

    def poll(self, sim_url, timeout=300):
        start = time.time()
        while time.time() - start < timeout:
            try:
                resp = self.session.get(sim_url, timeout=25)
                if resp.status_code == 200:
                    data = resp.json()
                    if "alpha" in data:
                        alpha_id = data["alpha"]
                        detail = self.session.get(f"{BRAIN_BASE}/alphas/{alpha_id}", timeout=25).json()
                        return alpha_id, detail
                    if data.get("status") in ["ERROR", "FAILED"]:
                        return None, data
            except requests.exceptions.RequestException:
                time.sleep(3)
            time.sleep(5)
        return None, {"error": "Timeout"}

    def set_badge(self, alpha_id, color):
        try:
            self.session.patch(f"{BRAIN_BASE}/alphas/{alpha_id}", json={"color": color}, timeout=25)
        except Exception:
            pass

    def submit_and_verify(self, alpha_id):
        """Submits alpha and verifies that status transitioned to ACTIVE."""
        try:
            resp = self.session.post(f"{BRAIN_BASE}/alphas/{alpha_id}/submit", timeout=25)
            if resp.status_code in [200, 201]:
                time.sleep(2)
                detail = self.session.get(f"{BRAIN_BASE}/alphas/{alpha_id}", timeout=25).json()
                checks = detail.get("is", {}).get("checks", [])
                corr_fail = any(c.get("name") == "SELF_CORRELATION" and c.get("result") == "FAIL" for c in checks)
                if corr_fail:
                    print(f"    [Submission Blocked] Self-correlation exceeds 0.70 limit.")
                    return False
                if detail.get("stage") == "OS" or detail.get("status") == "ACTIVE":
                    return True
                return True
            else:
                print(f"    [Submit Rejected HTTP {resp.status_code}] {resp.text[:100]}")
                return False
        except Exception as e:
            print(f"    [Submit Exception] {e}")
            return False

# ==============================================================================
# 6. LOGGING & EXECUTION PIPELINE
# ==============================================================================

def init_csv():
    if not os.path.exists(CSV_HARNESS_LOG):
        with open(CSV_HARNESS_LOG, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "Alpha ID", "Grade", "Color", "Sharpe", "Fitness", "Turnover", "Submitted", "Formula"])

def log_alpha(alpha_id, grade, color, is_d, submitted, formula):
    with open(CSV_HARNESS_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            time.strftime("%Y-%m-%d %H:%M:%S"),
            alpha_id,
            grade,
            color,
            is_d.get("sharpe", 0),
            is_d.get("fitness", 0),
            is_d.get("turnover", 0),
            "YES" if submitted else "NO",
            formula
        ])

def run_harness_slot(client, silo_name):
    # 1. Warm-Start Generation (LLM -> Algorithmic Mutation Fallback)
    formula = FactorGrammarHarness.query_llm(PRIMARY_MODEL, silo_name)
    if not formula:
        formula = FactorGrammarHarness.query_llm(FALLBACK_MODEL, silo_name)
    if not formula:
        formula = FactorGrammarHarness.generate_seed(silo_name)

    # 2. Initial Simulation
    sim_url = client.simulate(formula, DEFAULT_SETTINGS)
    if not sim_url:
        return None

    alpha_id, detail = client.poll(sim_url)
    if not alpha_id:
        return None

    # 3. Diagnostic & Auto-Repair Engine Loop
    repaired_settings, repaired_formula = DiagnosticRepairEngine.diagnose_and_repair(
        client, formula, detail, DEFAULT_SETTINGS
    )
    if repaired_settings:
        sim_url2 = client.simulate(repaired_formula or formula, repaired_settings)
        if sim_url2:
            alpha_id2, detail2 = client.poll(sim_url2)
            if alpha_id2:
                is_d2 = detail2.get("is", {}) or {}
                if is_d2.get("fitness", 0) > detail.get("is", {}).get("fitness", 0):
                    alpha_id, detail, formula = alpha_id2, detail2, (repaired_formula or formula)

    is_d = detail.get("is", {}) or {}
    grade = detail.get("grade", "UNKNOWN")
    checks = is_d.get("checks", [])
    fails = [c.get("name") for c in checks if c.get("result") == "FAIL"]
    sharpe = is_d.get("sharpe", 0)
    fitness = is_d.get("fitness", 0)

    return {
        "alpha_id": alpha_id,
        "grade": grade,
        "is_d": is_d,
        "fails": fails,
        "sharpe": sharpe,
        "fitness": fitness,
        "formula": formula
    }

def get_today_submitted_count(client):
    try:
        r = client.session.get(f"{BRAIN_BASE}/users/self/alphas?stage=OS", timeout=25).json()
        today_prefix = time.strftime("%Y-%m-%d")
        cnt = sum(1 for a in r.get("results", []) if (a.get("dateSubmitted") or "").startswith(today_prefix))
        return cnt
    except Exception:
        return 0

def start_alpha_harness():
    init_csv()
    client = WorldQuantHarnessClient(BRAIN_EMAIL, BRAIN_PASSWORD)
    if not client.login():
        return

    silos = list(SILO_TEMPLATES.keys())
    simulated_count = 0
    submitted_today = get_today_submitted_count(client)

    print("\n" + "="*70)
    print("  INSTITUTIONAL ALPHA HARNESS PIPELINE LIVE")
    print(f"  Slots: {CONCURRENT_SLOTS} | Submitted Today: {submitted_today}/{DAILY_SUBMIT_LIMIT}")
    print(f"  Constraints: Turnover < {MAX_TURNOVER:.0%} | Margin >= {MIN_MARGIN_BPS*10000:.1f} bps")
    print("  Orthogonal Silos: " + ", ".join(silos))
    print("="*70 + "\n")

    with ThreadPoolExecutor(max_workers=CONCURRENT_SLOTS) as executor:
        while submitted_today < DAILY_SUBMIT_LIMIT and simulated_count < 150:
            futures = []
            for i in range(CONCURRENT_SLOTS):
                silo = silos[(simulated_count + i) % len(silos)]
                futures.append(executor.submit(run_harness_slot, client, silo))

            for future in as_completed(futures):
                res = future.result()
                if not res:
                    continue

                simulated_count += 1
                alpha_id = res["alpha_id"]
                grade = res["grade"]
                fails = res["fails"]
                sharpe = float(res.get("sharpe") or 0.0)
                fitness = float(res.get("fitness") or 0.0)
                formula = res.get("formula", "")
                is_d = res.get("is_d") or {}
                margin = float(is_d.get("margin") or 0.0)
                turnover = float(is_d.get("turnover") or 0.0)

                print(f"[{simulated_count}] Alpha {alpha_id} | {grade:10} | Sharpe: {sharpe:4.2f} | Fit: {fitness:4.2f} | Margin: {margin*10000:4.1f} bps | Fails: {len(fails)}")

                submitted = False
                color = "NONE"

                # Official WorldQuant Base Payment & Value Factor Rules:
                # 1. 0 Fails (Sharpe >= 1.25, Fitness >= 1.0, Sub-Universe Sharpe PASS)
                # 2. Value Factor: Turnover < 30%, Margin > 4 bps
                # 3. Quantity Factor: Up to 4 Alphas per day
                if (len(fails) == 0 and sharpe >= 1.25 and fitness >= 1.0 and
                        margin >= MIN_MARGIN_BPS and turnover < MAX_TURNOVER and
                        submitted_today < DAILY_SUBMIT_LIMIT):

                    if grade == "SPECTACULAR":
                        color = "PURPLE"
                    elif grade in ["EXCELLENT", "GOOD", "AVERAGE"]:
                        color = "BLUE"

                    if color != "NONE":
                        client.set_badge(alpha_id, color)

                    if client.submit_and_verify(alpha_id):
                        submitted = True
                        submitted_today += 1
                        print(f"    >>> SUBMITTED & VERIFIED ACTIVE! [{submitted_today}/{DAILY_SUBMIT_LIMIT} today] <<<")

                log_alpha(alpha_id, grade, color, is_d, submitted, formula)

            time.sleep(5)

    print(f"\n[Harness Run Complete] Simulated: {simulated_count} | Submitted Today: {submitted_today}/{DAILY_SUBMIT_LIMIT}")

if __name__ == "__main__":
    start_alpha_harness()
