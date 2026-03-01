# four.meme Agentic Mode — Autonomous Token Launcher

An AI agent that autonomously creates and launches meme tokens on [four.meme](https://four.meme) (BSC).

Inspired by four.meme's upcoming **Agentic Mode** — where memes are created and operated by AI agents.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Agent Loop                         │
│                                                      │
│  MarketAnalyzer ──► AgentBrain ──► LaunchStrategy   │
│       │                 │                            │
│  four.meme API    TokenConcept ──► ImageGenerator    │
│       │                 │                │           │
│  upload_image     create_token      PIL/DALL-E/SD    │
│       │                 │                            │
│       └────────► BSCChain.submit ──► TokenManager2   │
│                         │                            │
│                    AgentMemory (JSON)                │
└─────────────────────────────────────────────────────┘
```

### Modules

| Module | Description |
|--------|-------------|
| `src/four_meme/auth.py` | Nonce + wallet-signed login |
| `src/four_meme/api.py` | Full four.meme REST client |
| `src/four_meme/onchain.py` | BSC Web3 — calls `TokenManager2.createToken()` |
| `src/agent/brain.py` | LLM-powered concept generation + ranking |
| `src/agent/memory.py` | Persistent launch history + learnings |
| `src/agent/strategy.py` | Launch timing + market analysis |
| `src/image/generator.py` | DALL-E / Stable Diffusion / Pillow image gen |

---

## Setup

```bash
git clone https://github.com/alenfour/four-meme-agent
cd four-meme-agent
pip install -r requirements.txt
cp .env.example .env
# Fill in your .env values
```

---

## Usage

### Autonomous agent mode
```bash
python scripts/run_agent.py
```

### Single launch (dry run — no real tx)
```bash
python scripts/run_agent.py --once --dry-run
```

### Force a theme
```bash
python scripts/run_agent.py --once --theme "AI cat taking over BSC"
```

### Manual token launch
```bash
python scripts/create_token.py \
  --name "My Token" \
  --symbol "MTK" \
  --description "The most based token on BSC" \
  --image path/to/logo.png \
  --raise-bnb 0.5
```

---

## Agent Insider Mode (內盤模式)

> four.meme upcoming feature — only agent wallets can participate in the insider phase before public launch.

### What is an Agent Wallet?

A wallet is recognised as an **agent wallet** if it holds on-chain registration via:

| NFT Standard | Contract |
|---|---|
| `ERC-8004` | TBD — defined by four.meme |
| `BAP-578` | TBD — defined by four.meme |

```
Agent Wallet = address that holds ERC-8004 or BAP-578 NFT on BSC
```

### Insider Phase Flow

```
Token Created by Agent Wallet
         │
         ▼
┌─────────────────────────────────┐
│         INSIDER PHASE           │
│                                 │
│  Only agent wallets can buy     │
│  Bonding curve raises in BNB    │
│  raisedAmount decreases as      │
│  insider buys accumulate        │
└─────────────────┬───────────────┘
                  │  raise target hit / insider phase ends
                  ▼
┌─────────────────────────────────┐
│         PUBLIC PHASE            │
│                                 │
│  All wallets can trade          │
│  Normal four.meme bonding curve │
│  DEX graduation as usual        │
└─────────────────────────────────┘
```

### Transaction Validation Logic

four.meme validates the **transaction initiator** (not just the `msg.sender`):

```python
# Pseudocode — four.meme router check
def is_agent_wallet(address: str) -> bool:
    return (
        holds_erc8004_nft(address) or
        holds_bap578_nft(address)
    )

def can_trade_insider(tx_origin: str, token: Token) -> bool:
    if not token.insider_phase_active:
        return True  # public phase, anyone can trade
    return is_agent_wallet(tx_origin)
```

### Third-Party Router Compatibility

Agent wallets **can** still route trades through third-party aggregators (e.g. 1inch, Paraswap) during insider phase:

```
Agent Wallet ──► Third-Party Router ──► four.meme Pool  ✅
Regular Wallet ──► Third-Party Router ──► four.meme Pool ❌ (insider phase blocked)
Regular Wallet ──► four.meme Pool (direct)               ❌ (insider phase blocked)
```

> four.meme checks `tx.origin`, not `msg.sender` — so routing through aggregators does not bypass the agent check.

### Token Identification Flags (for Explorers / Aggregators)

Tokens launched in agent insider mode expose these features:

| Feature | Description |
|---|---|
| Custom tax slot | Separate fee tier for insider vs public phase |
| `permit` support | Gasless approvals for agent wallet UX |
| Insider badge | Suggested display: "🤖 Agent Insider" label |
| Special route hint | Link to official four.meme agent onboarding |

### Integration Recommendation

```
DO:
  ✅ Display "Agent Insider Token" badge
  ✅ Show phase status (INSIDER / PUBLIC)
  ✅ Allow agent wallet trades via your router

DON'T:
  ❌ Block or hide agent insider tokens entirely
  ❌ Treat third-party routed agent trades as suspicious
```

---

## four.meme API Flow

```
1. GET  /meme-api/v1/public/user/login/nonce
        → { nonce }

2. Sign "You are sign in Meme {nonce}" with wallet private key

3. POST /meme-api/v1/public/user/login
        → { accessToken }

4. POST /meme-api/v1/private/tool/upload   (multipart image)
        → { url: "https://..." }

5. POST /meme-api/v1/private/token/create
        → { createArg: "0x...", signature: "0x..." }

6. BSC:  TokenManager2.createToken(createArg, signature)
        → token deployed on-chain
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `WALLET_PRIVATE_KEY` | BSC wallet private key | required |
| `LLM_API_KEY` | OpenAI (or compatible) API key | required |
| `LLM_API_BASE` | LLM API base URL | `https://api.openai.com/v1` |
| `LLM_MODEL` | Model to use | `gpt-4o` |
| `IMAGE_BACKEND` | `dalle` / `stable_diffusion` / `pillow` | `dalle` |
| `BSC_RPC_URL` | BSC RPC endpoint | public BSC node |
| `LOOP_INTERVAL_SECONDS` | Seconds between agent cycles | `600` |

---

## Warning

- Never commit your `.env` file or private key
- Always test with `--dry-run` first
- Launching tokens costs gas + optional BNB seed raise
- This project is for educational/research purposes

---

Built by [@alenfour](https://github.com/alenfour) | four.meme Solidity & Backend Engineer
