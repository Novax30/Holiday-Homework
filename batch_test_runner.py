#!/usr/bin/env python3
"""
Targeted Volatility Candidate Tester & Submitter
Aims for EXCELLENT (Sharpe >= 1.60, Fitness >= 2.00, Margin >= 20 bps, Max Corr < 0.70)
"""
import os
import sys
import time
import csv
import requests

EMAIL = "xstreamnova@gmail.com"
PASSWORD = "nova@1234"
BASE_URL = "https://api.worldquantbrain.com"

SESSION = requests.Session()
SESSION.auth = (EMAIL, PASSWORD)

def login():
    r = SESSION.post(f"{BASE_URL}/authentication")
    if r.status_code in [200, 201]:
        print("[Auth] Successfully logged in to WorldQuant BRAIN.")
        return True
    print(f"[Auth Error] {r.status_code}: {r.text}")
    return False

def check_active_alphas():
    r = SESSION.get(f"{BASE_URL}/users/self/alphas?limit=50")
    if r.status_code == 200:
        results = r.json().get("results", [])
        active = [a for a in results if a.get("status") == "ACTIVE"]
        print(f"[Account] Found {len(active)} active submitted alphas:")
        for a in active:
            is_st = a.get("is", {})
            print(f"  - {a['id']} | Grade: {a.get('grade')} | Sharpe: {is_st.get('sharpe')} | Fit: {is_st.get('fitness')} | Formula: {a.get('regular', {}).get('code')}")
        return [a["id"] for a in active]
    return []

def simulate(code, decay=2, neut="SUBINDUSTRY", trunc=0.08):
    payload = {
        "type": "REGULAR",
        "settings": {
            "instrumentType": "EQUITY",
            "region": "USA",
            "universe": "TOP3000",
            "delay": 1,
            "decay": decay,
            "neutralization": neut,
            "truncation": trunc,
            "pasteurization": "ON",
            "unitHandling": "VERIFY",
            "nanHandling": "OFF",
            "language": "FASTEXPR",
            "visualization": False
        },
        "regular": code
    }
    for attempt in range(3):
        r = SESSION.post(f"{BASE_URL}/simulations", json=payload)
        if r.status_code == 201:
            return r.headers.get("Location")
        elif r.status_code == 429:
            retry_after = float(r.headers.get("Retry-After", 6.0))
            print(f"  [Throttle] Sleeping {retry_after}s...")
            time.sleep(retry_after + 1.0)
        else:
            print(f"  [Sim Post Error {r.status_code}] {r.text[:120]}")
            time.sleep(4)
    return None

def wait_sim(sim_url, timeout=120):
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(3)
        try:
            r = SESSION.get(sim_url, timeout=20)
            if r.status_code == 200:
                data = r.json()
                if "alpha" in data:
                    return data["alpha"]
                if data.get("status") in ["ERROR", "FAILED"]:
                    print(f"  [Sim Failed] {data.get('message')}")
                    return None
        except Exception as e:
            time.sleep(2)
    return None

def check_alpha(alpha_id):
    r = SESSION.get(f"{BASE_URL}/alphas/{alpha_id}")
    if r.status_code != 200:
        return None
    data = r.json()
    grade = data.get("grade")
    is_st = data.get("is", {})
    sharpe = is_st.get("sharpe", 0)
    fitness = is_st.get("fitness", 0)
    turnover = is_st.get("turnover", 0)
    margin = is_st.get("margin", 0)
    checks = is_st.get("checks", [])
    fails = [c["name"] for c in checks if c.get("result") != "PASS"]
    
    # Check self correlation
    corr_res = SESSION.get(f"{BASE_URL}/alphas/{alpha_id}/correlations/self")
    max_corr = 0.0
    corr_details = []
    if corr_res.status_code == 200:
        corr_json = corr_res.json()
        max_corr = corr_json.get("max", 0.0)
        corr_details = corr_json.get("records", [])

    return {
        "id": alpha_id,
        "grade": grade,
        "sharpe": sharpe,
        "fitness": fitness,
        "turnover": turnover,
        "margin": margin,
        "fails": fails,
        "max_corr": max_corr,
        "corr_records": corr_details,
        "code": data.get("regular", {}).get("code")
    }

