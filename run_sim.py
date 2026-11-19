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

# 1. Login
auth_req = urllib.request.Request(
    "https://api.worldquantbrain.com/authentication",
    headers={"Authorization": f"Basic {b64_auth}", "Content-Type": "application/json"},
    method="POST"
)
with opener.open(auth_req) as resp:
    print("Authenticated.")

def simulate(code, decay=4, neutralization="SUBINDUSTRY"):
    payload = {
        "type": "REGULAR",
        "settings": {
            "instrumentType": "EQUITY",
            "region": "USA",
            "universe": "TOP3000",
            "delay": 1,
            "decay": decay,
            "neutralization": neutralization,
            "truncation": 0.08,
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

    try:
        with opener.open(req) as resp:
            # Check Location header or response body
            loc = resp.headers.get("Location")
            print("Simulation created. Location:", loc)
            data = resp.read().decode("utf-8")
            if data:
                print("Body:", data[:300])
            
            # Poll location
            if loc:
                sim_url = loc if loc.startswith("http") else f"https://api.worldquantbrain.com{loc}"
                for i in range(30):
                    time.sleep(3)
                    poll_req = urllib.request.Request(sim_url)
                    with opener.open(poll_req) as poll_resp:
                        poll_data = json.loads(poll_resp.read().decode("utf-8"))
                        status = poll_data.get("status")
                        progress = poll_data.get("progress")
                        print(f"[{i*3}s] Status: {status}, Progress: {progress}")
                        if status == "COMPLETED":
                            alpha_id = poll_data.get("alpha")
                            print("Alpha ID:", alpha_id)
                            # Fetch alpha details
                            alpha_url = f"https://api.worldquantbrain.com/alphas/{alpha_id}"
                            with opener.open(urllib.request.Request(alpha_url)) as a_resp:
                                return json.loads(a_resp.read().decode("utf-8"))
                        elif status in ["ERROR", "FAILED"]:
                            print("Simulation failed:", poll_data)
                            return poll_data
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode('utf-8')}")
        return None

# Let's test a simple simulation that meets the tutorial check
code = """
positive_days = ts_sum(returns > 0, 20);
trade_when(volume > adv20, if_else(positive_days > 10, -(close - vwap) / close, 0), -1)
"""
result = simulate(code.strip())
print("\n--- Simulation Result ---")
if result:
    print(json.dumps(result, indent=2)[:1500])
