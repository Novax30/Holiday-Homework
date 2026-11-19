#!/usr/bin/env python3
import requests, time, os, sys, json

env = {}
with open('/Users/nova/Documents/ALPAHA/.env') as f:
    for line in f:
        if '=' in line:
            k, v = line.strip().split('=', 1)
            env[k.strip('\"\' ')] = v.strip('\"\' ')

s = requests.Session()
s.auth = (env.get('BRAIN_EMAIL'), env.get('BRAIN_PASSWORD'))
s.post('https://api.worldquantbrain.com/authentication')

sims = [
    ("TradeWhen_Fundamental_Dislocation", "https://api.worldquantbrain.com/simulations/1rBk9NcG44Hi8xMHPfPZLtA"),
    ("Quantile_Analyst_Cashflow_Surprise", "https://api.worldquantbrain.com/simulations/2spCe6fAc4KQav917nBg66YU"),
    ("Residual_Price_Exhaustion", "https://api.worldquantbrain.com/simulations/3IEJlu36N4Pf8VS1fP9aGPK9")
]

pending = list(sims)
results = {}

while pending:
    time.sleep(5)
    for i in range(len(pending)-1, -1, -1):
        name, url = pending[i]
        res = s.get(url)
        if res.status_code != 200:
            continue
        data = res.json()
        status = data.get("status")
        progress = data.get("progress", 0)
        
        if status == "COMPLETE" or progress >= 1.0 or "alpha" in data:
            alpha_id = data.get("alpha")
            print(f"\n[DONE] {name} completed! Alpha ID: {alpha_id}")
            pending.pop(i)
            
            # Fetch Alpha details
            a_res = s.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}").json()
            is_stat = a_res.get("is", {})
            sharpe = is_stat.get("sharpe")
            fitness = is_stat.get("fitness")
            turnover = is_stat.get("turnover")
            margin = is_stat.get("margin")
            returns = is_stat.get("returns")
            checks = is_stat.get("checks", [])
            fails = [chk.get("name") for chk in checks if chk.get("result") == "FAIL"]
            
            results[name] = {
                "id": alpha_id,
                "sharpe": sharpe,
                "fitness": fitness,
                "turnover": turnover,
                "margin": margin,
                "returns": returns,
                "fails": fails
            }
            print(f"[{name}] Results:")
            print(f"  Sharpe: {sharpe}")
            print(f"  Fitness: {fitness}")
            print(f"  Turnover: {turnover*100 if turnover else 0:.2f}%")
            print(f"  Margin: {margin*10000 if margin else 0:.2f} bps")
            print(f"  Annual Return: {returns*100 if returns else 0:.2f}%")
            print(f"  Fails: {fails}")
            
            # Check self correlation
            time.sleep(2)
            c_res = s.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}/correlations/self")
            if c_res.status_code == 200:
                try:
                    c_data = c_res.json()
                    print(f"  Max Self-Correlation: {c_data.get('max')}")
                except:
                    pass
        elif status == "ERROR":
            print(f"[ERROR] {name}: {data.get('message')}")
            pending.pop(i)
        else:
            print(f"[{name}] progress: {progress*100:.0f}%")
