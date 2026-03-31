"""
ancile_shadow_agent.py — Autonomous Social Agent
Monitors Ancile core for real threats and posts to Telegram + Twitter.
Uses Claude API for intelligent tweet generation.
"""

import time
import requests
import asyncio
import os
from dotenv import load_dotenv
import anthropic

load_dotenv()

# ============================================================
# CREDENTIALS
# ============================================================
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID  = os.getenv("TELEGRAM_CHAT_ID", "")
X_API_KEY         = os.getenv("X_API_KEY", "")
X_API_SECRET      = os.getenv("X_API_SECRET", "")
X_ACCESS_TOKEN    = os.getenv("X_ACCESS_TOKEN", "")
X_ACCESS_SECRET   = os.getenv("X_ACCESS_SECRET", "")
CORE_API          = "http://127.0.0.1:5000"

# ============================================================
# POST FREQUENCY CONTROLS
# ============================================================
ROUTINE_POST_INTERVAL = 3600    # routine update every 1 hour
THREAT_COOLDOWN       = 300     # max 1 threat alert per 5 min
STATS_POST_INTERVAL   = 21600   # stats summary every 6 hours

# ============================================================
# CLAUDE PERSONALITY
# ============================================================
SYSTEM_PROMPT = """
You are 'Ancile Shadow', an autonomous security node watching Solana Mainnet.
You post updates for the Ancile Protocol community.
Rules:
- Always under 240 characters
- Always include $ANCL and at least one hashtag like #Solana #DePIN #Web3Security
- Tone: technical, confident, slightly degen, community-focused
- Use relevant emojis: 🛡️ 🚨 🟢 📡 ⚠️ 🔍
- Never make up data — only use numbers provided to you
- No hashtag spam — max 3 hashtags per tweet
"""

# ============================================================
# CLAUDE TWEET WRITER
# ============================================================
def write_tweet(event_type: str, data: dict) -> str:
    prompts = {
        "threat_detected": (
            f"Write an urgent tweet. A CRITICAL security threat was detected on Solana Mainnet.\n"
            f"Event: {data.get('current_task', 'Anomaly detected')}\n"
            f"Location: {data.get('location', 'SOL-MAINNET')}\n"
            f"The Ancile shield is active and responding."
        ),
        "threat_cleared": (
            "Write a tweet. The Ancile node just neutralized a threat. "
            "Everything is back to STABLE. The shield held."
        ),
        "routine_update": (
            f"Write a routine status tweet.\n"
            f"Scans completed: {data.get('total_scanned', 0)}\n"
            f"Threats blocked: {data.get('threats_blocked', 0)}\n"
            f"Status: All systems nominal."
        ),
        "stats_milestone": (
            f"Write a milestone celebration tweet.\n"
            f"Total scans: {data.get('total_scanned', 0)}\n"
            f"Total stakers: {data.get('total_stakers', 0)}\n"
            f"Total ANCL staked: {data.get('total_staked', 0)}\n"
            f"The protocol keeps growing."
        ),
    }

    # Try Claude API first
    try:
        client  = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompts.get(event_type, prompts["routine_update"])}]
        )
        tweet = message.content[0].text.strip()
        # Strip quotes if Claude wrapped it
        tweet = tweet.strip('"').strip("'")
        return tweet[:270] + "..." if len(tweet) > 270 else tweet

    except Exception as e:
        print(f"  ⚠️ Claude API error: {e} — using fallback")

    # Fallback templates (no API needed)
    fallbacks = {
        "threat_detected": (
            f"🚨 ANCILE ALERT: {data.get('current_task', 'Anomaly on Solana')} "
            f"| Shield active. $ANCL #Solana #DePIN"
        ),
        "threat_cleared": (
            "✅ Threat neutralized. Ancile shield held. Back to green. 🛡️ $ANCL #Solana"
        ),
        "routine_update": (
            f"📡 ANCILE NODE: {data.get('total_scanned', 0)} wallets scanned | "
            f"{data.get('threats_blocked', 0)} threats blocked | "
            f"All systems nominal 🟢 $ANCL #Solana"
        ),
        "stats_milestone": (
            f"🎯 {data.get('total_scanned', 0)} scans | "
            f"{data.get('total_stakers', 0)} stakers | "
            f"The divine shield grows stronger 🛡️ $ANCL #Solana"
        ),
    }
    return fallbacks.get(event_type, "🛡️ Ancile Protocol node active. $ANCL #Solana")

