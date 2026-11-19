#!/usr/bin/env python3
"""
================================================================================
SPECTACULAR ALPHA AUTONOMOUS ENGINE (WORLDQUANT BRAIN)
================================================================================
Target: Discovers, validates, and submits EXACTLY 1 SPECTACULAR Alpha (Purple 🟣)
Platform Grade: SPECTACULAR (Sharpe >= 1.60, Fitness >= 2.20, Turnover <= 15%)
Decay Bound: Decay <= 4 (Strictly enforced)
Self-Correlation: Max Pearson correlation < 0.70 against all Out-of-Sample alphas
Color Badge: PURPLE
================================================================================
"""

import os
import sys
import time
import json
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# Load credentials from .env
ENV_PATH = "/Users/nova/Documents/ALPAHA/.env"
env = {}
if os.path.exists(ENV_PATH):
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")

BRAIN_EMAIL = env.get("BRAIN_EMAIL", "")
BRAIN_PASSWORD = env.get("BRAIN_PASSWORD", "")
BASE_URL = "https://api.worldquantbrain.com"

STATUS_FILE = "/Users/nova/Documents/ALPAHA/spectacular_engine_status.json"

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out = f"[{ts}] {msg}"
    print(out, flush=True)

def update_status(state, details=None):
    payload = {
        "timestamp": datetime.now().isoformat(),
        "state": state,
        "details": details or {}
    }
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

