"""
master_quant_engine.py
-----------------------
Autonomous WorldQuant BRAIN Alpha Pipeline for macOS (Apple Silicon).
Features:
- Queries local DeepSeek / Qwen via Ollama.
- Self-healing: feeds error messages back to the LLM to auto-correct broken syntax.
- Enforces strict hub rules (<= 4 fields, <= 8 operators).
- Simulates on WorldQuant BRAIN API.
- Evaluates test scorecards (Sharpe >= 1.25, Fitness >= 1.0, 0 fails).
- Checks self-correlation against active portfolio (< 0.70).
- Sets UI badges: PURPLE for Spectacular, BLUE for Excellent.
- Submits up to DAILY_SUBMIT_LIMIT, then continues simulating toward the 1,500 weekly goal.
"""

import os
import re
import csv
import time
import requests

# ==============================================================================
# USER CONFIGURATION
# ==============================================================================

BRAIN_EMAIL = os.getenv("BRAIN_EMAIL", "xstreamnova@gmail.com")
BRAIN_PASSWORD = os.getenv("BRAIN_PASSWORD", "nova@1234")

DAILY_SUBMIT_LIMIT = 10        # Alphas to submit per day
TOTAL_SIMULATION_TARGET = 220  # ~215/day to hit 1,500/week

# Local LLM Endpoint (Ollama default on Mac)
OLLAMA_URL = "http://localhost:11434/api/generate"
PRIMARY_MODEL = "deepseek-coder"
FALLBACK_MODEL = "qwen2.5-coder"

BRAIN_BASE = "https://api.worldquantbrain.com"
CSV_LOG = "quant_master_results.csv"

# Compliant Default Settings
DEFAULT_SETTINGS = {
    "instrumentType": "EQUITY",
    "region": "USA",
    "universe": "TOP3000",
    "delay": 1,
    "decay": 5,
    "neutralization": "SUBINDUSTRY",
    "truncation": 0.08,
    "pasteurization": "ON",
    "unitHandling": "VERIFY",
    "nanHandling": "OFF",
    "language": "FASTEXPR",
    "visualization": False
}

# Allowed Data Fields & Operators (Strict <= 4 fields, <= 8 operators)
ALLOWED_FIELDS = [
    "high", "low", "close", "open", "volume", "vwap", "adv20",
    "implied_volatility_call_30", "implied_volatility_put_30",
    "cashflow_op", "assets", "revenue", "operating_income", "cap"
]

ALLOWED_OPERATORS = [
    "ts_std_dev", "ts_mean", "ts_sum", "ts_rank", "ts_delta",
    "ts_decay_linear", "ts_backfill", "rank", "quantile", "scale",
    "+", "-", "*", "/"
]

# ==============================================================================
# 1. LOCAL LLM INTERFACE WITH SELF-HEALING
# ==============================================================================

PROMPT_BASE = """You are a mathematical researcher writing one-line alphas for WorldQuant BRAIN.
Syntax Rules:
1. Maximum 4 data fields and Maximum 8 operators.
2. Allowed fields: high, low, close, open, volume, vwap, adv20, implied_volatility_call_30, implied_volatility_put_30, cashflow_op, assets, revenue, operating_income, cap.
3. Allowed operators: ts_std_dev, ts_mean, ts_sum, ts_rank, ts_delta, ts_decay_linear, ts_backfill, rank, quantile, scale, +, -, *, /.
4. Theme: {theme}
{feedback}
Output ONLY the clean, one-line FastExpression formula. Do NOT provide explanations, code blocks, or markdown fences."""

def query_local_llm(theme, error_feedback="", model=PRIMARY_MODEL):
    feedback_text = ""
    if error_feedback:
        feedback_text = f"IMPORTANT: Your previous attempt failed with error: '{error_feedback}'. Fix this mistake and write a valid formula."

    prompt = PROMPT_BASE.format(theme=theme, feedback=feedback_text)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.65}
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=60)
        if resp.status_code == 200:
            raw = resp.json().get("response", "").strip()
            clean = re.sub(r"```[a-zA-Z]*", "", raw).replace("```", "").strip()
            lines = [l.strip() for l in clean.splitlines() if l.strip()]
            return lines[0] if lines else None
    except Exception as e:
        print(f"[{model} Warning] Connection error: {e}")
    return None

