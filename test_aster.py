import json, requests

BASE = "https://medisvc.asterhealth.com/vault/v1"
H = {"application-id": "com.asterdm.patient",
     "content-type": "application/json; charset=UTF-8",
     "accept-encoding": "gzip"}

def probe(label, path, params=None):
    url = f"{BASE}/{path}"
    print("\n" + "="*55)
    print(f"TEST: {label}\n  {url} params={params}")
    try:
        r = requests.get(url, headers=H, params=params, timeout=30)
    except Exception as e:
        print("  ERROR:", e); return None
    print("  Status:", r.status_code)
    if r.status_code != 200:
        print("  Body:", r.text[:300]); return None
    try:
        d = r.json()
    except Exception:
        print("  Not JSON:", r.text[:300]); return None
    if isinstance(d, dict):
        print("  Keys:", list(d.keys()))
        for k in ("data","results","items","doctors"):
            if isinstance(d.get(k), list):
                print(f"  '{k}' has {len(d[k])} items")
                if d[k]: print("  Fields:", list(d[k][0].keys()))
                break
        for k in d:
            if any(w in k.lower() for w in ("total","count","page")):
                print(f"  {k}: {d[k]}")
    elif isinstance(d, list):
        print("  List of", len(d))
        if d: print("  Fields:", list(d[0].keys()))
    return d

d = probe("Doctors, no filter", "doctor", {"page":1,"limit":10})
probe("Doctors, limit=100", "doctor", {"page":1,"limit":100})
for p in ("speciality","specialities","specialty","specialties","department","departments"):
    probe(f"/{p}", p, {"page":1,"limit":100})
for p in ("hospital","hospitals","branch","branches","facility","location","locations"):
    probe(f"/{p}", p, {"page":1,"limit":100})

if d:
    json.dump(d, open("aster_probe_doctors.json","w",encoding="utf-8"), indent=2, ensure_ascii=False)
    print("\nSaved aster_probe_doctors.json")