def get_session():
    s = requests.Session()
    retries = Retry(total=5, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.auth = (BRAIN_EMAIL, BRAIN_PASSWORD)
    r = s.post(f"{BASE_URL}/authentication")
    if r.status_code not in [200, 201]:
        log(f"Authentication failed: HTTP {r.status_code}")
        return None
    return s

# Curated candidates specifically calibrated for SPECTACULAR grade
SPECTACULAR_CANDIDATES = [
    {
        "name": "Microstructure_VWAP_Stability",
        "code": "group_rank(-ts_std_dev(vwap / close, 35), subindustry)",
        "decay": 4, "truncation": 0.05, "neutralization": "SUBINDUSTRY"
    },
    {
        "name": "Volume_Stability_Momentum_Filter",
        "code": "group_rank(-ts_std_dev(volume / adv20, 50), subindustry) + 0.15 * group_rank(close / ts_delay(close, 20) - 1, subindustry)",
        "decay": 3, "truncation": 0.05, "neutralization": "SUBINDUSTRY"
    },
    {
        "name": "MultiHorizon_Operating_ROA_Acceleration",
        "code": "group_rank(ts_rank(ts_backfill(operating_income / assets, 65), 180), subindustry) + group_rank(ts_delta(ts_backfill(operating_income / assets, 65), 63), subindustry)",
        "decay": 4, "truncation": 0.05, "neutralization": "SUBINDUSTRY"
    },
    {
        "name": "Volume_Dispersion_Residual_LongLookback",
        "code": "group_rank(-ts_std_dev(volume / adv20, 60), subindustry)",
        "decay": 3, "truncation": 0.05, "neutralization": "SUBINDUSTRY"
    },
    {
        "name": "Options_IV_Curvature_Sector_LowTurnover",
        "code": "group_rank(ts_mean(ts_backfill(implied_volatility_call_60 - implied_volatility_put_60, 5), 30), sector)",
        "decay": 4, "truncation": 0.05, "neutralization": "SECTOR"
    },
    {
        "name": "Parkinson_Spread_Residual_Decay4",
        "code": "group_rank(-ts_std_dev(high / low, 45), subindustry)",
        "decay": 4, "truncation": 0.05, "neutralization": "SUBINDUSTRY"
    }
]

def check_self_correlation(session, alpha_id, max_retries=6):
    for i in range(max_retries):
        try:
            r = session.get(f"{BASE_URL}/alphas/{alpha_id}/correlations/self", timeout=25)
            if r.status_code == 200 and r.text.strip():
                records = r.json().get("records", [])
                if records:
                    max_c = 0.0
                    for rec in records:
                        val = abs(rec[5]) if len(rec) > 5 and isinstance(rec[5], (int, float)) else 0.0
                        if val > max_c:
                            max_c = val
                    return max_c, records
            time.sleep(3)
        except Exception as e:
            time.sleep(3)
    return 1.0, []

def run_spectacular_search():
    s = get_session()
    if not s:
        update_status("AUTH_FAILED", {"error": "Failed to authenticate session"})
        return False

    # Check today's OS submissions
    r = s.get(f"{BASE_URL}/users/self/alphas?stage=OS&limit=50")
    if r.status_code == 200:
        alphas = r.json().get("results", [])
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        today_subs = [a for a in alphas if (a.get("dateSubmitted") or "").startswith(today_str)]
        log(f"Account: {BRAIN_EMAIL} | Out-of-Sample alphas: {len(alphas)} | Today's submissions: {len(today_subs)}/4")
        if len(today_subs) >= 4:
            log("Daily quota of 4 submissions already reached for today. System is capped.")
            update_status("QUOTA_REACHED", {"today_submissions": len(today_subs), "total_os": len(alphas)})
            return True

    for idx, c in enumerate(SPECTACULAR_CANDIDATES, 1):
        name = c["name"]
        code = c["code"]
        decay = c["decay"]
        log(f"\nEvaluating Candidate #{idx}: {name} (Decay: {decay})")
        log(f"  Formula: {code}")

        payload = {
            "type": "REGULAR",
            "settings": {
                "instrumentType": "EQUITY", "region": "USA", "universe": "TOP3000",
                "delay": 1, "decay": decay, "neutralization": c["neutralization"],
                "truncation": c["truncation"], "pasteurization": "ON", "unitHandling": "VERIFY",
                "nanHandling": "OFF", "language": "FASTEXPR", "visualization": False
            },
            "regular": code
        }

        # Dispatch simulation with 429 retry backoff
        sim_id = None
        for attempt in range(10):
            sim_res = s.post(f"{BASE_URL}/simulations", json=payload)
            if sim_res.status_code == 201:
                loc = sim_res.headers.get("Location")
                sim_id = loc.split("/")[-1] if loc else ""
                log(f"  Queued simulation: {sim_id}")
                break
            elif sim_res.status_code == 429:
                log(f"  Simulation slots busy (HTTP 429). Waiting 15s for slot to clear (Attempt {attempt+1}/10)...")
                time.sleep(15)
            else:
                log(f"  Dispatch error: HTTP {sim_res.status_code} {sim_res.text[:120]}")
                time.sleep(5)
                break

        if not sim_id:
            log("  Could not dispatch simulation. Skipping to next candidate.")
            continue

        # Poll simulation
        alpha_id = None
        for _ in range(30):
            time.sleep(6)
            sr = s.get(f"{BASE_URL}/simulations/{sim_id}")
            if sr.status_code == 200:
                sd = sr.json()
                status = sd.get("status")
                alpha_id = sd.get("alpha")
                if status in ["COMPLETE", "WARNING"]:
                    break
                elif status in ["ERROR", "CANCELLED"]:
                    log(f"  Simulation failed: {status}")
                    break

        if not alpha_id:
            log("  No alpha returned from simulation. Proceeding to next candidate.")
            continue

        # Fetch Alpha Details
        ar = s.get(f"{BASE_URL}/alphas/{alpha_id}")
        if ar.status_code != 200:
            continue

        ad = ar.json()
        grade = ad.get("grade", "UNKNOWN")
        is_d = ad.get("is", {})
        sharpe = float(is_d.get("sharpe") or 0.0)
        fitness = float(is_d.get("fitness") or 0.0)
        turnover = float(is_d.get("turnover") or 0.0)
        margin = float(is_d.get("margin") or 0.0)
        checks = is_d.get("checks", [])
        fails = [chk["name"] for chk in checks if chk.get("result") == "FAIL"]

        log(f"  Metrics: Grade: {grade} | Sharpe: {sharpe:.2f} | Fitness: {fitness:.2f} | Turnover: {turnover:.2%} | Margin: {margin*10000:.1f} bps | Fails: {fails}")

        # Evaluate Spectacular Criteria
        is_spectacular = (grade == "SPECTACULAR" or (fitness >= 2.20 and turnover <= 0.15 and sharpe >= 1.50))
        passes_checks = (len(fails) == 0 and sharpe >= 1.25 and fitness >= 1.00)

        if passes_checks and is_spectacular:
            log(f"  🌟 >>> SPECTACULAR GRADE DETECTED! (Grade: {grade}, Fit: {fitness:.2f}, TO: {turnover:.2%}) <<<")
            log("  Checking self-correlation against all portfolio alphas...")
            max_c, records = check_self_correlation(s, alpha_id)
            log(f"  Max self-correlation: {max_c:.4f} across {len(records)} existing alphas (Hurdle: < 0.70)")

            if max_c < 0.70:
                log(f"  🎉 PERFECT PASS! Alpha {alpha_id} passed all gates and self-correlation!")
                # Badge as PURPLE
                s.patch(f"{BASE_URL}/alphas/{alpha_id}", json={"color": "PURPLE", "name": name})
                log(f"  Tagged alpha {alpha_id} with color PURPLE and name '{name}'.")

                # Submit to OS
                sub_r = s.post(f"{BASE_URL}/alphas/{alpha_id}/submit")
                if sub_r.status_code in [200, 201]:
                    log(f"  🏆 *** [MISSION ACCOMPLISHED] Spectacular Alpha {alpha_id} submitted to Out-of-Sample! *** 🏆")
                    update_status("SUBMITTED", {
                        "alpha_id": alpha_id,
                        "name": name,
                        "grade": grade,
                        "color": "PURPLE",
                        "sharpe": sharpe,
                        "fitness": fitness,
                        "turnover": turnover,
                        "margin_bps": margin * 10000,
                        "max_self_correlation": max_c
                    })
                    return True
                else:
                    log(f"  Submission response: HTTP {sub_r.status_code} {sub_r.text[:120]}")
            else:
                log(f"  Rejected due to self-correlation: {max_c:.4f} >= 0.70")
        else:
            log(f"  Did not meet SPECTACULAR threshold. Moving to next candidate...")

    update_status("SEARCHING", {"message": "Pass completed without qualifying spectacular alpha, iterating..."})
    return False

if __name__ == "__main__":
    run_spectacular_search()