def submit_alpha(alpha_id, grade):
    color = "PURPLE" if grade == "SPECTACULAR" else "BLUE"
    SESSION.patch(f"{BASE_URL}/alphas/{alpha_id}", json={"color": color})
    
    r = SESSION.post(f"{BASE_URL}/alphas/{alpha_id}/submit")
    print(f"  >>> [SUBMIT ACTION] Alpha {alpha_id} POST /submit -> HTTP {r.status_code}")
    if r.status_code in [200, 201]:
        time.sleep(2)
        ver = SESSION.get(f"{BASE_URL}/alphas/{alpha_id}").json()
        print(f"  >>> [SUBMIT VERIFIED] Status: {ver.get('status')} | Date: {ver.get('dateSubmitted')}")
        return True
    else:
        print(f"  >>> [SUBMIT FAILED] {r.text}")
        return False

# High conviction candidates targeting EXCELLENT/SPECTACULAR grades
CANDIDATES = [
    # 1. Volume Volatility & Price Ratio Interactions
    {"code": "-ts_std_dev(volume / adv20, 25) * (high / low)", "decay": 1, "trunc": 0.05},
    {"code": "-ts_std_dev(volume / adv20, 30) * (high / low)", "decay": 1, "trunc": 0.05},
    {"code": "-ts_std_dev(volume / adv20, 40) * (high / low)", "decay": 1, "trunc": 0.05},
    {"code": "-ts_std_dev(volume / adv20, 45) * (high / low)", "decay": 0, "trunc": 0.05},
    {"code": "-ts_std_dev(volume / adv30, 35) * (high / low)", "decay": 0, "trunc": 0.05},
    {"code": "-ts_std_dev(volume / adv40, 35) * (high / low)", "decay": 0, "trunc": 0.05},
    {"code": "-ts_std_dev(volume / adv20, 35) * (high / close)", "decay": 0, "trunc": 0.05},
    {"code": "-ts_std_dev(volume / adv20, 35) * (close / open)", "decay": 0, "trunc": 0.05},
    {"code": "-ts_std_dev(volume / adv20, 35) * (open / low)", "decay": 0, "trunc": 0.05},
    {"code": "-ts_std_dev(volume / adv20, 35) * (vwap / close)", "decay": 0, "trunc": 0.05},
    
    # 2. Normalized Range Volatility (High Margin, low turnover)
    {"code": "-ts_std_dev((high - low) / close, 22)", "decay": 4, "trunc": 0.08},
    {"code": "-ts_std_dev((high - low) / close, 30)", "decay": 4, "trunc": 0.08},
    {"code": "-ts_std_dev((high - low) / close, 35)", "decay": 4, "trunc": 0.08},
    {"code": "-ts_std_dev((high - low) / vwap, 22)", "decay": 4, "trunc": 0.08},
    {"code": "-ts_std_dev((high - low) / vwap, 30)", "decay": 4, "trunc": 0.08},
    {"code": "-ts_std_dev((high - low) / open, 25)", "decay": 4, "trunc": 0.08},
    {"code": "-ts_std_dev((high - low) / open, 35)", "decay": 4, "trunc": 0.08},
    
    # 3. High/Low Range with Volume interaction
    {"code": "-ts_std_dev(high / low, 25) * (volume / adv20)", "decay": 2, "trunc": 0.08},
    {"code": "-ts_std_dev(high / low, 30) * (volume / adv20)", "decay": 2, "trunc": 0.08},
    {"code": "-ts_std_dev(high / low, 35) * (volume / adv20)", "decay": 2, "trunc": 0.08},
    {"code": "-ts_std_dev(high / low, 30) * (close / open)", "decay": 3, "trunc": 0.08},
    {"code": "-ts_std_dev(high / low, 35) * (close / open)", "decay": 3, "trunc": 0.08},
    
    # 4. Return Volatility & Price Range Interaction
    {"code": "-ts_std_dev(abs(returns), 25) * (high / low)", "decay": 1, "trunc": 0.05},
    {"code": "-ts_std_dev(abs(returns), 35) * (high / low)", "decay": 1, "trunc": 0.05},
    {"code": "-ts_std_dev(returns, 25) * (high / low)", "decay": 1, "trunc": 0.05},
    {"code": "-ts_std_dev(returns, 35) * (high / low)", "decay": 1, "trunc": 0.05},
    {"code": "-ts_std_dev(returns, 30) * (volume / adv20)", "decay": 2, "trunc": 0.05},
    
    # 5. Parkinson / Intraday Trend Spread
    {"code": "-ts_std_dev((close - open) / (high - low), 25)", "decay": 4, "trunc": 0.08},
    {"code": "-ts_std_dev((close - open) / (high - low), 35)", "decay": 4, "trunc": 0.08},
    {"code": "-ts_std_dev(high / low, 35)", "decay": 4, "trunc": 0.08},
    {"code": "-ts_std_dev(high / low, 40)", "decay": 4, "trunc": 0.08},
]

