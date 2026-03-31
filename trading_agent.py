import time
import schedule
from colorama import Fore, Style, init
from market_data import get_trending_tokens, get_price, get_token_stats
from strategy import get_signal
from executor import swap_via_jupiter, get_wallet_address

init(autoreset=True)

# ============================================================
# CONFIGURATION — controlled aggression mode
# ============================================================
USDC_MINT        = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
MAX_TRADE_USD    = 10
DAILY_LOSS_LIMIT = 40
MAX_OPEN_TRADES  = 3
TRADE_INTERVAL   = 3
STOP_LOSS_PCT    = 0.07
TAKE_PROFIT_PCT  = 0.25
# ============================================================

daily_loss = 0
positions  = {}

def log(color, label, msg):
    print(f"{color}[{label}]{Style.RESET_ALL} {msg}")

def check_open_positions():
    global daily_loss, positions

    for addr, pos in list(positions.items()):
        try:
            current_price = get_price(addr)
            entry         = pos["entry_price"]
            change_pct    = (current_price - entry) / entry

            log(Fore.WHITE, pos["symbol"],
                f"Entry ${entry:.4f} | Now ${current_price:.4f} | {change_pct*100:+.1f}%")

            should_exit = False
            reason      = ""

            if change_pct <= -STOP_LOSS_PCT:
                should_exit = True
                reason = f"STOP LOSS ({change_pct*100:.1f}%)"
            elif change_pct >= TAKE_PROFIT_PCT:
                should_exit = True
                reason = f"TAKE PROFIT (+{change_pct*100:.1f}%)"

            if should_exit:
                log(Fore.MAGENTA, "EXIT", f"{pos['symbol']} — {reason}")
                amount_lamports = int((pos["amount_usd"] / current_price) * 1e9)
                success = swap_via_jupiter(addr, USDC_MINT, amount_lamports)
                if success:
                    pnl = pos["amount_usd"] * change_pct
                    daily_loss += min(0, pnl)
                    del positions[addr]
                    log(Fore.YELLOW, "PNL",
                        f"{pos['symbol']} closed. PnL: ${pnl:+.2f} | Daily loss: ${abs(daily_loss):.2f}")

        except Exception as e:
            log(Fore.RED, "ERROR", f"Position check {pos.get('symbol', '?')}: {e}")

def scan_and_trade():
    global positions

    if len(positions) >= MAX_OPEN_TRADES:
        log(Fore.YELLOW, "FULL", f"Holding {MAX_OPEN_TRADES} positions. Skipping scan.")
        return

    log(Fore.CYAN, "SCAN", "Fetching trending tokens...")
    tokens = get_trending_tokens(limit=50)
    log(Fore.CYAN, "SCAN", f"Found {len(tokens)} qualifying tokens")

    for token in tokens:
        addr   = token["address"]
        symbol = token["symbol"]

        if addr in positions:
            continue
        if addr == USDC_MINT:
            continue

        try:
            stats  = get_token_stats(addr)
            signal = get_signal(stats)

            log(Fore.WHITE, symbol, f"Signal: {signal}")

            if signal == "BUY":
                log(Fore.GREEN, "BUY",
                    f"{symbol} | Vol: ${token['volume']:,.0f} | MC: ${token['mc']:,.0f}")

                success = swap_via_jupiter(
                    USDC_MINT, addr,
                    int(MAX_TRADE_USD * 1e6)
                )

                if success:
                    positions[addr] = {
                        "symbol":      symbol,
                        "entry_price": token["price"],
                        "amount_usd":  MAX_TRADE_USD,
                    }
                    log(Fore.GREEN, "OPENED", f"{symbol} at ${token['price']:.6f}")

                if len(positions) >= MAX_OPEN_TRADES:
                    break

        except Exception as e:
            log(Fore.RED, "ERROR", f"{symbol}: {e}")

def run_agent():
    global daily_loss

    if daily_loss >= DAILY_LOSS_LIMIT:
        log(Fore.RED, "HALTED",
            f"Daily loss limit ${DAILY_LOSS_LIMIT} reached. Stopping for today.")
        return

    print("\n" + "═" * 55)
    log(Fore.CYAN, "AGENT", f"Wallet: {get_wallet_address()}")
    log(Fore.CYAN, "AGENT",
        f"Open positions: {len(positions)}/{MAX_OPEN_TRADES} | Daily loss: ${abs(daily_loss):.2f}")

    check_open_positions()
    scan_and_trade()

if __name__ == "__main__":
    print(Fore.CYAN + "\n🤖 Solana Multi-Token Agent starting...\n")
    run_agent()
    schedule.every(TRADE_INTERVAL).minutes.do(run_agent)
    while True:
        schedule.run_pending()
        time.sleep(30)
