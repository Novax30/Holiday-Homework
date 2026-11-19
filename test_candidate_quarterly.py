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

def get_opener():
    auth_req = urllib.request.Request(
        "https://api.worldquantbrain.com/authentication",
        headers={"Authorization": f"Basic {b64_auth}", "Content-Type": "application/json"},
        method="POST"
    )
    with opener.open(auth_req) as resp:
        pass
    return opener

def test_alpha(code, decay=6, neutralization="SUBINDUSTRY", truncation=0.08):
    op = get_opener()
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

    with op.open(req) as resp:
        loc = resp.headers.get("Location")
        print(f"Simulation queued: {loc}")
        sim_url = loc if loc.startswith("http") else f"https://api.worldquantbrain.com{loc}"
        for attempt in range(60):
            time.sleep(4)
            with op.open(urllib.request.Request(sim_url)) as p_resp:
                data = json.loads(p_resp.read().decode("utf-8"))
                status = data.get("status")
                progress = data.get("progress")
                if status == "COMPLETED" or data.get("alpha"):
                    alpha_id = data.get("alpha")
                    print(f"COMPLETED! Alpha ID: {alpha_id}")
                    alpha_url = f"https://api.worldquantbrain.com/alphas/{alpha_id}"
                    with op.open(urllib.request.Request(alpha_url)) as a_resp:
                        alpha_data = json.loads(a_resp.read().decode("utf-8"))
                        is_d = alpha_data.get("is", {}) or {}
                        print(f"GRADE: {alpha_data.get('grade')}")
                        print(f"SHARPE: {is_d.get('sharpe')}")
                        print(f"FITNESS: {is_d.get('fitness')}")
                        print(f"TURNOVER: {is_d.get('turnover')}")
                        print(f"MARGIN: {(is_d.get('margin') or 0)*10000} bps")
                        print(f"SELF CORR: {is_d.get('selfCorrelation')}")
                        return alpha_data
                elif status in ["ERROR", "FAILED"]:
                    print("Simulation failed:", data)
                    return data
        return None

# Test candidate: Quarterly Parkinson Volatility Contraction
test_alpha("-ts_std_dev(high / low, 60)", decay=6)
