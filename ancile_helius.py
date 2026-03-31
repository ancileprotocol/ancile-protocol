"""
ancile_helius.py — Real-time Solana monitoring via Helius webhooks
Replaces the 30-second polling with instant push notifications
"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()

HELIUS_API_KEY  = os.getenv("HELIUS_API_KEY", "")
WEBHOOK_URL     = os.getenv("CLOUDFLARE_URL", "") + "/webhook"

WATCHLIST = [
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",
]

def register_webhook():
    """Register Helius webhook to watch key Solana programs"""
    url  = f"https://api.helius.xyz/v0/webhooks?api-key={HELIUS_API_KEY}"
    body = {
        "webhookURL":       WEBHOOK_URL,
        "transactionTypes": ["ANY"],
        "accountAddresses": WATCHLIST,
        "webhookType":      "enhanced",
    }
    resp = requests.post(url, json=body)
    if resp.status_code == 200:
        data = resp.json()
        print(f"✅ Helius webhook registered: {data.get('webhookID')}")
        return data.get("webhookID")
    else:
        print(f"❌ Helius error: {resp.text}")
        return None

def list_webhooks():
    url  = f"https://api.helius.xyz/v0/webhooks?api-key={HELIUS_API_KEY}"
    resp = requests.get(url)
    return resp.json()

if __name__ == "__main__":
    print("Registering Helius webhook...")
    print(f"Webhook target: {WEBHOOK_URL}")
    wid = register_webhook()
    if wid:
        print(f"Done. Webhook ID: {wid}")
        print("Helius will now push alerts to your /webhook endpoint instantly.")
