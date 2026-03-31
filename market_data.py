import requests
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("BIRDEYE_API_KEY")
HEADERS = {"X-API-KEY": API_KEY}

STABLES = {"USDT","USDC","BUSD","DAI","USDG","USD1","PYUSD","TUSD","USDD","WETH","CBBTC"}

def get_trending_tokens(limit=20):
    url = "https://public-api.birdeye.so/defi/tokenlist?sort_by=v24hUSD&sort_type=desc&offset=0&limit=50"
    r = requests.get(url, headers=HEADERS, timeout=10)
    tokens = r.json()["data"]["tokens"]
    filtered = []
    for t in tokens:
        if t.get("v24hUSD", 0) < 500_000:
            continue
        if t.get("liquidity", 0) < 100_000:
            continue
        if t.get("mc", 0) < 1_000_000:
            continue
        if t.get("symbol", "").upper() in STABLES:
            continue
        filtered.append({
            "address": t["address"],
            "symbol":  t.get("symbol", "???"),
            "price":   t.get("price", 0),
            "volume":  t.get("v24hUSD", 0),
            "mc":      t.get("mc", 0),
        })
        if len(filtered) >= limit:
            break
    return filtered

def get_token_stats(token_address):
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
        r = requests.get(url, timeout=10)
        data = r.json()
        pairs = data.get("pairs", [])
        if not pairs:
            return None
        sol_pairs = [p for p in pairs if p.get("chainId") == "solana"]
        if not sol_pairs:
            return None
        pair = sorted(sol_pairs, key=lambda x: x.get("liquidity", {}).get("usd", 0), reverse=True)[0]
        changes = pair.get("priceChange", {})
        volume  = pair.get("volume", {})
        return {
            "price":     float(pair.get("priceUsd", 0)),
            "change5m":  float(changes.get("m5", 0)),
            "change1h":  float(changes.get("h1", 0)),
            "change6h":  float(changes.get("h6", 0)),
            "change24h": float(changes.get("h24", 0)),
            "vol1h":     float(volume.get("h1", 0)),
            "liquidity": float(pair.get("liquidity", {}).get("usd", 0)),
        }
    except Exception as e:
        print(f"  [SKIP] {token_address[:8]}: {e}")
        return None

def get_price(token_address):
    url = f"https://public-api.birdeye.so/defi/price?address={token_address}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    return r.json()["data"]["value"]
