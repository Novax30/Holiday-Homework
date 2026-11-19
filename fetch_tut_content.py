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

p = get("/tutorials/examples/sample-alpha-concepts")
if isinstance(p, dict):
    print("Title:", p.get("title"))
    print("Content preview:", p.get("content", "")[:1000])
    with open("/Users/nova/Documents/ALPAHA/sample_alpha_concepts.html", "w") as f:
        f.write(p.get("content", ""))
else:
    print(p)

p2 = get("/tutorials/discover-brain/intermediate-pack-part-3")
if isinstance(p2, dict):
    print("\nPart 3 Title:", p2.get("title"))
    print("Part 3 Content:", p2.get("content", "")[:1000])
    with open("/Users/nova/Documents/ALPAHA/intermediate_pack_part3.html", "w") as f:
        f.write(p2.get("content", ""))
else:
    print("\nPart 3:", p2)
