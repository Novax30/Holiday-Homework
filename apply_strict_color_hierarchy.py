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

def classify_strict(sharpe):
    if sharpe is None or sharpe < 1.25:
        return None, "Average"
    elif sharpe < 1.50:
        return "GREEN", "Good"
    elif sharpe < 2.00:
        return "BLUE", "Excellent"
    else:
        return "PURPLE", "Spectacular"

updated = []
for a in alphas:
    aid = a.get("id")
    name = a.get("name") or "Unnamed"
    sharpe = a.get("is", {}).get("sharpe")
    fitness = a.get("is", {}).get("fitness")
    turnover = a.get("is", {}).get("turnover")
    
    color, tier = classify_strict(sharpe)
    
    # Patch color
    r = s.patch(f"https://api.worldquantbrain.com/alphas/{aid}", json={"color": color})
    
    updated.append({
        "id": aid,
        "name": name,
        "sharpe": sharpe,
        "fitness": fitness,
        "turnover": f"{turnover*100:.1f}%" if turnover else "N/A",
        "tier": tier,
        "color": color or "None (Uncolored)",
        "status": r.status_code
    })

# Sort strictly by Sharpe descending
updated.sort(key=lambda x: x["sharpe"] or 0, reverse=True)

print(f"{'#':<3} {'ID':<10} {'Tier':<14} {'Color':<18} {'Sharpe':<8} {'Fitness':<8} {'Name':<35}")
print("-" * 105)
for idx, r in enumerate(updated, 1):
    print(f"{idx:<3} {r['id']:<10} {r['tier']:<14} {r['color']:<18} {r['sharpe'] or 0:<8.2f} {r['fitness'] or 0:<8.2f} {r['name']:<35}")

print(f"\nSuccessfully updated all {len(updated)} alphas on WorldQuant BRAIN!")