def validate_formula(formula):
    """Enforces <= 4 fields and <= 8 operators."""
    if not formula or len(formula) < 6:
        return False, "Formula too short"

    op_count = sum(formula.count(op) for op in ALLOWED_OPERATORS)
    if op_count > 8:
        return False, f"Too many operators ({op_count} > 8)"
    if op_count == 0:
        return False, "No valid operators found"

    field_count = sum(1 for f in ALLOWED_FIELDS if re.search(r'\b' + f + r'\b', formula))
    if field_count > 4:
        return False, f"Too many data fields ({field_count} > 4)"
    if field_count == 0:
        return False, "No recognized data fields"

    return True, "Valid"

# ==============================================================================
# 2. WORLDQUANT BRAIN CLIENT
# ==============================================================================

class BrainClient:
    def __init__(self, email, password):
        self.session = requests.Session()
        self.email = email
        self.password = password
        self.authenticated = False

    def login(self):
        resp = self.session.post(f"{BRAIN_BASE}/authentication", auth=(self.email, self.password), timeout=30)
        if resp.status_code in [200, 201]:
            self.authenticated = True
            print("[Auth] Successfully logged into WorldQuant BRAIN.")
            return True
        else:
            print(f"[Auth Error] {resp.status_code}: {resp.text}")
            return False

    def simulate(self, formula):
        if not self.authenticated and not self.login():
            return None, "Authentication Failed"
        payload = {
            "type": "REGULAR",
            "settings": DEFAULT_SETTINGS,
            "regular": formula
        }
        try:
            resp = self.session.post(f"{BRAIN_BASE}/simulations", json=payload, timeout=30)
            if resp.status_code == 201:
                return resp.headers.get("Location"), "Queued"
            return None, resp.text
        except Exception as e:
            return None, str(e)

    def poll_simulation(self, sim_url, timeout=360):
        start = time.time()
        while time.time() - start < timeout:
            try:
                resp = self.session.get(sim_url, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    if "alpha" in data:
                        alpha_id = data["alpha"]
                        detail = self.session.get(f"{BRAIN_BASE}/alphas/{alpha_id}", timeout=30).json()
                        return alpha_id, detail, "Success"
                    if data.get("status") in ["ERROR", "FAILED"]:
                        return None, None, data.get("message", "Simulation Failed")
            except requests.exceptions.RequestException:
                pass
            time.sleep(5)
        return None, None, "Simulation Timed Out"

    def get_self_correlation(self, alpha_id):
        try:
            resp = self.session.get(f"{BRAIN_BASE}/alphas/{alpha_id}/correlations/self", timeout=30)
            if resp.status_code == 200 and resp.text:
                return resp.json().get("max", 0.0)
        except Exception:
            pass
        return 0.0

    def set_badge_color(self, alpha_id, color):
        try:
            self.session.patch(f"{BRAIN_BASE}/alphas/{alpha_id}", json={"color": color}, timeout=30)
            print(f"[UI] Alpha {alpha_id} color set to {color}.")
        except Exception as e:
            print(f"[UI Error] {e}")

    def submit_alpha(self, alpha_id):
        try:
            resp = self.session.post(f"{BRAIN_BASE}/alphas/{alpha_id}/submit", timeout=30)
            if resp.status_code in [200, 201]:
                print(f"[SUBMISSION SUCCESS] Alpha {alpha_id} is SUBMITTED & ACTIVE!")
                return True
            else:
                print(f"[Submission Error] {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"[Submit Exception] {e}")
        return False

# ==============================================================================
# 3. CSV LOGGING
# ==============================================================================

def init_csv():
    if not os.path.exists(CSV_LOG):
        with open(CSV_LOG, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Timestamp", "Alpha ID", "Grade", "Color", "Sharpe",
                "Fitness", "Turnover", "Max Correlation", "Submitted", "Formula"
            ])

def log_alpha(alpha_id, grade, color, is_d, max_corr, submitted, formula):
    with open(CSV_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            time.strftime("%Y-%m-%d %H:%M:%S"),
            alpha_id,
            grade,
            color,
            is_d.get("sharpe", 0),
            is_d.get("fitness", 0),
            is_d.get("turnover", 0),
            max_corr,
            "YES" if submitted else "NO",
            formula
        ])

# ==============================================================================
# 4. MAIN ORCHESTRATION LOOP
# ==============================================================================

