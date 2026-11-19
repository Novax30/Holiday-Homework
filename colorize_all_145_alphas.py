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

# Fetch all alphas
alphas = []
offset = 0
limit = 50
while True:
    r = s.get(f'https://api.worldquantbrain.com/users/self/alphas?limit={limit}&offset={offset}').json()
    batch = r.get('results', [])
    if not batch:
        break
    alphas.extend(batch)
    offset += limit
    if offset >= r.get('count', 0):
        break

print(f"Total alphas in account: {len(alphas)}")

counts = {"PURPLE": 0, "BLUE": 0, "GREEN": 0, "None": 0}
modified = 0

for a in alphas:
    aid = a.get("id")
    sharpe = a.get("is", {}).get("sharpe")
    fitness = a.get("is", {}).get("fitness")
    curr_color = a.get("color")
    
    # Target color calculation
    if sharpe is None or fitness is None or sharpe < 1.25 or fitness < 1.00:
        target_color = None
        counts["None"] += 1
    elif sharpe >= 2.00:
        target_color = "PURPLE"
        counts["PURPLE"] += 1
    elif sharpe >= 1.50:
        target_color = "BLUE"
        counts["BLUE"] += 1
    else:
        target_color = "GREEN"
        counts["GREEN"] += 1
        
    # Only patch if color needs to change
    if curr_color != target_color:
        res = s.patch(f"https://api.worldquantbrain.com/alphas/{aid}", json={"color": target_color})
        if res.status_code == 200:
            modified += 1
        time.sleep(0.05) # gentle pacing

print(f"\nColor alignment complete!")
print(f"Alphas updated: {modified}")
print(f"🟣 Spectacular (PURPLE): {counts['PURPLE']}")
print(f"🔵 Excellent (BLUE): {counts['BLUE']}")
print(f"🟢 Good (GREEN): {counts['GREEN']}")
print(f"⚪ Average (Uncolored / None): {counts['None']}")
