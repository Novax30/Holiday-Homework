import os
import json
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

sim_url = "https://api.worldquantbrain.com/simulations/naNyae650g9R643peFWPy"
with opener.open(urllib.request.Request(sim_url)) as resp:
    data = json.loads(resp.read().decode("utf-8"))
    print("Simulation status:", json.dumps(data, indent=2))
    if data.get("alpha"):
        alpha_id = data.get("alpha")
        with opener.open(urllib.request.Request(f"https://api.worldquantbrain.com/alphas/{alpha_id}")) as a_resp:
            print("\nAlpha:", json.dumps(json.loads(a_resp.read().decode("utf-8")), indent=2))