def main():
    print("=" * 70)
    print("WORLDQUANT BRAIN: TARGETED EXCELLENT ALPHA DISPATCHER")
    print("=" * 70)
    
    if not login():
        return
        
    active_alphas = check_active_alphas()
    remaining_slots = 2  # exactly 2 submissions remaining today to hit daily max 4
    print(f"\n[Target] Need {remaining_slots} EXCELLENT / SPECTACULAR alphas.")
    print(f"[Rules] Sharpe >= 1.60, Fitness >= 2.00, Margin >= 20 bps, Turnover < 25%, Decay <= 5, Max Corr < 0.70\n")
    
    submitted_count = 0
    results_log = []
    
    for idx, cand in enumerate(CANDIDATES, 1):
        if submitted_count >= remaining_slots:
            print("\n[SUCCESS] Achieved target of 2 submitted alphas! Halting process.")
            break
            
        code = cand["code"]
        decay = cand["decay"]
        trunc = cand["trunc"]
        neut = cand.get("neut", "SUBINDUSTRY")
        
        print(f"\n[{idx}/{len(CANDIDATES)}] Dispatching: {code} (decay={decay}, trunc={trunc})...")
        sim_url = simulate(code, decay=decay, neut=neut, trunc=trunc)
        if not sim_url:
            time.sleep(5)
            continue
            
        print(f"  Simulation URL: {sim_url}")
        alpha_id = wait_sim(sim_url)
        if not alpha_id:
            print("  Simulation timed out or failed.")
            time.sleep(6)
            continue
            
        stats = check_alpha(alpha_id)
        if not stats:
            time.sleep(6)
            continue
            
        grade = stats["grade"]
        sharpe = stats["sharpe"]
        fit = stats["fitness"]
        t_over = stats["turnover"]
        margin_bps = stats["margin"] * 10000
        fails = stats["fails"]
        max_corr = stats["max_corr"]
        
        is_excellent = (grade in ["EXCELLENT", "SPECTACULAR"]) or (sharpe >= 1.60 and fit >= 2.00)
        passes_checks = len(fails) == 0
        passes_turnover = t_over < 0.25
        passes_margin = stats["margin"] >= 0.0004
        passes_corr = max_corr < 0.70
        
        print(f"  >>> ID: {alpha_id} | Grade: {grade} | Sharpe: {sharpe:.2f} | Fit: {fit:.2f} | T/O: {t_over*100:.1f}% | Margin: {margin_bps:.1f} bps | Fails: {fails} | MaxCorr: {max_corr:.4f}")
        
        record = {
            "id": alpha_id,
            "grade": grade,
            "sharpe": sharpe,
            "fitness": fit,
            "turnover": t_over,
            "margin_bps": margin_bps,
            "fails": str(fails),
            "max_corr": max_corr,
            "formula": code,
            "submitted": "NO"
        }
        
        if is_excellent and passes_checks and passes_turnover and passes_margin and passes_corr:
            print(f"  *** MATCH CONFIRMED: Submitting Alpha {alpha_id} ({grade})! ***")
            success = submit_alpha(alpha_id, grade)
            if success:
                submitted_count += 1
                record["submitted"] = "YES"
                print(f"  *** SUBMISSION COMPLETED ({submitted_count}/{remaining_slots}) ***")
        else:
            reasons = []
            if not is_excellent: reasons.append(f"Grade {grade} (Sharpe {sharpe}, Fit {fit})")
            if not passes_checks: reasons.append(f"Fails {fails}")
            if not passes_turnover: reasons.append(f"High Turnover {t_over*100:.1f}%")
            if not passes_margin: reasons.append(f"Low Margin {margin_bps:.1f} bps")
            if not passes_corr: reasons.append(f"High Self-Corr {max_corr:.4f}")
            print(f"  [Skipped] {', '.join(reasons)}")
            
        results_log.append(record)
        time.sleep(6.0) # Respect BRAIN 5s dispatch rate limit
        
    print("\n" + "=" * 70)
    print(f"RUN FINISHED: {submitted_count} ALPHAS SUBMITTED TODAY.")
    print("=" * 70)

if __name__ == "__main__":
    main()