# ============================================================
# CORE API HELPERS
# ============================================================
def get_core_status() -> dict:
    try:
        return requests.get(CORE_API, timeout=5).json()
    except:
        return {}

def get_global_stats() -> dict:
    try:
        return requests.get(f"{CORE_API}/stats", timeout=5).json()
    except:
        return {}

def get_recent_threats() -> list:
    try:
        return requests.get(f"{CORE_API}/threats", timeout=5).json().get("recent_threats", [])
    except:
        return []

# ============================================================
# POSTING FUNCTIONS
# ============================================================
async def post_telegram(message: str):
    if not TELEGRAM_TOKEN or "your_" in TELEGRAM_TOKEN:
        print("  ⚠️ Telegram not configured")
        return
    try:
        from telegram import Bot
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        print("  ✅ Telegram sent")
    except Exception as e:
        print(f"  ❌ Telegram: {e}")

def post_twitter(message: str):
    if not X_API_KEY or "your_" in X_API_KEY:
        print("  ⚠️ Twitter not configured")
        return
    try:
        import tweepy
        client = tweepy.Client(
            consumer_key=X_API_KEY,
            consumer_secret=X_API_SECRET,
            access_token=X_ACCESS_TOKEN,
            access_token_secret=X_ACCESS_SECRET
        )
        client.create_tweet(text=message)
        print("  ✅ Twitter posted")
    except Exception as e:
        print(f"  ❌ Twitter: {e}")

async def broadcast(message: str):
    print(f"\n[🐦 SHADOW]: {message}\n")
    await post_telegram(message)
    post_twitter(message)

# ============================================================
# MAIN LOOP
# ============================================================
async def main():
    print("🕵️  ANCILE SHADOW AGENT STARTING...")
    print(f"   Claude API : {'✅ configured' if ANTHROPIC_API_KEY and 'your_' not in ANTHROPIC_API_KEY else '⚠️ not set'}")
    print(f"   Telegram   : {'✅ configured' if TELEGRAM_TOKEN and 'your_' not in TELEGRAM_TOKEN else '⚠️ not set'}")
    print(f"   Twitter    : {'✅ configured' if X_API_KEY and 'your_' not in X_API_KEY else '⚠️ not set'}")

    last_threat_level = "STABLE"
    last_routine_post = 0
    last_stats_post   = 0
    last_threat_post  = 0

    while True:
        now       = time.time()
        core_data = get_core_status()

        if not core_data:
            print("⚠️  Cannot reach Core — is ancile_core.py running?")
            await asyncio.sleep(15)
            continue

        current_threat = core_data.get("threat_level", "STABLE")

        # 1. Threat detected
        if current_threat == "CRITICAL" and last_threat_level != "CRITICAL":
            if now - last_threat_post > THREAT_COOLDOWN:
                print("🚨 NEW THREAT — alerting community...")
                tweet = write_tweet("threat_detected", core_data)
                await broadcast(tweet)
                last_threat_post = now

        # 2. Threat cleared
        elif last_threat_level == "CRITICAL" and current_threat == "STABLE":
            print("✅ THREAT CLEARED — notifying community...")
            tweet = write_tweet("threat_cleared", core_data)
            await broadcast(tweet)

        last_threat_level = current_threat

        # 3. Routine update
        if now - last_routine_post > ROUTINE_POST_INTERVAL:
            stats = get_global_stats()
            tweet = write_tweet("routine_update", {**core_data, **stats})
            await broadcast(tweet)
            last_routine_post = now

        # 4. Stats summary
        if now - last_stats_post > STATS_POST_INTERVAL:
            stats = get_global_stats()
            tweet = write_tweet("stats_milestone", stats)
            await broadcast(tweet)
            last_stats_post = now

        # 5. Console log
        threats = get_recent_threats()
        if threats:
            latest = threats[-1]
            addr   = latest.get('address', latest.get('program', ''))[:12]
            level  = latest.get('level', latest.get('risk', '?'))
            print(f"📋 Latest: [{latest.get('time')}] {addr}... — {level}")

        print(f"💓 Heartbeat | Threat: {current_threat} | Scans: {core_data.get('total_scanned', 0)}")
        await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())
