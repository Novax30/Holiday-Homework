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

res = s.get('https://api.worldquantbrain.com/users/self/alphas?stage=OS&limit=50').json()
alphas = res.get('results', [])
print(f"Total OS Alphas: {len(alphas)}\n")

def get_tier_color(sharpe, fitness):
    if sharpe is None or fitness is None:
        return None, "Average"
    # Spectacular: Sharpe >= 2.0 OR Fitness >= 2.0 (or Sharpe >= 1.95)
    if sharpe >= 2.0 or fitness >= 2.0 or (sharpe >= 1.90 and fitness >= 1.40):
        return "PURPLE", "Spectacular"
    # Excellent: Sharpe >= 1.50 and Fitness >= 1.10
    elif sharpe >= 1.50 and fitness >= 1.10:
        return "BLUE", "Excellent"
    # Good: Sharpe >= 1.25 and Fitness >= 1.00
    elif sharpe >= 1.25 and fitness >= 1.00:
        return "GREEN", "Good"
    # Average: below institutional thresholds
    else:
        return None, "Average"

results = []
for a in alphas:
    aid = a.get("id")
    name = a.get("name") or "Unnamed"
    sharpe = a.get("is", {}).get("sharpe")
    fitness = a.get("is", {}).get("fitness")
    turnover = a.get("is", {}).get("turnover")
    
    color, tier = get_tier_color(sharpe, fitness)
    
    # Patch color
    patch_res = s.patch(f"https://api.worldquantbrain.com/alphas/{aid}", json={"color": color})
    status = "OK" if patch_res.status_code == 200 else f"Err {patch_res.status_code}"
    
    results.append({
        "id": aid,
        "name": name,
        "sharpe": sharpe,
        "fitness": fitness,
        "turnover": f"{turnover*100:.1f}%" if turnover else "N/A",
        "tier": tier,
        "color": color or "None (Uncolored)",
        "patch": status
    })

print(f"{'#':<3} {'ID':<10} {'Tier':<14} {'Color':<18} {'Sharpe':<8} {'Fitness':<8} {'Name':<35}")
print("-" * 105)
for idx, r in enumerate(results, 1):
    print(f"{idx:<3} {r['id']:<10} {r['tier']:<14} {r['color']:<18} {r['sharpe'] or 0:<8.2f} {r['fitness'] or 0:<8.2f} {r['name']:<35}")

print(f"\nSuccessfully rearranged colors for all {len(results)} Out-of-Sample alphas!")
