import requests
import json
import os
import base64
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solana.rpc.api import Client
from dotenv import load_dotenv

load_dotenv()

RPC_URL     = os.getenv("RPC_URL")
PRIVATE_KEY = json.loads(os.getenv("TRADING_WALLET_PRIVATE_KEY"))

def get_keypair():
    return Keypair.from_bytes(bytes(PRIVATE_KEY))

def get_wallet_address():
    return str(get_keypair().pubkey())

def swap_via_jupiter(input_mint, output_mint, amount, slippage_bps=50):
    try:
        wallet = get_wallet_address()

        quote_url = (
            f"https://quote-api.jup.ag/v6/quote"
            f"?inputMint={input_mint}"
            f"&outputMint={output_mint}"
            f"&amount={amount}"
            f"&slippageBps={slippage_bps}"
        )
        quote = requests.get(quote_url, timeout=10).json()

        if "error" in quote:
            print(f"  [ERROR] Quote: {quote['error']}")
            return False

        swap_resp = requests.post(
            "https://quote-api.jup.ag/v6/swap",
            json={
                "quoteResponse": quote,
                "userPublicKey": wallet,
                "wrapAndUnwrapSol": True,
                "dynamicComputeUnitLimit": True,
                "prioritizationFeeLamports": 1000,
            },
            timeout=10,
        ).json()

        if "swapTransaction" not in swap_resp:
            print(f"  [ERROR] Swap: {swap_resp}")
            return False

        keypair   = get_keypair()
        client    = Client(RPC_URL)
        raw_tx    = base64.b64decode(swap_resp["swapTransaction"])
        tx        = VersionedTransaction.from_bytes(raw_tx)
        signed    = keypair.sign_message(bytes(tx.message))
        tx_signed = VersionedTransaction.populate(tx.message, [signed])
        result    = client.send_raw_transaction(bytes(tx_signed))

        print(f"  [TX] https://solscan.io/tx/{result.value}")
        return True

    except Exception as e:
        print(f"  [ERROR] Executor: {e}")
        return False
