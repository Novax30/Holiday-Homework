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

sim_url = "https://api.worldquantbrain.com/simulations/zZK7q5Ch5dQbIMiSrlZrjM"

for attempt in range(40):
    try:
        with opener.open(urllib.request.Request(sim_url)) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            status = data.get("status")
            progress = data.get("progress")
            print(f"[{attempt*5}s] Status: {status}, Progress: {progress}")
            if status == "COMPLETED" or data.get("alpha"):
                alpha_id = data.get("alpha")
                print("\n=== SIMULATION COMPLETED! ===")
                print(f"Alpha ID: {alpha_id}")
                alpha_url = f"https://api.worldquantbrain.com/alphas/{alpha_id}"
                with opener.open(urllib.request.Request(alpha_url)) as a_resp:
                    alpha_data = json.loads(a_resp.read().decode("utf-8"))
                    print(json.dumps(alpha_data, indent=2))
                break
            elif status in ["ERROR", "FAILED"]:
                print("Simulation failed:", data)
                break
    except Exception as e:
        print("Poll error:", e)
    time.sleep(5)
