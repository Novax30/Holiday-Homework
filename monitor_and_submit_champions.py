#!/usr/bin/env python3
import requests, time, os, sys

env = {}
with open('/Users/nova/Documents/ALPAHA/.env') as f:
    for line in f:
        if '=' in line:
            k, v = line.strip().split('=', 1)
            env[k.strip('\"\' ')] = v.strip('\"\' ')

s = requests.Session()
s.auth = (env.get('BRAIN_EMAIL'), env.get('BRAIN_PASSWORD'))
r = s.post('https://api.worldquantbrain.com/authentication')
if r.status_code not in [200, 201]:
    print('Auth failed')
    sys.exit(1)

sims = [
    ('Sentiment_Buzz_lb20', 'https://api.worldquantbrain.com/simulations/17nT2rcqB4j38Mn88IomBvE'),
    ('Variance_Risk_Premium_Spread', 'https://api.worldquantbrain.com/simulations/2Jakklb9Y4uwc5zioec7o6H'),
    ('Intraday_Candle_Smoothed_Decay8', 'https://api.worldquantbrain.com/simulations/2hhnzTbKg4vH8N856MHIe39')
]

submitted = 0
for name, url in sims:
    print(f"\n==========================================")
    print(f"Monitoring: {name}")
    print(f"URL: {url}")
    print(f"==========================================")
    
    alpha_id = None
    for attempt in range(60):
        try:
            resp = s.get(url, timeout=15)
            d = resp.json()
            st = d.get('status')
            prog = d.get('progress')
            if st in ['COMPLETED', 'COMPLETE', 'WARNING']:
                alpha_id = d.get('alpha')
                print(f"[{name}] Finished simulation! Alpha ID: {alpha_id}")
                break
            elif st == 'ERROR':
                print(f"[{name}] ERROR: {d.get('message')}")
                break
            else:
                if attempt % 3 == 0:
                    print(f"[{name}] Status: {st}, Progress: {prog}")
                time.sleep(3)
        except Exception as e:
            print(f"Poll error: {e}")
            time.sleep(3)

    if not alpha_id:
        continue

    # Fetch alpha details
    ar = s.get(f'https://api.worldquantbrain.com/alphas/{alpha_id}', timeout=15)
    ad = ar.json()
    is_res = ad.get('is', {}) or {}
    checks = is_res.get('checks', []) or []
    fails = [c.get('name') for c in checks if c.get('result') == 'FAIL']
    sharpe = is_res.get('sharpe') or 0
    fit = is_res.get('fitness') or 0
    turn = (is_res.get('turnover') or 0) * 100
    margin = (is_res.get('margin') or 0) * 10000

    print(f"\n[{name}] Performance Evaluation:")
    print(f"  Sharpe: {sharpe:.2f} | Fitness: {fit:.2f} | Turnover: {turn:.1f}% | Margin: {margin:.1f}bps")
    print(f"  Fails: {fails}")
    for c in checks:
        print(f"    - {c.get('name')}: {c.get('result')} (value={c.get('value')}, limit={c.get('limit')})")

    if not fails and sharpe >= 1.25 and fit >= 1.00:
        print(f"\n[{name}] 100% Passed all checks! Checking self-correlation against OS portfolio...")
        recs = []
        max_corr = 0.0
        for _ in range(15):
            time.sleep(2)
            corr_resp = s.get(f'https://api.worldquantbrain.com/alphas/{alpha_id}/correlations/self', timeout=20)
            if corr_resp.status_code == 200:
                try:
                    recs = corr_resp.json().get('records', [])
                    for r in recs:
                        cval = abs(r[5] if len(r) > 5 else 0)
                        if cval > max_corr: max_corr = cval
                        print(f"    vs {r[0]} ({r[1]}): {r[5]:.4f}")
                    break
                except:
                    pass

        print(f"  Max Self-Correlation: {max_corr:.4f} across {len(recs)} OS alphas (Hurdle < 0.70)")

        if max_corr < 0.70:
            badge_color = 'PURPLE' if fit >= 2.0 or sharpe >= 2.0 else 'BLUE'
            s.patch(f'https://api.worldquantbrain.com/alphas/{alpha_id}', json={'color': badge_color, 'name': name}, timeout=15)
            print(f"\n>>> SUBMITTING {alpha_id} ({name}) TO OUT-OF-SAMPLE! <<<")
            sub_resp = s.post(f'https://api.worldquantbrain.com/alphas/{alpha_id}/submit', timeout=25)
            print(f"Submit HTTP status: {sub_resp.status_code}")
            if sub_resp.status_code in [200, 201]:
                submitted += 1
                print(f"🎉 SUCCESS! Alpha {alpha_id} submitted to Out-of-Sample! ({submitted} submitted this run) 🎉")
        else:
            print(f"[{name}] Correlation {max_corr:.4f} >= 0.70 hurdle. Not submitted.")
    else:
        print(f"[{name}] Institutional checks did not pass. Not submitted.")

print(f"\n==========================================")
print(f"Batch completed. Total new submissions: {submitted}")
print(f"==========================================")
