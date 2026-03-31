\# Ancile Protocol — The Divine Shield for AI Agents



Real-time security scanner for Solana wallets, tokens, and programs.



\## What it does

\- Scans wallets for known drainers, scams, and phishing contracts

\- Analyzes token mints for rug pull indicators

\- Monitors Raydium, Jupiter, and Orca for anomalies in real time

\- Posts autonomous threat alerts to Telegram and Twitter via Claude AI



\## Live API

\\```

POST https://your-url.trycloudflare.com/scan

{"address": "WALLET\_ADDRESS", "type": "wallet"}

\\```



\## Quick start

\\```bash

git clone https://github.com/YOURUSERNAME/ancile-protocol

cd ancile-protocol

pip install -r requirements.txt

cp .env.example .env  # fill in your keys

python ancile\_core.py

\\```



\## Scan response

\\```json

{

&#x20; "address": "...",

&#x20; "risk": "LOW",

&#x20; "safe": true,

&#x20; "threats": \[],

&#x20; "checks\_run": 4,

&#x20; "scan\_time": 0.8

}

\\```



\## Tech stack

\- Python + Flask backend

\- Solana RPC + Blowfish + SolanaFM threat detection

\- Claude AI for autonomous alert generation

\- Cloudflare tunnel for public API access



\## Token

$ANCL on Solana — HqYZfwyjjcLaGAFfhjnKjXbqZMZWrwXU8fyEP36Wpump



\## Links

\- Website: https://ancileprotocol.io

\- Twitter: https://twitter.com/AncileProtocol

