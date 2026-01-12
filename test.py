import os
import sys
import json
import requests
from dotenv import load_dotenv

load_dotenv()  # Load from .env file in root directory

BASE_URL = "https://api.helmholtz-blablador.fz-juelich.de"
API_KEY = os.getenv("BLABLADOR_API_KEY")

if not API_KEY:
    print("Missing env var BLABLADOR_API_KEY. Example:")
    print('  export BLABLADOR_API_KEY="YOUR_KEY_HERE"')
    sys.exit(2)

headers = {"Authorization": f"Bearer {API_KEY}"}

def pretty(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False)[:4000])

def request_json(method, url, **kwargs):
    r = requests.request(method, url, timeout=30, **kwargs)
    ct = r.headers.get("content-type", "")
    try:
        data = r.json() if "application/json" in ct else {"raw": r.text}
    except Exception:
        data = {"raw": r.text}
    return r.status_code, data

# 1) List models
print("1) Testing /v1/models ...")
status, data = request_json("GET", f"{BASE_URL}/v1/models", headers=headers)
print("Status:", status)
if status != 200:
    pretty(data)
    sys.exit(1)

models = [m.get("id") for m in data.get("data", []) if isinstance(m, dict)]
print("Models found (first 10):", models[:10])

# Pick a model (prefer Mistral/Mixtral if present)
model = models[0] if models else None

if not model:
    print("No models returned — unexpected.")
    sys.exit(1)

print("\nUsing model:", model)

# 2) Try chat/completions
print("\n2) Testing /v1/chat/completions ...")
chat_payload = {
    "model": model,
    "messages": [{"role": "user", "content": "What is AI?"}],
    "temperature": 0,
}
status, out = request_json(
    "POST",
    f"{BASE_URL}/v1/chat/completions",
    headers={**headers, "Content-Type": "application/json"},
    json=chat_payload,
)
print("Status:", status)
if status == 200:
    # best-effort extraction of text
    try:
        text = out["choices"][0]["message"]["content"]
    except Exception:
        text = None
    print("Model output:", repr(text) if text is not None else "(couldn't parse)")
else:
    print("chat/completions failed; response:")
    pretty(out)
    print("\n3) Trying /v1/completions as fallback ...")

    comp_payload = {
        "model": model,
        "prompt": "Reply with just: OK",
        "max_tokens": 5,
        "temperature": 0,
    }
    status2, out2 = request_json(
        "POST",
        f"{BASE_URL}/v1/completions",
        headers={**headers, "Content-Type": "application/json"},
        json=comp_payload,
    )
    print("Status:", status2)
    if status2 == 200:
        try:
            text2 = out2["choices"][0]["text"]
        except Exception:
            text2 = None
        print("Model output:", repr(text2) if text2 is not None else "(couldn't parse)")
    else:
        print("completions also failed; response:")
        pretty(out2)
        sys.exit(1)

print("\n✅ API key looks OK and generation endpoint works.")
