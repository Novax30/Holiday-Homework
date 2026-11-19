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

def get(path):
    req = urllib.request.Request(f"https://api.worldquantbrain.com{path}")
    try:
        with opener.open(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}: {e.read().decode('utf-8')}"

tutorials = get("/tutorials")
for section in tutorials.get("results", []):
    for page in section.get("pages", []):
        p_id = page.get("id")
        p_data = get(f"/tutorial-pages/{p_id}")
        if isinstance(p_data, dict):
            content_str = json.dumps(p_data)
            if "positive_days" in content_str or "logical" in content_str.lower():
                print(f"FOUND MATCH in page: {p_id} ({page.get('title')})")
                for block in p_data.get("content", []):
                    if "positive_days" in json.dumps(block) or "trade_when" in json.dumps(block):
                        print("Block:", block)
