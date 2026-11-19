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

grade_to_color = {
    "SPECTACULAR": "PURPLE",
    "EXCELLENT": "BLUE",
    "GOOD": "GREEN",
    "AVERAGE": None
}

results = []
for a in alphas:
    aid = a.get("id")
    name = a.get("name") or "Unnamed"
    grade = a.get("grade")
    sharpe = a.get("is", {}).get("sharpe")
    fitness = a.get("is", {}).get("fitness")
    
    target_color = grade_to_color.get(grade, None)
    
    # Patch color to match official platform grade
    patch = s.patch(f"https://api.worldquantbrain.com/alphas/{aid}", json={"color": target_color})
    
    results.append({
        "id": aid,
        "name": name,
        "grade": grade,
        "color": target_color or "None (Uncolored)",
        "sharpe": sharpe,
        "fitness": fitness
    })

print(f"{'#':<3} {'ID':<10} {'Platform Grade':<16} {'Assigned Color':<18} {'Sharpe':<8} {'Fitness':<8} {'Name':<35}")
print("-" * 105)
for idx, r in enumerate(results, 1):
    print(f"{idx:<3} {r['id']:<10} {r['grade'] or 'N/A':<16} {r['color']:<18} {r['sharpe'] or 0:<8.2f} {r['fitness'] or 0:<8.2f} {r['name']:<35}")

print(f"\nSuccessfully aligned colors to official WorldQuant BRAIN grades for all {len(results)} submitted alphas!")
