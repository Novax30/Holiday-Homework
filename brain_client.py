import os
import json
import base64
import urllib.request
import urllib.error
import http.cookiejar

# Parse .env manually
env_vars = {}
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
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

# Basic auth header
auth_str = f"{email}:{password}"
b64_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")

req = urllib.request.Request(
    "https://api.worldquantbrain.com/authentication",
    headers={
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/json"
    },
    method="POST"
)

try:
    with opener.open(req) as resp:
        print(f"Status Code: {resp.status}")
        data = resp.read().decode("utf-8")
        print(f"Response: {data[:500]}")
        print("Cookies:")
        for cookie in cj:
            print(f"  {cookie.name}={cookie.value[:10]}...")
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.read().decode('utf-8')}")
except Exception as e:
    print(f"Error: {e}")
