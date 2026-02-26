"""Simple OpenAI-compatible chat test for Portal."""

import os
import requests

base = os.getenv("PORTAL_OPENAI_BASE", "http://localhost:8081/v1")
api_key = os.getenv("PORTAL_API_KEY", "")
headers = {"Content-Type": "application/json", "x-portal-user-id": "local-test-user"}
if api_key:
    headers["Authorization"] = f"Bearer {api_key}"

payload = {
    "model": "auto",
    "stream": False,
    "messages": [
        {"role": "system", "content": "You are concise."},
        {"role": "user", "content": "Say hello from Portal."},
    ],
}

resp = requests.post(f"{base}/chat/completions", headers=headers, json=payload, timeout=120)
print(resp.status_code)
print(resp.text)