def run_quant_engine():
    init_csv()
    brain = BrainClient(BRAIN_EMAIL, BRAIN_PASSWORD)
    if not brain.login():
        print("Failed to authenticate with BRAIN. Check credentials.")
        return

    submitted_today = 0
    simulated_count = 0
    consecutive_errors = 0
    error_feedback = ""

    themes = [
        "intraday price dispersion volatility",
        "volume spread exhaustion",
        "options implied volatility put call skew",
        "liquidity weighted short term mean reversion",
        "fundamental operating profit yield momentum"
    ]

    print("\n" + "="*60)
    print("  QUANT ENGINE ACTIVE (Apple Silicon Optimized)")
    print(f"  Target: {DAILY_SUBMIT_LIMIT} Submissions | {TOTAL_SIMULATION_TARGET} Simulations")
    print("="*60 + "\n")

    while simulated_count < TOTAL_SIMULATION_TARGET:
        theme = themes[simulated_count % len(themes)]
        model = PRIMARY_MODEL if consecutive_errors < 3 else FALLBACK_MODEL

        print(f"\n[Run {simulated_count + 1}/{TOTAL_SIMULATION_TARGET}] Theme: {theme} (Model: {model})")

        # Step 1: Generate & Validate Formula
        formula = query_local_llm(theme, error_feedback, model)
        is_valid, validation_msg = validate_formula(formula)

        if not is_valid:
            print(f"  [LLM Format Check Failed] {validation_msg}. Auto-correcting...")
            error_feedback = validation_msg
            consecutive_errors += 1
            time.sleep(2)
            continue

        print(f"  [Formula] {formula}")
        error_feedback = ""

        # Step 2: Queue on BRAIN API
        sim_url, status_msg = brain.simulate(formula)
        if not sim_url:
            print(f"  [Simulation Rejected] {status_msg}. Feeding error to LLM for next attempt.")
            error_feedback = status_msg
            consecutive_errors += 1
            time.sleep(5)
            continue

        print(f"  [Queued] {sim_url}")
        simulated_count += 1
        consecutive_errors = 0

        # Step 3: Poll results
        alpha_id, detail, poll_msg = brain.poll_simulation(sim_url)
        if not alpha_id:
            print(f"  [Execution Failed] {poll_msg}")
            error_feedback = poll_msg
            time.sleep(5)
            continue

        is_d = detail.get("is", {}) or {}
        grade = detail.get("grade", "UNKNOWN")
        checks = is_d.get("checks", [])
        fails = [c.get("name") for c in checks if c.get("result") == "FAIL"]

        sharpe = is_d.get("sharpe", 0)
        fitness = is_d.get("fitness", 0)
        turnover = is_d.get("turnover", 0)

        print(f"  [Scorecard] Alpha: {alpha_id} | Grade: {grade} | Sharpe: {sharpe} | Fitness: {fitness} | Fails: {len(fails)}")

        # Step 4: Evaluate for Submission
        # Criteria: 0 Fails, Sharpe >= 1.25, Fitness >= 1.0
        can_submit = (len(fails) == 0 and sharpe >= 1.25 and fitness >= 1.0 and submitted_today < DAILY_SUBMIT_LIMIT)
        color = "NONE"
        max_corr = 0.0

        if len(fails) == 0:
            if grade == "SPECTACULAR":
                color = "PURPLE"
            elif grade in ["EXCELLENT", "GOOD"]:
                color = "BLUE"

            if color != "NONE":
                brain.set_badge_color(alpha_id, color)

            # Check self-correlation against active portfolio
            max_corr = brain.get_self_correlation(alpha_id)
            print(f"  [Correlation] Max: {max_corr} (Hurdle < 0.70)")

            if max_corr >= 0.70:
                can_submit = False
                print(f"  [Blocked] Self-correlation too high ({max_corr} >= 0.70).")

            if can_submit:
                if brain.submit_alpha(alpha_id):
                    submitted_today += 1
                    print(f"  >>> SUBMITTED! [{submitted_today}/{DAILY_SUBMIT_LIMIT} for today] <<<")

        # Step 5: Log to CSV
        log_alpha(alpha_id, grade, color, is_d, max_corr, can_submit, formula)

        # Step 6: Pacing Breather (Prevents rate limits)
        print("  [Pacing] Sleeping 8 seconds before next candidate...")
        time.sleep(8)

    print("\n" + "="*60)
    print(f"  RUN COMPLETED! Simulations: {simulated_count} | Submitted: {submitted_today}")
    print(f"  Log saved to: {CSV_LOG}")
    print("="*60 + "\n")

if __name__ == "__main__":
    run_quant_engine()
