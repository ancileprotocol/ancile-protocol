import requests
import time
import os
from solana.rpc.api import Client
from solders.pubkey import Pubkey

RPC_URL       = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")
solana_client = Client(RPC_URL)

KNOWN_DRAINERS = {
    "HN7cABqLq46Es1jh92dQQisAq662SmxELLLsHHe4YWrH": "Known wallet drainer",
    "7sDKtmxnHVDdPKRdVVFRWEBGE2rAFJULnEMKmZt8Hfx":  "Phishing contract",
    "9BVcYqEQxyccuwznvxXqDkSJFavvTyheiTYk231T1A8S":  "Rug pull contract",
    "AUoE4FHZGcmHEHUaLgCBXEsJDjp52LVZA1tBvpMwGwA4": "Flash loan exploit",
    "FsJ3A3u2vn5cTVofAjvy6y5kwABJAqYWpe4975bi76Bg":  "Known scam token mint",
}

def check_blacklist(address):
    if address in KNOWN_DRAINERS:
        return {"source": "blacklist", "risk": "CRITICAL", "reason": KNOWN_DRAINERS[address]}
    return {"source": "blacklist", "risk": "LOW"}

def check_blowfish(address):
    try:
        resp = requests.post(
            "https://solana.api.blowfish.xyz/v0/solana/mainnet/scan/address",
            json={"address": address},
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        if resp.status_code == 200:
            data     = resp.json()
            warnings = data.get("warnings", [])
            return {"source": "blowfish", "warnings": warnings, "risk": "HIGH" if warnings else "LOW"}
    except:
        pass
    return {"source": "blowfish", "warnings": [], "risk": "UNKNOWN"}

def check_solanafm(address):
    try:
        resp = requests.get(f"https://api.solana.fm/v1/accounts/{address}", timeout=5)
        if resp.status_code == 200:
            data   = resp.json()
            labels = data.get("result", {}).get("labels", [])
            bad    = [l for l in labels if any(s in l.lower() for s in ["scam","hack","exploit","drainer","phishing"])]
            if bad:
                return {"source": "solanafm", "risk": "HIGH", "labels": bad}
            return {"source": "solanafm", "risk": "LOW", "labels": labels}
    except:
        pass
    return {"source": "solanafm", "risk": "UNKNOWN"}

def analyze_token_mint(mint_address):
    threats = []
    risk    = "LOW"
    try:
        pubkey    = Pubkey.from_string(mint_address)
        mint_resp = requests.post(RPC_URL, json={
            "jsonrpc": "2.0", "id": 1,
            "method": "getAccountInfo",
            "params": [mint_address, {"encoding": "jsonParsed"}]
        }, timeout=5).json()

        info = mint_resp.get("result", {}).get("value", {}).get("data", {}).get("parsed", {}).get("info", {})

        if info.get("mintAuthority"):
            threats.append("Mint authority not renounced — devs can print tokens")
            risk = "MEDIUM"
        if info.get("freezeAuthority"):
            threats.append("Freeze authority active — devs can freeze your tokens")
            risk = "HIGH"

        supply_resp  = solana_client.get_token_supply(pubkey)
        largest_resp = solana_client.get_token_largest_accounts(pubkey)

        if supply_resp.value and largest_resp.value:
            total = float(supply_resp.value.amount)
            if total > 0 and largest_resp.value:
                top_pct = float(largest_resp.value[0].amount.amount) / total * 100
                if top_pct > 50:
                    threats.append(f"Top holder owns {top_pct:.1f}% of supply")
                    risk = "HIGH"
                elif top_pct > 30:
                    threats.append(f"High concentration: top holder {top_pct:.1f}%")
                    if risk == "LOW":
                        risk = "MEDIUM"
    except Exception as e:
        threats.append(f"Analysis error: {str(e)[:60]}")
    return {"source": "onchain_token", "risk": risk, "threats": threats}

def analyze_wallet_history(address):
    threats = []
    risk    = "LOW"
    try:
        pubkey = Pubkey.from_string(address)
        sigs   = solana_client.get_signatures_for_address(pubkey, limit=20)
        if not sigs.value:
            return {"source": "history", "risk": "LOW", "threats": []}

        failed = sum(1 for s in sigs.value if s.err is not None)
        total  = len(sigs.value)

        if total > 5 and failed / total > 0.5:
            threats.append(f"High failed tx rate: {failed}/{total} transactions failed")
            risk = "MEDIUM"

        for sig in sigs.value[:5]:
            try:
                tx   = requests.post(RPC_URL, json={
                    "jsonrpc": "2.0", "id": 1,
                    "method": "getTransaction",
                    "params": [str(sig.signature), {"encoding": "json", "maxSupportedTransactionVersion": 0}]
                }, timeout=5).json()
                accs = tx.get("result", {}).get("transaction", {}).get("message", {}).get("accountKeys", [])
                for acc in accs:
                    if acc in KNOWN_DRAINERS:
                        threats.append(f"Interacted with known drainer: {acc[:8]}...")
                        risk = "CRITICAL"
            except:
                continue
    except:
        pass
    return {"source": "history", "risk": risk, "threats": threats}

def full_scan(address, scan_type="wallet"):
    start   = time.time()
    results = []
    threats = []

    bl = check_blacklist(address)
    results.append(bl)
    if bl["risk"] == "CRITICAL":
        threats.append(bl.get("reason", "Known malicious address"))

    bf = check_blowfish(address)
    results.append(bf)
    for w in bf.get("warnings", []):
        threats.append(w.get("message", str(w)))

    sfm = check_solanafm(address)
    results.append(sfm)
    for l in sfm.get("labels", []):
        if any(s in l.lower() for s in ["scam","hack","exploit"]):
            threats.append(f"Labeled: {l}")

    if scan_type == "token":
        mint = analyze_token_mint(address)
        results.append(mint)
        threats.extend(mint.get("threats", []))
    else:
        hist = analyze_wallet_history(address)
        results.append(hist)
        threats.extend(hist.get("threats", []))

    levels    = [r.get("risk", "LOW") for r in results]
    final     = "CRITICAL" if "CRITICAL" in levels else "HIGH" if "HIGH" in levels else "MEDIUM" if "MEDIUM" in levels else "LOW"
    scan_time = round(time.time() - start, 2)

    return {
        "address": address, "risk": final,
        "threats": threats, "checks_run": len(results),
        "scan_time_seconds": scan_time,
        "safe": final in ["LOW", "UNKNOWN"]
    }
