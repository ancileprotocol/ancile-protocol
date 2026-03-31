"""
ancile_core.py — Ancile Protocol Backend
Real threat detection + on-chain staking verification + automated payouts
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import threading
import time
import requests
import json
import os
from dotenv import load_dotenv
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solana.rpc.api import Client

load_dotenv()

app  = Flask(__name__)
CORS(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

# ============================================================
# CONFIGURATION
# ============================================================
PAYER_PRIVATE_KEY = os.getenv("PAYER_PRIVATE_KEY", "")
TOKEN_MINT        = os.getenv("TOKEN_MINT_ADDRESS", "HqYZfwyjjcLaGAFfhjnKjXbqZMZWrwXU8fyEP36Wpump")
TOKEN_DECIMALS    = int(os.getenv("TOKEN_DECIMALS", "6"))
RPC_URL           = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")
VAULT_ADDRESS     = os.getenv("STAKING_VAULT_ADDRESS", "8DafGReeupxLQQa5YXSnwtavWExPZMFK8cCeXtdJz1fg")
PAYOUT_INTERVAL   = int(os.getenv("PAYOUT_INTERVAL", "43200"))
MIN_PAYOUT        = float(os.getenv("MIN_PAYOUT", "50.0"))

TIERS = {
    "Scout":    {"min": 0,      "apy": 0.05},
    "Guardian": {"min": 10000,  "apy": 0.12},
    "Titan":    {"min": 100000, "apy": 0.25},
}

WATCHLIST = [
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",
]

# ============================================================
# DATABASE
# ============================================================
STATS_FILE   = "node_stats.json"
STAKERS_FILE = "stakers.json"
THREATS_FILE = "threat_log.json"

def load_json(filename, default):
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except:
            pass
    return default

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

STAKERS_DB = load_json(STAKERS_FILE, {})
REAL_STATS  = load_json(STATS_FILE, {"total_scans": 0, "threats_detected": 0, "total_staked": 0})
THREAT_LOG  = load_json(THREATS_FILE, [])

# migrate old key if present
if "threats_blocked" in REAL_STATS:
    REAL_STATS["threats_detected"] = REAL_STATS.pop("threats_blocked")
    save_json(STATS_FILE, REAL_STATS)

CURRENT_STATE = {
    "threat_level": "STABLE",
    "current_task": "Monitoring Solana Mainnet",
    "location":     "SOL-MAINNET",
    "last_threat":  None,
    "uptime_start": time.time()
}

# ============================================================
# SOLANA CLIENT
# ============================================================
try:
    solana_client = Client(RPC_URL)
    if PAYER_PRIVATE_KEY and "your_" not in PAYER_PRIVATE_KEY:
        payer_keypair = Keypair.from_base58_string(PAYER_PRIVATE_KEY)
        print(f"✅ Payout wallet: {payer_keypair.pubkey()}")
    else:
        payer_keypair = None
        print("⚠️  Payout disabled — add PAYER_PRIVATE_KEY to .env")
except Exception as e:
    payer_keypair = None
    print(f"⚠️  Solana client error: {e}")

# ============================================================
# ON-CHAIN STAKING VERIFICATION
# ============================================================
def verify_stake_onchain(user_wallet, claimed_amount):
    try:
        vault_pk = Pubkey.from_string(VAULT_ADDRESS)
        sigs     = solana_client.get_signatures_for_address(vault_pk, limit=50)

        if not sigs.value:
            return {"verified": False, "reason": "No transactions on vault yet"}

        for sig in sigs.value:
            try:
                tx = requests.post(RPC_URL, json={
                    "jsonrpc": "2.0", "id": 1,
                    "method": "getTransaction",
                    "params": [str(sig.signature), {
                        "encoding": "jsonParsed",
                        "maxSupportedTransactionVersion": 0
                    }]
                }, timeout=8).json()

                result = tx.get("result", {})
                if not result:
                    continue

                pre      = result.get("meta", {}).get("preTokenBalances", [])
                post     = result.get("meta", {}).get("postTokenBalances", [])
                accs     = result.get("transaction", {}).get("message", {}).get("accountKeys", [])
                acc_strs = [str(a) if isinstance(a, dict) else a for a in accs]

                for p in post:
                    for b in pre:
                        if p.get("accountIndex") != b.get("accountIndex"):
                            continue
                        if p.get("mint") != TOKEN_MINT:
                            continue
                        pre_amt  = float(b.get("uiTokenAmount", {}).get("uiAmount") or 0)
                        post_amt = float(p.get("uiTokenAmount", {}).get("uiAmount") or 0)
                        diff     = post_amt - pre_amt
                        if user_wallet in acc_strs and diff >= claimed_amount * 0.99:
                            return {"verified": True, "amount": diff, "signature": str(sig.signature)}
            except:
                continue

        return {"verified": False, "reason": f"No matching deposit found. Send ANCL to {VAULT_ADDRESS} first."}

    except Exception as e:
        return {"verified": False, "reason": str(e)}

# ============================================================
# PAYOUT ENGINE
# ============================================================
def execute_payout(user_wallet, amount):
    if not payer_keypair:
        return False, "Payout wallet not configured"
    try:
        import base64
        from solders.transaction import VersionedTransaction

        USDC_MINT  = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        amount_raw = int(amount * (10 ** TOKEN_DECIMALS))

        quote = requests.get(
            f"https://quote-api.jup.ag/v6/quote"
            f"?inputMint={TOKEN_MINT}&outputMint={USDC_MINT}"
            f"&amount={amount_raw}&slippageBps=50",
            timeout=10
        ).json()

        if "error" in quote:
            return False, f"Quote error: {quote['error']}"

        swap = requests.post("https://quote-api.jup.ag/v6/swap", json={
            "quoteResponse":             quote,
            "userPublicKey":             str(payer_keypair.pubkey()),
            "wrapAndUnwrapSol":          True,
            "dynamicComputeUnitLimit":   True,
            "prioritizationFeeLamports": 1000
        }, timeout=10).json()

        if "swapTransaction" not in swap:
            return False, f"Swap error: {swap}"

        raw_tx    = base64.b64decode(swap["swapTransaction"])
        tx        = VersionedTransaction.from_bytes(raw_tx)
        signed    = payer_keypair.sign_message(bytes(tx.message))
        tx_signed = VersionedTransaction.populate(tx.message, [signed])
        result    = solana_client.send_raw_transaction(bytes(tx_signed))

        print(f"✅ PAYOUT: {amount} ANCL → {user_wallet[:8]} | TX: {result.value}")
        return True, str(result.value)

    except Exception as e:
        print(f"❌ PAYOUT ERROR: {e}")
        return False, str(e)

# ============================================================
# INTEREST CALCULATION
# ============================================================
def calculate_interest(user, data, now):
    last   = data.get("last_update", now)
    apy    = TIERS.get(data["tier"], TIERS["Scout"])["apy"]
    earned = data["balance"] * apy * ((now - last) / 31536000)
    data["rewards"]    += earned
    data["last_update"] = now

# ============================================================
# PAYROLL WORKER
# ============================================================
def payroll_worker():
    while True:
        if payer_keypair and STAKERS_DB:
            now = time.time()
            print(f"💰 Payroll: checking {len(STAKERS_DB)} stakers...")
            for user, data in STAKERS_DB.items():
                calculate_interest(user, data, now)
                if data["rewards"] >= MIN_PAYOUT:
                    ok, _ = execute_payout(user, data["rewards"])
                    if ok:
                        data["total_paid"] = data.get("total_paid", 0) + data["rewards"]
                        data["rewards"]    = 0
                        save_json(STAKERS_FILE, STAKERS_DB)
        time.sleep(PAYOUT_INTERVAL)

threading.Thread(target=payroll_worker, daemon=True).start()

# ============================================================
# THREAT MONITOR
# ============================================================
def monitor_threats():
    while True:
        try:
            for program in WATCHLIST:
                pk   = Pubkey.from_string(program)
                sigs = solana_client.get_signatures_for_address(pk, limit=5)
                if not sigs.value:
                    continue

                failed = sum(1 for s in sigs.value if s.err is not None)

                if failed >= 3:
                    CURRENT_STATE["threat_level"] = "CRITICAL"
                    CURRENT_STATE["current_task"] = f"High failure rate on {program[:8]}... — {failed}/5 txs failed"
                    CURRENT_STATE["location"]     = f"Program: {program[:12]}..."
                    CURRENT_STATE["last_threat"]  = time.time()
                    REAL_STATS["threats_detected"] += 1
                    save_json(STATS_FILE, REAL_STATS)

                    THREAT_LOG.append({
                        "time":    time.strftime("%Y-%m-%d %H:%M:%S"),
                        "program": program,
                        "failed":  failed,
                        "level":   "CRITICAL"
                    })
                    save_json(THREATS_FILE, THREAT_LOG[-100:])
                    print(f"🚨 THREAT DETECTED: {program[:8]} — {failed} failed txs")
                else:
                    last = CURRENT_STATE.get("last_threat")
                    if last is None or time.time() - last > 300:
                        CURRENT_STATE["threat_level"] = "STABLE"
                        CURRENT_STATE["current_task"] = f"Scanning {program[:12]}... — All clear"

        except Exception as e:
            print(f"⚠️ Monitor error: {e}")

        time.sleep(30)

threading.Thread(target=monitor_threats, daemon=True).start()

# ============================================================
# API ENDPOINTS
# ============================================================
@app.route('/', methods=['GET'])
def status():
    return jsonify({
        "status":            "ONLINE 🟢",
        "threat_level":      CURRENT_STATE["threat_level"],
        "current_task":      CURRENT_STATE["current_task"],
        "location":          CURRENT_STATE["location"],
        "total_scanned":     REAL_STATS["total_scans"],
        "threats_detected":  REAL_STATS["threats_detected"],
        "total_staked":      REAL_STATS.get("total_staked", 0),
        "payroll":           "AUTOMATED" if payer_keypair else "MANUAL",
        "uptime_seconds":    int(time.time() - CURRENT_STATE["uptime_start"]),
    })

@limiter.limit("10 per minute")
@app.route('/scan', methods=['POST', 'OPTIONS'])
def scan_wallet():
    
@app.route('/scan', methods=['POST', 'OPTIONS'])
def scan_wallet():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    body      = request.json or {}
    target    = body.get('address', '').strip()
    scan_type = body.get('type', 'wallet')

    if not target:
        return jsonify({"error": "No address provided"}), 400

    try:
        Pubkey.from_string(target)
    except:
        return jsonify({"error": "Invalid Solana address"}), 400

    from ancile_threat import full_scan
    print(f"🔍 SCAN [{scan_type}]: {target}")
    result = full_scan(target, scan_type)

    REAL_STATS["total_scans"] += 1
    if result["risk"] in ["HIGH", "CRITICAL"]:
        REAL_STATS["threats_detected"] += 1
        CURRENT_STATE["threat_level"]  = "CRITICAL"
        CURRENT_STATE["current_task"]  = f"Threat detected: {target[:8]}..."
        CURRENT_STATE["last_threat"]   = time.time()
        THREAT_LOG.append({
            "time":    time.strftime("%Y-%m-%d %H:%M:%S"),
            "address": target,
            "risk":    result["risk"],
            "threats": result["threats"]
        })
        save_json(THREATS_FILE, THREAT_LOG[-100:])

    save_json(STATS_FILE, REAL_STATS)

    return jsonify({
        "address":    target,
        "risk":       result["risk"],
        "safe":       result["safe"],
        "threats":    result["threats"],
        "checks_run": result["checks_run"],
        "scan_time":  result["scan_time_seconds"],
        "message":    "✅ All clear" if result["safe"] else f"🚨 {len(result['threats'])} threat(s) detected"
    })

@app.route('/stake', methods=['POST'])
def stake_tokens():
    body   = request.json or {}
    user   = body.get('wallet', '').strip()
    amount = float(body.get('amount', 0))

    if not user or amount <= 0:
        return jsonify({"error": "Invalid wallet or amount"}), 400

    verify = verify_stake_onchain(user, amount)
    if not verify["verified"]:
        return jsonify({
            "error":        "Stake not verified on-chain",
            "reason":       verify["reason"],
            "vault":        VAULT_ADDRESS,
            "instructions": f"Send {amount} ANCL to {VAULT_ADDRESS} then call /stake again"
        }), 400

    tier = "Scout"
    for name, info in sorted(TIERS.items(), key=lambda x: x[1]["min"], reverse=True):
        if amount >= info["min"]:
            tier = name
            break

    if user not in STAKERS_DB:
        STAKERS_DB[user] = {
            "balance": 0, "tier": tier,
            "rewards": 0, "last_update": time.time(),
            "total_paid": 0, "stake_tx": verify["signature"]
        }

    STAKERS_DB[user]["balance"] += verify["amount"]
    STAKERS_DB[user]["tier"]     = tier
    REAL_STATS["total_staked"]   = sum(s["balance"] for s in STAKERS_DB.values())

    save_json(STAKERS_FILE, STAKERS_DB)
    save_json(STATS_FILE, REAL_STATS)

    return jsonify({
        "status": "success",
        "tier":   tier,
        "staked": verify["amount"],
        "apy":    f"{TIERS[tier]['apy']*100:.0f}%",
        "tx":     verify["signature"]
    })

@app.route('/user_stats', methods=['POST'])
def user_stats():
    user = (request.json or {}).get('wallet', '')
    if user in STAKERS_DB:
        calculate_interest(user, STAKERS_DB[user], time.time())
        d = STAKERS_DB[user]
        return jsonify({
            "staked":     d["balance"],
            "rewards":    round(d["rewards"], 6),
            "tier":       d["tier"],
            "apy":        f"{TIERS[d['tier']]['apy']*100:.0f}%",
            "total_paid": d.get("total_paid", 0)
        })
    return jsonify({"staked": 0, "rewards": 0, "tier": "None"})

@app.route('/stats', methods=['GET'])
def global_stats():
    return jsonify({
        "total_scans":      REAL_STATS["total_scans"],
        "threats_detected": REAL_STATS["threats_detected"],
        "total_stakers":    len(STAKERS_DB),
        "total_staked":     REAL_STATS.get("total_staked", 0),
        "threat_level":     CURRENT_STATE["threat_level"]
    })

@app.route('/threats', methods=['GET'])
def get_threats():
    return jsonify({
        "recent_threats": THREAT_LOG[-20:],
        "total_threats":  len(THREAT_LOG),
        "current_level":  CURRENT_STATE["threat_level"]
    })

if __name__ == '__main__':
    print("🛡️  ANCILE PROTOCOL CORE STARTING...")
    print(f"🏦  Vault:  {VAULT_ADDRESS}")
    print(f"🪙   Token: {TOKEN_MINT}")
    app.run(port=5000, debug=False)
