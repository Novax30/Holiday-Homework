import os
import json
import base64
import urllib.request
import urllib.error
import http.cookiejar

env_vars = {}
env_path = os.path.join(os.path.dirname(__file__), ".env")
with open(env_path, "r") as f:
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

# 1. Authenticate
auth_req = urllib.request.Request(
    "https://api.worldquantbrain.com/authentication",
    headers={"Authorization": f"Basic {b64_auth}", "Content-Type": "application/json"},
    method="POST"
)
with opener.open(auth_req) as resp:
    user_info = json.loads(resp.read().decode("utf-8"))
    print("Logged in successfully:", user_info)

def get(path):
    req = urllib.request.Request(f"https://api.worldquantbrain.com{path}")
    try:
        with opener.open(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"Error {path}: HTTP {e.code} - {e.read().decode('utf-8')}")
        return None

# Check user profile
print("\n--- User Profile ---")
profile = get("/users/self")
print(json.dumps(profile, indent=2))

# Check tutorials
print("\n--- Tutorials ---")
tutorials = get("/users/self/tutorials")
print(json.dumps(tutorials, indent=2))

# Check user's alphas
print("\n--- User Alphas ---")
alphas = get("/users/self/alphas?limit=10")
print(json.dumps(alphas, indent=2))
