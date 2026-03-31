"""
ancile_bot.py — Ancile Protocol Telegram Bot
Commands:
/scan   — scan any wallet or token
/buy    — pre-buy token safety check
/sim    — simulate a transaction
/skill  — scan an AI agent skill/plugin URL
"""

import telebot
import requests
import anthropic
import os
import json
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN     = os.getenv("TELEGRAM_BOT_TOKEN", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
RAILWAY_API   = "https://ancile-protocol-production.up.railway.app"

bot    = telebot.TeleBot(BOT_TOKEN)
claude = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

# ============================================================
# HELPERS
# ============================================================

def risk_emoji(risk):
    return {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴", "CRITICAL": "🚨", "UNKNOWN": "⚪"}.get(risk, "⚪")

def call_scan_api(address, scan_type="wallet"):
    try:
        r = requests.post(
            f"{RAILWAY_API}/scan",
            json={"address": address, "type": scan_type},
            timeout=15
        )
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def ask_claude(prompt):
    try:
        msg = claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text.strip()
    except Exception as e:
        return f"Analysis unavailable: {e}"

def format_scan_result(result, address):
    if "error" in result:
        return f"❌ Scan error: {result['error']}"

    risk    = result.get("risk", "UNKNOWN")
    safe    = result.get("safe", True)
    threats = result.get("threats", [])
    emoji   = risk_emoji(risk)

    lines = [
        f"{emoji} *Ancile Scan Report*",
        f"`{address[:20]}...`",
        f"",
        f"*Risk Level:* `{risk}`",
        f"*Status:* {'✅ SAFE' if safe else '🚨 THREAT DETECTED'}",
        f"*Checks Run:* {result.get('checks_run', 0)}",
        f"*Scan Time:* {result.get('scan_time', 0)}s",
    ]

    if threats:
        lines.append(f"")
        lines.append(f"*Threats Found:*")
        for t in threats[:5]:
            lines.append(f"• {t}")

    lines.append(f"")
    lines.append(f"_Powered by Ancile Protocol_ 🛡️")
    return "\n".join(lines)

# ============================================================
# /start
# ============================================================
@bot.message_handler(commands=['start', 'help'])
def handle_start(message):
    text = """
🛡️ *Ancile Protocol — AI Security Shield*

Real-time Solana security scanner powered by AI.

*Commands:*
`/scan <address>` — Scan any wallet or token
`/buy <token_address>` — Pre-buy safety check
`/sim <transaction_data>` — Simulate a transaction
`/skill <url>` — Scan an AI agent skill/plugin

*Examples:*
`/scan HqYZfwyjjcLaGAFfhjnKjXbqZMZWrwXU8fyEP36Wpump`
`/buy DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`

_The divine shield for AI agents on Solana_ ✨
"""
    bot.reply_to(message, text, parse_mode="Markdown")

# ============================================================
# /scan — wallet or token scanner
# ============================================================
@bot.message_handler(commands=['scan'])
def handle_scan(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Usage: `/scan <solana_address>`", parse_mode="Markdown")
        return

    address = parts[1].strip()
    msg     = bot.reply_to(message, "🔍 Scanning... please wait")

    result  = call_scan_api(address, "wallet")
    report  = format_scan_result(result, address)

    # Ask Claude to add a plain English summary
    if result.get("threats"):
        summary = ask_claude(
            f"In 2 sentences, explain these Solana security threats to a non-technical user: "
            f"{', '.join(result['threats'][:3])}. Be direct and clear."
        )
        report += f"\n\n*AI Summary:* {summary}"

    bot.edit_message_text(
        report,
        message.chat.id,
        msg.message_id,
        parse_mode="Markdown"
    )

# ============================================================
# /buy — pre-buy token safety check
# ============================================================
@bot.message_handler(commands=['buy'])
def handle_buy(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Usage: `/buy <token_mint_address>`", parse_mode="Markdown")
        return

    address = parts[1].strip()
    msg     = bot.reply_to(message, "🔍 Running pre-buy safety check...")

    # Scan as token type for deeper analysis
    result  = call_scan_api(address, "token")
    risk    = result.get("risk", "UNKNOWN")
    threats = result.get("threats", [])
    emoji   = risk_emoji(risk)

    # Get DexScreener data
    dex_data = {}
    try:
        r = requests.get(
            f"https://api.dexscreener.com/latest/dex/tokens/{address}",
            timeout=8
        )
        pairs = r.json().get("pairs", [])
        if pairs:
            pair     = sorted(pairs, key=lambda x: x.get("liquidity", {}).get("usd", 0), reverse=True)[0]
            dex_data = {
                "price":     pair.get("priceUsd", "?"),
                "liquidity": pair.get("liquidity", {}).get("usd", 0),
                "volume24h": pair.get("volume", {}).get("h24", 0),
                "change24h": pair.get("priceChange", {}).get("h24", 0),
                "dex":       pair.get("dexId", "?"),
            }
    except:
        pass

    lines = [
        f"{emoji} *Pre-Buy Safety Report*",
        f"`{address[:20]}...`",
        f"",
        f"*Risk Level:* `{risk}`",
    ]

    if dex_data:
        lines += [
            f"",
            f"*Market Data:*",
            f"• Price: `${dex_data['price']}`",
            f"• Liquidity: `${float(dex_data['liquidity']):,.0f}`",
            f"• 24h Volume: `${float(dex_data['volume24h']):,.0f}`",
            f"• 24h Change: `{dex_data['change24h']:+.1f}%`",
            f"• DEX: `{dex_data['dex']}`",
        ]

    if threats:
        lines += [f"", f"*⚠️ Red Flags:*"]
        for t in threats[:5]:
            lines.append(f"• {t}")

    # Claude verdict
    verdict_prompt = (
        f"A user is about to buy a Solana token. "
        f"Risk level: {risk}. "
        f"Issues found: {threats if threats else 'none'}. "
        f"Liquidity: ${dex_data.get('liquidity', 0):,.0f}. "
        f"Give a 1-sentence buy/caution/avoid verdict. Be direct."
    )
    verdict = ask_claude(verdict_prompt)

    lines += [f"", f"*🤖 AI Verdict:* {verdict}"]
    lines.append(f"")
    lines.append(f"_Always DYOR. Not financial advice._ 🛡️")

    bot.edit_message_text(
        "\n".join(lines),
        message.chat.id,
        msg.message_id,
        parse_mode="Markdown"
    )

# ============================================================
# /sim — transaction simulator
# ============================================================
@bot.message_handler(commands=['sim'])
def handle_sim(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        help_text = (
            "Usage: `/sim <transaction_data>`\n\n"
            "Paste the raw transaction data, base58 encoded transaction, "
            "or describe what a dApp is asking you to sign.\n\n"
            "Example:\n"
            "`/sim The dApp is asking me to approve unlimited USDC spending to address ABC123`"
        )
        bot.reply_to(message, help_text, parse_mode="Markdown")
        return

    tx_data = parts[1].strip()
    msg     = bot.reply_to(message, "⚙️ Simulating transaction...")

    # Use Claude to analyze the transaction
    analysis = ask_claude(f"""
You are a Solana security expert. A user is about to sign this transaction or approval:

"{tx_data}"

Analyze it and respond with:
1. What this transaction ACTUALLY does in plain English
2. Risk level: SAFE / SUSPICIOUS / DANGEROUS
3. Specific red flags if any
4. Recommendation: SIGN / DO NOT SIGN / VERIFY FIRST

Be direct and clear. Format your response clearly.
""")

    # Determine risk emoji based on Claude's response
    if "DANGEROUS" in analysis.upper():
        emoji = "🚨"
    elif "SUSPICIOUS" in analysis.upper():
        emoji = "⚠️"
    else:
        emoji = "✅"

    report = f"""
{emoji} *Transaction Simulation Report*

*Input:* `{tx_data[:80]}{'...' if len(tx_data) > 80 else ''}`

{analysis}

_Ancile Protocol Transaction Simulator_ 🛡️
"""

    bot.edit_message_text(
        report,
        message.chat.id,
        msg.message_id,
        parse_mode="Markdown"
    )

# ============================================================
# /skill — AI agent skill/plugin scanner
# ============================================================
@bot.message_handler(commands=['skill'])
def handle_skill(message):
    parts = message.text.split()
    if len(parts) < 2:
        help_text = (
            "Usage: `/skill <url_or_package_name>`\n\n"
            "Scan any AI agent skill, plugin, or npm package "
            "before installing it.\n\n"
            "Examples:\n"
            "`/skill https://github.com/user/solana-skill`\n"
            "`/skill solana-wallet-tracker`"
        )
        bot.reply_to(message, help_text, parse_mode="Markdown")
        return

    target  = parts[1].strip()
    msg     = bot.reply_to(message, "🔍 Scanning AI skill/plugin...")

    # Fetch the skill content if it's a URL
    skill_content = ""
    if target.startswith("http"):
        try:
            r = requests.get(target, timeout=10)
            skill_content = r.text[:3000]
        except:
            skill_content = "Could not fetch URL content"
    else:
        skill_content = f"Package name: {target}"

    # Claude analyzes for malicious patterns
    analysis = ask_claude(f"""
You are a cybersecurity expert specializing in AI agent security.
Analyze this AI agent skill/plugin for malicious patterns:

Target: {target}
Content preview: {skill_content[:1000]}

Check for:
1. Keyloggers or credential theft
2. Suspicious network calls to unknown endpoints
3. File system access outside expected scope
4. Private key or seed phrase extraction
5. Obfuscated or encoded malicious code
6. Requests for excessive permissions

Respond with:
- SAFE / SUSPICIOUS / DANGEROUS verdict
- Specific concerns found
- Recommendation

Be direct and specific.
""")

    if "DANGEROUS" in analysis.upper():
        emoji = "🚨"
    elif "SUSPICIOUS" in analysis.upper():
        emoji = "⚠️"
    else:
        emoji = "✅"

    report = f"""
{emoji} *AI Skill Security Scan*

*Target:* `{target}`

{analysis}

_Ancile Protocol — Divine Shield for AI Agents_ 🛡️
"""

    bot.edit_message_text(
        report,
        message.chat.id,
        msg.message_id,
        parse_mode="Markdown"
    )

# ============================================================
# Handle plain address messages (no command needed)
# ============================================================
@bot.message_handler(func=lambda m: len(m.text) > 30 and not m.text.startswith('/'))
def handle_plain_address(message):
    text = message.text.strip()
    # If it looks like a Solana address, auto-scan it
    if len(text) in range(32, 50) and ' ' not in text:
        msg    = bot.reply_to(message, "🔍 Auto-scanning address...")
        result = call_scan_api(text, "wallet")
        report = format_scan_result(result, text)
        bot.edit_message_text(
            report,
            message.chat.id,
            msg.message_id,
            parse_mode="Markdown"
        )

# ============================================================
# AUTO-MOD — delete spam and ban promoters
# ============================================================

# Your group/channel chat ID — get it by adding @userinfobot to your group
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID", "")

# Keywords that trigger auto-ban
SPAM_KEYWORDS = [
    # Pump and shill patterns
    "100x", "1000x", "gem", "moonshot", "presale", "pre-sale",
    "whitelist", "airdrop", "free tokens", "guaranteed profit",
    "next solana", "next btc", "buy now", "don't miss",
    "low cap", "microcap", "x100", "x1000",
    # Common spam phrases
    "dm me", "dm for", "check my bio", "check bio",
    "join our", "join my", "t.me/", "telegram.me/",
    # Contract address spam (other tokens)
    "pump.fun", "just launched", "just deployed", "stealth launch",
    "fair launch", "renounced", "lp locked",
    # Other chain spam
    "eth contract", "bsc contract", "base contract",
]

# Whitelist — these users will never be banned (add admin usernames)
WHITELISTED_USERS = [
    "ancileprotocol",  # your username
]

def is_spam(text):
    """Check if a message contains spam keywords"""
    if not text:
        return False, None
    text_lower = text.lower()
    for keyword in SPAM_KEYWORDS:
        if keyword.lower() in text_lower:
            return True, keyword
    return False, None

def is_spam_ai(text):
    """Use Claude AI to detect spam more intelligently"""
    if not text or len(text) < 10:
        return False
    try:
        verdict = ask_claude(f"""
You are a Telegram group moderator for a Solana crypto security project called Ancile Protocol.
Is this message spam, token promotion, scam, or unauthorized advertising?

Message: "{text}"

Examples of SPAM:
- Promoting other tokens or coins
- Sharing contract addresses of other projects
- "DM me for alpha"
- Pump.fun links
- Airdrop or presale promotions
- "100x gem" type messages
- Referral links
- Random t.me links

Examples of CLEAN:
- Questions about Ancile Protocol
- Security questions
- General Solana discussion
- Legitimate conversation

Reply with only one word: SPAM or CLEAN
""")
        return "SPAM" in verdict.upper()
    except:
        return False

def is_whitelisted(user):
    """Check if user is whitelisted"""
    if not user:
        return False
    username = user.username or ""
    return username.lower() in [w.lower() for w in WHITELISTED_USERS]

@bot.message_handler(func=lambda message: True, content_types=['text'])
def auto_mod(message):
    """Auto-mod all group messages"""
    print(f"💬 Chat ID: {message.chat.id} | Type: {message.chat.type} | User: {message.from_user.username}")
    # Only moderate group chats
    if message.chat.type not in ['group', 'supergroup']:
        return

    # Skip whitelisted users
    if is_whitelisted(message.from_user):
        return

    # Skip bot messages
    if message.from_user.is_bot:
        return

    text = message.text or ""
    spam, keyword = is_spam(text)

    if not spam:
        spam    = is_spam_ai(text)
        keyword = "AI detected"

    if spam:
        try:
            # 1. Delete the message
            bot.delete_message(message.chat.id, message.message_id)

            # 2. Ban the user
            bot.ban_chat_member(message.chat.id, message.from_user.id)

            # 3. Log it
            username = message.from_user.username or message.from_user.first_name
            print(f"🚫 BANNED: @{username} — triggered keyword: '{keyword}'")

            # 4. Post warning in group
            warning = (
                f"🚫 @{username} was automatically removed for "
                f"promoting unauthorized content.\n\n"
                f"_Ancile Protocol Auto-Mod_ 🛡️"
            )
            bot.send_message(message.chat.id, warning, parse_mode="Markdown")

        except Exception as e:
            print(f"⚠️ Mod error: {e}")



# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    print("🤖 Ancile Bot starting...")
    print(f"   Railway API: {RAILWAY_API}")
    print(f"   Claude API:  {'✅' if ANTHROPIC_KEY else '❌ missing'}")
    print(f"   Bot Token:   {'✅' if BOT_TOKEN else '❌ missing'}")
    print("   Polling for messages...")
    bot.infinity_polling()
