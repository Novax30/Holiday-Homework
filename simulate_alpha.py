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

def run_simulation(code, decay=4, neutralization="SUBINDUSTRY", truncation=0.08):
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
                print(f"[{attempt*4}s] Progress: {progress}, Status: {status}")
                if status in ["COMPLETE", "COMPLETED"]:
                    alpha_id = data.get("alpha")
                    print(f"SUCCESS! Alpha ID: {alpha_id}")
                    alpha_url = f"https://api.worldquantbrain.com/alphas/{alpha_id}"
                    with op.open(urllib.request.Request(alpha_url)) as a_resp:
                        alpha_data = json.loads(a_resp.read().decode("utf-8"))
                        try:
                            corr_url = f"https://api.worldquantbrain.com/alphas/{alpha_id}/correlations/self"
                            with op.open(urllib.request.Request(corr_url)) as c_resp:
                                c_data = json.loads(c_resp.read().decode("utf-8"))
                                alpha_data["self_correlation"] = c_data
                        except Exception as e:
                            alpha_data["self_correlation"] = str(e)
                        return alpha_data
                elif status == "WARNING":
                    print(f"WARNING: {data.get('message')}")
                    alpha_id = data.get("alpha")
                    if alpha_id:
                        alpha_url = f"https://api.worldquantbrain.com/alphas/{alpha_id}"
                        with op.open(urllib.request.Request(alpha_url)) as a_resp:
                            return json.loads(a_resp.read().decode("utf-8"))
                    return data
                elif status in ["ERROR", "FAILED"]:
                    print("Simulation failed:", data)
                    return data
        return None

if __name__ == "__main__":
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else "group_rank(ts_mean((2 * close - high - low) / (high - low + 0.001) * (volume / adv20), 20), subindustry)"
    decay = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    neutralization = sys.argv[3] if len(sys.argv) > 3 else "SUBINDUSTRY"
    truncation = float(sys.argv[4]) if len(sys.argv) > 4 else 0.05
    alpha = run_simulation(code, decay=decay, neutralization=neutralization, truncation=truncation)
    if alpha:
        is_d = alpha.get("is", {}) or {}
        print("\n===============================")
        print(f"ALPHA ID: {alpha.get('id')}")
        print(f"GRADE: {alpha.get('grade')}")
        print(f"SHARPE: {is_d.get('sharpe')}")
        print(f"FITNESS: {is_d.get('fitness')}")
        print(f"TURNOVER: {is_d.get('turnover')}")
        print(f"MARGIN (bps): {(is_d.get('margin') or 0) * 10000}")
        print("CHECKS:")
        for c in is_d.get("checks", []):
            print(f"  - {c.get('name')}: {c.get('result')} (value={c.get('value')}, limit={c.get('limit')})")
        if "self_correlation" in alpha:
            sc = alpha["self_correlation"]
            if isinstance(sc, dict):
                print(f"SELF CORRELATION: min={sc.get('min')}, max={sc.get('max')}")
            else:
                print(f"SELF CORRELATION: {sc}")
        print("===============================\n")
