import os
import json
import time
import base64
import urllib.request
import urllib.error
import http.cookiejar

env_vars = {}
with open("/Users/nova/Documents/ALPAHA/.env", "r") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env_vars[k.strip()] = v.strip().strip('"').strip("'")

email = env_vars.get("BRAIN_EMAIL")
password = env_vars.get("BRAIN_PASSWORD")

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

auth_str = f"{email}:{password}"
b64_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")

auth_req = urllib.request.Request(
    "https://api.worldquantbrain.com/authentication",
    headers={"Authorization": f"Basic {b64_auth}", "Content-Type": "application/json"},
    method="POST"
)
with opener.open(auth_req) as resp:
    pass

def simulate(code, decay=6, neutralization="SUBINDUSTRY", truncation=0.08):
    payload = {
        "type": "REGULAR",
        "settings": {
            "instrumentType": "EQUITY",
            "region": "USA",
            "universe": "TOP3000",
            "delay": 1,
            "decay": decay,
            "neutralization": neutralization,
            "truncation": truncation,
            "pasteurization": "ON",
            "unitHandling": "VERIFY",
            "nanHandling": "OFF",
            "language": "FASTEXPR",
            "visualization": False
        },
        "regular": code
    }

    req = urllib.request.Request(
        "https://api.worldquantbrain.com/simulations",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with opener.open(req) as resp:
        loc = resp.headers.get("Location")
        print("Simulation Location:", loc)
        sim_url = loc if loc.startswith("http") else f"https://api.worldquantbrain.com{loc}"
        for attempt in range(60):
            time.sleep(4)
            with opener.open(urllib.request.Request(sim_url)) as p_resp:
                data = json.loads(p_resp.read().decode("utf-8"))
                status = data.get("status")
                progress = data.get("progress")
                print(f"[{attempt*4}s] Progress: {progress}, Status: {status}")
                if status == "COMPLETED" or data.get("alpha"):
                    alpha_id = data.get("alpha")
                    print(f"COMPLETED! Alpha ID: {alpha_id}")
                    alpha_url = f"https://api.worldquantbrain.com/alphas/{alpha_id}"
                    with opener.open(urllib.request.Request(alpha_url)) as a_resp:
                        return json.loads(a_resp.read().decode("utf-8"))
                elif status in ["ERROR", "FAILED"]:
                    print("Simulation failed:", data)
                    return data
        return None

code = """positive_days = ts_sum(returns > 0, 20);
signal = if_else(positive_days > 10, -ts_delta(close, 5) / ts_delay(close, 5), 0);
group_rank(trade_when(volume > adv20, signal, -1), subindustry)"""

res = simulate(code)
if res:
    is_data = res.get("is", {})
    print("\n--- RESULTS ---")
    print("Grade:", res.get("grade"))
    print("Sharpe:", is_data.get("sharpe"))
    print("Fitness:", is_data.get("fitness"))
    print("Turnover:", is_data.get("turnover"))
    print("Margin (bps):", (is_data.get("margin") or 0) * 10000)
    print("Checks:", [c.get("name") + ": " + c.get("result") for c in is_data.get("checks", [])])
